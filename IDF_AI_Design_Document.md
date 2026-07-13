# IDF.ai — AI/ML System Design Document

## Executive Summary

IDF.ai is an AI-powered developer tool for Nutanix's Insights Data Fabric (IDF). The system converts natural language questions into executable IDF Protobuf queries using a locally fine-tuned Microsoft Phi-4 model, and provides intelligent documentation search via a 5-stage RAG (Retrieval-Augmented Generation) pipeline.

**Models Used:**

- **Microsoft Phi-4 (14B parameters)** — Fine-tuned with LoRA for IDF query generation and knowledge synthesis
- **nomic-embed-text** — Embedding model for semantic vector search across 460 internal documents

**Key Metrics:**

- 3,018 training examples (auto-generated from live cluster schema)
- 21 IDF API methods supported
- 460 knowledge base documents indexed
- Runs entirely on Apple Silicon (M3, 18GB unified memory)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IDF.ai AI ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    USER INTERFACE (Browser)                          │    │
│  │                                                                     │    │
│  │   "get all VMs where           "How does CAS work         "validate │    │
│  │    memory > 8GB"                in IDF?"                   my proto" │    │
│  │         │                            │                        │     │    │
│  └─────────┼────────────────────────────┼────────────────────────┼─────┘    │
│            │                            │                        │           │
│            ▼                            ▼                        ▼           │
│  ┌─────────────────┐    ┌───────────────────────┐    ┌──────────────────┐   │
│  │ QUERY PIPELINE  │    │  RAG KNOWLEDGE BASE   │    │ SCHEMA VALIDATOR │   │
│  │                 │    │                       │    │  (Rule-based)    │   │
│  │ NL → Proto →   │    │ Embed → Search →      │    │                  │   │
│  │ Validate →     │    │ Filter → Synthesize   │    │  14 static rules │   │
│  │ Execute        │    │                       │    │                  │   │
│  └────────┬────────┘    └───────────┬───────────┘    └──────────────────┘   │
│           │                         │                                        │
│           ▼                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │              MICROSOFT PHI-4 (phi4_idf_fused)                     │       │
│  │              Served via MLX on port 8090                          │       │
│  │              OpenAI-compatible chat/completions API                │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│           │                         │                                        │
│           ▼                         ▼                                        │
│  ┌─────────────────┐    ┌───────────────────────┐                           │
│  │  LIVE CLUSTER   │    │     ChromaDB          │                           │
│  │  (CVM via SSH)  │    │  (Vector Database)    │                           │
│  │                 │    │                       │                           │
│  │  Executes the   │    │  460 docs embedded    │                           │
│  │  generated      │    │  via nomic-embed-text │                           │
│  │  proto query    │    │                       │                           │
│  └─────────────────┘    └───────────────────────┘                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Training Data Generation Pipeline

### Purpose

Microsoft Phi-4 is a general-purpose coding model. It knows Python, SQL, and common programming patterns, but has zero knowledge of:

- IDF Protobuf message structures
- Nutanix entity types (vm, node, cluster, disk, alert, task)
- IDF operator syntax (kEQ, kGT, kLT, kLike, kExists)
- RPC method names (GetEntitiesWithMetrics, UpdateEntity, Watch, etc.)

We need to teach it this domain knowledge. To do so, we generate structured training data from the actual cluster schema.

### Data Sources

