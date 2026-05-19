# Insights NL→Query Agent — Design (First Version)

## Overview

First version of an agent that turns **natural language** into an **insights Query proto (JSON)**. Input is a **command-line query string**; output is the query JSON. No Go/Python code generation in this version (TODO later).

**Full design (components, vector DB, APIs, data model):** See [NL_QUERY_DESIGN.md](./NL_QUERY_DESIGN.md).

---

## First-Version Scope

| Item | First version |
|------|----------------|
| **Input** | Single natural-language query string from the **command line** (CLI). |
| **Output** | Query proto as **JSON** (canonical representation of the Query message). |
| **Go/Python code gen** | **TODO** — not implemented; design assumes “proto first, then code” when we add it. |

---

## Components (High Level)

### 1. CLI (lightweight Python script)

- **Input**: One string from the console (single argv or stdin).
- **Action**: Send the string to the server (e.g. `POST /query`); print the response (query JSON or error).
- **Output**: Stdout = query JSON; stderr = errors; exit non-zero on failure.

### 2. Server (Python)

- **On startup**:
  - Read schema file(s) (entity types + indexed attributes).
  - If the **vector DB already exists** at the configured path and is up-to-date (e.g. same schema hash), **do not** re-embed; load it.
  - Otherwise: **tokenize/chunk** the schema, call the **embeddings API** (`hack-embed` at `https://hkn12.ai.nutanix.com/enterpriseai/v1/embeddings`), build the **vector DB**, persist it to disk.
- **Vector DB**: Lightweight, runnable on a dev VM; **Chroma** (file-based, no separate server). Data model and “don’t rebuild if DB exists” are in [NL_QUERY_DESIGN.md](./NL_QUERY_DESIGN.md).
- **On each query**:
  - Embed the user query (same embeddings API).
  - **Retrieve** top-k schema chunks from the vector DB (“kb files”).
  - Send **query + retrieved chunks** to the **chat/completions API** (`hack-reason` at `https://hkn12.ai.nutanix.com/enterpriseai/v1/chat/completions`); system message = instructions + rules; user message = NL query + “Relevant schema: …” (retrieved chunks).
  - Parse JSON from LLM response; run **structural validation** (and optionally real-schema validation).
  - Return **query JSON** (or error) to the client.

### 3. External APIs (Nutanix Enterprise AI)

- **Embeddings**: `POST .../enterpriseai/v1/embeddings` — model `hack-embed`, `input`: list of strings, `encoding_format`: `float`. Used to embed schema chunks at startup and the user query at request time.
- **Chat**: `POST .../enterpriseai/v1/chat/completions` — model `hack-reason`, `messages` (system + user with kb chunks), `max_tokens`, optional `stream`. Used to produce the query JSON. No tools required in the first version.

Authentication: `Authorization: Bearer $API_KEY` (e.g. from env).

---

## Vector DB (Chroma)

- **Choice**: Chroma — file-based, in-process, persists to a directory; suitable for a random dev VM.
- **Persistence**: DB lives in a configured directory (e.g. `./schema_vectordb`). If the directory exists and the stored index is up-to-date (e.g. marker file with schema hash), the server **does not** re-embed; it loads the existing DB.
- **Data model**: One collection (e.g. `insights_schema`). Per document: chunk text, embedding (from `hack-embed`), metadata (entity_type_name, metric_name, is_index_column, index_type). See [NL_QUERY_DESIGN.md](./NL_QUERY_DESIGN.md) for chunking and schema.

---

## Flow (First Version)

1. User runs: `python nl_query_cli.py "give me all vms which belong to cluster X"`.
2. CLI POSTs the string to the server.
3. Server embeds query → retrieves top-k schema chunks → calls chat/completions with query + kb → parses and validates JSON → returns query proto (JSON).
4. CLI prints the JSON (or error).

**No Go/Python code generation** in this version.

---

## Deferred (TODO)

- **Go/Python code generation**: From the validated query proto only (template or second LLM call). Design in [NL_QUERY_DESIGN.md](./NL_QUERY_DESIGN.md) keeps “proto first, then code”; implementation is out of scope for the first version.
- Optional: Tools in chat/completions (e.g. “search_schema” implemented with the same vector search); first version injects retrieved chunks directly in the prompt.

---

## References

- **Full design**: [NL_QUERY_DESIGN.md](./NL_QUERY_DESIGN.md) — CLI and server behavior, Chroma data model, persistence/skip logic, validation, query modes (real vs imaginary), and “what to build” checklist.
