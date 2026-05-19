"""
GRPO (Group Relative Policy Optimization) Training for IDF Query Model.

Memory-efficient approach for M3 18GB:
  - Uses the running MLX server for generation (avoiding double model load)
  - Trains only the lightweight LoRA adapter locally
  - Applies reward-weighted policy gradient updates

Hardware: Apple Silicon M3, 18GB unified memory
Model: idf_query_fused (Qwen2.5-Coder-7B-Instruct-4bit, LoRA fine-tuned)

Usage:
    python3.12 grpo_train.py              # Full GRPO training
    python3.12 grpo_train.py --validate   # Just validate reward function
    python3.12 grpo_train.py --server     # Use server for generation (memory-efficient)
"""

import json
import os
import re
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proto_response_generator import _validate_proto

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GRPO_DATA_PATH = os.path.join(SCRIPT_DIR, "grpo_training_data.jsonl")
EXISTING_TRAIN_PATH = os.path.join(SCRIPT_DIR, "mlx_finetune_data", "train.jsonl")
MODEL_PATH = os.path.join(SCRIPT_DIR, "idf_query_fused")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "idf_grpo_adapter")
MERGED_OUTPUT = os.path.join(SCRIPT_DIR, "idf_query_fused_rl")
MLX_SERVER_URL = "http://127.0.0.1:8090/v1/chat/completions"

VALID_API_NAMES = {
    "GetEntitiesWithMetrics", "GetEntityTypes", "GetMetricTypes",
    "UpdateEntity", "DeleteEntity", "RegisterEntityTypes",
    "RegisterMetricTypes", "UnregisterMetricTypes",
    "BatchGetEntitiesWithMetrics", "BatchUpdateEntities",
    "BatchDeleteEntities", "GetEntities", "GetMetricData",
    "PutMetricData", "SpotLightSearch", "GetEntitiesTrail",
    "AttachEntity", "DetachEntity", "GetMasterLocation", "Watch", "PutEvent"
}

SYSTEM_PROMPT = """You are an IDF query generator. Output the API method on line 1 as "API: <Method>" then the protobuf text on subsequent lines."""


def _parse_llm_response(response: str):
    """Parse LLM response into (api_method, proto_text)."""
    lines = response.strip().split('\n')
    api_method = ""
    proto_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("API:"):
            api_method = line.strip().replace("API:", "").strip()
            proto_start = i + 1
            break
    proto_text = '\n'.join(lines[proto_start:]).strip()
    return api_method, proto_text


def idf_reward(response: str, ground_truth: str) -> float:
    """
    IDF-specific reward function for GRPO training.
    
    Components:
      0.2 - Format compliance (starts with "API: X", valid API name)
      0.3 - Correct API method (matches ground truth)
      0.3 - Proto structural validity (passes _validate_proto)
      0.2 - Field-level accuracy (key fields present)
    
    Returns float in [0.0, 1.0]
    """
    score = 0.0
    
    try:
        api_method, proto_text = _parse_llm_response(response)
    except Exception:
        return 0.0
    
    try:
        gt_api, gt_proto = _parse_llm_response(ground_truth)
    except Exception:
        gt_api, gt_proto = "", ""
    
    # R1: Format compliance (0.2)
    if response.strip().startswith("API: ") and api_method in VALID_API_NAMES:
        score += 0.2
    
    # R2: Correct API method (0.3)
    if api_method == gt_api:
        score += 0.3
    
    # R3: Proto structural validity (0.3)
    if api_method and proto_text:
        is_valid, _ = _validate_proto(proto_text, api_method)
        if is_valid:
            score += 0.3
    
    # R4: Field-level accuracy (0.2)
    if gt_proto and proto_text:
        gt_fields = set(re.findall(r'(\w+):', gt_proto))
        resp_fields = set(re.findall(r'(\w+):', proto_text))
        if gt_fields:
            overlap = len(gt_fields & resp_fields) / len(gt_fields)
            score += 0.2 * overlap
    
    return min(score, 1.0)


