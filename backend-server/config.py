"""
Configuration constants for the NL Query server.
Paths are relative to project root (parent of backend-server).

LLM backend selection
----------------------
The chat/generation backend is chosen by IDF_LLM_BACKEND:

  auto   (default) - use the fine-tuned MLX Phi-4 server if it is reachable on
                     port 8090; otherwise fall back to a local Ollama code model
                     (qwen2.5-coder), otherwise the remote Nutanix endpoint.
  mlx              - force the local MLX Phi-4 server.
  ollama           - force the local Ollama model.
  remote           - force the remote Nutanix AI endpoint.

Phi-4 stays the *primary* model. The fallback exists so the AI keeps working on
hosts where MLX cannot run (non-Apple servers, or memory-constrained machines
where an 8 GB model cannot stay resident). The grounded generation pipeline
(schema grounding -> validate/repair -> deterministic render) is model-agnostic,
so accuracy stays high on either backend.
"""

import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Candidate backends ----------------------------------------------------
MLX_SERVER_URL = "http://127.0.0.1:8090/v1"
MLX_MODEL_NAME = "phi4_idf_fused"

OLLAMA_V1_URL = "http://localhost:11434/v1"
OLLAMA_BASE_URL = "http://localhost:11434/v1"  # back-compat alias (OpenAI-compat base)
# Native Ollama base (no /v1) for management endpoints like /api/tags, /api/pull.
OLLAMA_NATIVE_URL = os.getenv("OLLAMA_NATIVE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("IDF_OLLAMA_CHAT_MODEL", "qwen2.5-coder:7b-instruct")

REMOTE_API_BASE_URL = "https://hkn12.ai.nutanix.com/enterpriseai/v1"
REMOTE_API_KEY = os.getenv("API_KEY", "")
REMOTE_CHAT_MODEL = "hack-reason"


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    """Return True if a GET to `url` returns any HTTP response (server is up)."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError:
        # A 4xx still means the server is alive and answering.
        return True
    except Exception:
        return False


def _resolve_backend() -> str:
    choice = os.getenv("IDF_LLM_BACKEND", "auto").strip().lower()
    if choice in ("mlx", "ollama", "remote"):
        return choice
    # auto-detect
    if _http_ok("http://127.0.0.1:8090/v1/models"):
        return "mlx"
    if _http_ok("http://localhost:11434/api/tags"):
        return "ollama"
    return "remote"


LLM_BACKEND = _resolve_backend()

# --- Constrained decoding / grounded generation flags ----------------------
# The grounded pipeline grounds the prompt in the real schema and uses the
# validate/repair -> deterministic-render pipeline. Kept ON for every backend.
USE_GROUNDED_PIPELINE = True
# Number of few-shot exemplars injected into the grounded prompt.
GROUNDING_FEWSHOT_K = 3

if LLM_BACKEND == "mlx":
    USE_FINETUNED_MODEL = True
    API_BASE_URL = MLX_SERVER_URL
    CHAT_MODEL = MLX_MODEL_NAME
    API_KEY = ""
    MAX_TOKENS = 512
    PROTO_MAX_TOKENS = 300
    LLM_TIMEOUT = 60
    # Grammar-constrained JSON (Outlines) is only available on the MLX server.
    USE_CONSTRAINED_DECODING = True
elif LLM_BACKEND == "ollama":
    USE_FINETUNED_MODEL = False
    API_BASE_URL = OLLAMA_V1_URL
    CHAT_MODEL = OLLAMA_CHAT_MODEL
    API_KEY = "ollama"
    MAX_TOKENS = 1024
    PROTO_MAX_TOKENS = 512
    LLM_TIMEOUT = 150
    # Ollama has no Outlines/guided_json; rely on grounded validate/repair.
    USE_CONSTRAINED_DECODING = False
else:  # remote
    USE_FINETUNED_MODEL = False
    API_BASE_URL = REMOTE_API_BASE_URL
    CHAT_MODEL = REMOTE_CHAT_MODEL
    API_KEY = REMOTE_API_KEY
    MAX_TOKENS = 2048
    PROTO_MAX_TOKENS = 1024
    LLM_TIMEOUT = 60
    USE_CONSTRAINED_DECODING = False

logger.info("LLM backend resolved to '%s' (%s @ %s)", LLM_BACKEND, CHAT_MODEL, API_BASE_URL)

# --- Embeddings (Ollama's nomic-embed-text, used for KB + schema RAG) -------
EMBEDDINGS_BASE_URL = "http://localhost:11434/v1"
EMBEDDINGS_MODEL = "nomic-embed-text"
EMBEDDINGS_TIMEOUT = 30

# --- Knowledge / Schema paths ----------------------------------------------
SCHEMA_DIR = os.path.join(_ROOT, "knowledge", "schema")
ENTITY_ATTRIBUTE_CONFIG_FILE = os.path.join(_ROOT, "knowledge", "schema", "entity_attribute_config.proto.template")
QUERY_SAMPLES_FILE = os.path.join(_ROOT, "knowledge", "structure-and-rules", "query_samples.txt")

# --- Vector DB (legacy schema RAG; grounded pipeline does not require it) ----
VECTOR_DB_PATH = os.path.join(_ROOT, "vectordb")
VECTOR_DB_COLLECTION_NAME = "insights_schema"
VECTOR_DB_MARKER_FILE = ".schema_hash"
TOP_K_RETRIEVAL = 70

# --- Server ----------------------------------------------------------------
SERVER_HOST = os.getenv("IDF_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("IDF_SERVER_PORT", "8000"))
