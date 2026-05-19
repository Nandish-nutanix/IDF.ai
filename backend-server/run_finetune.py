#!/usr/bin/env python3
"""Local MLX fine-tuning for IDF Query Model on Apple Silicon."""
import sys
import os
import time

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["HF_HUB_DISABLE_XET"] = "1"

WORKDIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKDIR)

LOG_FILE = os.path.join(WORKDIR, "finetune_log.txt")

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def main():
    log("=" * 50)
    log("IDF Query Model - Local MLX Fine-tuning")
    log("=" * 50)

    MODEL = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"

    log(f"Step 1: Downloading model ({MODEL})...")
    from huggingface_hub import snapshot_download
    model_path = snapshot_download(MODEL)
    log(f"Model cached at: {model_path}")

    log("Step 2: Starting LoRA training...")
    from mlx_lm import lora

    sys.argv = [
        "mlx_lm_lora",
        "--model", MODEL,
        "--train",
        "--data", "./mlx_finetune_data",
        "--fine-tune-type", "lora",
        "--batch-size", "1",
        "--grad-accumulation-steps", "8",
        "--iters", "225",
        "--num-layers", "16",
        "--learning-rate", "5e-5",
        "--max-seq-length", "1024",
        "--grad-checkpoint",
        "--mask-prompt",
        "--adapter-path", "./idf_lora_adapter",
        "--save-every", "50",
        "--steps-per-report", "10",
        "--steps-per-eval", "50",
        "--val-batches", "10",
        "--seed", "42",
    ]
    lora.main()

    log("=" * 50)
    log("Training COMPLETE!")
    log("Adapter saved to: ./idf_lora_adapter/")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        with open(LOG_FILE, "a") as f:
            traceback.print_exc(file=f)
        sys.exit(1)
