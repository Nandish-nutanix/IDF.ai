# IDF AI — How the Query Pipeline Works (Detailed Explanation)

> A presenter-friendly, end-to-end explanation of the AI that turns a plain‑English
> question into a valid IDF query proto. Pair this with `docs/diagrams/ai_architecture.png`
> and the demo video `docs/diagrams/idf_demo.mp4`.

---

## 1. TL;DR (say this first)

> "A user types a question in plain English. We **ground** it in the real IDF schema so the
> model knows the valid entities and fields. **Microsoft Phi‑4** drafts the query. We then
> **validate** that draft against the schema and correct anything invalid, and finally
> **render** a guaranteed‑valid IDF proto. If a draft can't be fixed, the model self‑corrects
> once; in the worst case we emit a minimal valid proto — so the system **returns a valid
> result every time**. The model itself is fine‑tuned offline with LoRA and then improved with
> GRPO reinforcement using a schema‑aware reward."

That's the whole story in ~30 seconds. The rest of this doc is the detail behind each phrase.

---

## 2. The big picture

There are **two timelines**:

| Timeline | When it runs | What it produces |
|---|---|---|
| **Inference** | Every time a user asks a question | A valid IDF query proto + a confidence score |
| **Build‑time (training)** | Once, offline | The fine‑tuned Phi‑4 model that inference uses |

The inference pipeline is **4 visible steps** plus a **safety net**:

```
Plain‑English query
   → 1) Ground in schema
   → 2) Phi‑4 drafts the query
   → 3) Validate against schema (fix invalid fields/types)
   → 4) Render proto
   → Valid IDF proto + confidence

Safety net: if step 3 can't fix the draft → self‑correct once;
            if anything still fails → guaranteed minimal fallback.
```

Everything is **grounded in one source of truth**: the real IDF schema.

---

## 3. Inference, step by step

### Step 0 — Input
The user types a natural‑language request, e.g. *"get all vms where power_state is on"*.
The UI sends it to the query server.

- **Files:** `idf_query_ui/` (frontend + backend proxy) → `backend-server/server.py`

### Step 1 — Ground in the schema
Before the model sees the question, we attach **grounding**: the relevant entity type(s)
and their **real, valid attributes**, plus a few **similar worked examples** (few‑shot).

- **Why:** LLMs hallucinate field names. If we show the model the actual columns for `vm`
  (e.g. `power_state`, `num_vcpus`, `memory_size_bytes`), it stops inventing fields.
- **How:**
  - `schema_service` resolves which entity type the question is about
    (`resolve_entity_types`, with alias matching and fuzzy `nearest_entity_type`).
  - It lists that entity's valid attributes.
  - We retrieve a handful of **lexically similar examples** from the training set
    (Jaccard similarity) so the model has a concrete pattern to imitate.
- **Files:** `proto_response_generator.py` (`_build_grounding`, `_retrieve_exemplars`),
  `schema_service.py`

### Step 2 — Phi‑4 drafts the query
The grounded prompt goes to **Microsoft Phi‑4**, served locally. The model returns a draft
of the query.

- **Two output modes** (the pipeline handles both):
  - **Constrained JSON** — using *Outlines*, the model is forced to emit a typed JSON object
    that matches our `QueryIR` schema. This guarantees the *structure* is valid before we even
    parse it.
  - **Trained text format** — `API: <method>` followed by proto text (what the fine‑tuned
    model is trained to produce).
- We make **one** model call and then interpret whatever it returned.
- **Files:** `proto_response_generator.py` (`_generate_one`, `_ir_from_text`),
  `constrained_decode.py`, `llm_client.py` (`call_llm`, `call_llm_json`),
  `query_ir.py` (the typed IR)

> **Query IR** = a single typed intermediate representation (a Pydantic model) that can express
> any of the ~21 IDF APIs with enums for the API method, operators, and value types. Working
> against the IR (instead of raw text) is what makes validation and rendering reliable.

### Step 3 — Validate against the schema (and repair)
We take the draft (now a `QueryIR`) and check **every part** of it against the real schema:

- Is the **entity type** real? If not, snap to the nearest real one.
- Does every **filter / select / sort column** actually exist on that entity? If a field is
  invalid, snap it to the closest real attribute (alias match → substring → fuzzy/Levenshtein).
- Does the **value type** match the column's data type? Coerce if needed
  (e.g. a number where an int is expected).
- Are the **operators** valid for the comparison?

Each correction is recorded in a **ValidationReport**, which yields a **quality** label
(`exact`, `repaired`, or `low`) and a **confidence** score. An untouched, fully‑valid draft is
high confidence; a draft we had to repair is reported with lower confidence so the user knows.

- **Files:** `ir_validator.py` (`validate_and_repair`, `ValidationReport`),
  `schema_service.py` (`nearest_attribute`), `proto_ast.py` (parsing proto text to an AST)

### Step 4 — Render the proto
A **deterministic renderer** turns the validated `QueryIR` into exact IDF proto text. This is
pure code — no regex guessing — so the output is **structurally guaranteed**.

- **Files:** `ir_to_proto.py` (`render`, per‑API renderers)

### Output
The server returns the **proto text + confidence**. The UI also offers generated Python code,
a copy button, and an execute action.

---

## 4. Why it never fails (the safety net)

Two fallbacks guarantee a usable result:

1. **Self‑correct (retry once):** if the draft can't be repaired into something valid, we make
   **one** targeted Phi‑4 call, feeding back what was wrong, and re‑validate.
2. **Guaranteed minimal fallback:** if generation itself errors, we construct a minimal but
   **valid** `QueryIR`, so the deterministic renderer always has something correct to emit.

Because the final step is deterministic rendering of a validated IR, **every path ends in a
structurally valid, schema‑faithful proto.** That's the core promise.