```
┌──────────────────────────────────────────────────────────────────┐
│                    TRAINING DATA SOURCES                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────┐   ┌──────────────────────────────┐  │
│  │  Live Cluster Schema    │   │  IDF Schema Reference         │  │
│  │                         │   │                               │  │
│  │  entity_attribute_      │   │  idf_schema_reference.md      │  │
│  │  config.proto           │   │  - 21 RPC definitions         │  │
│  │  - 15 entity types      │   │  - Message structures         │  │
│  │  - Real attribute names │   │  - Operator enums             │  │
│  │  - Data types           │   │  - Field constraints          │  │
│  └────────────┬────────────┘   └──────────────┬───────────────┘  │
│               │                                │                   │
│               └────────────────┬───────────────┘                   │
│                                │                                   │
│                                ▼                                   │
│               ┌────────────────────────────────┐                   │
│               │  nutest_extracted_queries.md    │                   │
│               │  (4721 lines)                  │                   │
│               │  Real query patterns from       │                   │
│               │  production test suites         │                   │
│               └────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

### Entity Schema Used

The training data generator contains real entity schemas from a live Nutanix cluster:


| Entity Type         | String Attributes                                                 | Integer Attributes                                              | Boolean Attributes         |
| ------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------- |
| vm                  | vm_name, power_state, node, cluster, hypervisor_type, guest_os... | num_vcpus, memory_mb, memory_size_bytes, disk_capacity_bytes... | is_cvm, is_live_migratable |
| node                | node_name, cluster, hypervisor_type, cpu_model, serial_number...  | num_vms, num_cpu_cores, memory_size_bytes, cpu_usage_ppm...     | is_degraded                |
| cluster             | cluster_name, version, timezone, operation_mode...                | num_nodes, num_vms, storage_capacity_bytes, iops...             | is_registered_to_pc        |
| disk                | disk_id, serial_number, model, vendor, storage_tier...            | disk_size_bytes, num_io, avg_io_latency_usecs...                | is_mounted                 |
| container           | container_name, storage_pool_uuid, replication_factor...          | max_capacity_bytes, usage_bytes, free_space_bytes...            | is_compressed              |
| alert               | alert_title, severity, classification, alert_status...            | creation_time_usecs, resolved_time_usecs...                     | acknowledged               |
| task                | task_type, status, operation_type, entity_type...                 | start_time_usecs, completion_time_usecs, progress_pct...        | is_internal                |
| virtual_disk        | vm, container, disk_address, storage_container_uuid...            | disk_capacity_bytes, usage_bytes, num_iops...                   | is_flash_mode_enabled      |
| virtual_network     | subnet_name, subnet_type, vpc_uuid, cluster...                    | vlan_id, ip_pool_count, num_vms_connected                       | is_external                |
| image               | image_name, image_type, image_state, source_uri...                | size_bytes, creation_time_usecs...                              | is_active                  |
| protection_domain   | pd_name, type, remote_site, status...                             | num_protected_entities, total_user_data_bytes...                | is_active                  |
| volume_group_config | uuid, name, sharing_status...                                     | size_bytes, num_virtual_disks...                                | is_hidden                  |
| storage_pool        | storage_pool_name, cluster, disk_list                             | capacity_bytes, usage_bytes, num_disks...                       | —                          |
| category            | name, value, description, owner_uuid...                           | entity_count, creation_time_usecs...                            | is_system_defined          |
| virtual_nic         | vm, virtual_network, mac_address, ip_address...                   | vlan_id, rx_bytes, tx_bytes...                                  | is_connected               |


### Generation Process

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   TRAINING DATA GENERATION FLOW                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  For EACH entity type (15 types):                                          │
│    │                                                                       │
│    ├──▶ Basic queries        "get all VMs"                                │
│    ├──▶ Equality filters     "VMs where power_state = on"                 │
│    ├──▶ Numeric comparisons  "VMs with memory > 8192"                     │
│    ├──▶ Pattern matching     "VMs where name contains prod"               │
│    ├──▶ Existence checks     "VMs where ip_address exists"                │
│    ├──▶ Sorting / Top-N      "top 5 VMs by cpu_usage"                     │
│    ├──▶ Aggregations         "average memory across clusters"             │
│    ├──▶ Compound filters     "VMs where state=on AND memory > 4GB"        │
│    ├──▶ Column selection     "get vm_name, memory for all VMs"            │
│    ├──▶ Cursor pagination    "paginate tasks with batch size 50"          │
│    ├──▶ Update operations    "update VM abc123 set name to test"          │
│    └──▶ Delete operations    "delete VM with id 1234"                     │
│                                                                            │
│  Plus non-entity-specific APIs:                                            │
│    ├──▶ Watch                "watch for changes on VM entity type"         │
│    ├──▶ BatchGet             "batch query: count VMs and get clusters"     │
│    ├──▶ RegisterMetricTypes  "register attribute cpu_temp for vm"          │
│    ├──▶ GetEntitiesTrail     "show change history for VM abc"             │
│    ├──▶ GetEntityTypes       "describe entity type vm"                     │
│    ├──▶ GetMetricTypes       "list metrics for vm"                         │
│    ├──▶ PutEvent             "publish event on vm entity"                  │
│    ├──▶ SpotLightSearch      "spotlight search for prod-web"               │
│    ├──▶ AttachEntity         "attach entity with incarnation id 5"         │
│    ├──▶ DetachEntity         "detach entity moving to cluster B"           │
│    └──▶ ...                                                                │
│                                                                            │
│  OUTPUT: 3,018 training examples                                           │
│                                                                            │
│  API Distribution:                                                         │
│    GetEntitiesWithMetrics    ~2200 examples (most complex, most used)      │
│    UpdateEntity              ~150 examples                                 │
│    DeleteEntity              ~100 examples                                 │
│    Watch                     ~80 examples                                  │
│    BatchGetEntitiesWithMetrics ~60 examples                                │
│    RegisterMetricTypes       ~50 examples                                  │
│    GetEntityTypes            ~50 examples                                  │
│    Other APIs                ~328 examples                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

### Training Data Format

Each example is a 3-message conversation in ChatML format:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an IDF query generator. Output the API method on line 1 as \"API: <Method>\" then the protobuf text on subsequent lines."
    },
    {
      "role": "user",
      "content": "show subnets with ip_pool_count under 61"
    },
    {
      "role": "assistant",
      "content": "API: GetEntitiesWithMetrics\nquery {\n    entity_list { entity_type_name: \"virtual_network\" }\n    where_clause {\n    comparison_expr {\n      lhs {\n        leaf {\n          column: \"ip_pool_count\"\n        }\n      }\n      operator: kLT\n      rhs {\n        leaf {\n          value {\n            int64_value: 61\n          }\n        }\n      }\n    }\n  }\n  group_by {\n    raw_columns { column: \"overlay_network_uuid\" }\n    raw_columns { column: \"subnet_type\" }\n    raw_columns { column: \"ip_pool_count\" }\n  }\n  query_name: \"auto_query\"\n}"
    }
  ]
}
```

