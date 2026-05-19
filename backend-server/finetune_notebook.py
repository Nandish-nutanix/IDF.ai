"""
QLoRA Fine-tuning Script for IDF Query Model
=============================================
Run this on Google Colab (free T4 GPU) or any machine with >= 8GB VRAM.

Prerequisites:
    pip install unsloth transformers datasets trl

Steps:
    1. Upload training_data.jsonl to Colab
    2. Run this script
    3. Download the exported GGUF model
    4. Register with Ollama: ollama create idf-query-7b -f Modelfile

Expected training time: ~30-60 minutes on T4 for ~1000 examples.
"""

# ==============================================================================
# STEP 0: Install dependencies (uncomment for Colab)
# ==============================================================================
# !pip install -q unsloth transformers datasets trl peft accelerate bitsandbytes

# ==============================================================================
# STEP 1: Load base model with 4-bit quantization
# ==============================================================================
from unsloth import FastLanguageModel
import torch

MODEL_NAME = "unsloth/Qwen2.5-Coder-7B-Instruct"
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True

print("Loading base model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,  # auto-detect
    load_in_4bit=LOAD_IN_4BIT,
)
print(f"Model loaded: {MODEL_NAME}")

# ==============================================================================
# STEP 2: Apply LoRA adapters
# ==============================================================================
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.0
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=TARGET_MODULES,
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)
print(f"LoRA applied: r={LORA_R}, alpha={LORA_ALPHA}")
model.print_trainable_parameters()

# ==============================================================================
# STEP 3: Load and format training data
# ==============================================================================
from datasets import load_dataset

TRAINING_FILE = "training_data.jsonl"

dataset = load_dataset("json", data_files=TRAINING_FILE, split="train")
print(f"Dataset loaded: {len(dataset)} examples")


def format_chat(example):
    """Apply Qwen2.5 chat template to each example."""
    messages = example["messages"]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


dataset = dataset.map(format_chat)
print(f"Chat template applied. Sample length: {len(dataset[0]['text'])} chars")
print(f"Sample (first 500 chars):\n{dataset[0]['text'][:500]}")

# ==============================================================================
# STEP 4: Training configuration
# ==============================================================================
from trl import SFTTrainer
from transformers import TrainingArguments

EPOCHS = 3
BATCH_SIZE = 4
GRADIENT_ACCUMULATION = 4
LEARNING_RATE = 2e-4
WARMUP_RATIO = 0.05
OUTPUT_DIR = "./idf_query_model_output"

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=True,
    args=TrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        warmup_ratio=WARMUP_RATIO,
        num_train_epochs=EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        output_dir=OUTPUT_DIR,
        save_strategy="epoch",
        report_to="none",
    ),
)

print(f"\nTraining config:")
print(f"  Epochs: {EPOCHS}")
print(f"  Effective batch: {BATCH_SIZE * GRADIENT_ACCUMULATION}")
print(f"  Learning rate: {LEARNING_RATE}")
print(f"  Output: {OUTPUT_DIR}")

# ==============================================================================
# STEP 5: Train
# ==============================================================================
print("\nStarting training...")
trainer_stats = trainer.train()

print(f"\nTraining complete!")
print(f"  Total steps: {trainer_stats.global_step}")
print(f"  Training loss: {trainer_stats.training_loss:.4f}")
print(f"  Runtime: {trainer_stats.metrics['train_runtime']:.0f}s")

# ==============================================================================
# STEP 6: Save LoRA adapter (intermediate checkpoint)
# ==============================================================================
LORA_OUTPUT = "./idf_query_lora"
model.save_pretrained(LORA_OUTPUT)
tokenizer.save_pretrained(LORA_OUTPUT)
print(f"\nLoRA adapter saved to: {LORA_OUTPUT}")

# ==============================================================================
# STEP 7: Export to GGUF for Ollama
# ==============================================================================
GGUF_OUTPUT = "./idf_query_gguf"
QUANTIZATION = "q4_k_m"

print(f"\nExporting to GGUF ({QUANTIZATION})...")
model.save_pretrained_gguf(
    GGUF_OUTPUT,
    tokenizer,
    quantization_method=QUANTIZATION,
)
print(f"GGUF model saved to: {GGUF_OUTPUT}/")

# ==============================================================================
# STEP 8: Generate Ollama Modelfile
# ==============================================================================
import os

gguf_files = [f for f in os.listdir(GGUF_OUTPUT) if f.endswith(".gguf")]
gguf_filename = gguf_files[0] if gguf_files else "unsloth.Q4_K_M.gguf"

MODELFILE_CONTENT = f"""FROM ./{GGUF_OUTPUT}/{gguf_filename}

TEMPLATE \"\"\"{{{{- if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{- end }}}}
<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
<|im_start|>assistant
\"\"\"

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
PARAMETER temperature 0
PARAMETER num_predict 512
"""

modelfile_path = os.path.join(GGUF_OUTPUT, "Modelfile")
with open(modelfile_path, "w") as f:
    f.write(MODELFILE_CONTENT)

print(f"\nOllama Modelfile written to: {modelfile_path}")
print(f"\nTo register with Ollama:")
print(f"  cd {GGUF_OUTPUT}")
print(f"  ollama create idf-query-7b -f Modelfile")
print(f"\nThen update config.py:")
print(f'  CHAT_MODEL = "idf-query-7b"')

# ==============================================================================
# STEP 9: Quick inference test
# ==============================================================================
print("\n" + "=" * 60)
print("Quick inference test (fine-tuned model):")
print("=" * 60)

FastLanguageModel.for_inference(model)

test_queries = [
    "get all VMs",
    "create a vm named test_001",
    "update vm test_001 setting power_state to on",
    "delete vm entity test_001",
]

for query in test_queries:
    messages = [
        {"role": "system", "content": "You are an IDF query generator. Output API method and proto."},
        {"role": "user", "content": query},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=256,
        temperature=0.0,
        do_sample=False,
    )
    response = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True)
    print(f"\nQ: {query}")
    print(f"A: {response[:200]}")

print("\n" + "=" * 60)
print("DONE! All artifacts saved.")
print("=" * 60)
