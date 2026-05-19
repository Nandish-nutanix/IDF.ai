"""
Configuration constants for the NL Query server.
Paths are relative to project root (parent of backend-server).
"""

import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- LLM Backend Configuration ---
# Set USE_FINETUNED_MODEL=True to use the local MLX fine-tuned model (faster, more accurate)
# Set to False to fall back to the remote Nutanix AI endpoint or Ollama
USE_FINETUNED_MODEL = False

# Fine-tuned MLX model server (local, started via: python -m mlx_lm server --model ./idf_query_fused --port 8090)
MLX_SERVER_URL = "http://127.0.0.1:8090/v1"
MLX_MODEL_NAME = "phi4_idf_fused"

# Remote Nutanix AI endpoint (fallback)
REMOTE_API_BASE_URL = "https://hkn12.ai.nutanix.com/enterpriseai/v1"
REMOTE_API_KEY = os.getenv("API_KEY", "")
REMOTE_CHAT_MODEL = "hack-reason"
REMOTE_EMBEDDINGS_MODEL = "hack-embed"

# Ollama (alternative local fallback)
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_CHAT_MODEL = "qwen2.5-coder:7b-instruct"

# Active configuration (resolved based on USE_FINETUNED_MODEL)
if USE_FINETUNED_MODEL:
    API_BASE_URL = MLX_SERVER_URL
    CHAT_MODEL = MLX_MODEL_NAME
    API_KEY = ""
    MAX_TOKENS = 512
    LLM_TIMEOUT = 60
    PROTO_MAX_TOKENS = 300
else:
    API_BASE_URL = REMOTE_API_BASE_URL
    CHAT_MODEL = REMOTE_CHAT_MODEL
    API_KEY = REMOTE_API_KEY
    MAX_TOKENS = 2048
    LLM_TIMEOUT = 60
    PROTO_MAX_TOKENS = 1024

# --- Embeddings (use Ollama's nomic-embed-text locally) ---
EMBEDDINGS_BASE_URL = "http://localhost:11434/v1"
EMBEDDINGS_MODEL = "nomic-embed-text"
EMBEDDINGS_TIMEOUT = 30

# --- Knowledge / Schema paths ---
SCHEMA_DIR = os.path.join(_ROOT, "knowledge", "schema")
ENTITY_ATTRIBUTE_CONFIG_FILE = os.path.join(_ROOT, "knowledge", "schema", "entity_attribute_config.proto.template")
QUERY_SAMPLES_FILE = os.path.join(_ROOT, "knowledge", "structure-and-rules", "query_samples.txt")

# --- Vector DB ---
VECTOR_DB_PATH = os.path.join(_ROOT, "vectordb")
VECTOR_DB_COLLECTION_NAME = "insights_schema"
VECTOR_DB_MARKER_FILE = ".schema_hash"
TOP_K_RETRIEVAL = 70

# --- Server ---
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