### Why Programmatic Generation (Not Manual)?


| Approach                        | Pros                                            | Cons                                     |
| ------------------------------- | ----------------------------------------------- | ---------------------------------------- |
| Manual labeling                 | High quality per example                        | Extremely slow (3000 examples = weeks)   |
| LLM-generated                   | Fast                                            | Hallucinated field names, invalid syntax |
| **Programmatic (our approach)** | **Perfect syntax guaranteed, uses real schema** | **Requires schema knowledge upfront**    |


Our approach ensures every training example has syntactically correct protobuf that would actually execute on the cluster. There are zero hallucinated field names because we generate from the real `entity_attribute_config.proto`.

---

## Part 2: LoRA Fine-Tuning

### Why LoRA?


| Method           | Parameters Updated     | Memory Required | Time              |
| ---------------- | ---------------------- | --------------- | ----------------- |
| Full fine-tuning | 14,000,000,000         | 56+ GB          | Hours on A100     |
| **LoRA**         | **~85,000,000 (0.6%)** | **~14 GB**      | **~30 min on M3** |


LoRA (Low-Rank Adaptation) freezes the entire base model and trains small adapter matrices that modify specific layers' behavior.

### How LoRA Works

```
┌──────────────────────────────────────────────────────────────────────┐
│                      LoRA MECHANISM                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  STANDARD TRANSFORMER LAYER:                                           │
│                                                                        │
│     input ──▶ [ W (frozen, 4096×4096) ] ──▶ output                    │
│                  16,777,216 parameters                                 │
│                  NOT UPDATED                                           │
│                                                                        │
│  WITH LoRA ADAPTER:                                                    │
│                                                                        │
│                    ┌───────────────────┐                               │
│     input ──┬──▶  │ W (frozen)        │ ──┐                           │
│             │     └───────────────────┘   │                           │
│             │                             ├──▶ output (sum)            │
│             │     ┌───────────────────┐   │                           │
│             └──▶  │ B × A (trainable) │ ──┘                           │
│                   └───────────────────┘                                │
│                                                                        │
│                   A: shape (rank × 4096)  = 65,536 params              │
│                   B: shape (4096 × rank)  = 65,536 params              │
│                   rank = 16 (hyperparameter)                           │
│                                                                        │
│                   Total trainable per layer: 131,072                   │
│                   vs. frozen per layer: 16,777,216                      │
│                   Reduction: 99.2%                                      │
│                                                                        │
│  Applied to top 16 of 32 transformer layers:                           │
│                                                                        │
│    Layer  1: Frozen only (general language understanding)              │
│    Layer  2: Frozen only                                               │
│    ...                                                                 │
│    Layer 16: Frozen only                                               │
│    Layer 17: Frozen + LoRA ◄── adapters start here                    │
│    Layer 18: Frozen + LoRA                                             │
│    ...                                                                 │
│    Layer 32: Frozen + LoRA                                             │
│                                                                        │
│  Rationale: Upper layers encode task-specific behavior.                │
│  Lower layers encode universal language representations.               │
│  We only need to modify task-specific behavior.                        │
└──────────────────────────────────────────────────────────────────────┘
```

### Training Configuration


