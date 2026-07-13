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

    # Microsoft Phi-4 is the ONLY base model used by this project.
    MODEL = "mlx-community/phi-4-4bit"

    log(f"Step 1: Downloading model ({MODEL})...")
    from huggingface_hub import snapshot_download
    model_path = snapshot_download(MODEL)
    log(f"Model cached at: {model_path}")

    log("Step 2: Starting LoRA training (Phi-4)...")
    from mlx_lm import lora

    # More iterations than the original 225 (~0.6 epoch). 600 iters with the
    # grounded dataset gives ~2-3 epochs, which is where the format + schema
    # grounding actually converge without overfitting (val loss is monitored).
    sys.argv = [
        "mlx_lm_lora",
        "--model", MODEL,
        "--train",
        "--data", "./mlx_finetune_data_grounded",
        "--fine-tune-type", "lora",
        "--batch-size", "1",
        "--grad-accumulation-steps", "8",
        "--iters", "600",
        "--num-layers", "16",
        "--learning-rate", "5e-5",
        "--max-seq-length", "1536",
        "--grad-checkpoint",
        "--mask-prompt",
        "--adapter-path", "./phi4_idf_adapter",
        "--save-every", "100",
        "--steps-per-report", "10",
        "--steps-per-eval", "100",
        "--val-batches", "20",
        "--seed", "42",
    ]
    lora.main()

    log("=" * 50)
    log("Training COMPLETE!")
    log("Adapter saved to: ./phi4_idf_adapter/")
    log("Next: fuse with  python3 -m mlx_lm.fuse --model mlx-community/phi-4-4bit \\")
    log("        --adapter-path ./phi4_idf_adapter --save-path ./phi4_idf_fused")
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
