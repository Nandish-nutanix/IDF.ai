"""
Startup verification that required Ollama models are available.

Checks that the configured chat and embedding models are pulled and ready
before the server starts accepting queries. If models are missing and Ollama
is reachable, attempts to pull them automatically.
"""

import time
from typing import List, Tuple

import requests

import config


def check_ollama_health() -> bool:
    """Check if Ollama is running and reachable."""
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/tags"
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


def list_available_models() -> List[str]:
    """Get list of models currently pulled in Ollama."""
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/tags"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except requests.RequestException:
        pass
    return []


def is_model_available(model_name: str, available_models: List[str]) -> bool:
    """Check if a model is available, handling tag variations."""
    if model_name in available_models:
        return True
    if ":" not in model_name:
        for m in available_models:
            if m.startswith(model_name + ":"):
                return True
    base = model_name.split(":")[0]
    for m in available_models:
        if m.startswith(base + ":"):
            return True
    return False


def pull_model(model_name: str) -> bool:
    """Attempt to pull a model from Ollama registry."""
    print(f"[Model Check] Pulling model: {model_name} (this may take a while)...")
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/pull"
        response = requests.post(
            url,
            json={"name": model_name, "stream": False},
            timeout=600,
        )
        if response.status_code == 200:
            print(f"[Model Check] Successfully pulled: {model_name}")
            return True
        else:
            print(f"[Model Check] Failed to pull {model_name}: HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"[Model Check] Failed to pull {model_name}: {e}")
        return False


def check_mlx_server_health() -> bool:
    """Check if the MLX fine-tuned model server is running."""
    try:
        url = f"{config.MLX_SERVER_URL}/models"
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


def verify_models(auto_pull: bool = True) -> Tuple[bool, List[str]]:
    """
    Verify that required models are available.

    When USE_FINETUNED_MODEL is True, checks the MLX server.
    Otherwise checks Ollama.

    Returns:
        Tuple of (all_ready, list_of_issues)
    """
    issues = []

    if config.USE_FINETUNED_MODEL:
        if check_mlx_server_health():
            print("[Model Check] MLX fine-tuned model server is ready.")
            return True, []
        else:
            issues.append(
                f"MLX model server not reachable at {config.MLX_SERVER_URL}. "
                f"Start it with: cd backend-server && python3 -m mlx_lm server "
                f"--model ./idf_query_fused --port 8090"
            )
            return False, issues

    if not check_ollama_health():
        base_url = config.OLLAMA_BASE_URL
        issues.append(
            f"Ollama is not reachable at {base_url}. "
            f"Please start Ollama: 'ollama serve' or 'systemctl start ollama'"
        )
        return False, issues

    available = list_available_models()
    required_models = [
        (config.CHAT_MODEL, "chat/reasoning"),
        (config.EMBEDDINGS_MODEL, "embeddings"),
    ]

    all_ready = True
    for model_name, purpose in required_models:
        if is_model_available(model_name, available):
            print(f"[Model Check] {purpose} model ready: {model_name}")
        else:
            print(f"[Model Check] {purpose} model MISSING: {model_name}")
            if auto_pull:
                success = pull_model(model_name)
                if not success:
                    all_ready = False
                    issues.append(
                        f"Model '{model_name}' ({purpose}) is not available and auto-pull failed. "
                        f"Please run: ollama pull {model_name}"
                    )
            else:
                all_ready = False
                issues.append(
                    f"Model '{model_name}' ({purpose}) is not available. "
                    f"Please run: ollama pull {model_name}"
                )

    return all_ready, issues


def wait_for_ollama(max_wait_seconds: int = 60) -> bool:
    """Wait for Ollama to become available (useful during container startup)."""
    print(f"[Model Check] Waiting for Ollama at {config.OLLAMA_BASE_URL}...")
    start = time.time()
    while time.time() - start < max_wait_seconds:
        if check_ollama_health():
            print("[Model Check] Ollama is ready.")
            return True
        time.sleep(2)
    print(f"[Model Check] Ollama not available after {max_wait_seconds}s")
    return False