| Parameter              | Value                             | Rationale                                                |
| ---------------------- | --------------------------------- | -------------------------------------------------------- |
| Base model             | Microsoft Phi-4 (4-bit quantized) | Best reasoning model that fits in 18GB                   |
| Fine-tune type         | LoRA                              | Memory-efficient, prevents catastrophic forgetting       |
| Batch size             | 1                                 | Memory constraint (18GB RAM)                             |
| Gradient accumulation  | 8 steps                           | Simulates effective batch size of 8                      |
| Training iterations    | 225                               | ~0.6 epochs — enough to learn format without overfitting |
| LoRA layers            | Top 16 of 32                      | Upper layers handle task-specific output                 |
| Learning rate          | 5×10⁻⁵                            | Conservative to preserve base model capabilities         |
| Max sequence length    | 1024 tokens                       | Sufficient for longest proto outputs                     |
| Gradient checkpointing | Enabled                           | Trades compute for memory (essential for 18GB)           |
| Prompt masking         | Enabled                           | Loss computed ONLY on assistant response                 |


### Prompt Masking — Critical Design Choice

```
┌─────────────────────────────────────────────────────────────────┐
│              PROMPT MASKING ILLUSTRATION                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  WITHOUT mask-prompt (wasteful):                                  │
│                                                                   │
│    [system: "You are an IDF query..."]  ← Loss computed (waste)  │
│    [user: "get all VMs"]                ← Loss computed (waste)  │
│    [assistant: "API: GetEntities..."]   ← Loss computed (useful) │
│                                                                   │
│    Model wastes capacity learning to predict the question text.   │
│                                                                   │
│  WITH mask-prompt (focused):                                      │
│                                                                   │
│    [system: "You are an IDF query..."]  ← MASKED (no gradient)   │
│    [user: "get all VMs"]                ← MASKED (no gradient)   │
│    [assistant: "API: GetEntities..."]   ← LOSS COMPUTED HERE     │
│                                                                   │
│    100% of learning signal goes toward correct proto generation.  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Adapter Fusion

After training produces the adapter (~50MB), it is permanently merged into the base model:

```
W_final = W_base + B × A

