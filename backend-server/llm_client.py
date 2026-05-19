"""
LLM client for calling an OpenAI-compatible chat/completions API.

Supports:
- Local MLX fine-tuned model (fast, accurate, preferred)
- Remote Nutanix AI endpoint
- Ollama (local fallback)

This module ONLY handles LLM API communication. All domain-specific logic
(proto generation, Python code generation) is in separate modules.
"""

import time
import requests

import config

# Compact system prompt for the fine-tuned model (it already knows the domain)
FINETUNED_SYSTEM_PROMPT = """You are an IDF (Insights Data Fabric) query generator. Given a natural language query, output:
1. The API method name on line 1 as "API: <MethodName>"
2. The protobuf text format query on subsequent lines

Valid API names: GetEntitiesWithMetrics, GetEntityTypes, GetMetricTypes, UpdateEntity, DeleteEntity, RegisterEntityTypes, RegisterMetricTypes, UnregisterMetricTypes, BatchGetEntitiesWithMetrics, BatchUpdateEntities, BatchDeleteEntities, GetEntities, GetMetricData, PutMetricData, SpotLightSearch, GetEntitiesTrail, AttachEntity, DetachEntity, GetMasterLocation, Watch, PutEvent"""


def call_llm(system_message: str, user_message: str, max_tokens: int = None) -> str:
    """
    Call the LLM API with system and user messages.

    When USE_FINETUNED_MODEL is True, uses the compact system prompt instead of
    the full one (fine-tuned model already has domain knowledge baked in).
    """
    url = f"{config.API_BASE_URL}/chat/completions"

    effective_system = system_message
    if config.USE_FINETUNED_MODEL:
        effective_system = FINETUNED_SYSTEM_PROMPT

    payload = {
        "model": config.CHAT_MODEL,
        "messages": [
            {"role": "system", "content": effective_system},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": max_tokens or config.MAX_TOKENS,
        "temperature": 0,
        "stream": False
    }

    if config.USE_FINETUNED_MODEL:
        payload["stop"] = ["<|im_end|>"]

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    if config.API_KEY and config.API_KEY != "ollama" and config.API_KEY:
        headers["Authorization"] = f"Bearer {config.API_KEY}"

    is_localhost = "localhost" in url or "127.0.0.1" in url
    verify_ssl = not is_localhost

    t0 = time.time()
    print(f"[LLM Client] Calling {config.CHAT_MODEL} at {url}")

    response = requests.post(
        url, json=payload, headers=headers,
        verify=verify_ssl, timeout=config.LLM_TIMEOUT
    )
    response.raise_for_status()

    result = response.json()
    elapsed = time.time() - t0

    if "choices" not in result or len(result["choices"]) == 0:
        raise ValueError("Invalid LLM response: no choices")

    content = result["choices"][0]["message"]["content"]
    tokens = result.get("usage", {}).get("completion_tokens", "?")
    print(f"[LLM Client] Response: {tokens} tokens in {elapsed:.1f}s")

    return content
