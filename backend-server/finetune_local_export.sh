#!/bin/bash
# Export fine-tuned model: Fuse LoRA adapters + convert to GGUF for Ollama
set -e

cd "$(dirname "$0")"

echo "Step 1: Fusing Phi-4 LoRA adapters into base model..."
python3 -m mlx_lm fuse \
    --model mlx-community/phi-4-4bit \
    --adapter-path ./phi4_idf_adapter \
    --save-path ./phi4_idf_fused

echo ""
echo "Step 2: Verifying fused Phi-4 model..."
python3 -c "
import os
fused_path = './phi4_idf_fused'
if os.path.exists(fused_path):
    print('Fused Phi-4 model ready at:', fused_path)
    print('Serve with: python3 -m mlx_lm server --model ./phi4_idf_fused --port 8090')
    print('Or test:    python3 -m mlx_lm generate --model ./phi4_idf_fused --prompt \"get all VMs\"')
"

echo ""
echo "Step 3: Creating Ollama Modelfile (optional)..."

# For MLX fused models, we can use Ollama's direct import
cat > ./phi4_idf_fused/Modelfile << 'EOF'
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
echo "Option A - Serve directly with MLX (recommended, no Ollama needed):"
echo "  python3 -m mlx_lm server --model ./phi4_idf_fused --port 8090"
echo ""
echo "Option B - Quick test:"
echo "  python3 -m mlx_lm generate --model ./phi4_idf_fused --prompt 'get all VMs'"
echo ""
