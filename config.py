"""
Configuration constants for the NL Query server.
Paths are relative to project root (run server from project root).

Default configuration targets a local Ollama instance with:
  - Chat model: qwen2.5-coder:7b-instruct (Apache 2.0, best open-source 7B code model)
  - Embedding model: nomic-embed-text (Apache 2.0, 137M params, 768 dims)
"""

import os

# LLM API Configuration (OpenAI-compatible endpoint)
# Default: Ollama running locally on port 11434
API_BASE_URL = os.getenv("LLM_API_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", "qwen2.5-coder:7b-fast")
EMBEDDINGS_MODEL = os.getenv("LLM_EMBED_MODEL", "nomic-embed-text")

# Ollama base URL (without /v1) for model management operations
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Schema Configuration
SCHEMA_DIR = "./knowledge/schema"
ENTITY_ATTRIBUTE_CONFIG_FILE = os.path.join(SCHEMA_DIR, "entity_attribute_config.proto.template")

# Query samples for LLM few-shot context (proto format examples)
QUERY_SAMPLES_FILE = "./knowledge/structure-and-rules/query_samples.txt"

# Vector DB Configuration
VECTOR_DB_PATH = "./knowledge/schema/vectordb"
VECTOR_DB_COLLECTION_NAME = "insights_schema"
VECTOR_DB_MARKER_FILE = os.path.join(VECTOR_DB_PATH, ".schema_hash")

# Retrieval Configuration
TOP_K_RETRIEVAL = 10  # Fewer chunks = less LLM context = faster inference
TOP_K_VECTOR = 15  # Initial vector search candidates before reranking
TOP_K_BM25 = 15  # Initial BM25 keyword search candidates before merging
RERANK_WEIGHT_VECTOR = 0.6  # Weight for vector similarity in hybrid scoring
RERANK_WEIGHT_BM25 = 0.4  # Weight for BM25 keyword match in hybrid scoring

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# LLM Configuration
MAX_TOKENS = 4096  # Default max tokens (code generation needs more)
PROTO_MAX_TOKENS = 512  # Proto generation needs far fewer tokens (10-30 lines)

# API Timeout Configuration (in seconds)
EMBEDDINGS_TIMEOUT = 30  # Timeout for embeddings API calls
LLM_TIMEOUT = 60  # Timeout for LLM chat completions API calls
