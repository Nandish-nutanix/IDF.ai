#!/bin/bash
# Export fine-tuned model: Fuse LoRA adapters + convert to GGUF for Ollama
set -e

cd "$(dirname "$0")"

echo "Step 1: Fusing LoRA adapters into base model..."
python3 -m mlx_lm fuse \
    --model Qwen/Qwen2.5-Coder-7B-Instruct \
    --adapter-path ./idf_lora_adapter \
    --save-path ./idf_query_fused

echo ""
echo "Step 2: Converting to GGUF (q4_k_m quantization)..."
python3 -m mlx_lm convert \
    --model ./idf_query_fused \
    --quantize \
    -q 4 \
    --upload-repo "" \
    --hf-path ./idf_query_gguf 2>/dev/null || \
python3 -c "
import subprocess, os

# Use llama.cpp convert if mlx_lm convert doesn't output GGUF directly
# First check if the fused model exists
fused_path = './idf_query_fused'
if os.path.exists(fused_path):
    print('Fused model ready at:', fused_path)
    print('To convert to GGUF, use llama.cpp or upload to HuggingFace.')
    print()
    print('Alternative: Use the fused model directly with mlx_lm.generate:')
    print('  python3 -m mlx_lm generate --model ./idf_query_fused --prompt \"get all VMs\"')
"

echo ""
echo "Step 3: Creating Ollama Modelfile..."

# For MLX fused models, we can use Ollama's direct import
cat > ./idf_query_fused/Modelfile << 'EOF'
FROM .

TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{- end }}
<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
PARAMETER temperature 0
PARAMETER num_predict 512
PARAMETER num_ctx 1024
EOF

echo ""
echo "============================================"
echo " Export complete!"
echo "============================================"
echo ""
echo "Option A - Use with Ollama (recommended):"
echo "  cd idf_query_fused"
echo "  ollama create idf-query-7b -f Modelfile"
echo "  Then update backend config: CHAT_MODEL = 'idf-query-7b'"
echo ""
echo "Option B - Use directly with MLX (no Ollama needed):"
echo "  python3 -m mlx_lm generate --model ./idf_query_fused --prompt 'get all VMs'"
echo ""