Result: phi4_idf_fused/ (single model, no adapter overhead at inference)
```

---

## Part 3: GRPO Reinforcement Learning

### Purpose

SFT (supervised fine-tuning) teaches the model the correct format and common patterns, but it can still make mistakes on edge cases — wrong API name, missing fields, or invalid nesting. GRPO uses a reward signal to further improve accuracy.

### GRPO Algorithm

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         GRPO TRAINING LOOP                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  FOR EACH training prompt (100 iterations):                                │
│                                                                            │
│    ┌──────────────────────────────────────────────────────────┐            │
│    │  "paginate through all tasks with batch size 50"          │            │
│    └──────────────────────────┬───────────────────────────────┘            │
│                               │                                            │
│                               ▼                                            │
│    ┌─── Generate 4 completions (temperature=0.7) ───────────┐             │
│    │                                                         │             │
│    │  Completion A: "API: GetEntitiesWithMetrics\n..."       │             │
│    │  Completion B: "API: GetEntitiesWithMetrics\n..."       │             │
│    │  Completion C: "API: GetEntityTypes\n..."  (wrong API)  │             │
│    │  Completion D: "API: GetEntitiesWithMetrics\n..."       │             │
│    └──────────────────────────┬──────────────────────────────┘             │
│                               │                                            │
│                               ▼                                            │
│    ┌─── Score each with reward function ────────────────────┐             │
│    │                                                         │             │
│    │  Completion A: reward = 0.85 (correct API, valid proto) │             │
│    │  Completion B: reward = 0.95 (best — all fields match)  │◄── WINNER  │
│    │  Completion C: reward = 0.20 (wrong API)                │             │
│    │  Completion D: reward = 0.70 (right API, missing field) │             │
│    └──────────────────────────┬──────────────────────────────┘             │
│                               │                                            │
│                               ▼                                            │
│    ┌─── Keep best completion as training signal ────────────┐             │
│    │                                                         │             │
│    │  Save (prompt, Completion B) to improved dataset         │             │
│    │                                                         │             │
│    │  If best reward < 0.5: use ground truth instead          │             │
│    └─────────────────────────────────────────────────────────┘             │
│                                                                            │
│  AFTER all iterations:                                                     │
│    ┌─────────────────────────────────────────────────────────┐             │
│    │  Run another LoRA pass on the improved dataset           │             │
│    │  (50 iterations, learning rate 5×10⁻⁶)                  │             │
│    │  Fuse into final model: phi4_idf_fused                   │             │
│    └─────────────────────────────────────────────────────────┘             │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### Reward Function Design

The reward function is domain-specific and has 4 components:

```
┌──────────────────────────────────────────────────────────────────┐
│                    REWARD FUNCTION (0.0 — 1.0)                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Component 1: FORMAT COMPLIANCE (weight: 0.2)                      │
│  ─────────────────────────────────────────────                     │
│  Does the response start with "API: ValidMethodName"?              │
│  Is the method name in the allowed set of 21 IDF APIs?             │
│                                                                    │
│  Component 2: CORRECT API METHOD (weight: 0.3)                     │
│  ─────────────────────────────────────────────                     │
│  Does the predicted API method match the ground truth?             │
│  e.g., Did it correctly choose "Watch" vs "GetEntitiesWithMetrics" │
│                                                                    │
│  Component 3: PROTO STRUCTURAL VALIDITY (weight: 0.3)              │
│  ─────────────────────────────────────────────────────             │
│  Does the proto text pass the structural validator?                │
│  - Correct nesting of braces                                       │
│  - Valid field names for the chosen API                            │
│  - Proper operator usage (kEQ, kGT, kLT, kLike)                   │
│  - Required fields present (entity_type_name, query_name)          │
│                                                                    │
│  Component 4: FIELD-LEVEL ACCURACY (weight: 0.2)                   │
│  ────────────────────────────────────────────────                  │
│  Jaccard overlap between predicted fields and expected fields:     │
│  score = |predicted_fields ∩ expected_fields| / |expected_fields|  │
│                                                                    │
│  TOTAL REWARD = C1 + C2 + C3 + C4  ∈ [0.0, 1.0]                  │
│                                                                    │
│  Examples:                                                         │
│    Perfect match to ground truth        → 1.0                      │
│    Right API + valid proto + 50% fields → 0.8                      │
│    Wrong API but valid format           → 0.2                      │
│    Garbage / unparseable output         → 0.0                      │
└──────────────────────────────────────────────────────────────────┘
```

### Memory-Efficient Design

The GRPO pipeline runs on 18GB Apple Silicon by splitting into two phases:

1. **Generation phase**: Uses the already-running MLX server (no additional memory)
2. **Training phase**: Stops the server, frees memory, runs lightweight LoRA (50 iterations)

---

## Part 4: Production Inference Pipeline

### Query Processing Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   PRODUCTION QUERY PIPELINE                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  USER INPUT: "get all VMs where power_state is on and memory > 4GB"        │
│       │                                                                    │
│       ▼                                                                    │
│  ┌────────────────────────────────────────────────────────────┐            │
│  │  STEP 1: LLM CALL (proto_response_generator.py)            │            │
│  │                                                            │            │
│  │  System prompt (compact, for fine-tuned model):             │            │
│  │  "You are an IDF query generator. Output API on line 1     │            │
│  │   as 'API: <Method>' then protobuf text below."            │            │
│  │                                                            │            │
│  │  → Sends to phi4_idf_fused at localhost:8090               │            │
│  │  → temperature=0, max_tokens=300, stop=["<|im_end|>"]     │            │
│  └──────────────────────────┬─────────────────────────────────┘            │
│                             │                                              │
│                             ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐            │
│  │  RAW LLM OUTPUT:                                            │            │
│  │                                                            │            │
│  │  API: GetEntitiesWithMetrics                                │            │
│  │  query {                                                    │            │
│  │    entity_list { entity_type_name: "vm" }                   │            │
│  │    where_clause {                                           │            │
│  │      logical_expr {                                         │            │
│  │        lhs { comparison_expr { ... "power_state" kEQ "on" } │            │
│  │        rhs { comparison_expr { ... "memory_size_bytes" kGT  │            │
│  │              4294967296 } }                                  │            │
│  │        operator: kAnd                                       │            │
│  │      }                                                      │            │
│  │    }                                                        │            │
│  │    group_by { raw_columns { column: "vm_name" } }           │            │
│  │    query_name: "auto_query"                                 │            │
│  │  }                                                          │            │
│  └──────────────────────────┬─────────────────────────────────┘            │
│                             │                                              │
│                             ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐            │
│  │  STEP 2: VALIDATION & POST-PROCESSING                      │            │
│  │                                                            │            │
│  │  • Parse "API: MethodName" line                            │            │
│  │  • Validate method is in allowed set (21 APIs)             │            │
│  │  • Check proto structure (brace matching, required fields) │            │
│  │  • Auto-fix common issues:                                 │            │
│  │    - GetEntities → GetEntitiesWithMetrics (if has filters) │            │
│  │    - Add missing query_name field                          │            │
│  │    - Fix operator casing                                   │            │
│  │  • Retry with LLM if validation fails (up to 2 retries)   │            │
│  └──────────────────────────┬─────────────────────────────────┘            │
│                             │                                              │
│                             ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐            │
│  │  STEP 3: PYTHON CODE GENERATION                            │            │
│  │                                                            │            │
│  │  Generates executable Python using InsightsInterface SDK:   │            │
│  │                                                            │            │
│  │  from util.insights_interface_pb2 import *                  │            │
│  │  from util.insights_interface import InsightsInterface       │            │
│  │  ifc = InsightsInterface("10.46.30.35", "2027")            │            │
│  │  arg = GetEntitiesWithMetricsArg()                          │            │
│  │  # ... populate proto fields ...                            │            │
│  │  ret = ifc.get_entities_with_metrics(arg)                   │            │
│  │  print(ret)                                                 │            │
│  └──────────────────────────┬─────────────────────────────────┘            │
│                             │                                              │
│                             ▼                                              │
│  ┌────────────────────────────────────────────────────────────┐            │
│  │  STEP 4: REMOTE EXECUTION                                  │            │
│  │                                                            │            │
│  │  SSH into CVM → activate Python venv → execute script      │            │
│  │  Parse output → format results for UI                      │            │
│  └────────────────────────────────────────────────────────────┘            │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### Why a Single LLM Call?

Traditional NLP pipelines use multiple steps (intent classification → entity extraction → template filling). We use a single LLM call because:

1. **The fine-tuned model handles all three tasks at once** — intent (API method), extraction (entity types, filters), and generation (proto text)
2. **Fewer failure points** — no classification errors propagating downstream
3. **Faster** — one 300ms inference call vs. multiple model invocations
4. **More flexible** — the model generalizes to novel query patterns not seen in training

---

## Part 5: RAG Knowledge Base Pipeline

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    RAG KNOWLEDGE BASE ARCHITECTURE                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  OFFLINE (indexing):                                                       │
│                                                                            │
│    460 documents (.docx files)                                             │
│         │                                                                  │
│         ▼                                                                  │
│    kb_indexer.py                                                            │
│    - Extract text from .docx                                               │
│    - Chunk into ~1500 char segments                                        │
│    - Classify into 12 categories                                           │
│    - Extract features/keywords                                             │
│         │                                                                  │
│         ▼                                                                  │
│    nomic-embed-text (via Ollama)                                           │
│    - Convert each chunk to 768-dim vector                                  │
│         │                                                                  │
│         ▼                                                                  │
│    ChromaDB (persistent vector database)                                   │
│    - Store vectors + metadata + original text                              │
│                                                                            │
│  ──────────────────────────────────────────────────────────────────────    │
│                                                                            │
│  ONLINE (search):                                                          │
│                                                                            │
│    User: "How does CAS work in IDF?"                                       │
│         │                                                                  │
│         ▼                                                                  │
│    ┌──── 5-STAGE DEEP SEARCH PIPELINE ────────────────────────────┐       │
│    │                                                               │       │
│    │  STAGE 1: Query Expansion                                     │       │
│    │  ┌──────────────────────────────────────────────────────┐    │       │
│    │  │ Phi-4 generates 2 alternative search angles:          │    │       │
│    │  │   Original: "How does CAS work in IDF?"               │    │       │
│    │  │   Alt 1: "IDF compare and swap concurrency mechanism" │    │       │
│    │  │   Alt 2: "cas_value optimistic locking entity update" │    │       │
│    │  └──────────────────────────────────────────────────────┘    │       │
│    │                             │                                 │       │
│    │                             ▼                                 │       │
│    │  STAGE 2: Multi-Pass Retrieval                                │       │
│    │  ┌──────────────────────────────────────────────────────┐    │       │
│    │  │ For each query (3 total):                             │    │       │
│    │  │   → nomic-embed-text converts to vector              │    │       │
│    │  │   → ChromaDB returns top 8 nearest chunks            │    │       │
│    │  │ Total: up to 24 candidate chunks                      │    │       │
│    │  └──────────────────────────────────────────────────────┘    │       │
│    │                             │                                 │       │
│    │                             ▼                                 │       │
│    │  STAGE 3: Deduplicate & Re-rank (RRF)                         │       │
│    │  ┌──────────────────────────────────────────────────────┐    │       │
│    │  │ Reciprocal Rank Fusion:                               │    │       │
│    │  │   RRF_score = Σ 1/(60 + rank_in_query_i)            │    │       │
│    │  │                                                       │    │       │
│    │  │ Cross-query boost:                                    │    │       │
│    │  │   If a chunk appears in multiple queries,             │    │       │
│    │  │   multiply score by (1 + 0.3 × appearance_count)     │    │       │
│    │  │                                                       │    │       │
│    │  │ Deduplicate by first 200 chars → top 15 candidates   │    │       │
│    │  └──────────────────────────────────────────────────────┘    │       │
│    │                             │                                 │       │
│    │                             ▼                                 │       │
│    │  STAGE 4: Relevance Filter                                    │       │
│    │  ┌──────────────────────────────────────────────────────┐    │       │
│    │  │ Phi-4 reads all 15 snippets and decides:              │    │       │
│    │  │ "Which chunks actually answer the question?"          │    │       │
│    │  │ Returns: "1, 3, 5, 7, 11" (relevant chunk numbers)   │    │       │
│    │  │                                                       │    │       │
│    │  │ Result: 5-8 highly relevant chunks                    │    │       │
│    │  └──────────────────────────────────────────────────────┘    │       │
│    │                             │                                 │       │
│    │                             ▼                                 │       │
│    │  STAGE 5: Synthesis                                           │       │
│    │  ┌──────────────────────────────────────────────────────┐    │       │
│    │  │ Phi-4 generates comprehensive answer using:           │    │       │
│    │  │   - Filtered chunks as context                        │    │       │
│    │  │   - IDF_GROUND_TRUTH definitions (anti-hallucination) │    │       │
│    │  │   - Structured format with ## headers, citations      │    │       │
│    │  │                                                       │    │       │
│    │  │ Output: Markdown answer with [Source: filename] refs  │    │       │
│    │  └──────────────────────────────────────────────────────┘    │       │
│    │                                                               │       │
│    └───────────────────────────────────────────────────────────────┘       │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### Anti-Hallucination: Ground Truth Injection

A 2,000-character block of authoritative IDF definitions is injected into every synthesis prompt:

```
IDF_GROUND_TRUTH = """
- CAS (Compare-And-Swap): An optimistic concurrency control mechanism...
- Entity Type: A schema definition in IDF (like a table)...
- Metric Type / Attribute: A named, typed field on an entity type...
- Namespace: A partition mechanism for attributes...
- Evictable vs Unevictable: Entity types can be kEvictable or kNotEvictable...
- IDF Lattice: Framework for Federated Entity Types...
- Watch: A subscription mechanism...
- GEWM (GetEntitiesWithMetrics): The primary read/query API...
- Secondary Index: Attributes marked for indexing...
- Prism Central (PC) / Prism Element (PE): Management planes...
"""
```

This prevents the model from inventing alternative definitions (e.g., expanding CAS as "Conflict-Abort-Sync" instead of the correct "Compare-And-Swap").

### Why nomic-embed-text?


| Property     | nomic-embed-text          | OpenAI ada-002    |
| ------------ | ------------------------- | ----------------- |
| Runs locally | Yes (Ollama)              | No (cloud API)    |
| Dimensions   | 768                       | 1536              |
| Cost         | Free                      | $0.0001/1K tokens |
| Privacy      | Data stays local          | Sent to OpenAI    |
| Latency      | ~10ms                     | ~200ms            |
| Quality      | Strong for technical docs | Slightly better   |


For an internal enterprise tool handling confidential documentation, local embedding is mandatory.

---

## Part 6: Cross-Validation Framework

### Test Categories

```
┌──────────────────────────────────────────────────────────────────┐
│                  CROSS-VALIDATION MATRIX                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  SAFE (executed on cluster):                                       │
│  ├── GetEntitiesWithMetrics (basic, filter, sort, aggregate)      │
│  ├── Cursor pagination queries                                    │
│  ├── Batch queries (read-only)                                    │
│  └── Lookup queries (joins)                                       │
│                                                                    │
│  VALIDATED ONLY (proto structure check, NOT executed):             │
│  ├── UpdateEntity (would modify data)                             │
│  ├── DeleteEntity (would destroy data)                            │
│  ├── RegisterEntityTypes (would alter schema)                     │
│  ├── RegisterMetricTypes (would alter schema)                     │
│  └── Watch (would create subscriptions)                           │
│                                                                    │
│  VALIDATION CHECKS:                                                │
│  ├── Correct API method classification                            │
│  ├── Proto contains all expected fields                           │
│  ├── Proto structure is syntactically valid                       │
│  └── (For safe ops) Execution returns data without errors         │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part 7: Model Serving Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    MODEL SERVING STACK                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  MLX Server (Apple Metal-accelerated)                        │  │
│  │  Port: 8090                                                  │  │
│  │  Model: phi4_idf_fused (Phi-4 + LoRA + GRPO, fused)        │  │
│  │  API: OpenAI-compatible /v1/chat/completions                 │  │
│  │  Quantization: 4-bit (MLX native)                           │  │
│  │  Inference speed: ~50 tokens/sec on M3                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Ollama Server (nomic-embed-text)                            │  │
│  │  Port: 11434                                                 │  │
│  │  Model: nomic-embed-text                                     │  │
│  │  API: /api/embeddings                                        │  │
│  │  Output: 768-dimensional float vectors                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  ChromaDB (Persistent vector store)                          │  │
│  │  Path: ./chroma_db/                                          │  │
│  │  Collection: idf_knowledge_base                              │  │
│  │  Documents: 460 (chunked into ~2000 vectors)                 │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Summary: End-to-End Training Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐    │
│  │  CLUSTER  │     │ GENERATE  │     │   LORA    │     │   GRPO    │    │
│  │  SCHEMA   │────▶│ TRAINING  │────▶│ FINE-TUNE │────▶│    RL     │    │
│  │           │     │   DATA    │     │           │     │           │    │
│  └───────────┘     └───────────┘     └───────────┘     └───────────┘    │
│                                                                            │
│  15 entity types    3,018 examples    LoRA adapters     Reward-filtered   │
│  Real attributes    21 API types      50MB / 225 iter   Best-of-N data    │
│  Live proto specs   ChatML format     Top 16 layers     50 iterations     │
│                                                                            │
│                                              │                             │
│                                              ▼                             │
│                                       ┌───────────┐                        │
│                                       │   FUSE    │                        │
│                                       │  ADAPTER  │                        │
│                                       │           │                        │
│                                       │ W = W + BA│                        │
│                                       └─────┬─────┘                        │
│                                             │                              │
│                                             ▼                              │
│                                       ┌───────────┐                        │
│                                       │   SERVE   │                        │
│                                       │  MLX :8090│                        │
│                                       │           │                        │
│                                       │ phi4_idf_ │                        │
│                                       │ fused     │                        │
│                                       └─────┬─────┘                        │
│                                             │                              │
│                                    ┌────────┼────────┐                     │
│                                    ▼        ▼        ▼                     │
│                              ┌─────────┐ ┌──────┐ ┌──────┐                │
│                              │  QUERY  │ │ RAG  │ │CROSS │                │
│                              │PIPELINE │ │SEARCH│ │VALID.│                │
│                              │         │ │      │ │      │                │
│                              │NL→Proto │ │5-stg │ │E2E   │                │
│                              │→Execute │ │deep  │ │tests │                │
│                              └─────────┘ └──────┘ └──────┘                │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Choices & Justification