---

## 5. Supporting components

### Schema service — the single source of truth
- Parses the real schema from `entity_attribute_config.proto.template` (702 entity types and
  their attributes, data types, index flags), and **caches** it for speed.
- Provides lookups (`attributes_for`, `data_type_of`, `indexed_attributes`) and the fuzzy
  resolvers (`nearest_entity_type`, `nearest_attribute`) plus human‑friendly aliases.
- **Used by both** grounding (Step 1) and validation (Step 3), and by training data generation —
  so training and serving see the *same* schema (no train/serve skew).
- **File:** `schema_service.py`

### Model serving (local, on‑device)
- `mlx_server_local.py` exposes an **OpenAI‑compatible** API on port **8090**, running the
  fine‑tuned Phi‑4 via Apple's **MLX** framework. It honors `temperature`, `stop`, and
  `guided_json` (for constrained decoding).
- `llm_client.py` is the thin client (`call_llm`, `call_llm_json`).
- Model name: **`phi4_idf_fused`**.

### Knowledge Base / RAG (the "Knowledge Base" tab)
- A vector store (**ChromaDB**) over IDF documentation, embedded with **`nomic-embed-text`**
  (served by Ollama on port 11434). Powers documentation search and cited answers.
- **File:** `knowledge_base/kb_service.py`

---

## 6. How the model is built (offline training)

This runs once to produce the model that inference uses. Three stages:

### a) Generate training data (from the real schema)
- `generate_training_data.py` builds examples using **real attributes** from `schema_service`,
  in the **same grounded format** used at inference, and **balances** the API coverage so rare
  APIs aren't starved. Produces a train/valid split.

### b) LoRA fine‑tune
- `run_finetune.py` takes the base **`phi‑4‑4bit`** and trains lightweight **LoRA** adapters on
  the grounded data, teaching Phi‑4 the IDF query format. The adapters are fused into
  **`phi4_idf_fused`**.

### c) GRPO reinforcement (best‑of‑N)
- `grpo_train.py` further improves the model with **GRPO**, a reinforcement method that rewards
  better outputs. The reward is **schema‑aware**, combining:
  - **Right format** (follows the expected structure)
  - **Right API method**
  - **Structurally valid** proto (parses cleanly)
  - **Fields exist in the schema** (column‑exists rate)
  - **Matches intent** (field overlap / Jaccard with the target)
- Output: **`phi4_idf_fused_rl`**.

> **Why GRPO matters:** fine‑tuning teaches the *format*; GRPO pushes the model toward outputs
> that are actually *schema‑valid and correct*, because that's literally what earns reward.

---

## 7. How confidence is computed

Confidence reflects how much we trusted/repaired the draft:

- **No repair needed** → high confidence (≈100%).
- **Repaired** (we corrected a field/type/entity) → reported lower (e.g. ~80%) so the user
  knows the system adjusted their request.
- **Low / fallback** → flagged so it can be reviewed.

It's surfaced in the UI next to each result and comes from the `ValidationReport`.

---

## 8. The components, mapped to files (cheat sheet)

| Concern | File(s) |
|---|---|
| Orchestration of the whole inference loop | `proto_response_generator.py` |
| Schema source of truth + fuzzy matching | `schema_service.py` |
| Typed intermediate representation (IR) | `query_ir.py` |
| Grammar‑constrained JSON generation | `constrained_decode.py` |
| Schema‑aware validation & repair | `ir_validator.py` |
| Deterministic IR → proto rendering | `ir_to_proto.py` |
| Proto text parsing (tokenizer + AST) | `proto_ast.py` |
| Local Phi‑4 model server (MLX) | `mlx_server_local.py` |
| LLM client | `llm_client.py` |
| Config / feature flags | `config.py` |
| Training data generation | `generate_training_data.py` |
| LoRA fine‑tuning | `run_finetune.py` |
| GRPO RL + reward | `grpo_train.py` |
| Accuracy evaluation harness | `eval_accuracy.py` |
| Knowledge base / RAG | `knowledge_base/kb_service.py` |

---

## 9. 60‑second talk track (for the presentation)

1. **Problem:** plain‑English → a correct IDF query proto is hard; naive LLMs hallucinate
   field names and produce invalid output.
2. **Our approach:** ground → generate → validate → render, all anchored to the real schema.
3. **Ground:** we show the model the real entity and its valid fields + a few examples.
4. **Generate:** Phi‑4 drafts the query (optionally forced into a valid structure).
5. **Validate & repair:** we check every entity/field/type against the schema and fix invalid
   ones; confidence reflects whether we had to repair.
6. **Render:** deterministic code emits a guaranteed‑valid proto.
7. **Never fails:** self‑correct once, else a minimal valid fallback.
8. **The model:** fine‑tuned offline with LoRA, then improved with GRPO using a schema‑aware
   reward, served locally on‑device via MLX.

---

## 10. Glossary

- **Proto (protobuf):** the structured query format IDF expects.
- **Schema:** the catalog of entity types (e.g. `vm`, `node`, `alert`) and their valid fields.
- **Grounding:** injecting real schema facts (and examples) into the prompt so the model stays
  factual.
- **IR (Query IR):** a typed in‑memory representation of the query we validate and render from.
- **Constrained decoding:** forcing the model to only emit structurally valid output.
- **LoRA:** lightweight fine‑tuning that adapts a base model without retraining all weights.
- **GRPO:** a reinforcement‑learning method that rewards better generations.
- **MLX:** Apple's framework for running/fine‑tuning models efficiently on Apple silicon.
- **RAG:** retrieval‑augmented generation — fetch relevant docs, then answer with citations.
- **Phi‑4:** the Microsoft language model at the core of the pipeline.
