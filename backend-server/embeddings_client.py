"""
Embeddings client for calling an OpenAI-compatible embeddings API.

Default backend: Ollama running nomic-embed-text locally.
Also compatible with any OpenAI-format API (vLLM, LiteLLM, OpenAI, etc.).
"""

import requests
from typing import List

import config


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings for a list of text strings.

    Uses the OpenAI-compatible /embeddings endpoint which is
    natively supported by Ollama, vLLM, LiteLLM, and others.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)

    Raises:
        requests.RequestException: On API errors
    """
    url = f"{config.EMBEDDINGS_BASE_URL}/embeddings"

    payload = {
        "model": config.EMBEDDINGS_MODEL,
        "input": texts,
        "encoding_format": "float"
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    if config.API_KEY and config.API_KEY != "ollama":
        headers["Authorization"] = f"Bearer {config.API_KEY}"

    is_localhost = "localhost" in url or "127.0.0.1" in url
    verify_ssl = not is_localhost

    response = requests.post(
        url, json=payload, headers=headers,
        verify=verify_ssl, timeout=config.EMBEDDINGS_TIMEOUT
    )
    response.raise_for_status()

    result = response.json()

    # Response format: {"data": [{"embedding": [...]}, ...], "model": "...", ...}
    if "data" not in result:
        raise ValueError("Invalid embeddings API response: missing 'data' field")

    embeddings = [item["embedding"] for item in result["data"]]
    return embeddings
