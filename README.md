# IDF.ai

**AI-powered natural-language interface for the Insights Data Fabric (IDF).**

IDF.ai turns plain-English questions into valid IDF query protos — grounded in your
cluster's real schema, drafted by a fine-tuned **Microsoft Phi-4**, validated field-by-field,
and safe to run live. Alongside query generation it bundles interactive workflows, a
searchable GFlags catalog, a live schema explorer and validator, and a documentation
knowledge base with a one-click Glean hand-off.

**Live app:** http://10.111.71.207:3000

---

## Demo — IDF.ai walkthrough

<video src="https://github.com/Nandish-nutanix/IDF.ai/raw/main/docs/diagrams/idf_demo.mp4" controls width="100%"></video>

▶ **[Watch the IDF.ai walkthrough](docs/diagrams/idf_demo.mp4)** — full end-to-end tour of every feature, running live against a real cluster.

---

## Features

- **Natural language → IDF proto** — ask in plain English and get a schema-valid query proto plus runnable Python, then execute it live on the cluster.
- **Grounded & self-correcting** — every entity and field is checked against the live schema; invalid drafts are repaired automatically, so the output is always valid.
- **Bring your own model** — Phi-4 runs on-device by default; plug in any OpenAI-compatible endpoint (your key stays in your browser) and the same grounded pipeline still runs.
- **Workflow playground** — live, editable, step-by-step IDF workflows (e.g. lookup queries / joins) that run end-to-end on the cluster.
- **GFlags catalog** — search hundreds of live gflags and edit values against the cluster.
- **Knowledge Base → Glean** — ask a question, get a structured answer from indexed IDF docs, view live cluster stats, and hand the rephrased question off to Glean in one click.
- **Schema Explorer** — browse the connected cluster's real entity types and attributes, preview data, and generate starter protos.
- **Schema Validator** — 16 best-practice checks for `RegisterEntityType` protos, with instant error feedback.
- **Guides** — indexing, testing, and container build/deploy walkthroughs with copy-ready commands.

---

## How it works

1. **Ground** the question in the live IDF schema (real entities, fields, examples).
2. **Draft** a candidate with Microsoft Phi-4 (or your configured model) using constrained decoding.
3. **Validate & repair** every entity, field, and type against the real schema.
4. **Render** a deterministic, guaranteed-valid proto — with runnable Python and a confidence score.

The model is a Microsoft Phi-4 (LoRA fine-tuned on real-schema data, then GRPO reward-tuned for schema-valid output) served locally via **MLX**.

---

## Tech stack

Microsoft Phi-4 (MLX) · nomic-embed-text · FastAPI · ChromaDB · vanilla JS frontend
