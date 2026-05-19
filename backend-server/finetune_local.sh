#!/bin/bash
# Local QLoRA fine-tuning on Apple Silicon (M3 18GB)
# Uses MLX-lm — runs natively on Metal GPU

set -e

cd "$(dirname "$0")"

PYTHON="/usr/local/bin/python3.12"

echo "============================================"
echo " IDF Query Model - Local Fine-tuning (MLX)"
echo " Model: Qwen2.5-Coder-7B-Instruct (4-bit)"
echo " Data:  $(wc -l < mlx_finetune_data/train.jsonl) train / $(wc -l < mlx_finetune_data/valid.jsonl) valid"
echo " Hardware: Apple Silicon M3 (18GB unified)"
echo "============================================"
echo ""

# 3 epochs ≈ 593 * 3 / 4 = ~445 optimizer steps (batch=1, grad_accum=4)
$PYTHON -m mlx_lm lora \
    --model Qwen/Qwen2.5-Coder-7B-Instruct \
    --train \
    --data ./mlx_finetune_data \
    --fine-tune-type lora \
    --batch-size 1 \
    --grad-accumulation-steps 4 \
    --iters 450 \
    --num-layers 16 \
    --learning-rate 2e-4 \
    --max-seq-length 1024 \
    --grad-checkpoint \
    --mask-prompt \
    --adapter-path ./idf_lora_adapter \
    --save-every 100 \
    --steps-per-report 10 \
    --steps-per-eval 100 \
    --val-batches 10 \
    --seed 42

echo ""
echo "============================================"
echo " Training complete!"
echo " Adapter saved to: ./idf_lora_adapter/"
echo "============================================"
echo ""
echo "Next: Run ./finetune_local_export.sh to fuse + export GGUF"
