# Natural Language → Insights Query (First Version)

## Goal

**First version:** A lightweight flow that:

1. Takes a **single natural-language query string from the command line** (e.g. *"give me all vms which belong to cluster 01010897549764"* or *"get attribute a, b for table c where b = id1, top 20 by sort"*).
2. Returns the **query proto (canonical JSON)** for the insights DB.

**Out of scope for first version (TODO later):**

- Go/Python code generation from the query proto. Design keeps “proto first, then code” for when we add it; code gen is not implemented now.

---

## Components

### 1. CLI script (lightweight Python)

- **Input**: One string from the console.
  - Either: single command-line argument (the query string).
  - Or: read from stdin (one line or multi-line).
- **Behavior**: Send that string to the server (HTTP POST to a single endpoint), receive the response (query JSON + optional metadata).
- **Output**: Print the response to stdout (query JSON; optionally pretty-printed). On error (e.g. server unreachable, LLM error), print error message to stderr and exit non-zero.

No API key in the script if the server holds it; otherwise CLI can pass it (e.g. env `API_KEY`) or the server reads from env.

### 2. Server (Python)

- **Role**: Owns schema indexing (embeddings + vector DB), retrieval, and LLM call. Exposes one endpoint that accepts the query string and returns the query proto (JSON).

**Startup:**

1. **Schema source**: Read the schema file(s) that describe entity types and indexed attributes (e.g. from `entity_attribute_config` or a single preprocessed JSON/text file). Chunk the schema into units suitable for retrieval (e.g. per entity type: “entity_type: X, indexed attributes: A (type), B (type), …” or one chunk per indexed metric).
2. **Vector DB path**: Use a fixed directory (e.g. `./schema_vectordb` or configurable). This is where the vector DB is stored and reused.
3. **Skip if already built**: If the vector DB directory exists **and** the stored index is considered up-to-date (e.g. a marker file with schema file path/hash, or collection document count matches expected), **do not** re-tokenize or re-embed. Load the existing DB and continue.
4. **Build if missing**: If the DB does not exist or is stale:
   - Produce the list of text chunks from the schema.
   - Call the **embeddings API** (see below) with `input: [chunk1, chunk2, ...]` (batch as needed by API limits).
   - Insert into the vector DB: each chunk’s text, its embedding, and metadata (entity_type_name, metric_name, is_index_column, index_type, etc.).
   - Persist the DB to disk and write the marker/hash so the next run skips rebuild.

**On each query (request):**

1. **Embed the query**: Call the same embeddings API with `input: [user_query_string]` to get the query vector.
2. **Retrieve**: Run vector search in the DB (e.g. top-k, k=10–20) to get the most relevant schema chunks (“kb files”).
3. **LLM call**: Send to the **chat/completions API** (see below):
   - **System message**: Instructions that (a) you are an assistant that turns natural language into an insights Query proto in JSON form; (b) use only the provided schema chunks (kb) for entity/attribute names and indexed columns; (c) output a single JSON object that matches the Query message shape (entity_list, where_clause, group_by if needed); (d) rules: only indexed columns in where_clause; use kEQ for scalar equality, kContains for list “contains”; str_value must be string; etc.
   - **User message**: The user’s natural language query, plus (e.g. in the same message or a follow-up) the retrieved schema chunks as context (“Relevant schema:\n…”).
4. **Parse and validate**: Extract JSON from the LLM response (e.g. strip markdown if present). Run **structural validation** on the proto (entity_list present, where_clause well-formed, valid operators and value types). Optionally run **real-schema validation** if we resolved to a real entity type (entity and WHERE columns exist and are indexed).
5. **Response**: Return the query proto (JSON) to the client. If validation fails, return an error message and optionally a short reason.

**APIs used:**

- **Embeddings** (tokenize schema chunks and embed user query):

  ```bash
  curl -k -X POST 'https://hkn12.ai.nutanix.com/enterpriseai/v1/embeddings' \
    -H "Authorization: Bearer $API_KEY" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "hack-embed",
      "input": ["What is your name?", "How are you doing?"],
      "encoding_format": "float"
    }'
  ```

- **Chat completions** (LLM to produce query JSON):

  ```bash
  curl -k -X POST "https://hkn12.ai.nutanix.com/enterpriseai/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "hack-reason",
      "messages": [
        { "role": "system", "content": "..." },
        { "role": "user", "content": "..." }
      ],
      "max_tokens": 2048,
      "stream": false
    }'
  ```

  For the first version we do **not** require tools (e.g. no `search_research_papers`-style tool). The server does retrieval itself and injects the retrieved “kb” (schema chunks) into the prompt. Later we could add a tool that the LLM calls to “search schema,” implemented server-side with the same vector search.

---

## Vector DB: choice and data model

### Choice: Chroma (lightweight, dev VM friendly)

- **Why**: File-based, no separate server process; runs in-process with the Python server. Persists to a directory; can run on a random dev VM. Good Python support, simple API.
- **Alternatives considered**: FAISS (file-based, no metadata out of the box), LanceDB (embedded), Qdrant (server). Chroma gives a simple “collection + documents + metadata” model and persistence with minimal setup.

### Data model (Chroma)