| Component       | Technology            | Why This Choice                                                       |
| --------------- | --------------------- | --------------------------------------------------------------------- |
| Base LLM        | Microsoft Phi-4 (14B) | Best reasoning quality in its size class; fits in 18GB quantized      |
| Fine-tuning     | LoRA via MLX          | Runs on Apple Silicon; 99% memory reduction vs full fine-tune         |
| RL method       | GRPO                  | Simpler than PPO; works with limited memory; reward is easy to define |
| Embedding       | nomic-embed-text      | Local, free, fast, strong on technical docs                           |
| Vector DB       | ChromaDB              | Persistent, lightweight, no infrastructure needed                     |
| Serving         | MLX Server            | Native Apple Silicon acceleration; OpenAI-compatible API              |
| Training format | ChatML (messages)     | Standard for instruction-following models                             |
| Quantization    | 4-bit (MLX native)    | ~4x memory reduction with minimal quality loss                        |
| Hardware        | Apple M3, 18GB        | Everything runs locally — no cloud dependency or cost                 |


---

## File Reference


| File                            | Lines | Purpose                                           |
| ------------------------------- | ----- | ------------------------------------------------- |
| `generate_training_data.py`     | 1,439 | Programmatic training data generation from schema |
| `run_finetune.py`               | 77    | LoRA fine-tuning orchestration                    |
| `grpo_train.py`                 | 386   | GRPO reinforcement learning pipeline              |
| `proto_response_generator.py`   | 2,240 | LLM call + validation + post-processing           |
| `llm_client.py`                 | 84    | HTTP client for MLX server                        |
| `config.py`                     | 64    | Model paths, URLs, hyperparameters                |
| `knowledge_base/kb_service.py`  | 684   | RAG pipeline + Deep Search                        |
| `knowledge_base/kb_indexer.py`  | ~200  | Document chunking + embedding + indexing          |
| `cross_validate.py`             | ~200  | End-to-end read query validation                  |
| `cross_validate_complex.py`     | 274   | Multi-API validation (write ops)                  |
| `mlx_finetune_data/train.jsonl` | 3,018 | Training dataset                                  |
| `finetune_local_export.sh`      | 70    | Adapter fusion + export script                    |


---

*Document generated for IDF.ai project — Nutanix Hack 2026*