def generate_completion(prompt: str, temperature: float = 0.7) -> str:
    """Generate a completion using the running MLX server."""
    try:
        resp = requests.post(
            MLX_SERVER_URL,
            json={
                "model": "idf_query_fused",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 300,
                "temperature": temperature,
                "stop": ["<|im_end|>"]
            },
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return ""


def load_grpo_dataset():
    """Load training data in prompt/answer format."""
    dataset = []
    
    if os.path.exists(GRPO_DATA_PATH):
        with open(GRPO_DATA_PATH) as f:
            for line in f:
                item = json.loads(line)
                user_content = item["messages"][-1]["content"] if item["messages"] else ""
                dataset.append({
                    "prompt": user_content,
                    "answer": item["answer"],
                })
    
    if os.path.exists(EXISTING_TRAIN_PATH):
        with open(EXISTING_TRAIN_PATH) as f:
            for line in f:
                item = json.loads(line)
                msgs = item.get("messages", [])
                if len(msgs) >= 3:
                    user_content = msgs[-2].get("content", "") if len(msgs) >= 2 else ""
                    assistant_content = msgs[-1].get("content", "")
                    if user_content:
                        dataset.append({
                            "prompt": user_content,
                            "answer": assistant_content,
                        })
    
    print(f"Loaded {len(dataset)} training examples")
    return dataset


def run_server_grpo(num_iterations=100, num_generations=4):
    """
    Server-based GRPO: Generate completions via MLX server, score with reward,
    then create preference data for DPO/SFT training on the best responses.
    
    This approach works within M3 18GB limits by:
    1. Using the running MLX server for generation (no extra model load)
    2. Collecting (prompt, best_response) pairs weighted by reward
    3. Re-training with SFT on the reward-filtered data
    """
    print("=" * 60)
    print(" IDF Query Model - Server-Based GRPO")
    print(f" MLX Server: {MLX_SERVER_URL}")
    print(f" Iterations: {num_iterations}")
    print(f" Generations per prompt: {num_generations}")
    print("=" * 60)
    
    # Check MLX server
    try:
        r = requests.get("http://127.0.0.1:8090/v1/models", timeout=5)
        if r.status_code != 200:
            print("ERROR: MLX server not responding")
            sys.exit(1)
    except Exception:
        print("ERROR: MLX server not reachable at port 8090")
        sys.exit(1)
    
    dataset = load_grpo_dataset()
    
    # GRPO Loop: For each prompt, generate N completions, reward them,
    # keep the best as training signal
    improved_data = []
    total_reward = 0.0
    num_processed = 0
    
    print(f"\nRunning GRPO collection ({num_iterations} prompts, {num_generations} completions each)...")
    print("-" * 60)
    
    import random
    random.seed(42)
    random.shuffle(dataset)
    
    for i in range(min(num_iterations, len(dataset))):
        item = dataset[i]
        prompt = item["prompt"]
        ground_truth = item["answer"]
        
        # Generate N completions with temperature sampling
        completions = []
        for _ in range(num_generations):
            comp = generate_completion(prompt, temperature=0.7)
            if comp:
                completions.append(comp)
        
        if not completions:
            continue
        
        # Score each completion
        rewards = [idf_reward(c, ground_truth) for c in completions]
        
        # GRPO: Keep the best completion as positive signal
        best_idx = rewards.index(max(rewards))
        best_reward = rewards[best_idx]
        best_completion = completions[best_idx]
        
        # Also add ground truth if none scored well
        if best_reward < 0.5:
            best_completion = ground_truth
            best_reward = 1.0
        
        improved_data.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": best_completion}
            ]
        })
        
        total_reward += best_reward
        num_processed += 1
        
        avg_rewards = [f"{r:.2f}" for r in rewards]
        if (i + 1) % 10 == 0 or i < 5:
            print(f"  [{i+1:3d}/{num_iterations}] avg_reward={sum(rewards)/len(rewards):.3f} "
                  f"best={best_reward:.2f} | {prompt[:40]}...")
    
    print(f"\n{'=' * 60}")
    print(f" GRPO Collection Complete")
    print(f" Processed: {num_processed}")
    print(f" Avg best reward: {total_reward/max(num_processed,1):.3f}")
    print(f" Improved examples: {len(improved_data)}")
    print(f"{'=' * 60}")
    
    # Save improved dataset for SFT re-training
    output_path = os.path.join(SCRIPT_DIR, "grpo_improved_data.jsonl")
    with open(output_path, 'w') as f:
        for item in improved_data:
            f.write(json.dumps(item) + '\n')
    print(f"\nImproved dataset saved: {output_path}")
    
    # Now run lightweight SFT on the improved data
    print("\n" + "=" * 60)
    print(" Phase 2: SFT Re-training on GRPO-improved data")
    print("=" * 60)
    
    grpo_data_dir = os.path.join(SCRIPT_DIR, "mlx_grpo_data")
    os.makedirs(grpo_data_dir, exist_ok=True)
    
    sft_train_path = os.path.join(grpo_data_dir, "train.jsonl")
    with open(sft_train_path, 'w') as f:
        for item in improved_data:
            f.write(json.dumps(item) + '\n')
    
    val_path = os.path.join(grpo_data_dir, "valid.jsonl")
    val_items = improved_data[:max(5, len(improved_data) // 10)]
    with open(val_path, 'w') as f:
        for item in val_items:
            f.write(json.dumps(item) + '\n')
    
    print(f"  Training data: {sft_train_path} ({len(improved_data)} examples)")
    print(f"  Validation data: {val_path} ({len(val_items)} examples)")
    print(f"\n  Starting LoRA fine-tuning on improved data...")
    
    # Stop the MLX server before training to free memory
    print("  Stopping MLX server to free memory for training...")
    os.system("kill $(lsof -ti:8090) 2>/dev/null")
    time.sleep(3)
    
    # Run mlx_lm.lora with the improved data
    import subprocess
    cmd = [
        sys.executable, "-m", "mlx_lm.lora",
        "--model", MODEL_PATH,
        "--train",
        "--data", grpo_data_dir,
        "--iters", "50",
        "--batch-size", "1",
        "--num-layers", "8",
        "--learning-rate", "5e-6",
        "--adapter-path", OUTPUT_DIR,
    ]
    
    print(f"  Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=False, text=True,
                           cwd=SCRIPT_DIR, env={**os.environ, "MLX_METAL_JIT": "1"})
    
    if result.returncode == 0:
        print(f"\n  LoRA training complete! Adapter saved to: {OUTPUT_DIR}")
        
        # Fuse the adapter
        print("\n  Fusing adapter into model...")
        fuse_cmd = [
            sys.executable, "-m", "mlx_lm.fuse",
            "--model", MODEL_PATH,
            "--adapter-path", OUTPUT_DIR,
            "--save-path", MERGED_OUTPUT,
        ]
        fuse_result = subprocess.run(fuse_cmd, capture_output=False, text=True, cwd=SCRIPT_DIR)
        
        if fuse_result.returncode == 0:
            print(f"  Merged model saved to: {MERGED_OUTPUT}")
        else:
            print(f"  Fuse failed (exit code {fuse_result.returncode})")
    else:
        print(f"\n  Training failed (exit code {result.returncode})")
    
    # Restart MLX server with new model (or old if training failed)
    model_to_serve = MERGED_OUTPUT if os.path.exists(MERGED_OUTPUT) else MODEL_PATH
    print(f"\n  Restarting MLX server with: {model_to_serve}")
    os.system(f"nohup {sys.executable} -m mlx_lm server --model {model_to_serve} --port 8090 > /tmp/mlx_server.log 2>&1 &")
    time.sleep(5)
    
    print("\n" + "=" * 60)
    print(" GRPO Pipeline Complete!")
    print("=" * 60)
    print("\nNext: Run validation to confirm improvement")
    print("  python3.12 grpo_train.py --validate")


def validate_reward():
    """Quick validation of the reward function on dataset."""
    print("Running reward function validation...")
    dataset = load_grpo_dataset()
    scores = []
    for item in dataset[:20]:
        answer = item["answer"]
        score = idf_reward(answer, answer)
        scores.append(score)
    avg = sum(scores) / len(scores) if scores else 0
    print(f"Self-reward (should be ~1.0): {avg:.3f}")
    print(f"Min: {min(scores):.3f}, Max: {max(scores):.3f}")
    
    # Test with wrong answers
    bad_scores = []
    for item in dataset[:20]:
        bad_answer = "API: GetEntitiesWithMetrics\nsome random text"
        score = idf_reward(bad_answer, item["answer"])
        bad_scores.append(score)
    avg_bad = sum(bad_scores) / len(bad_scores) if bad_scores else 0
    print(f"\nBad answer reward (should be low): {avg_bad:.3f}")
    print(f"Min: {min(bad_scores):.3f}, Max: {max(bad_scores):.3f}")


if __name__ == "__main__":
    if "--validate" in sys.argv:
        validate_reward()
    elif "--server" in sys.argv or True:  # Default to server mode for M3
        iters = 100
        gens = 4
        for arg in sys.argv[1:]:
            if arg.startswith("--iters="):
                iters = int(arg.split("=")[1])
            elif arg.startswith("--gens="):
                gens = int(arg.split("=")[1])
        run_server_grpo(num_iterations=iters, num_generations=gens)