- **Collection name**: e.g. `insights_schema` (single collection for all schema chunks).
- **Per document**:
  - **id** (string): Unique per chunk, e.g. `entity_type:vm:metric:cluster_uuid` or `entity:vm:chunk:0`.
  - **embedding** (list of float): From `hack-embed` for the chunk text; dimension from API response.
  - **document** (string): The searchable text (e.g. “entity_type: vm\nmetric_name: cluster_uuid\nis_index_column: true\nindex_type: kString” or a short description).
  - **metadata** (dict): At least:
    - `entity_type_name`: str  
    - `metric_name`: str  
    - `is_index_column`: bool  
    - `index_type`: str (e.g. `"kString"`, `"kInt64"`)  
    Optional: source file, line range, data_type from user_metadata.

Chunking strategy (recommended): One chunk per **indexed** metric (entity_type + metric_name + is_index_column + index_type). That gives fine-grained retrieval (e.g. “vm cluster” retrieves vm’s cluster_uuid chunk). Optionally add a few “entity summary” chunks per entity type (e.g. “entity_type: vm, indexed attributes: cluster_uuid, name, …”) for better entity-level matches.

### Persistence and “don’t do it again”

- Chroma persists the collection to a **persistent directory** (e.g. `./schema_vectordb`). The server is configured with this path.
- **Condition to skip rebuild**: Before embedding, the server checks:
  1. The persistent directory exists.
  2. The collection `insights_schema` exists and has documents.
  3. (Optional) A small **marker file** in that directory stores the **schema source path** and **content hash** (e.g. SHA256 of the schema file or concatenated schema files). If the current schema source has the same hash, treat the DB as up-to-date and skip re-embedding.
- If any of the above fails (missing dir, empty collection, or hash mismatch), (re)build: chunk schema → embed via API → add to Chroma → persist → write marker file with current hash.

---

## End-to-end flow (first version)

1. **User** runs: `python nl_query_cli.py "give me all vms which belong to cluster 01010897549764"` (or echoes the query into stdin).
2. **CLI** sends the string to the server (e.g. `POST /query` with `{"query": "..."}`).
3. **Server**:
   - Embeds the query string (embeddings API).
   - Vector search in Chroma → top-k schema chunks.
   - Builds messages: system (instructions + rules) + user (natural language query + “Relevant schema: …” with retrieved chunks).
   - Calls chat/completions (hack-reason); gets LLM response.
   - Parses JSON from response; runs structural (and optionally real-schema) validation.
   - Returns query JSON (or validation error).
4. **CLI** prints the response (query JSON or error) to stdout/stderr.

**Output of first version:** Query proto as JSON only. No Go/Python code.

---

## Query modes (unchanged conceptually)

- **Real schema**: User intent refers to real entities/attributes; we use retrieved schema and validate entity type and indexed columns. (Real-schema validation can be strict in a later iteration.)
- **Imaginary schema**: User describes a hypothetical table/attributes (e.g. “table c”, “attributes a, b”); we do not validate against the real schema, only structural validation. Mode can be inferred from the query or passed as a flag from CLI (e.g. `--imaginary`).

---

## Pipeline: proto first (code gen TODO)

- **First version:** NL → (retrieve schema chunks) → LLM → **query proto (JSON)** → validate → return JSON. **No code generation.**
- **Later (TODO):** Add a step: from the **validated proto only**, generate Go and Python code (template or second LLM call). Design remains “proto first, then code”; the first version simply stops at the proto.

---

## What to build (first version)

1. **Schema chunking**: Script or in-server logic that reads the schema file(s) (e.g. entity_attribute_config or a derived JSON) and produces a list of text chunks (+ metadata) for indexed attributes (and optionally entity summaries).
2. **Chroma setup**: Create collection `insights_schema`; add documents with embeddings and metadata; persist to configurable path; implement “skip if DB exists and hash matches.”
3. **Embeddings client**: Call `enterpriseai/v1/embeddings` with `hack-embed`, batch inputs if needed; use for both indexing chunks and embedding the user query.
4. **Server**: Single process (e.g. FastAPI/Flask). On startup: load or build vector DB (as above). One endpoint: e.g. `POST /query` body `{"query": "<nl string>", "schema_mode": "real"|"imaginary"}` → `{"query_json": {...}}` or `{"error": "..."}`. Use chat/completions with system + user message containing retrieved chunks; parse and validate JSON; return result.
5. **CLI**: Lightweight Python script; input = one string (argv or stdin); HTTP POST to server; print response.
6. **Config**: API base URL, API key (e.g. from env), vector DB path, schema file path(s). Optional: `schema_mode` default.

**Explicitly not in first version:** Go/Python code generation from the query proto (TODO).

---

## Summary

- **First version**: CLI (one string in) → Server (vector DB + retrieval + LLM) → query proto (JSON) out. No code gen.
- **Vector DB**: Chroma; persistent directory; skip re-embed if DB exists and schema hash unchanged; data model = one chunk per indexed metric (or similar) with metadata (entity_type_name, metric_name, is_index_column, index_type).
- **APIs**: Embeddings (`hack-embed`) for schema chunks and user query; chat/completions (`hack-reason`) with retrieved “kb” (schema chunks) in the prompt to produce query JSON.
- **Later (TODO):** Generate Go and Python from the validated proto only; same “proto first, then code” design.
