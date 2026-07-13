"""
LLM-First proto generation from natural language.

Single LLM call handles:
1. Intent classification (which IDF API)
2. Parameter extraction (entity types, filters, values)
3. Proto text generation

No regex classification - the LLM does everything.
"""

import json
import os
import re
from typing import List, Optional, Tuple

import config
import llm_client

# Grounded pipeline modules (Phase 1-3).
import schema_service
import ir_to_proto
import ir_validator
from query_ir import ApiMethod, QueryIR

MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Grounded generation: schema grounding + few-shot exemplars
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_TRAIN_PATH = os.path.join(_SCRIPT_DIR, "mlx_finetune_data", "train.jsonl")
_exemplars_cache: Optional[List[dict]] = None


def _load_exemplars() -> List[dict]:
    """Load (user, assistant) training pairs once for few-shot retrieval."""
    global _exemplars_cache
    if _exemplars_cache is not None:
        return _exemplars_cache
    items: List[dict] = []
    try:
        with open(_TRAIN_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if len(msgs) >= 2:
                    user = msgs[-2].get("content", "")
                    assistant = msgs[-1].get("content", "")
                    if user and assistant:
                        items.append({
                            "user": user,
                            "assistant": assistant,
                            "tokens": set(re.findall(r"[a-z0-9_]+", user.lower())),
                        })
    except (OSError, json.JSONDecodeError):
        pass
    _exemplars_cache = items
    return items


def _retrieve_exemplars(query: str, k: int = 3) -> List[dict]:
    """Retrieve top-k most lexically similar training exemplars (Jaccard)."""
    items = _load_exemplars()
    if not items:
        return []
    q_tokens = set(re.findall(r"[a-z0-9_]+", query.lower()))
    if not q_tokens:
        return items[:k]
    scored = []
    for it in items:
        inter = len(q_tokens & it["tokens"])
        if inter == 0:
            continue
        union = len(q_tokens | it["tokens"]) or 1
        scored.append((inter / union, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:k]]


def _build_grounding(query: str) -> str:
    """
    Build a concise grounding appendix: candidate entity types with their real
    queryable attributes + a few retrieved exemplars. Kept short so the
    fine-tuned model can use it without drifting from its trained behavior.
    """
    lines: List[str] = []
    entities = schema_service.resolve_entity_types(query, limit=2)
    if entities:
        lines.append("VALID SCHEMA (use these exact names):")
        for et in entities:
            attrs = schema_service.attributes_for(et)
            # Prefer indexed attributes, then fill with common ones, cap at 40.
            indexed = schema_service.indexed_attributes(et)
            names = list(dict.fromkeys(indexed + list(attrs.keys())))[:15]
            if names:
                lines.append(f"- {et}: {', '.join(names)}")
    exemplars = _retrieve_exemplars(query, k=config.GROUNDING_FEWSHOT_K)
    if exemplars:
        lines.append("\nEXAMPLES:")
        for ex in exemplars:
            lines.append(f"Q: {ex['user']}")
            lines.append(ex["assistant"])
            lines.append("")
    return "\n".join(lines).strip()

UNIFIED_SYSTEM_PROMPT = """You are an expert IDF (Insights Data Fabric) query generator for Nutanix.

Given a natural language query, you MUST output exactly two things:
1. Line 1: "API: <MethodName>" (the EXACT IDF RPC method name from the list below)
2. Lines 2+: The proto text in protobuf text format (or empty if no args needed)

CRITICAL: You MUST use ONLY the exact API names listed below. Do NOT invent names like "DeleteVM" or "ListMetrics".
The ONLY valid API names are: GetEntitiesWithMetrics, GetEntityTypes, GetMetricTypes, UpdateEntity, DeleteEntity,
RegisterEntityTypes, RegisterMetricTypes, UnregisterMetricTypes, BatchGetEntitiesWithMetrics,
BatchUpdateEntities, BatchDeleteEntities, GetEntities, GetMetricData, PutMetricData,
SpotLightSearch, GetEntitiesTrail, AttachEntity, DetachEntity, GetMasterLocation, Watch, PutEvent

=== KEYWORD TRIGGERS FOR LESS COMMON APIs ===
These keywords MUST trigger specific APIs (NOT GetEntitiesWithMetrics):
- "batch query"/"batch get"/"in one call"/"multiple queries" -> BatchGetEntitiesWithMetrics
- "batch update"/"bulk update"/"batch set" -> BatchUpdateEntities
- "batch delete"/"bulk delete"/"batch remove" -> BatchDeleteEntities
- "by id"/"by guid"/"fetch entity with guid"/"specific entity" -> GetEntities
- "metric data"/"time-series"/"time series"/"historical data"/"get metric" -> GetMetricData
- "write metric"/"publish metric"/"put metric"/"record metric" -> PutMetricData
- "change history"/"audit trail"/"entity trail"/"change log"/"modification history"/"trail" -> GetEntitiesTrail
- "register metric"/"register attribute"/"add metric"/"add attribute" -> RegisterMetricTypes
- "unregister metric"/"remove metric"/"remove attribute"/"unregister attribute"/"delete metric type" -> UnregisterMetricTypes
- "attach entity"/"attach"+"incarnation" -> AttachEntity
- "detach entity"/"detach"+"moving to"/"detach"+"cluster" -> DetachEntity
- "publish event"/"put event"/"create event"/"fire event" -> PutEvent
- "lookup entity"/"lookup by id" -> GetEntities

=== AVAILABLE APIs ===

1. GetEntitiesWithMetrics - Read/query entities with filters, sorting, aggregation
   Proto: GetEntitiesWithMetricsArg
   Use for: "get VMs", "show disks where...", "count tasks", "top 5 by...", "average memory"
   Structure: query { entity_list { entity_type_name: "X" } ... query_name: "..." }

2. GetEntityTypes - Get entity type schema/info/definition
   Proto: GetEntityTypesArg
   Use for: "describe entity type X", "show all entity types", "get info about X entity type",
            "what is entity type X", "info about X entity type", ANY query asking about an entity TYPE DEFINITION
   IMPORTANT: If the user asks about an entity TYPE (not entities/rows), use this API!
   Structure: entity_type_name: "X" (or empty for all types)

3. GetMetricTypes - List metrics/attributes/columns for an entity type
   Proto: GetMetricTypesArg
   Use for: "list metrics for vm", "show attributes of disk", "what metrics/attributes/columns does vm have",
            "list all metrics for entity type X", ANY query asking what METRICS or ATTRIBUTES exist
   IMPORTANT: If the user wants to know what metrics/attributes/columns an entity type HAS, use this API!
   Structure: regex: ".*:entity_type" (or ".*" for all)

4. UpdateEntity - Create or modify entity attributes (IDF uses UpdateEntity for both create and update)
   Proto: UpdateEntityArg
   Use for: "update vm X setting Y to Z", "modify attribute", "create a vm named X"
   CRITICAL STRUCTURE - entity_guid and attribute_data_arg_list MUST be TOP-LEVEL siblings:
   entity_guid {
     entity_type_name: "X"
     entity_id: "ID"
   }
   cas_value: 0
   attribute_data_arg_list {
     attribute_data {
       name: "attr_name"
       value { str_value: "val" }
     }
   }
   DO NOT wrap entity_guid inside attribute_data_arg_list or entity_with_attribute_list!
   DO NOT use "entity_with_attribute_list" - that field does NOT exist in UpdateEntityArg!

5. DeleteEntity - Remove an entity
   Proto: DeleteEntityArg
   Use for: "delete vm X", "remove entity"
   Structure: entity_guid { entity_type_name: "X" entity_id: "ID" }

6. RegisterEntityTypes - Register new entity types
   Proto: RegisterEntityTypesArg
   Use for: "register new entity type X", "create entity type"
   Structure: entity_type_info_list { entity_type_name: "X" type_info { parent_list: "node" } }

7. RegisterMetricTypes - Register new metrics/attributes
   Proto: RegisterMetricTypesArg
   Use for: "register attribute X for vm", "add metric"
   Structure: metric_type_list { is_attribute: true metric_name: "X" entity_type_name: "Y" }

8. UnregisterMetricTypes - Remove metrics
   Proto: UnregisterMetricTypesArg
   Use for: "unregister metric X from Y", "remove attribute"
   Structure: metric_type_list { metric_name: "X" entity_type_name: "Y" }

9. BatchGetEntitiesWithMetrics - Multiple queries in one call
   Proto: BatchGetEntitiesWithMetricsArg
   Use for: "batch query: get X and Y", "multiple queries"
   Structure: query_list { query { ... } } query_list { query { ... } }

10. BatchUpdateEntities - Bulk update
    Proto: BatchUpdateEntitiesArg
    Use for: "batch update entities", "bulk update"
    Structure: entity_list { entity_guid {...} attribute_data_arg_list {...} } (repeated)

11. BatchDeleteEntities - Bulk delete
    Proto: BatchDeleteEntitiesArg
    Use for: "batch delete entities", "bulk delete"
    Structure: entity_list { entity_guid {...} } (repeated)

12. GetEntities - Fetch by specific GUID
    Proto: GetEntitiesArg
    Use for: "get entity by id X", "fetch entity with guid", "lookup entity"
    Structure: entity_guid_list { entity_type_name: "X" entity_id: "ID" }

13. GetMetricData - Read time-series metric data
    Proto: GetMetricDataArg
    Use for: "get metric data for X", "time-series for cpu_usage", "historical metric"
    Structure: entity_type_name: "X" entity_id_list: "ID" metric_name_list: "metric"

14. PutMetricData - Write time-series data
    Proto: PutMetricDataArg
    Use for: "write metric data", "publish metric", "record metric value"
    Structure: entity_with_metric_list { entity_guid { entity_type_name: "X" entity_id: "ID" } metric_data_list { name: "M" value_list { value { uint64_value: V } } } }

15. SpotLightSearch - Full-text search across entities (NO specific field)
    Proto: SpotLightSearchArg
    Use for: "search for entities containing X" (NO specific field mentioned)
    Structure: search_term: "X" entity_type_name_list: "Y" limit { limit: 20 }

16. GetEntitiesTrail - Entity change history / audit trail
    Proto: GetEntitiesTrailArg
    Use for: "get history for entity X", "show change trail", "audit trail", "audit log"
    Structure: entity_guid_list { entity_type_name: "X" entity_id: "ID" }

17. AttachEntity - Attach entity for replication
    Proto: AttachEntityArg
    Use for: "attach entity X"
    Structure: update_entity_arg { entity_guid { entity_type_name: "X" entity_id: "ID" } } incarnation_id: N

18. DetachEntity - Detach entity for migration
    Proto: DetachEntityArg
    Use for: "detach entity X moving to cluster Y"
    Structure: delete_entity_arg { entity_guid { entity_type_name: "X" entity_id: "ID" } } moved_to_cluster_uuid: "UUID"

19. GetMasterLocation - Get IDF master node
    Proto: GetMasterLocationArg
    Use for: "get master location", "who is the master"
    Structure: (empty - no fields needed)

20. Watch (RegisterWatch) - Subscribe to entity changes
    Proto: RegisterWatchArg
    Use for: "watch for changes on VM", "monitor new alerts", "subscribe to updates"
    Structure: client_id: "X" session_id: "Y" watch_list { watch_name: "Z" entity_type_name: "E" watch_type_mask: 7 }
    watch_type_mask: 1=Create, 2=Update, 4=Delete, 7=All

21. PutEvent - Publish an event
    Proto: PutEventArg
    Use for: "publish event", "create event for entity", "fire event"
    Structure: event_type: "X" entity_type_name: "Y" entity_id: "ID"

=== CRITICAL RULES FOR GetEntitiesWithMetrics PROTO STRUCTURE ===

DO NOT generate simplified/generic proto like:
  WRONG: filter { field_name: "X" operator: GT value: 4 }
  WRONG: order_by { field_name: "X" direction: DESCENDING }
  WRONG: limit: 10
  WRONG: group_by: "cluster_name"
  WRONG: fields: "vm_name"

The ONLY valid format is the exact IDF nested structure shown in the examples below.

RULE 1 - TOP-LEVEL STRUCTURE:
query {
  entity_list { entity_type_name: "X" }
  where_clause { ... }     # optional filtering
  group_by { ... }         # columns, sorting, pagination, aggregation
  query_name: "..."        # always required
}

RULE 2 - WHERE CLAUSE (filtering):
   where_clause {
     comparison_expr {
    lhs { leaf { column: "FIELD_NAME" } }
    operator: kEQ           # MUST use kEQ/kNE/kGT/kGE/kLT/kLE/kLike
    rhs { leaf { value { str_value: "VALUE" } } }
  }
}
For numeric: rhs { leaf { value { uint64_value: 42 } } }
For regex: operator: kLike, rhs { leaf { value { str_value: ".*pattern.*" } } }

RULE 3 - COLUMN SELECTION (return specific columns):
group_by {
  raw_columns { column: "col1" }
  raw_columns { column: "col2" }
}

RULE 4 - SORTING:
group_by {
  raw_columns { column: "sort_field" }
  raw_sort_order { column: "sort_field" order: kDescending }
  raw_limit { limit: N offset: 0 }
}
NOTE: raw_sort_order REQUIRES raw_columns and raw_limit to also be present.

RULE 5 - PAGINATION / LIMIT:
group_by {
  raw_columns { column: "some_col" }
  raw_limit { limit: N offset: 0 }
}

RULE 6 - AGGREGATION:
group_by {
  aggregate_columns { column: "field" operator: kAvg }
}

RULE 7 - ENTITY TYPE MAPPING:
- "host"/"hosts" -> entity_type_name: "node"
- "storage_container"/"storage containers" -> entity_type_name: "container"

RULE 8 - EVICTABLE ENTITIES (alert, event, task, audit_entry):
- MUST include group_by { raw_columns { ... } raw_limit { limit: N offset: 0 } }

RULE 9 - OPERATORS (use EXACTLY these spellings):
- Comparison: kEQ, kNE, kLT, kLE, kGT, kGE
- Pattern: kLike (for regex/contains), kContains (list membership), kExists (no rhs)
- Logical: kAnd, kOr
- Aggregation: kSum, kAvg, kCount, kMin, kMax
- Sort: kAscending, kDescending
DO NOT use: GT, LT, EQUALS, DESCENDING, ASCENDING, >, <, =, !=

RULE 10 - COMPOUND WHERE (AND/OR):
where_clause {
  lhs { comparison_expr { ... } }
  operator: kAnd
  rhs { comparison_expr { ... } }
}

RULE 11 - VALUE TYPES:
- str_value: "text", uint64_value: 42, int64_value: -5, bool_value: true
- str_list { value_list: "a" value_list: "b" }

RULE 12 - COUNT: use group_by { raw_limit { limit: 0 } } or flags: 2

RULE 13 - kExists has NO rhs:
comparison_expr { lhs { leaf { column: "attr" } } operator: kExists }

RULE 14 - FETCHING A SPECIFIC ENTITY BY NAME/ID:
When the user says "fetch/get/show <entity_type> named X" or "details of <entity_type> X",
use entity_id in entity_list to fetch by ID (NOT a where_clause on "name"):
query {
  entity_list {
    entity_type_name: "vm"
    entity_id: "X"
  }
  query_name: "auto_query"
}
DO NOT use where_clause with column: "name" - that column often does not exist!
The entity_id IS the name/identifier of the entity in IDF.

RULE 15 - CREATING AN ENTITY (UpdateEntity):
When the user says "create a <type> named X", use UpdateEntity with:
- entity_id = X (the name becomes the ID)
- Set a meaningful attribute like "<type>_name" with the same value
entity_guid {
  entity_type_name: "vm"
  entity_id: "X"
}
cas_value: 0
attribute_data_arg_list {
  attribute_data {
    name: "vm_name"
    value { str_value: "X" }
  }
}

=== DISAMBIGUATION RULES (CRITICAL - READ CAREFULLY) ===
- "get info about X entity type" or "describe X entity type" -> GetEntityTypes (NOT GetEntitiesWithMetrics)
- "list metrics/attributes for X" -> GetMetricTypes (NOT GetEntitiesWithMetrics)
- "get all Xs" or "show Xs where..." -> GetEntitiesWithMetrics (querying entity DATA)
- "update/modify/set entity X" -> UpdateEntity
- "register new entity type" or "create entity type" -> RegisterEntityTypes (NOT GetEntitiesWithMetrics!)
- "watch for changes" or "subscribe" or "monitor" -> Watch
- "audit trail"/"change history"/"trail"/"change log" -> GetEntitiesTrail (NOT GetEntitiesWithMetrics!)
- "unregister"/"remove metric"/"remove attribute" -> UnregisterMetricTypes (NOT GetEntitiesWithMetrics!)
- "lookup entity"/"get entity by id" -> GetEntities (NOT GetEntitiesWithMetrics!)
- ONLY use API names from the exact valid list. Do NOT invent new names.

CRITICAL SpotLightSearch vs GetEntitiesWithMetrics:
- SpotLightSearch: "search for entities containing X" (generic text search, NO specific field)
- GetEntitiesWithMetrics with kLike: "find VMs where vm_name contains X" (field-specific filter)
- If a SPECIFIC FIELD is mentioned (vm_name, node_name, cluster_name, etc.) -> use kLike in GetEntitiesWithMetrics
- If NO field is mentioned and it's a generic "search/find entities" -> use SpotLightSearch

=== WHEN TO USE GetEntitiesWithMetrics vs OTHER APIs ===
GetEntitiesWithMetrics is ONLY for reading/querying entity DATA rows (get VMs, show disks where X, top N by Y).
Do NOT use it for:
- Registering new types (use RegisterEntityTypes)
- Getting entity type definitions/schema (use GetEntityTypes)
- Getting metric/attribute definitions (use GetMetricTypes)
- Getting entity change history/trail (use GetEntitiesTrail)
- Looking up entity by specific ID/GUID (use GetEntities)
- Unregistering metrics (use UnregisterMetricTypes)

=== FEW-SHOT EXAMPLES ===

Example 1: "get all VMs"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by { raw_columns { column: "vm_name" } }
  query_name: "fetch_all_vms"
}

Example 2: "get VMs where power_state = on"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "power_state" } }
       operator: kEQ
      rhs { leaf { value { str_value: "on" } } }
    }
  }
  group_by { raw_columns { column: "vm_name" } raw_columns { column: "power_state" } }
  query_name: "vm_by_power_state"
}

Example 3: "get top 5 VMs sorted by num_vcpus descending"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "num_vcpus" }
    raw_sort_order { column: "num_vcpus" order: kDescending }
    raw_limit { limit: 5 offset: 0 }
  }
  query_name: "top_vms_by_vcpus"
}

Example 4: "show all entity types"
API: GetEntityTypes

Example 5: "get info about vm entity type"
API: GetEntityTypes
entity_type_name: "vm"

Example 6: "list all metrics for entity type vm"
API: GetMetricTypes
regex: ".*:vm"

Example 7: "update vm entity vm-001 setting power_state to on with cas value 5"
API: UpdateEntity
entity_guid {
  entity_type_name: "vm"
  entity_id: "vm-001"
}
cas_value: 5
attribute_data_arg_list {
  attribute_data {
    name: "power_state"
    value { str_value: "on" }
  }
}

Example 8: "delete vm entity vm-test-123"
API: DeleteEntity
entity_guid {
  entity_type_name: "vm"
  entity_id: "vm-test-123"
}

Example 9: "register new entity type custom_sensor with parent node"
API: RegisterEntityTypes
entity_type_info_list {
  entity_type_name: "custom_sensor"
  type_info {
    parent_list: "node"
  }
}

Example 10: "watch for changes on VM entity type"
API: Watch
client_id: "idf_watch_vm_client"
session_id: "session_001"
watch_list {
  watch_name: "watch_vm_all"
  entity_type_name: "vm"
  watch_type_mask: 7
}

Example 11: "search for entities containing production"
API: SpotLightSearch
search_term: "production"
entity_type_name_list: "vm"
limit {
  limit: 20
}

Example 12: "get master location"
API: GetMasterLocation

Example 13: "count all VMs"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by { raw_limit { limit: 0 } }
  query_name: "count_vms"
}

Example 14: "get VMs where vm_name contains test"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "vm_name" } }
      operator: kLike
      rhs { leaf { value { str_value: ".*test.*" } } }
    }
  }
  group_by { raw_columns { column: "vm_name" } }
  query_name: "vm_name_contains_test"
}

Example 15: "get average memory_mb for VMs"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by {
    aggregate_columns {
      column: "memory_mb"
      operator: kAvg
    }
  }
  query_name: "avg_memory_vms"
}

Example 16: "get first 10 VMs"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_columns { column: "vm_name" }
    raw_limit { limit: 10 offset: 0 }
  }
  query_name: "first_10_vms"
}

Example 17: "show VMs sorted by memory_mb descending limit 5"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "memory_mb" }
    raw_sort_order { column: "memory_mb" order: kDescending }
    raw_limit { limit: 5 offset: 0 }
  }
  query_name: "vms_sorted_memory"
}

Example 18: "get VMs grouped by cluster_name"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_columns { column: "cluster_name" }
    raw_columns { column: "vm_name" }
  }
  query_name: "vms_by_cluster"
}

Example 19: "get vm_name and power_state for all VMs"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "power_state" }
  }
  query_name: "vm_columns"
}

Example 20: "get VMs where num_vcpus > 4"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "num_vcpus" } }
      operator: kGT
      rhs { leaf { value { uint64_value: 4 } } }
    }
  }
  group_by { raw_columns { column: "vm_name" } raw_columns { column: "num_vcpus" } }
  query_name: "vms_vcpus_gt_4"
}

Example 21: "get VMs where memory_mb < 2048"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "memory_mb" } }
      operator: kLT
      rhs { leaf { value { uint64_value: 2048 } } }
    }
  }
  group_by { raw_columns { column: "vm_name" } raw_columns { column: "memory_mb" } }
  query_name: "vms_low_memory"
}

Example 22: "get VMs where power_state equals ON and num_vcpus >= 2"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "power_state" } }
        operator: kEQ
        rhs { leaf { value { str_value: "ON" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "num_vcpus" } }
        operator: kGE
        rhs { leaf { value { uint64_value: 2 } } }
      }
    }
  }
  group_by { raw_columns { column: "vm_name" } raw_columns { column: "power_state" } raw_columns { column: "num_vcpus" } }
  query_name: "vms_on_and_vcpus"
}

Example 23: "get info about my_custom_type entity type"
API: GetEntityTypes
entity_type_name: "my_custom_type"

Example 24: "what attributes does vm entity type have"
API: GetMetricTypes
regex: ".*:vm"

Example 25: "update VM vm-abc setting memory_mb to 8192"
API: UpdateEntity
entity_guid {
  entity_type_name: "vm"
  entity_id: "vm-abc"
}
cas_value: 0
attribute_data_arg_list {
  attribute_data {
    name: "memory_mb"
    value { uint64_value: 8192 }
  }
}

Example 26: "get entity by id abc-123 of type vm"
API: GetEntities
entity_guid_list {
  entity_type_name: "vm"
  entity_id: "abc-123"
}

Example 27: "lookup entity with id node-xyz of type node"
API: GetEntities
entity_guid_list {
  entity_type_name: "node"
  entity_id: "node-xyz"
}

Example 28: "get change history for VM entity vm-001"
API: GetEntitiesTrail
entity_guid_list {
  entity_type_name: "vm"
  entity_id: "vm-001"
}

Example 29: "get audit trail for disk entity disk-abc"
API: GetEntitiesTrail
entity_guid_list {
  entity_type_name: "disk"
  entity_id: "disk-abc"
}

Example 30: "batch query: get all VMs and all nodes"
API: BatchGetEntitiesWithMetrics
query_list {
  query {
    entity_list { entity_type_name: "vm" }
    group_by { raw_columns { column: "vm_name" } }
    query_name: "batch_vms"
  }
}
query_list {
  query {
    entity_list { entity_type_name: "node" }
    group_by { raw_columns { column: "node_name" } }
    query_name: "batch_nodes"
  }
}

Example 31: "batch delete VMs vm-old-1 and vm-old-2"
API: BatchDeleteEntities
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-old-1"
  }
}
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-old-2"
  }
}

Example 32: "register attribute cpu_temp for entity type node"
API: RegisterMetricTypes
metric_type_list {
  is_attribute: true
  metric_name: "cpu_temp"
  entity_type_name: "node"
}

Example 33: "unregister metric old_attr from vm"
API: UnregisterMetricTypes
metric_type_list {
  metric_name: "old_attr"
  entity_type_name: "vm"
}

Example 34: "unregister attribute cpu_temp from entity type node"
API: UnregisterMetricTypes
metric_type_list {
  metric_name: "cpu_temp"
  entity_type_name: "node"
}

Example 35: "write metric cpu_usage value 85 for vm entity vm-001"
API: PutMetricData
entity_with_metric_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-001"
  }
  metric_data_list {
    name: "cpu_usage"
    value_list {
      value { uint64_value: 85 }
    }
  }
}

Example 36: "get metric data for cpu_usage of vm entity vm-001"
API: GetMetricData
entity_type_name: "vm"
entity_id_list: "vm-001"
metric_name_list: "cpu_usage"

Example 37: "publish event vm_created for VM entity vm-001"
API: PutEvent
event_type: "vm_created"
entity_type_name: "vm"
entity_id: "vm-001"

Example 38: "fire event disk_failure for disk entity disk-001"
API: PutEvent
event_type: "disk_failure"
entity_type_name: "disk"
entity_id: "disk-001"

Example 39: "attach entity VM vm-001 with incarnation 5"
API: AttachEntity
update_entity_arg {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-001"
  }
}
incarnation_id: 5

Example 40: "detach entity VM vm-migrate moving to cluster uuid-abc"
API: DetachEntity
delete_entity_arg {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-migrate"
  }
}
moved_to_cluster_uuid: "uuid-abc"

Example 41: "batch update VMs vm-1 and vm-2 setting power_state to off"
API: BatchUpdateEntities
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-1"
  }
  attribute_data_arg_list {
    attribute_data {
      name: "power_state"
      value { str_value: "off" }
    }
  }
}
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "vm-2"
  }
  attribute_data_arg_list {
    attribute_data {
      name: "power_state"
      value { str_value: "off" }
    }
  }
}

Example 42: "paginate through all tasks with batch size 50"
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "task" }
  group_by {
    raw_columns { column: "task_type" }
    raw_limit { limit: 50 offset: 0 }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 50
  }
  query_name: "cursor_tasks"
}

=== OUTPUT FORMAT ===
- Line 1 MUST be: API: <MethodName>
- Lines 2+: The proto text (protobuf text format, 2-space indent)
- If no proto fields needed (e.g. GetMasterLocation, GetEntityTypes for all): just output "API: MethodName" with nothing after
- No markdown, no code blocks, no explanation, no comments
- Do NOT wrap non-read APIs in query { }
- Only GetEntitiesWithMetrics and BatchGetEntitiesWithMetrics use the query { } wrapper"""


def generate_proto(query: str, schema_chunks: List[dict] = None,
                  selected_entity_types: List[str] = None,
                  selected_attributes: List[str] = None,
                  llm_override: dict = None,
                  meta: dict = None) -> Tuple[str, List[str], Optional[str], float]:
    """
    Generate an IDF query proto from natural language.

    Returns:
        Tuple of (proto_text, entity_types_found, api_method, confidence)

    `llm_override` optionally targets a user-supplied OpenAI-compatible endpoint
    ("bring your own model"); `meta` (if given) is populated with which backend
    actually produced the result.

    Dispatches to the grounded constrained pipeline (default) or the legacy
    regex pipeline when config.USE_GROUNDED_PIPELINE is False.
    """
    if getattr(config, "USE_GROUNDED_PIPELINE", True):
        return _generate_proto_grounded(query, llm_override=llm_override, meta=meta)
    proto_text, ets, api = _generate_proto_legacy(query, schema_chunks)
    return proto_text, ets, api, 1.0


# ---------------------------------------------------------------------------
# Grounded pipeline: ground -> constrained IR -> validate/repair -> render
#                    -> single self-correct -> guaranteed minimal fallback
# ---------------------------------------------------------------------------

_GROUNDED_SYSTEM = (
    "You are an IDF (Insights Data Fabric) query generator for Nutanix. "
    "Given a natural language query, output the API method on line 1 as "
    '"API: <MethodName>" then the IDF protobuf text on subsequent lines. '
    "Use only attribute and entity-type names that exist in the provided schema."
)

# Rich, self-contained prompt for NON fine-tuned models (e.g. Ollama Phi-4-mini).
# The fine-tuned MLX model already knows the format; a general model does not, so
# it needs the exact IDF proto grammar + concrete examples. Kept compact (~800
# tokens) so prompt-eval stays fast on CPU-only hosts.
_COMPACT_SYSTEM = """You are an IDF (Insights Data Fabric) query generator for Nutanix.

OUTPUT FORMAT - plain text ONLY. NO markdown, NO code fences, NO ```, NO JSON objects.
Line 1: API: <MethodName>
Lines 2+: the IDF protobuf text (some APIs need no body).

VALID API NAMES (pick EXACTLY one, NEVER invent a name):
GetEntitiesWithMetrics, GetEntities, GetEntityTypes, GetMetricTypes, GetMetricData,
UpdateEntity, DeleteEntity, RegisterEntityTypes, RegisterMetricTypes, UnregisterMetricTypes,
BatchGetEntitiesWithMetrics, BatchUpdateEntities, BatchDeleteEntities, PutMetricData,
SpotLightSearch, GetEntitiesTrail, AttachEntity, DetachEntity, GetMasterLocation, Watch, PutEvent

Reading/listing/counting/filtering entity rows uses GetEntitiesWithMetrics with this EXACT shape:
query {
  entity_list { entity_type_name: "<type>" }
  where_clause { ... }        # include ONLY when filtering
  group_by { ... }            # columns / sort / limit / aggregation
  query_name: "auto_query"
}

FILTER (where_clause), one condition:
where_clause { comparison_expr {
  lhs { leaf { column: "<attr>" } }
  operator: kEQ                              # kEQ kNE kLT kLE kGT kGE kLike kExists
  rhs { leaf { value { str_value: "<v>" } } }   # numbers: uint64_value: N
} }
Two conditions (AND/OR):
where_clause {
  lhs { comparison_expr { ... } }
  operator: kAnd
  rhs { comparison_expr { ... } }
}

group_by pieces:
  columns:     raw_columns { column: "<attr>" }
  sort:        raw_sort_order { column: "<attr>" order: kDescending }   (also needs raw_columns + raw_limit)
  limit/page:  raw_limit { limit: N offset: 0 }
  COUNT rows:  group_by { raw_limit { limit: 0 } }
  aggregate:   aggregate_columns { column: "<attr>" operator: kAvg }    (kSum kAvg kCount kMin kMax)

HARD RULES: use ONLY entity/attribute names from the SCHEMA given below. Map "host"->"node".
Operators MUST be the k-spellings (kEQ,kGT,...). NEVER use > < = != GT LT EQUALS DESCENDING.

EXAMPLES:
Q: get all VMs
API: GetEntitiesWithMetrics
query { entity_list { entity_type_name: "vm" } group_by { raw_columns { column: "vm_name" } } query_name: "auto_query" }

Q: get VMs where power_state = on
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause { comparison_expr { lhs { leaf { column: "power_state" } } operator: kEQ rhs { leaf { value { str_value: "on" } } } } }
  group_by { raw_columns { column: "vm_name" } raw_columns { column: "power_state" } }
  query_name: "auto_query"
}

Q: count powered on VMs with more than 4 vcpus
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    lhs { comparison_expr { lhs { leaf { column: "power_state" } } operator: kEQ rhs { leaf { value { str_value: "on" } } } } }
    operator: kAnd
    rhs { comparison_expr { lhs { leaf { column: "num_vcpus" } } operator: kGT rhs { leaf { value { uint64_value: 4 } } } } }
  }
  group_by { raw_limit { limit: 0 } }
  query_name: "auto_query"
}

Q: top 5 VMs by num_vcpus descending
API: GetEntitiesWithMetrics
query {
  entity_list { entity_type_name: "vm" }
  group_by { raw_columns { column: "vm_name" } raw_columns { column: "num_vcpus" } raw_sort_order { column: "num_vcpus" order: kDescending } raw_limit { limit: 5 offset: 0 } }
  query_name: "auto_query"
}

Q: average memory_mb for VMs
API: GetEntitiesWithMetrics
query { entity_list { entity_type_name: "vm" } group_by { aggregate_columns { column: "memory_mb" operator: kAvg } } query_name: "auto_query" }

Q: list metrics for entity type vm
API: GetMetricTypes
regex: ".*:vm"

Q: describe vm entity type
API: GetEntityTypes
entity_type_name: "vm"

Q: delete vm entity vm-test-1
API: DeleteEntity
entity_guid { entity_type_name: "vm" entity_id: "vm-test-1" }"""


def _active_system_prompt(force_general: bool = False) -> str:
    """Thin prompt for the fine-tuned model, rich grammar+examples otherwise.

    `force_general` returns the rich prompt even on a fine-tuned default (used for
    a custom override endpoint, which is a general model that needs the grammar).
    """
    if force_general:
        return _COMPACT_SYSTEM
    return _GROUNDED_SYSTEM if getattr(config, "USE_FINETUNED_MODEL", False) else _COMPACT_SYSTEM


def _ir_from_text(raw: str, query: str) -> QueryIR:
    """
    Parse a single model response into a QueryIR, handling BOTH shapes from one
    call: a constrained JSON IR (when Outlines is active) OR the trained
    "API: <method>\\n<proto>" text (when it is not). This keeps the pipeline to a
    single model call, which matters a lot for latency.
    """
    raw = (raw or "").strip()

    # Try JSON IR first (constrained decoding path).
    candidate = raw
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate[candidate.find("{"):] if "{" in candidate else candidate
    if candidate.lstrip().startswith("{"):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and ("api_method" in data or "entity_type" in data):
                return QueryIR.from_loose(data)
        except (json.JSONDecodeError, ValueError):
            pass

    # Otherwise treat it as trained proto-format output.
    api_method, proto_text = _parse_llm_response(raw)
    api_method = _override_api_from_query(query, api_method) or api_method or "GetEntitiesWithMetrics"
    proto_text = _reconstruct_flat_proto(proto_text, api_method, query)
    return ir_validator.proto_to_ir(proto_text, api_method)


def _generate_one(grounded_user: str, query: str,
                  llm_override: dict = None, meta: dict = None) -> QueryIR:
    """Single model call -> QueryIR (constrained JSON or proto, whichever comes back).

    If `llm_override` targets a custom endpoint, use it; on failure fall back to
    the local default so a bad key/URL never breaks the query. `meta['llm_used']`
    records which backend produced the result.
    """
    use_override = bool(llm_override and llm_override.get("api_key"))

    if use_override:
        try:
            raw = llm_client.call_llm(
                _active_system_prompt(force_general=True), grounded_user,
                max_tokens=config.PROTO_MAX_TOKENS, override=llm_override,
            )
            if meta is not None:
                meta["llm_used"] = "custom"
                meta["model"] = llm_override.get("model")
            return _ir_from_text(raw, query)
        except Exception as e:  # noqa: BLE001
            print(f"[Proto Gen] custom endpoint failed ({e}); falling back to local")
            if meta is not None:
                meta["llm_used"] = "local"
                meta["custom_error"] = str(e)[:200]

    system = _active_system_prompt()
    if getattr(config, "USE_CONSTRAINED_DECODING", True):
        try:
            raw = llm_client.call_llm_json(
                system, grounded_user, guided_schema="QueryIR",
                max_tokens=config.PROTO_MAX_TOKENS,
            )
            return _ir_from_text(raw, query)
        except Exception as e:  # noqa: BLE001
            print(f"[Proto Gen] guided call failed, using plain generation: {e}")
    raw = llm_client.call_llm(system, grounded_user,
                              max_tokens=config.PROTO_MAX_TOKENS)
    return _ir_from_text(raw, query)


def _generate_proto_grounded(query: str, llm_override: dict = None,
                             meta: dict = None) -> Tuple[str, List[str], Optional[str], float]:
    grounding = _build_grounding(query)
    grounded_user = query if not grounding else f"{query}\n\n{grounding}"

    print(f"[Proto Gen] Grounded generation: {query[:80]}")

    # 1) Primary generation: ONE model call (JSON IR or proto, parsed uniformly).
    ir = _generate_one(grounded_user, query, llm_override=llm_override, meta=meta)

    # Apply keyword-based API override (cheap, high-precision routing).
    overridden = _override_api_from_query(query, ir.api_method.value)
    if overridden and overridden in {m.value for m in ApiMethod}:
        ir.api_method = ApiMethod(overridden)

    # 2) Validate + repair against the real schema.
    report = ir_validator.validate_and_repair(ir)

    # 3) Self-correct ONCE if the entity type is still unknown/missing.
    needs_fix = (ir.api_method in (ApiMethod.GetEntitiesWithMetrics,
                                   ApiMethod.GetEntities, ApiMethod.GetMetricData)
                 and (not ir.entity_type or not schema_service.has_entity(ir.entity_type)))
    if needs_fix:
        valid_entities = ", ".join(schema_service.resolve_entity_types(query, limit=5)) or "vm, node, cluster, disk"
        correction = (
            f"{query}\n\nThe entity type must be one of the REAL types below. "
            f"Most likely: {valid_entities}.\n{grounding}"
        )
        try:
            ir2 = _generate_one(correction, query, llm_override=llm_override, meta=meta)
            ov2 = _override_api_from_query(query, ir2.api_method.value)
            if ov2 in {m.value for m in ApiMethod}:
                ir2.api_method = ApiMethod(ov2)
            report2 = ir_validator.validate_and_repair(ir2)
            if ir2.entity_type and schema_service.has_entity(ir2.entity_type):
                ir, report = ir2, report2
        except Exception as e:  # noqa: BLE001
            print(f"[Proto Gen] self-correct failed: {e}")

    # 4) Guaranteed fallback: ensure a usable entity type so render never empties.
    confidence = report.confidence
    if ir.api_method in (ApiMethod.GetEntitiesWithMetrics, ApiMethod.GetEntities,
                         ApiMethod.GetMetricData) and (
            not ir.entity_type or not schema_service.has_entity(ir.entity_type)):
        guess = schema_service.resolve_entity_types(query, limit=1)
        ir.entity_type = guess[0] if guess else "vm"
        confidence = min(confidence, 0.45)
        print(f"[Proto Gen] fallback entity -> {ir.entity_type}")

    # 5) Deterministic render (always structurally valid).
    proto_text = ir_to_proto.render(ir)

    entity_types = [ir.entity_type] if ir.entity_type else re.findall(
        r'entity_type_name\s*:\s*"([^"]+)"', proto_text)
    entity_types = list(dict.fromkeys(entity_types))

    if report.fixes:
        print(f"[Proto Gen] repaired ({len(report.fixes)} fix): {report.fixes}")
    print(f"[Proto Gen] api={ir.api_method.value} confidence={confidence:.2f}")
    return proto_text, entity_types, ir.api_method.value, round(confidence, 2)


def _generate_proto_legacy(query: str, schema_chunks: List[dict] = None
                           ) -> Tuple[str, List[str], Optional[str]]:
    """Original single-call + regex-normalization pipeline (kept behind flag)."""
    if config.USE_FINETUNED_MODEL:
        user_msg = query
    else:
        schema_text = _build_schema_context(schema_chunks or [])
        user_msg = f"""NATURAL LANGUAGE QUERY: {query}

SCHEMA CONTEXT (available entity types and attributes):
{schema_text}

Generate the IDF proto. Output "API: <Method>" on line 1, then the proto text."""

    print(f"[Proto Gen] Sending to LLM: {query}")
    content = llm_client.call_llm(UNIFIED_SYSTEM_PROMPT, user_msg, max_tokens=config.PROTO_MAX_TOKENS)
    print(f"[Proto Gen] LLM response ({len(content)} chars)")

    api_method, proto_text = _parse_llm_response(content)
    api_method = _override_api_from_query(query, api_method)

    if config.USE_FINETUNED_MODEL:
        proto_text = _reconstruct_flat_proto(proto_text, api_method, query)
        is_valid, error = _validate_proto(proto_text, api_method)
        if not is_valid:
            print(f"[Proto Gen] Validation note: {error} (applying normalization)")
        if api_method == "GetEntitiesWithMetrics":
            proto_text = _normalize_get_entities_proto(proto_text, query)
        else:
            proto_text = _normalize_other_proto(proto_text, api_method, query)
    else:
        is_valid, error = _validate_proto(proto_text, api_method)
        retry_count = 0
        while not is_valid and retry_count < MAX_RETRIES:
            retry_count += 1
            print(f"[Proto Gen] Validation failed ({error}), retry {retry_count}")
            correction_msg = f"""Your previous output had an error: {error}

Original query: {query}
Your output:
API: {api_method}
{proto_text}

Fix the issue. Output "API: <Method>" on line 1, then corrected proto text."""
            content = llm_client.call_llm(UNIFIED_SYSTEM_PROMPT, correction_msg, max_tokens=config.PROTO_MAX_TOKENS)
            api_method, proto_text = _parse_llm_response(content)
            api_method = _override_api_from_query(query, api_method)
            is_valid, error = _validate_proto(proto_text, api_method)
        if not is_valid:
            print(f"[Proto Gen] WARNING: {error}")
        api_method = _override_api_from_query(query, api_method)
        if api_method == "GetEntitiesWithMetrics":
            proto_text = _normalize_get_entities_proto(proto_text, query)
        else:
            proto_text = _normalize_other_proto(proto_text, api_method, query)

    entity_type_matches = re.findall(r'entity_type_name\s*:\s*"([^"]+)"', proto_text)
    result_entity_types = list(set(entity_type_matches)) if entity_type_matches else []
    return proto_text, result_entity_types, api_method


def _reconstruct_flat_proto(proto_text: str, api_method: str, original_query: str) -> str:
    """Reconstruct proto from flat/JSON-like LLM output that lacks proper proto structure."""
    s = proto_text.strip()

    # Skip if already has proper proto structure
    if 'query {' in s or 'entity_guid {' in s or 'watch_list {' in s or 'metric_type_list {' in s:
        return proto_text

    # Detect flat GetEntitiesWithMetrics output:
    #   entity_type: "vm"\nmetrics: [...]\nfilter: { ... }
    if api_method in ("GetEntitiesWithMetrics", "GetEntities"):
        api_method_out = "GetEntitiesWithMetrics"
        et_match = re.search(r'entity_type:\s*"([^"]+)"', s)
        if et_match:
            entity_type = et_match.group(1)
            # Extract columns/metrics
            columns = []
            metrics_match = re.search(r'metrics:\s*\[([^\]]*)\]', s)
            if metrics_match:
                columns = [c.strip().strip('"\'') for c in metrics_match.group(1).split(',') if c.strip()]
            metric_names_match = re.search(r'metric_names:\s*\[([^\]]*)\]', s)
            if metric_names_match:
                columns += [c.strip().strip('"\'') for c in metric_names_match.group(1).split(',') if c.strip()]
            # Extract filter
            filter_col = None
            filter_val = None
            filter_match = re.search(r'filter:\s*\{\s*"(\w+)":\s*"([^"]+)"', s)
            if filter_match:
                filter_col = filter_match.group(1)
                filter_val = filter_match.group(2)

            # Build proper proto
            proto = f'query {{\n  entity_list {{ entity_type_name: "{entity_type}" }}\n'
            if filter_col and filter_val:
                proto += f'  where_clause {{ comparison_expr {{ lhs {{ leaf {{ column: "{filter_col}" }} }} operator: kEQ rhs {{ leaf {{ value {{ str_value: "{filter_val}" }} }} }} }} }}\n'
            if columns:
                raw_cols = '\n    '.join(f'raw_columns {{ column: "{c}" }}' for c in columns)
                proto += f'  group_by {{\n    {raw_cols}\n  }}\n'
            proto += '  query_name: "auto_query"\n}'
            print(f"[Proto Gen] Reconstructed flat proto for {api_method_out}")
            return proto

    # Detect flat RegisterEntityTypes output
    if api_method == "RegisterEntityTypes":
        et_match = re.search(r'entity_types?:\s*"([^"]+)"', s)
        if et_match and 'message ' not in s[:20]:
            return f'entity_type_list {{ entity_type_name: "{et_match.group(1)}" }}'
        if 'message ' in s:
            et_match = re.search(r'entity_types?:\s*"([^"]+)"', s)
            if et_match:
                return f'entity_type_list {{ entity_type_name: "{et_match.group(1)}" }}'

    # Detect flat DeleteEntity output
    if api_method in ("DeleteEntity", "BatchDeleteEntities"):
        eid_match = re.search(r'entity_ids?:\s*"([^"]+)"', s)
        et_match = re.search(r'entity_type(?:_name)?:\s*"([^"]+)"', s)
        if eid_match:
            etype = et_match.group(1) if et_match else "vm"
            return f'entity_guid {{ entity_type_name: "{etype}" entity_id: "{eid_match.group(1)}" }}'

    return proto_text


def _override_api_from_query(query: str, detected_api: str) -> str:
    """Override LLM's API classification when query keywords strongly indicate a different intent."""
    ql = query.lower()

    # Force GetEntitiesWithMetrics for common read queries misclassified as SpotLightSearch
    if detected_api == "SpotLightSearch":
        if re.search(r'\b(alert|vm|disk|host|cluster|container|node|subnet|image|volume_group)\b', ql):
            if re.search(r'\b(get|list|show|find|fetch|recent|all|where|filter|sort)\b', ql):
                return "GetEntitiesWithMetrics"

    # GetEntitiesWithMetrics overrides - detect misclassification
    if detected_api == "GetEntitiesWithMetrics":
        if re.search(r'\b(lookup|by id|by guid|fetch entity with|specific\s+\w+\s+with\s+id|retrieve.*with\s+id|get entity\b.*\bid\b)', ql):
            return "GetEntities"
        if re.search(r'\b(audit trail|change history|entity trail|change log|modification history|changes\s+(?:were\s+)?made\s+to)\b', ql):
            return "GetEntitiesTrail"
        if re.search(r'\b(unregister|remove metric|remove attribute|delete metric type|delete attribute)\b', ql):
            return "UnregisterMetricTypes"
        if re.search(r'\b(batch delete|bulk delete|batch remove|bulk remove)\b', ql):
            return "BatchDeleteEntities"
        if re.search(r'\b(batch update|bulk update|batch set)\b', ql):
            return "BatchUpdateEntities"
        if re.search(r'\b(batch query|batch get|multiple queries|in one call|single batch|in a batch)\b', ql):
            return "BatchGetEntitiesWithMetrics"
        if re.search(r'\b(fire event|publish event|put event|create event)\b', ql):
            return "PutEvent"
        if re.search(r'\b(attach entity|attach.*incarnation)\b', ql):
            return "AttachEntity"
        if re.search(r'\b(detach entity|detach.*cluster)\b', ql):
            return "DetachEntity"
        if re.search(r'\b(subscribe|watch for|monitor\b.*\bchanges?|watch changes|watch.*entity type|notif\w+\s+when)\b', ql):
            return "Watch"
        if re.search(r'\b(register|create|define)\s+(?:a\s+)?(?:new\s+)?entity\s+type\b', ql):
            return "RegisterEntityTypes"
        if re.search(r'\b(full\s*text\s*search|text\s+search|spotlight|find\s+anything\s+related|search.*across\s+all)\b', ql):
            return "SpotLightSearch"
        if re.search(r'\bcreate\s+(?:a\s+)?(?:new\s+)?\w+\s+(?:named|called)\b', ql):
            if not re.search(r'\b(entity\s+type|metric|attribute)\b', ql):
                return "UpdateEntity"

    # GetMetricData overrides
    if detected_api == "GetMetricData":
        if re.search(r'\b(audit trail|change history|entity trail)\b', ql):
            return "GetEntitiesTrail"
        if re.search(r'\b(average|avg|sum|count|min|max|mean)\b.*\b(across|for|of)\b', ql):
            return "GetEntitiesWithMetrics"
        if re.search(r'\b(all\s+metrics|metrics\s+available|list\s+metrics|show\s+metrics|what\s+metrics)\b', ql):
            return "GetMetricTypes"
        if re.search(r'\b(get|fetch|show)\b.*\b(all|every)\b', ql):
            return "GetEntitiesWithMetrics"

    # GetEntities override - phi-4 often uses GetEntities instead of GetEntitiesWithMetrics
    if detected_api == "GetEntities":
        if not re.search(r'\b(lookup|by id|by guid|specific.*id|retrieve.*id)\b', ql):
            return "GetEntitiesWithMetrics"

    # BatchDeleteEntities override
    if detected_api == "BatchDeleteEntities":
        if not re.search(r'\b(batch|bulk|multiple)\b', ql):
            return "DeleteEntity"

    # PutMetricData overrides
    if detected_api == "PutMetricData":
        if re.search(r'\b(set|update|modify|change)\s+\w+\s+to\s+', ql):
            return "UpdateEntity"
        if re.search(r'\bsetting\s+\w+\s+to\s+', ql):
            return "UpdateEntity"
        if re.search(r'\bcas\s*(value|_value)?\s*', ql):
            return "UpdateEntity"
        if re.search(r'\bcreate\s+(?:a\s+)?(?:new\s+)?\w+\s+(?:named|called)\b', ql):
            return "UpdateEntity"

    # DeleteEntity overrides - "delete the watch" is Watch, not DeleteEntity
    if detected_api == "DeleteEntity":
        if re.search(r'\b(watch|unregister\s+watch|stop\s+watch|remove\s+watch|delete\s+.*watch)\b', ql):
            return "Watch"

    # UnregisterMetricTypes overrides - "unregister watch" is Watch, not UnregisterMetricTypes
    if detected_api == "UnregisterMetricTypes":
        if re.search(r'\b(watch|stop\s+watch|unregister\s+watch)\b', ql):
            return "Watch"

    # RegisterMetricTypes overrides - "create a vm named X" is UpdateEntity, not RegisterMetricTypes
    if detected_api == "RegisterMetricTypes":
        if re.search(r'\bcreate\s+(?:a\s+)?(?:new\s+)?\w+\s+(?:named|called|with\s+(?:name|id))\b', ql):
            if not re.search(r'\b(metric|attribute|register)\b', ql):
                return "UpdateEntity"
        if re.search(r'\b(update|modify|set)\s+', ql):
            return "UpdateEntity"

    # RegisterEntityTypes overrides - if user says "create a vm named X", that's UpdateEntity
    if detected_api == "RegisterEntityTypes":
        if re.search(r'\bcreate\s+(?:a\s+)?(?:new\s+)?\w+\s+(?:named|called|with\s+(?:name|id))\b', ql):
            if not re.search(r'\bentity\s+type\b', ql):
                return "UpdateEntity"

    # BatchUpdateEntities override when it's clearly a single entity
    if detected_api == "BatchUpdateEntities":
        if not re.search(r'\b(batch|bulk|multiple|all)\b', ql):
            return "UpdateEntity"

    # PutEvent overrides
    if detected_api == "PutEvent":
        if re.search(r'\b(notif\w+|subscribe|watch|monitor)\b', ql):
            return "Watch"

    # GetMasterLocation overrides (empty proto fallback)
    if detected_api == "GetMasterLocation":
        if re.search(r'\b(attribute|metric|column|field|schema|list|show|what)\b', ql):
            if re.search(r'\b(entity\s+type|for\s+\w+|of\s+\w+|does|have|available)\b', ql):
                return "GetMetricTypes"
        if re.search(r'\b(info|describe|schema|about)\b.*\b(entity|type)\b', ql):
            return "GetEntityTypes"

    # GetEntityTypes overrides
    if detected_api == "GetEntityTypes":
        if re.search(r'\b(fields?|columns?|metrics?|attributes?)\b', ql):
            if not re.search(r'\b(schema|describe|definition|info about)\b', ql):
                return "GetMetricTypes"

    # GetMetricTypes overrides
    if detected_api == "GetMetricTypes":
        if re.search(r'\b(schema|describe|definition)\b', ql) and not re.search(r'\b(fields?|columns?|metrics?|attributes?)\b', ql):
            return "GetEntityTypes"

    # RegisterMetricTypes overrides
    if detected_api == "RegisterMetricTypes":
        if re.search(r'\b(register|create|define)\s+(?:a\s+)?(?:new\s+)?entity\s+type\b', ql):
            return "RegisterEntityTypes"
        if re.search(r'\bentity\s+type\s+called\b', ql):
            return "RegisterEntityTypes"

    return detected_api


def _fix_update_entity_proto(s: str, original_query: str = "") -> str:
    """Restructure UpdateEntityArg proto so entity_guid and attribute_data_arg_list are top-level siblings."""
    # Strip update_entity_arg wrapper if present
    if re.search(r'^\s*update_entity_arg\s*\{', s):
        depth = 0
        start = s.find('{')
        for i in range(start, len(s)):
            if s[i] == '{':
                depth += 1
            elif s[i] == '}':
                depth -= 1
                if depth == 0:
                    s = s[start+1:i].strip()
                    break

    has_wrapper = ("entity_with_attribute_list" in s or
                   re.search(r'attribute_data_arg_list\s*\{\s*entity_guid', s) or
                   re.search(r'entity_list\s*\{\s*entity_guid', s))

    # Extract the key components regardless of nesting
    type_match = re.search(r'entity_type_name\s*:\s*"([^"]*)"', s)
    id_match = re.search(r'entity_id\s*:\s*"([^"]*)"', s)
    cas_match = re.search(r'cas_value\s*:\s*(\d+)', s)

    # Extract all attribute name/value pairs
    attr_pairs = []
    for m in re.finditer(r'name\s*:\s*"([^"]*)"', s):
        name = m.group(1)
        rest = s[m.end():]
        val_match = re.search(r'value\s*\{([^}]*)\}', rest)
        if val_match:
            attr_pairs.append((name, val_match.group(1).strip()))

    # If the proto doesn't have entity_guid at all (mismatched proto from wrong API classification),
    # try to generate it from the original query
    if not type_match or not id_match:
        if original_query:
            ql = original_query.lower()
            # Parse "update <type> with entity_id <id>" or "update <type> entity id <id>"
            update_eid = re.search(r'update\s+(\w+)\s+(?:with\s+)?entity[_\s]id\s+(\S+)', ql)
            # Parse "create a <type> named <id>" or "update <type> <id> setting..."
            create_m = re.search(r'create\s+(?:a\s+)?(?:new\s+)?(\w+)\s+(?:named|called)\s+(\S+)', ql)
            update_m = re.search(r'update\s+(\w+)\s+(\S+)\s+setting', ql)
            qm = update_eid or create_m or update_m
            if qm:
                entity_type = qm.group(1)
                entity_id = qm.group(2)
                # Use existing cas_value if found in proto, else 0
                cas_val = cas_match.group(1) if cas_match else "0"
                new_proto = f'entity_guid {{\n  entity_type_name: "{entity_type}"\n  entity_id: "{entity_id}"\n}}\ncas_value: {cas_val}'
                # For create, set <type>_name attribute
                if create_m and not update_eid:
                    new_proto += f'\nattribute_data_arg_list {{\n  attribute_data {{\n    name: "{entity_type}_name"\n    value {{ str_value: "{entity_id}" }}\n  }}\n}}'
                elif attr_pairs:
                    for attr_name, attr_val in attr_pairs:
                        new_proto += f'\nattribute_data_arg_list {{\n  attribute_data {{\n    name: "{attr_name}"\n    value {{ {attr_val} }}\n  }}\n}}'
                else:
                    setting_m = re.search(r'set(?:ting)?\s+(?:attribute\s+)?(\w+)\s+to\s+(\S+)', original_query, re.IGNORECASE)
                    if setting_m:
                        attr_name = setting_m.group(1)
                        attr_val_raw = setting_m.group(2)
                        try:
                            int_val = int(attr_val_raw)
                            val_str = f"uint64_value: {int_val}"
                        except ValueError:
                            val_str = f'str_value: "{attr_val_raw}"'
                        new_proto += f'\nattribute_data_arg_list {{\n  attribute_data {{\n    name: "{attr_name}"\n    value {{ {val_str} }}\n  }}\n}}'
                return new_proto
            # Fallback: if we have id_match but not type_match, extract type from query
            if id_match and not type_match:
                known_types = ['vm', 'node', 'disk', 'cluster', 'container', 'alert', 'task', 'host']
                entity_type = 'vm'
                for kt in known_types:
                    if kt in ql:
                        entity_type = kt
                        break
                entity_id = id_match.group(1)
                cas_val = cas_match.group(1) if cas_match else "0"
                new_proto = f'entity_guid {{\n  entity_type_name: "{entity_type}"\n  entity_id: "{entity_id}"\n}}\ncas_value: {cas_val}'
                for attr_name, attr_val in attr_pairs:
                    new_proto += f'\nattribute_data_arg_list {{\n  attribute_data {{\n    name: "{attr_name}"\n    value {{ {attr_val} }}\n  }}\n}}'
                if not attr_pairs:
                    setting_m = re.search(r'set(?:ting)?\s+(?:attribute\s+)?(\w+)\s+to\s+(\S+)', original_query, re.IGNORECASE)
                    if setting_m:
                        attr_name = setting_m.group(1)
                        attr_val_raw = setting_m.group(2)
                        try:
                            int_val = int(attr_val_raw)
                            val_str = f"uint64_value: {int_val}"
                        except ValueError:
                            val_str = f'str_value: "{attr_val_raw}"'
                        new_proto += f'\nattribute_data_arg_list {{\n  attribute_data {{\n    name: "{attr_name}"\n    value {{ {val_str} }}\n  }}\n}}'
                return new_proto
        return s

    if has_wrapper:
        entity_type = type_match.group(1)
        entity_id = id_match.group(1)
        new_proto = f'entity_guid {{\n  entity_type_name: "{entity_type}"\n  entity_id: "{entity_id}"\n}}'
        if cas_match:
            new_proto += f"\ncas_value: {cas_match.group(1)}"
        else:
            new_proto += "\ncas_value: 0"
        for attr_name, attr_val in attr_pairs:
            new_proto += f"\nattribute_data_arg_list {{\n  attribute_data {{\n    name: \"{attr_name}\"\n    value {{ {attr_val} }}\n  }}\n}}"
        if not attr_pairs:
            new_proto += '\nattribute_data_arg_list {\n  attribute_data {\n    name: ""\n    value { str_value: "" }\n  }\n}'
        return new_proto

    # Check if entity_guid is already at top level - if so, structure is fine
    if re.match(r'\s*entity_guid\s*\{', s):
        # Simple fixes for already-correct structure
        s = s.replace("entity_with_attribute_list", "attribute_data_arg_list")
        s = s.replace("attribute_updates", "attribute_data_arg_list")
        if re.search(r'\battribute_list\s*\{', s) and "attribute_data_arg_list" not in s:
            s = re.sub(r'\battribute_list\b', 'attribute_data_arg_list', s)
        # Fix bare "attribute_data {" without "attribute_data_arg_list" wrapper
        if "attribute_data_arg_list" not in s and re.search(r'\battribute_data\s*\{', s):
            s = re.sub(r'\battribute_data\s*\{', 'attribute_data_arg_list {\n  attribute_data {', s)
            # Add closing brace for the new wrapper
            last_brace = s.rfind('}')
            if last_brace != -1:
                s = s[:last_brace+1] + '\n}'
        # Fix bare "attribute {" without proper wrapper
        if "attribute_data_arg_list" not in s and re.search(r'\battribute\s*\{', s):
            s = re.sub(r'\battribute\s*\{', 'attribute_data_arg_list {\n  attribute_data {', s)
            last_brace = s.rfind('}')
            if last_brace != -1:
                s = s[:last_brace+1] + '\n}'
        if "attribute_data_arg_list" in s and "attribute_data {" not in s:
            s = re.sub(
                r'attribute_data_arg_list\s*\{\s*name:',
                'attribute_data_arg_list {\n  attribute_data {\n    name:',
                s
            )
        # Fix string_value -> str_value
        s = s.replace('string_value:', 'str_value:')
        return s

    # Proto has entity info but wrong structure - rebuild
    entity_type = type_match.group(1)
    entity_id = id_match.group(1)
    new_proto = f'entity_guid {{\n  entity_type_name: "{entity_type}"\n  entity_id: "{entity_id}"\n}}'
    if cas_match:
        new_proto += f"\ncas_value: {cas_match.group(1)}"
    else:
        new_proto += "\ncas_value: 0"
    for attr_name, attr_val in attr_pairs:
        new_proto += f"\nattribute_data_arg_list {{\n  attribute_data {{\n    name: \"{attr_name}\"\n    value {{ {attr_val} }}\n  }}\n}}"
    if not attr_pairs and original_query:
        # Try to extract attribute from query "setting X to Y"
        setting_m = re.search(r'setting\s+(\w+)\s+to\s+(\S+)', original_query, re.IGNORECASE)
        if setting_m:
            attr_name = setting_m.group(1)
            attr_val_raw = setting_m.group(2)
            try:
                int_val = int(attr_val_raw)
                val_str = f"uint64_value: {int_val}"
            except ValueError:
                val_str = f'str_value: "{attr_val_raw}"'
            new_proto += f'\nattribute_data_arg_list {{\n  attribute_data {{\n    name: "{attr_name}"\n    value {{ {val_str} }}\n  }}\n}}'
    return new_proto


def _normalize_other_proto(proto_text: str, api_method: str, original_query: str = "") -> str:
    """Post-process non-GetEntitiesWithMetrics protos to fix common issues."""
    s = proto_text.strip()
    ql = original_query.lower()

    # Fix common LLM field name mistakes for UpdateEntity
    if api_method == "UpdateEntity":
        s = _fix_update_entity_proto(s, original_query)

    # Fix DeleteEntity proto structure - model often outputs flat "entity_guid: ID" instead of nested message
    if api_method == "DeleteEntity":
        if "entity_guid {" not in s and "entity_guid{" not in s:
            entity_type = re.search(r'entity_type_name\s*:\s*"([^"]+)"', s)
            entity_id = re.search(r'entity_id\s*:\s*"([^"]+)"', s)
            # Model might output entity_guid: "id" as a scalar
            guid_scalar = re.search(r'entity_guid\s*:\s*"([^"]+)"', s)
            if not entity_id and guid_scalar:
                entity_id = guid_scalar
            if not entity_id and ql:
                id_m = re.search(r'(?:id|entity[_\s]id|named?)\s+(\S+)', ql)
                if id_m:
                    entity_id = type('M', (), {'group': lambda self, n: id_m.group(1).strip('"\'')})()
            if not entity_type and ql:
                known_types = ['vm', 'node', 'disk', 'cluster', 'container', 'alert', 'task']
                for kt in known_types:
                    if kt in ql:
                        entity_type = type('M', (), {'group': lambda self, n: kt})()
                        break
            if entity_id:
                et = entity_type.group(1) if entity_type else "vm"
                eid = entity_id.group(1)
                s = (
                    f'entity_guid {{\n'
                    f'  entity_type_name: "{et}"\n'
                    f'  entity_id: "{eid}"\n'
                    f'}}'
                )

    # Fix common LLM field name mistakes for BatchUpdateEntities
    if api_method == "BatchUpdateEntities":
        s = s.replace("entity_with_attribute_list", "attribute_data_arg_list")

    if api_method == "BatchDeleteEntities":
        if "entity_list" not in s and "entity_guid" not in s:
            entity_type = re.search(r'entity_type_name?\s*:\s*"?(\w[\w-]*)"?', s)
            # Handle both separate lines and space-separated IDs
            ids = re.findall(r'entity_id(?:_list)?\s*:\s*"([^"]+)"', s)
            if not ids:
                id_line = re.search(r'entity_id(?:_list)?\s*:\s*"?(.+)', s)
                if id_line:
                    ids = re.findall(r'"([^"]+)"', id_line.group(1))
                    if not ids:
                        ids = id_line.group(1).strip().split()
            if entity_type and ids:
                et = entity_type.group(1)
                parts = []
                for eid in ids:
                    eid = eid.strip('"')
                    parts.append(
                        f'entity_list {{\n'
                        f'  entity_guid {{\n'
                        f'    entity_type_name: "{et}"\n'
                        f'    entity_id: "{eid}"\n'
                        f'  }}\n'
                        f'}}'
                    )
                s = '\n'.join(parts)

    elif api_method == "BatchGetEntitiesWithMetrics":
        # Model might output multiple query{} blocks without query_list wrapper
        if "query_list" not in s:
            # Find all entity_type_name values to build proper query_list
            entity_types = re.findall(r'entity_type_name:\s*"([^"]+)"', s)
            if len(entity_types) >= 2:
                parts = []
                for et in entity_types:
                    parts.append(
                        f'query_list {{\n'
                        f'  query {{\n'
                        f'    entity_list {{ entity_type_name: "{et}" }}\n'
                        f'    group_by {{ raw_columns {{ column: "_entity_summary_" }} }}\n'
                        f'    query_name: "batch_{et}"\n'
                        f'  }}\n'
                        f'}}'
                    )
                s = '\n'.join(parts)
            elif entity_types:
                # Single entity - wrap in query_list
                s = (
                    f'query_list {{\n'
                    f'  query {{\n'
                    f'    entity_list {{ entity_type_name: "{entity_types[0]}" }}\n'
                    f'    group_by {{ raw_columns {{ column: "_entity_summary_" }} }}\n'
                    f'    query_name: "batch_{entity_types[0]}"\n'
                    f'  }}\n'
                    f'}}'
                )
            elif ql:
                # Extract from query text
                types_from_query = re.findall(r'\b(vm|node|disk|cluster|container|alert|task|host)s?\b', ql)
                unique_types = list(dict.fromkeys(types_from_query))
                if unique_types:
                    parts = []
                    for et in unique_types:
                        if et == 'host':
                            et = 'node'
                        parts.append(
                            f'query_list {{\n'
                            f'  query {{\n'
                            f'    entity_list {{ entity_type_name: "{et}" }}\n'
                            f'    group_by {{ raw_columns {{ column: "_entity_summary_" }} }}\n'
                            f'    query_name: "batch_{et}"\n'
                            f'  }}\n'
                            f'}}'
                        )
                    s = '\n'.join(parts)

    elif api_method == "GetEntities":
        if "entity_guid_list" not in s:
            entity_type = re.search(r'entity_type(?:_name)?\s*:\s*"([^"]+)"', s)
            entity_id = re.search(r'entity_id(?:_list)?\s*:\s*"([^"]+)"', s)
            if entity_type and entity_id:
                s = (
                    f'entity_guid_list {{\n'
                    f'  entity_type_name: "{entity_type.group(1)}"\n'
                    f'  entity_id: "{entity_id.group(1)}"\n'
                    f'}}'
                )

    elif api_method == "GetEntitiesTrail":
        if "entity_guid_list" not in s:
            entity_type = re.search(r'entity_type(?:_name)?\s*:\s*"([^"]+)"', s)
            entity_id = re.search(r'entity_id\s*:\s*"([^"]+)"', s)
            if entity_type and entity_id:
                s = (
                    f'entity_guid_list {{\n'
                    f'  entity_type_name: "{entity_type.group(1)}"\n'
                    f'  entity_id: "{entity_id.group(1)}"\n'
                    f'}}'
                )

    elif api_method == "GetEntityTypes":
        if not s and ql:
            known_types = ['vm', 'node', 'disk', 'cluster', 'container', 'alert', 'task']
            for kt in known_types:
                if kt in ql:
                    s = f'entity_type_name: "{kt}"'
                    break

    elif api_method == "GetMetricTypes":
        if "regex" not in s:
            entity_type = re.search(r'entity_type_name\s*:\s*"([^"]+)"', s)
            if entity_type:
                s = f'regex: ".*:{entity_type.group(1)}"'
            else:
                known_types = ['vm', 'node', 'disk', 'cluster', 'container', 'alert', 'task']
                found_type = None
                for kt in known_types:
                    if kt in ql:
                        found_type = kt
                        break
                if found_type:
                    s = f'regex: ".*:{found_type}"'
                else:
                    s = 'regex: ".*"'

    elif api_method == "Watch":
        # Extract entity type from QUERY first (priority), then fall back to proto
        known_types = ['vm', 'node', 'disk', 'cluster', 'container', 'alert', 'task', 'event']
        et = None
        for kt in known_types:
            if kt in ql or kt + 's' in ql:
                et = kt
                break
        if not et:
            entity_type = re.search(r'entity_type(?:_name)?\s*:\s*"([^"]+)"', s)
            et = entity_type.group(1) if entity_type else "vm"
        if "watch_list" not in s and "client_id" not in s:
            s = (
                f'client_id: "idf_watch_client"\n'
                f'session_id: "session_001"\n'
                f'watch_list {{\n'
                f'  watch_name: "watch_{et}_all"\n'
                f'  entity_type_name: "{et}"\n'
                f'  watch_type_mask: 7\n'
                f'}}'
            )
        else:
            # Fix entity type if the proto has a different one than what the query specifies
            proto_et = re.search(r'entity_type_name:\s*"([^"]+)"', s)
            if proto_et and proto_et.group(1) != et:
                s = s.replace(proto_et.group(1), et)
                s = re.sub(r'watch_name:\s*"[^"]*"', f'watch_name: "watch_{et}_all"', s)

    elif api_method == "RegisterMetricTypes":
        # Fix "name:" → "metric_name:" (common LLM mistake)
        s = re.sub(r'\bname\s*:', 'metric_name:', s)
        # Fix "data_type: INT64" → proper enum; also handle lowercase
        s = re.sub(r'data_type\s*:\s*"?int64"?', 'data_type: kInt64', s, flags=re.IGNORECASE)
        s = re.sub(r'data_type\s*:\s*"?INT64"?', 'data_type: kInt64', s)
        s = re.sub(r'data_type\s*:\s*"?string"?', 'data_type: kString', s, flags=re.IGNORECASE)
        s = re.sub(r'data_type\s*:\s*"?float"?', 'data_type: kFloat64', s, flags=re.IGNORECASE)
        s = re.sub(r'data_type\s*:\s*"?double"?', 'data_type: kFloat64', s, flags=re.IGNORECASE)
        s = re.sub(r'data_type\s*:\s*"?bool(?:ean)?"?', 'data_type: kBoolean', s, flags=re.IGNORECASE)

        # Add is_attribute: true if query says "attribute" and it's missing from proto
        is_attr = 'attribute' in ql
        if is_attr and "is_attribute" not in s:
            s = re.sub(r'(metric_type_list\s*\{)', r'\1\n  is_attribute: true', s)

        if "metric_type_list" not in s:
            metric_name = re.search(r'metric_name\s*:\s*"([^"]+)"', s)
            entity_type = re.search(r'entity_type_name\s*:\s*"([^"]+)"', s)
            if not metric_name and ql:
                m = re.search(r'(?:register|add)\s+(?:metric|attribute)\s+(\w[\w_-]*)', ql)
                if m:
                    metric_name = type('M', (), {'group': lambda self, n: m.group(1)})()
            if not entity_type and ql:
                et_match = re.search(r'(?:for|on|to)\s+(?:entity\s+type\s+)?(\w[\w_-]*)', ql)
                if et_match:
                    entity_type = type('M', (), {'group': lambda self, n: et_match.group(1)})()
            mn = metric_name.group(1) if metric_name else "unknown"
            et = entity_type.group(1) if entity_type else "vm"
            s = (
                f'metric_type_list {{\n'
                f'  is_attribute: {"true" if is_attr else "false"}\n'
                f'  metric_name: "{mn}"\n'
                f'  entity_type_name: "{et}"\n'
                f'}}'
            )

    elif api_method == "RegisterEntityTypes":
        if "entity_type_info_list" not in s:
            # Try to extract from original query first (more reliable than proto content)
            et = None
            parent_name = "node"
            if ql:
                q_match = re.search(r'(?:register|create|define)\s+(?:a\s+)?(?:new\s+)?entity\s+type\s+(?:called|named)\s+(\w[\w_-]*)', ql)
                if q_match:
                    et = q_match.group(1)
                p_match = re.search(r'(?:with\s+)?parent\s+(\w[\w_-]*)', ql)
                if p_match:
                    parent_name = p_match.group(1)
            if not et:
                entity_type = re.search(r'entity_type_name\s*:\s*"([^"]+)"', s)
                if entity_type:
                    et = entity_type.group(1)
            parent_from_proto = re.search(r'parent(?:_list)?\s*:\s*"([^"]+)"', s)
            if parent_from_proto:
                parent_name = parent_from_proto.group(1)
            if et:
                s = (
                    f'entity_type_info_list {{\n'
                    f'  entity_type_name: "{et}"\n'
                    f'  type_info {{\n'
                    f'    parent_list: "{parent_name}"\n'
                    f'  }}\n'
                    f'}}'
                )

    return s


def _normalize_get_entities_proto(proto_text: str, original_query: str = "") -> str:
    """Post-process GetEntitiesWithMetrics proto to fix common LLM formatting errors."""
    s = proto_text.strip()

    # Fix malformed output where entity_type_name/metric_name appear at root before query {}
    if re.match(r'^entity_type_name:', s) or re.match(r'^metric_name:', s):
        query_block = re.search(r'(query\s*\{.*)', s, re.DOTALL)
        if query_block:
            s = query_block.group(1)
        else:
            et = re.search(r'entity_type_name:\s*"([^"]+)"', s)
            metrics = re.findall(r'metric_name:\s*"([^"]+)"', s)
            entity_type = et.group(1) if et else "vm"
            cols = '\n    '.join(f'raw_columns {{ column: "{m}" }}' for m in metrics) if metrics else ''
            ql = original_query.lower()
            where = ''
            filter_match = re.search(r'where\s+(\w+)\s+(?:is|=|equals?)\s+(\w+)', ql, re.IGNORECASE)
            if filter_match:
                col = filter_match.group(1)
                val = filter_match.group(2)
                where = f'''  where_clause {{
    comparison_expr {{
      lhs {{ leaf {{ column: "{col}" }} }}
      operator: kEQ
      rhs {{ leaf {{ value {{ str_value: "{val}" }} }} }}
    }}
  }}
'''
            s = f'query {{\n  entity_list {{ entity_type_name: "{entity_type}" }}\n{where}  group_by {{\n    {cols}\n  }}\n  query_name: "auto_query"\n}}'

    # Fix QueryOrderBy field names: LLM generates "column:"/"order:" instead of
    # the correct "sort_column:"/"sort_order:" within raw_sort_order blocks.
    def _fix_sort_order_fields(m):
        block = m.group(0)
        block = re.sub(r'\bcolumn\s*:', 'sort_column:', block)
        block = re.sub(r'(?<!\bsort_)\border\s*:', 'sort_order:', block)
        return block
    s = re.sub(r'raw_sort_order\s*\{[^}]*\}', _fix_sort_order_fields, s, flags=re.DOTALL)
    s = re.sub(r'group_sort_order\s*\{[^}]*\}', _fix_sort_order_fields, s, flags=re.DOTALL)

    # Fix power_state case: IDF stores lowercase ("on", "off") but LLM often generates uppercase
    def _fix_power_state_case(m):
        val = m.group(1)
        if val.upper() in ("ON", "OFF", "PAUSED", "SUSPENDED"):
            return f'str_value: "{val.lower()}"'
        return m.group(0)
    if 'power_state' in s:
        s = re.sub(r'str_value:\s*"(ON|OFF|PAUSED|SUSPENDED)"', _fix_power_state_case, s, flags=re.IGNORECASE)

    # Fix nested group_by blocks: LLM sometimes generates
    #   group_by { raw_columns { column: "a" } group_by { raw_columns { column: "b" } ... } }
    # Should be a single group_by with multiple raw_columns entries.
    # Fix column_list (wrong field) -> group_by { raw_columns { ... } }
    col_list_cols = re.findall(r'column_list\s*\{\s*column:\s*"([^"]+)"\s*\}', s)
    if col_list_cols:
        s = re.sub(r'\s*column_list\s*\{[^}]*\}', '', s)
        raw_cols = '\n    '.join(f'raw_columns {{ column: "{c}" }}' for c in col_list_cols)
        if 'group_by' not in s:
            s = re.sub(r'(entity_list\s*\{[^}]*\}\s*\n)', f'\\1  group_by {{\n    {raw_cols}\n  }}\n', s, count=1)
        else:
            for c in col_list_cols:
                s = re.sub(r'(group_by\s*\{)', f'\\1\n    raw_columns {{ column: "{c}" }}', s, count=1)

    # Fix metric_name_list: "X" (flat repeated field) -> single group_by with raw_columns
    metric_cols = re.findall(r'metric_name_list:\s*"([^"]+)"', s)
    if metric_cols and 'group_by' not in s:
        s = re.sub(r'\s*metric_name_list:\s*"[^"]+"', '', s)
        raw_cols = '\n    '.join(f'raw_columns {{ column: "{c}" }}' for c in metric_cols)
        s = re.sub(r'(entity_list\s*\{[^}]*\}\s*\n)', f'\\1  group_by {{\n    {raw_cols}\n  }}\n', s, count=1)

    # Normalize raw_columns field name: LLM generates "name:" instead of "column:"
    def _fix_raw_col_name(m):
        block = m.group(0)
        block = re.sub(r'\bname\s*:', 'column:', block)
        return block
    s = re.sub(r'raw_columns\s*\{[^}]*\}', _fix_raw_col_name, s, flags=re.DOTALL)

    # Fix nested group_by blocks
    gb_count = s.count('group_by')
    if gb_count > 1:
        columns = re.findall(r'raw_columns\s*\{[^}]*?(?:column|name)\s*:\s*"([^"]+)"\s*\}', s)
        if not columns:
            columns = re.findall(r'(?:column|name)\s*:\s*"([^"]+)"', s)
        if columns:
            first_gb = s.find('group_by')
            if first_gb != -1:
                before_gb = s[:first_gb].rstrip()
                query_name_match = re.search(r'query_name:\s*"([^"]*)"', s)
                qn = query_name_match.group(1) if query_name_match else "auto_query"
                # Preserve where_clause if present
                where_match = re.search(r'(where_clause\s*\{.*?\}\s*\})', s, re.DOTALL)
                limit_match = re.search(r'raw_limit\s*\{[^}]*\}', s)
                sort_match = re.search(r'raw_sort_order\s*\{[^}]*\}', s)
                raw_cols = '\n    '.join(f'raw_columns {{ column: "{c}" }}' for c in columns)
                new_gb = f'  group_by {{\n    {raw_cols}\n'
                if sort_match:
                    new_gb += f'    {sort_match.group(0)}\n'
                if limit_match:
                    new_gb += f'    {limit_match.group(0)}\n'
                new_gb += '  }'
                result = f'{before_gb}\n'
                if where_match:
                    result += f'  {where_match.group(1)}\n'
                result += f'{new_gb}\n  query_name: "{qn}"\n}}'
                s = result

    # Convert where_clause filtering on "name" (or identity-like columns) with kEQ to entity_id.
    # In IDF, "name" is typically the entity_id itself, not a stored attribute column.
    name_filter = re.search(
        r'column:\s*"name"[\s\S]*?operator:\s*kEQ[\s\S]*?str_value:\s*"([^"]*)"',
        s
    )
    # Also detect when the query is "fetch/get X details for <specific_id>" or "get details of X named Y"
    if not name_filter and original_query:
        fetch_id_match = re.search(
            r'\b(?:fetch|get|show|find)\b.*\b(?:details?|info)\b.*\b(?:for|of|named)\s+(\S+)',
            original_query, re.IGNORECASE
        )
        if not fetch_id_match:
            fetch_id_match = re.search(
                r'\b(?:fetch|get|show|find)\b.*\bnamed\s+(\S+)',
                original_query, re.IGNORECASE
            )
        if not fetch_id_match:
            fetch_id_match = re.search(
                r'\b(?:details?|info)\b.*\b(?:for|of)\s+\w+\s+(\S+)',
                original_query, re.IGNORECASE
            )
        if fetch_id_match:
            target_id = fetch_id_match.group(1).strip('"\'')
            # Trigger if:
            # - proto has this value in where_clause
            # - target_id is missing from proto entirely
            # - target_id is in a flat entity_id field (not inside entity_list { })
            flat_id = re.search(r'^\s*entity_id:\s*"' + re.escape(target_id) + r'"', s, re.MULTILINE)
            if re.search(r'str_value:\s*"' + re.escape(target_id) + r'"', s) or target_id not in s or (flat_id and 'entity_list' not in s):
                name_filter = type('Match', (), {'group': lambda self, n: target_id})()
    
    if name_filter:
        entity_name_val = name_filter.group(1)
        # Extract entity_type_name - prefer from original query if available
        entity_type = None
        if original_query:
            # Try "get <type> details/info" pattern
            et_from_query = re.search(
                r'\b(?:fetch|get|show|find)\s+(\w+)\s+(?:details?|info)',
                original_query, re.IGNORECASE
            )
            if et_from_query and et_from_query.group(1).lower() not in ('the', 'all', 'details', 'some'):
                entity_type = et_from_query.group(1).lower()
            # Try "details of <type>" or "info for <type>"
            if not entity_type:
                et_alt = re.search(r'\b(?:details?|info)\s+(?:of|for)\s+(\w+)', original_query, re.IGNORECASE)
                if et_alt and et_alt.group(1).lower() not in ('the', 'a', 'an'):
                    entity_type = et_alt.group(1).lower()
        if not entity_type:
            etype = re.search(r'entity_type_name:\s*"([^"]*)"', s)
            entity_type = etype.group(1) if etype else "vm"
        # Extract query_name if present
        qname = re.search(r'query_name:\s*"([^"]*)"', s)
        # Extract group_by block if present (for columns, sorting, etc.)
        group_by_content = ""
        gb_start = s.find("group_by")
        if gb_start != -1:
            gb_brace = s.find("{", gb_start)
            if gb_brace != -1:
                depth = 0
                for i in range(gb_brace, len(s)):
                    if s[i] == '{':
                        depth += 1
                    elif s[i] == '}':
                        depth -= 1
                        if depth == 0:
                            group_by_content = s[gb_start:i+1]
                            break
        # Rebuild proto with entity_id instead of where_clause
        query_name = qname.group(1) if qname else "auto_query"
        s = f'query {{\n  entity_list {{\n    entity_type_name: "{entity_type}"\n    entity_id: "{entity_name_val}"\n  }}'
        if group_by_content:
            s += f"\n  {group_by_content}"
        s += f'\n  query_name: "{query_name}"\n}}'

    # Fix wrong entity type names
    _ENTITY_MAP = {
        'host': 'node', 'hosts': 'node', 'server': 'node', 'servers': 'node',
        'storage_container': 'container', 'storage_containers': 'container',
        'containers': 'container', 'storage_vdisk': 'container',
        'category_counts': 'node',
    }
    for wrong, right in _ENTITY_MAP.items():
        s = re.sub(rf'entity_type_name:\s*"{wrong}"', f'entity_type_name: "{right}"', s)

    # Fix entity_id_list → entity_id inside entity_list (LLM confusion with GetMetricData field)
    s = re.sub(r'\bentity_id_list:\s*"([^"]*)"', r'entity_id: "\1"', s)

    # Fix operator names everywhere in the text
    s = re.sub(r'\boperator:\s*GT\b', 'operator: kGT', s)
    s = re.sub(r'\boperator:\s*LT\b', 'operator: kLT', s)
    s = re.sub(r'\boperator:\s*GE\b', 'operator: kGE', s)
    s = re.sub(r'\boperator:\s*LE\b', 'operator: kLE', s)
    s = re.sub(r'\boperator:\s*EQ\b', 'operator: kEQ', s)
    s = re.sub(r'\boperator:\s*NE\b', 'operator: kNE', s)
    s = re.sub(r'\boperator:\s*EQUALS\b', 'operator: kEQ', s)
    s = re.sub(r'\boperator:\s*GREATER_THAN\b', 'operator: kGT', s)
    s = re.sub(r'\boperator:\s*LESS_THAN\b', 'operator: kLT', s)
    s = re.sub(r'\boperator:\s*LIKE\b', 'operator: kLike', s)
    s = re.sub(r'\boperator:\s*CONTAINS\b', 'operator: kLike', s)
    s = re.sub(r'\boperator:\s*kEqual\b', 'operator: kEQ', s)
    s = re.sub(r'\boperator:\s*kContains\b', 'operator: kLike', s)
    s = re.sub(r'\border:\s*DESCENDING\b', 'order: kDescending', s)
    s = re.sub(r'\border:\s*ASCENDING\b', 'order: kAscending', s)
    s = re.sub(r'\border:\s*DESC\b', 'order: kDescending', s)
    s = re.sub(r'\border:\s*ASC\b', 'order: kAscending', s)

    # Fix verbose/wrong operator names
    s = re.sub(r'\boperator:\s*(?:GREATER_THAN_OR_EQUAL|kGreaterThanOrEqual(?:To)?|kGTE|GTE|GEQ)\b', 'operator: kGE', s)
    s = re.sub(r'\boperator:\s*(?:LESS_THAN_OR_EQUAL|kLessThanOrEqual(?:To)?|kLTE|LTE|LEQ)\b', 'operator: kLE', s)
    s = re.sub(r'\boperator:\s*(?:NOT_EQUAL|kNotEqual|NEQ)\b', 'operator: kNE', s)
    s = re.sub(r'\boperator:\s*(?:kGreaterThan|GREATER_THAN)\b', 'operator: kGT', s)
    s = re.sub(r'\boperator:\s*(?:kLessThan|LESS_THAN)\b', 'operator: kLT', s)
    s = re.sub(r'\boperator:\s*(?:kEqualTo|EQUAL|EQUALS)\b', 'operator: kEQ', s)
    s = re.sub(r'\boperator:\s*(?:EXISTS|kExist)\b', 'operator: kExists', s)
    s = re.sub(r'\boperator:\s*\bIN\b', 'operator: kIN', s)

    # Fix attribute_list -> collect into a single group_by with raw_columns
    # Handles both attribute_name: "X" and name: "X" inside attribute_list blocks
    attr_cols = re.findall(r'attribute_list\s*\{\s*(?:attribute_name|name)\s*:\s*"([^"]+)"\s*\}', s)
    if attr_cols:
        s = re.sub(r'\s*attribute_list\s*\{[^}]*\}', '', s)
        raw_cols_str = '\n    '.join(f'raw_columns {{ column: "{c}" }}' for c in attr_cols)
        if 'group_by' not in s:
            s = re.sub(r'(entity_list\s*\{[^}]*\}\s*\n)', f'\\1  group_by {{\n    {raw_cols_str}\n  }}\n', s, count=1)
        else:
            s = re.sub(r'(group_by\s*\{)', f'\\1\n    {raw_cols_str}', s, count=1)

    # Fix "exists" filter: model may generate where_clause { attribute { name: "X" } } instead of proper kExists
    exists_match = re.search(r'where_clause\s*\{\s*attribute\s*\{\s*name:\s*"([^"]+)"', s)
    if exists_match and 'kExists' not in s and original_query and 'exists' in original_query.lower():
        col = exists_match.group(1)
        where_str = f'where_clause {{ comparison_expr {{ lhs {{ leaf {{ column: "{col}" }} }} operator: kExists }} }}'
        s = re.sub(r'where_clause\s*\{[^}]*attribute[^}]*\{[^}]*\}[^}]*\}', where_str, s, flags=re.DOTALL)

    # Fix comparison_operator: X → operator: X
    def _fix_comp_op(m):
        op = m.group(1)
        return f'operator: {_normalize_operator(op)}'
    s = re.sub(r'\bcomparison_operator:\s*"?(\w+)"?', _fix_comp_op, s)

    # FIRST: detect string_match/match_any/pattern (kLike) BEFORE generic filter
    pattern_match = re.search(r'(?:field_name|column)\s*:\s*"([^"]+)".*?pattern\s*:\s*"([^"]+)"', s, re.DOTALL)
    if pattern_match and 'where_clause' not in s:
        col = pattern_match.group(1)
        pattern = pattern_match.group(2)
        where_str = _build_where_clause(col, 'kLike', 'str_value', f'"{pattern}"')
        entity_match = re.search(r'entity_type_name\s*:\s*"([^"]+)"', s)
        entity_type = entity_match.group(1) if entity_match else 'vm'
        s = (
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{entity_type}" }}\n'
            f'  {where_str}\n'
            f'  group_by {{ raw_columns {{ column: "{col}" }} }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        return s

    # Detect and replace attribute_filter blocks (multi-line)
    if 'where_clause' not in s:
        col, op, val_type, val = _extract_filter_fields(s, 'attribute_filter')
        if col:
            where_str = _build_where_clause(col, op, val_type, val)
            s = _replace_block(s, 'attribute_filter', where_str)

    # Detect and replace filter blocks
    if 'where_clause' not in s:
        col, op, val_type, val = _extract_filter_fields(s, 'filter')
        if col:
            where_str = _build_where_clause(col, op, val_type, val)
            s = _replace_block(s, 'filter', where_str)

    # Ensure query { } wrapper
    if "query {" not in s and "query{" not in s:
        entity_match = re.search(r'entity_type_name\s*:\s*"([^"]+)"', s)
        if entity_match:
            entity_type = entity_match.group(1)
            where_in_s = ""
            if "where_clause" in s:
                wc_match = re.search(r'(where_clause\s*\{.*?\}\s*\})', s, re.DOTALL)
                if wc_match:
                    where_in_s = f'  {wc_match.group(1)}\n'
            s = (
                f'query {{\n'
                f'  entity_list {{ entity_type_name: "{entity_type}" }}\n'
                f'{where_in_s}'
                f'  group_by {{ raw_columns {{ column: "_entity_id_" }} }}\n'
                f'  query_name: "auto_query"\n'
                f'}}'
            )

    # Ensure query_name exists
    if "query_name" not in s and "query {" in s:
        s = re.sub(r'(\n\})\s*$', '\n  query_name: "auto_query"\n}', s)

    ql = original_query.lower()

    # If original query says "contains"/"matching"/"like" and proto uses wrong operator, fix to kLike
    if re.search(r'\b(contains|matching|like|matches)\b', ql) and 'kLike' not in s and 'where_clause' in s:
        col_match = re.search(r'column:\s*"([^"]+)"', s)
        if col_match:
            col = col_match.group(1)
            val_match = re.search(r'(?:str_value|uint64_value|int64_value):\s*"?([^"}\s]+)"?', s)
            val = val_match.group(1) if val_match else ''
            if val and not val.startswith('.*'):
                val = f'.*{val}.*'
            s = re.sub(r'operator:\s*\w+', 'operator: kLike', s, count=1)
            if val:
                s = re.sub(r'(value\s*\{)\s*(?:str_value|uint64_value):\s*"?[^"}\s]+"?\s*',
                          f'\\1 str_value: "{val}" ', s, count=1)

    # If query mentions sorting/ascending/descending/top and proto has raw_limit but no raw_sort_order
    sort_match = re.search(r'\b(?:sort(?:ed)?|order(?:ed)?|top|ascending|descending)\s+(?:by\s+)?(\w+)', ql)
    if not sort_match:
        sort_match = re.search(r'\bby\s+(\w+)\s+(?:ascending|descending|asc|desc)\b', ql)
    if sort_match and 'raw_sort_order' not in s and 'raw_limit' in s:
        sort_col = sort_match.group(1)
        if sort_col in ('by',):
            sort_col_m = re.search(r'(?:sort|order|top)\s+\w+\s+(\w+)', ql)
            if sort_col_m:
                sort_col = sort_col_m.group(1)
        order = 'kDescending' if re.search(r'\b(descending|desc)\b', ql) else 'kAscending'
        sort_line = f'    raw_sort_order {{ column: "{sort_col}" order: {order} }}\n'
        s = re.sub(r'(raw_limit\s*\{)', sort_line + '    \\1', s, count=1)
        if f'raw_columns {{ column: "{sort_col}"' not in s:
            s = re.sub(r'(raw_columns\s*\{)', f'raw_columns {{ column: "{sort_col}" }}\n    \\1', s, count=1)

    # If query says "where X = Y" / "where X > Y" etc. but proto has no where_clause, try to inject one
    where_match = re.search(r'\bwhere\s+(\w+)\s+(equals?|[><=!]+|greater|less|>=|<=)\s+(\w+)', ql)
    if where_match and 'where_clause' not in s and 'query {' in s:
        col = where_match.group(1)
        op_raw = where_match.group(2)
        val = where_match.group(3)
        op_map = {
            'equals': 'kEQ', 'equal': 'kEQ', '=': 'kEQ', '==': 'kEQ',
            '>': 'kGT', '>=': 'kGE', '<': 'kLT', '<=': 'kLE',
            '!=': 'kNE', 'greater': 'kGT', 'less': 'kLT',
        }
        op = op_map.get(op_raw, 'kEQ')
        if val.isdigit():
            val_expr = f'uint64_value: {val}'
        else:
            val_expr = f'str_value: "{val}"'
        where_str = (
            f'  where_clause {{\n'
            f'    comparison_expr {{\n'
            f'      lhs {{ leaf {{ column: "{col}" }} }}\n'
            f'      operator: {op}\n'
            f'      rhs {{ leaf {{ value {{ {val_expr} }} }} }}\n'
            f'    }}\n'
            f'  }}\n'
        )
        s = re.sub(r'(entity_list\s*\{[^}]*\}\s*\n)', '\\1' + where_str, s, count=1)

    return s


def _extract_filter_fields(text: str, block_name: str):
    """Extract column, operator, value_type, value from a filter-like block."""
    block_match = re.search(rf'{block_name}\s*\{{', text)
    if not block_match:
        return None, None, None, None

    start = block_match.start()
    depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    block = text[start:end]

    col_match = re.search(r'(?:attribute_name|field_name|name|column)\s*:\s*"([^"]+)"', block)
    op_match = re.search(r'(?:comparison_operator|operator)\s*:\s*"?(\w+)"?', block)
    val_match = re.search(r'(str_value|uint64_value|int64_value|bool_value|double_value)\s*:\s*([^\s}]+)', block)

    if not col_match:
        return None, None, None, None

    col = col_match.group(1)
    op = _normalize_operator(op_match.group(1)) if op_match else 'kEQ'

    if val_match:
        val_type = val_match.group(1)
        val = val_match.group(2).strip().strip('"')
        if val_type == 'str_value':
            val = f'"{val}"'
    else:
        val_raw = re.search(r'value\s*[:{]\s*"?([^"}\s]+)"?', block)
        if val_raw:
            v = val_raw.group(1)
            if v.isdigit():
                val_type, val = 'uint64_value', v
            else:
                val_type, val = 'str_value', f'"{v}"'
        else:
            val_type, val = 'str_value', '""'

    return col, op, val_type, val


def _build_where_clause(col: str, op: str, val_type: str, val: str) -> str:
    """Build a correct IDF where_clause from extracted components."""
    return (
        f'where_clause {{\n'
        f'    comparison_expr {{\n'
        f'      lhs {{ leaf {{ column: "{col}" }} }}\n'
        f'      operator: {op}\n'
        f'      rhs {{ leaf {{ value {{ {val_type}: {val} }} }} }}\n'
        f'    }}\n'
        f'  }}'
    )


def _replace_block(text: str, block_name: str, replacement: str) -> str:
    """Replace an entire brace-balanced block (block_name { ... }) with replacement."""
    block_match = re.search(rf'{block_name}\s*\{{', text)
    if not block_match:
        return text
    start = block_match.start()
    depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return text[:start] + replacement + text[end:]


def _fix_comparison_operator(match: re.Match) -> str:
    """Fix comparison_operator field to operator field."""
    op = match.group(1)
    return f'operator: {_normalize_operator(op)}'


def _normalize_operator(op: str) -> str:
    """Normalize operator name to IDF format."""
    op_map = {
        'GT': 'kGT', 'LT': 'kLT', 'GE': 'kGE', 'LE': 'kLE',
        'EQ': 'kEQ', 'NE': 'kNE', 'EQUALS': 'kEQ',
        'GREATER_THAN': 'kGT', 'LESS_THAN': 'kLT',
        'LIKE': 'kLike', 'CONTAINS': 'kLike',
        'kGT': 'kGT', 'kLT': 'kLT', 'kGE': 'kGE', 'kLE': 'kLE',
        'kEQ': 'kEQ', 'kNE': 'kNE', 'kLike': 'kLike',
        'kEqual': 'kEQ', 'kGreater': 'kGT', 'kLess': 'kLT',
    }
    return op_map.get(op, op)


def _parse_llm_response(content: str) -> Tuple[str, str]:
    """
    Parse the LLM response into (api_method, proto_text).
    Expected format:
      API: MethodName
      <proto text>
    """
    content = content.strip()

    # Remove markdown code blocks if present (anywhere in text)
    content = re.sub(r'```(?:proto(?:buf)?|text|plaintext)?\s*\n?', '', content)
    content = re.sub(r'\n?```', '', content)
    content = content.strip()

    # Extract API line
    api_match = re.match(r'^API:\s*(\w+)\s*$', content, re.MULTILINE)
    if api_match:
        api_method = api_match.group(1)
        proto_text = content[api_match.end():].strip()
    else:
        # Fallback: try to detect API from proto structure
        api_method = _detect_api_from_proto(content)
        proto_text = content

    # Normalize known API variations the LLM might generate
    _API_NORMALIZE = {
        "RegisterWatch": "Watch",
        "UnregisterWatch": "Watch",
        "WatchForChangesOnEntityType": "Watch",
        "WatchEntity": "Watch",
        "WatchEntities": "Watch",
        "WatchForChanges": "Watch",
        "WatchChanges": "Watch",
        "MonitorEntity": "Watch",
        "UpdateEntityAttribute": "UpdateEntity",
        "UpdateEntityAttributes": "UpdateEntity",
        "ModifyEntity": "UpdateEntity",
        "SetEntityAttribute": "UpdateEntity",
        "SetAttribute": "UpdateEntity",
        "RemoveEntity": "DeleteEntity",
        "DeleteVM": "DeleteEntity",
        "DeleteDisk": "DeleteEntity",
        "DeleteNode": "DeleteEntity",
        "RemoveVM": "DeleteEntity",
        "GetEntitiesMetrics": "GetEntitiesWithMetrics",
        "QueryEntities": "GetEntitiesWithMetrics",
        "FetchEntities": "GetEntitiesWithMetrics",
        "ListEntityTypes": "GetEntityTypes",
        "DescribeEntityType": "GetEntityTypes",
        "GetEntityType": "GetEntityTypes",
        "ShowEntityTypes": "GetEntityTypes",
        "ListMetricTypes": "GetMetricTypes",
        "ListMetrics": "GetMetricTypes",
        "GetMetrics": "GetMetricTypes",
        "ShowMetrics": "GetMetricTypes",
        "ListAttributes": "GetMetricTypes",
        "SearchEntities": "SpotLightSearch",
        "Search": "SpotLightSearch",
        "TextSearch": "SpotLightSearch",
        "RegisterEntity": "RegisterEntityTypes",
        "CreateEntityType": "RegisterEntityTypes",
        "RegisterMetric": "RegisterMetricTypes",
        "AddMetric": "RegisterMetricTypes",
        "AddAttribute": "RegisterMetricTypes",
        "UnregisterMetric": "UnregisterMetricTypes",
        "RemoveMetric": "UnregisterMetricTypes",
        "RemoveAttribute": "UnregisterMetricTypes",
        "DeleteMetricType": "UnregisterMetricTypes",
        "DeleteAttribute": "UnregisterMetricTypes",
        "BatchGet": "BatchGetEntitiesWithMetrics",
        "BatchQuery": "BatchGetEntitiesWithMetrics",
        "BatchUpdate": "BatchUpdateEntities",
        "BatchDelete": "BatchDeleteEntities",
        "BulkDelete": "BatchDeleteEntities",
        "BulkUpdate": "BatchUpdateEntities",
        "GetEntityTrail": "GetEntitiesTrail",
        "GetTrail": "GetEntitiesTrail",
        "GetAuditTrail": "GetEntitiesTrail",
        "AuditTrail": "GetEntitiesTrail",
        "GetChangeHistory": "GetEntitiesTrail",
        "LookupEntity": "GetEntities",
        "FetchEntity": "GetEntities",
        "GetEntityById": "GetEntities",
        "LookupQuery": "GetEntities",
        "FireEvent": "PutEvent",
        "CreateEvent": "PutEvent",
        "PublishEvent": "PutEvent",
        "WriteMetric": "PutMetricData",
        "RecordMetric": "PutMetricData",
        "PublishMetric": "PutMetricData",
        "ReadMetricData": "GetMetricData",
        "FetchMetricData": "GetMetricData",
    }
    api_method = _API_NORMALIZE.get(api_method, api_method)

    # Validate it's a known API - if not, try to detect from proto
    _VALID_APIS = {
        "GetEntitiesWithMetrics", "GetEntityTypes", "GetMetricTypes",
        "UpdateEntity", "DeleteEntity", "RegisterEntityTypes",
        "RegisterMetricTypes", "UnregisterMetricTypes",
        "BatchGetEntitiesWithMetrics", "BatchUpdateEntities",
        "BatchDeleteEntities", "GetEntities", "GetMetricData",
        "PutMetricData", "SpotLightSearch", "GetEntitiesTrail",
        "AttachEntity", "DetachEntity", "GetMasterLocation",
        "Watch", "PutEvent",
    }
    if api_method not in _VALID_APIS:
        api_method = _detect_api_from_proto(proto_text)

    return api_method, proto_text


def _detect_api_from_proto(proto_text: str) -> str:
    """Fallback API detection from proto structure when LLM doesn't output API: line."""
    s = proto_text.strip()
    if "query_list" in s:
        return "BatchGetEntitiesWithMetrics"
    if "entity_with_metric_list" in s:
        return "PutMetricData"
    if "metric_data_list" in s and "entity_guid" in s:
        return "PutMetricData"
    if "metric_name_list" in s or "metric_type_name" in s:
        if "entity_id_list" in s:
            return "GetMetricData"
    if "attribute_data_arg_list" in s or "attribute_data_list" in s:
        if "entity_list" in s:
            return "BatchUpdateEntities"
        return "UpdateEntity"
    if "entity_type_info_list" in s:
        return "RegisterEntityTypes"
    if "metric_type_list" in s:
        if "is_attribute" in s:
            return "RegisterMetricTypes"
        return "UnregisterMetricTypes"
    if "entity_guid_list" in s:
        return "GetEntities"
    if "watch_list" in s or "watch_type_mask" in s or "watch_name" in s:
        return "Watch"
    if "search_term" in s:
        return "SpotLightSearch"
    if "event_type" in s:
        return "PutEvent"
    if "incarnation_id" in s or "update_entity_arg" in s:
        return "AttachEntity"
    if "moved_to_cluster_uuid" in s or "delete_entity_arg" in s:
        return "DetachEntity"
    if "entity_guid" in s and "attribute_data" not in s and "entity_guid_list" not in s:
        if "entity_list" in s:
            return "BatchDeleteEntities"
        return "DeleteEntity"
    if "regex" in s and "query" not in s:
        return "GetMetricTypes"
    if re.match(r'^\s*entity_type_name\s*:', s) and "query" not in s and "entity_id" not in s:
        return "GetEntityTypes"
    if not s:
        return "GetMasterLocation"
    return "GetEntitiesWithMetrics"


def _validate_proto(proto_text: str, api_method: str) -> Tuple[bool, Optional[str]]:
    """Validate proto structure for the given API method."""
    s = proto_text.strip()

    if api_method == "GetMasterLocation":
        return True, None

    if api_method == "GetEntityTypes":
        return True, None

    if api_method == "GetMetricTypes":
        if not s:
            return False, "GetMetricTypes needs regex field"
        return True, None

    if api_method == "GetEntitiesWithMetrics":
        if "query {" not in s and "query{" not in s:
            return False, "GetEntitiesWithMetrics MUST wrap in query { }. Use: query { entity_list { entity_type_name: \"X\" } group_by { raw_columns { column: \"Y\" } } query_name: \"Z\" }"
        if "entity_list" not in s:
            return False, "GetEntitiesWithMetrics MUST have entity_list { entity_type_name: \"X\" } inside query { }"
        # Check for WRONG operator names
        wrong_ops = re.findall(r'operator:\s*(GT|LT|GE|LE|EQ|NE|EQUALS|GREATER|LESS|DESCENDING|ASCENDING)\b', s)
        if wrong_ops:
            return False, f"WRONG operator names found: {wrong_ops}. Use ONLY: kEQ, kNE, kGT, kGE, kLT, kLE, kLike, kAscending, kDescending"
        # Check for WRONG filter structures
        if "attribute_filter" in s or "filter {" in s:
            return False, "Do NOT use 'attribute_filter' or 'filter {{}}'. Use where_clause {{ comparison_expr {{ lhs {{ leaf {{ column: \"X\" }} }} operator: kEQ rhs {{ leaf {{ value {{ str_value: \"Y\" }} }} }} }} }}"
        if "order_by" in s or "sort_order {" in s:
            return False, "Do NOT use 'order_by' or 'sort_order'. Use group_by {{ raw_sort_order {{ column: \"X\" order: kDescending }} raw_limit {{ limit: N offset: 0 }} }}"
        if re.search(r'^\s*fields:', s, re.MULTILINE):
            return False, "Do NOT use 'fields:'. Use group_by {{ raw_columns {{ column: \"X\" }} }}"
        if re.search(r'^\s*limit:', s, re.MULTILINE) and "raw_limit" not in s:
            return False, "Do NOT use top-level 'limit:'. Use group_by {{ raw_limit {{ limit: N offset: 0 }} }}"
        if re.search(r'^\s*group_by:\s*"', s, re.MULTILINE):
            return False, "Do NOT use 'group_by: \"col\"'. Use group_by {{ raw_columns {{ column: \"col\" }} }}"
        return True, None

    if api_method == "UpdateEntity":
        if "entity_guid" not in s:
            return False, "UpdateEntity requires entity_guid { entity_type_name: \"X\" entity_id: \"ID\" }"
        if "attribute_data" not in s:
            return False, "UpdateEntity requires attribute_data_arg_list { attribute_data { name: \"X\" value { str_value: \"Y\" } } }"
        return True, None

    if api_method == "DeleteEntity":
        if "entity_guid" not in s:
            return False, "DeleteEntity requires entity_guid { entity_type_name: \"X\" entity_id: \"ID\" }"
        return True, None

    if api_method == "RegisterEntityTypes":
        if "entity_type_info_list" not in s and "entity_type_name" not in s:
            return False, "RegisterEntityTypes requires entity_type_info_list { entity_type_name: \"X\" }"
        return True, None

    if api_method == "RegisterMetricTypes":
        if "metric_type_list" not in s and "metric_name" not in s:
            return False, "RegisterMetricTypes requires metric_type_list { metric_name: \"X\" entity_type_name: \"Y\" }"
        return True, None

    if api_method == "UnregisterMetricTypes":
        if "metric_type_list" not in s and "metric_name" not in s:
            return False, "UnregisterMetricTypes requires metric_type_list { metric_name: \"X\" entity_type_name: \"Y\" }"
        return True, None

    if api_method == "BatchGetEntitiesWithMetrics":
        if "query_list" not in s:
            return False, "BatchGetEntitiesWithMetrics requires query_list { query { ... } }"
        return True, None

    if api_method == "Watch":
        if "entity_type_name" not in s and not s:
            return False, "Watch requires watch_list { watch_name: \"X\" entity_type_name: \"Y\" watch_type_mask: 7 }"
        return True, None

    if api_method == "SpotLightSearch":
        if "search_term" not in s:
            return False, "SpotLightSearch requires search_term: \"X\""
        return True, None

    if api_method == "GetEntitiesTrail":
        if "entity_guid_list" not in s:
            return False, "GetEntitiesTrail requires entity_guid_list { entity_type_name: \"X\" entity_id: \"ID\" }"
        return True, None

    if api_method == "GetEntities":
        if "entity_guid_list" not in s:
            return False, "GetEntities requires entity_guid_list { entity_type_name: \"X\" entity_id: \"ID\" }"
        return True, None

    if api_method == "GetMetricData":
        if "entity_type_name" not in s or "metric_name" not in s:
            return False, "GetMetricData requires entity_type_name and metric_name_list"
        return True, None

    if api_method == "PutMetricData":
        if "entity_with_metric_list" not in s and "metric_data_list" not in s:
            return False, "PutMetricData requires entity_with_metric_list { entity_guid { ... } metric_data_list { ... } }"
        return True, None

    if api_method == "PutEvent":
        if "event_type" not in s:
            return False, "PutEvent requires event_type: \"X\""
        return True, None

    if api_method == "AttachEntity":
        if "update_entity_arg" not in s and "entity_guid" not in s:
            return False, "AttachEntity requires update_entity_arg { entity_guid { ... } } incarnation_id: N"
        return True, None

    if api_method == "DetachEntity":
        if "delete_entity_arg" not in s and "entity_guid" not in s:
            return False, "DetachEntity requires delete_entity_arg { entity_guid { ... } } moved_to_cluster_uuid: \"X\""
        return True, None

    return True, None


def _build_schema_context(schema_chunks: List[dict]) -> str:
    """Build schema context string from retrieved chunks."""
    if not schema_chunks:
        return "(No schema context available)"

    entity_chunks = {}
    for chunk in schema_chunks:
        metadata = chunk.get('metadata', {})
        entity_type = metadata.get('entity_type', '')
        attribute = metadata.get('attribute', metadata.get('metric_name', ''))
        data_type = metadata.get('data_type', '')

        if entity_type and attribute:
            if entity_type not in entity_chunks:
                entity_chunks[entity_type] = []
            entity_chunks[entity_type].append({
                'attribute': attribute,
                'data_type': data_type
            })

    lines = []
    for entity_type in sorted(entity_chunks.keys()):
        attrs = entity_chunks[entity_type]
        lines.append(f"Entity type: {entity_type}")
        for attr_info in attrs:
            line = f"  - {attr_info['attribute']}"
            if attr_info.get('data_type'):
                line += f" ({attr_info['data_type']})"
            lines.append(line)
        lines.append("")

    return "\n".join(lines) if lines else "(No schema context available)"
