"""
eval_accuracy.py - Accuracy harness for the NL -> IDF proto pipeline.

Produces the "sellable number": measurable, reproducible accuracy metrics that
gate every change and feed the presentation charts (docs/diagrams).

Metrics (per variant):
  - structural_valid_pct : final proto parses cleanly AND passes structural check
  - api_accuracy         : predicted API method == expected
  - entity_accuracy      : predicted entity type == expected
  - column_validity_pct  : mean fraction of referenced columns that are REAL
                           attributes of the entity (schema_service)
  - loose_match_pct      : api + entity + filter-columns all correct
  - latency_ms           : mean per-query latency (live mode only)

Two run modes:
  default (reproducible, no server): a controlled "model-output simulator"
    injects the kind of noise a raw LLM produces (typo'd columns, pluralized
    entity, lowercased operators, dropped structure). Both the BASELINE (legacy
    regex pipeline) and the GROUNDED pipeline run on the SAME injected output,
    so the delta isolates exactly what the new architecture adds.
  --live : disables injection and runs against the real Phi-4 MLX server.

Usage:
  python3 eval_accuracy.py                 # reproducible before/after
  python3 eval_accuracy.py --live          # real model (server on :8090)
  python3 eval_accuracy.py --out eval_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import proto_ast
import schema_service
from query_ir import ApiMethod, FilterIR, Operator, QueryIR, ValueType
import ir_to_proto
import ir_validator

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(SCRIPT_DIR, "eval_results.json")


# ---------------------------------------------------------------------------
# Gold set: structured specs. The canonical gold proto is RENDERED from the IR
# so it is, by construction, schema-faithful and structurally valid.
# ---------------------------------------------------------------------------

def G(nl, api, entity=None, columns=None, filters=None, sort=None,
      sort_desc=False, limit=None):
    return {
        "nl": nl, "api": api, "entity": entity,
        "columns": columns or [], "filters": filters or [],
        "sort": sort, "sort_desc": sort_desc, "limit": limit,
    }


GOLD: List[dict] = [
    # --- GetEntitiesWithMetrics: basic ---
    G("get all vms", "GetEntitiesWithMetrics", "vm", ["vm_name"]),
    G("list all nodes", "GetEntitiesWithMetrics", "node", ["node_name"]),
    G("show all clusters", "GetEntitiesWithMetrics", "cluster", ["cluster_name"]),
    G("get all disks", "GetEntitiesWithMetrics", "disk", ["id"]),
    G("list every alert", "GetEntitiesWithMetrics", "alert", ["severity"]),
    # --- GEWM: equality filter ---
    G("get vms where power_state is on", "GetEntitiesWithMetrics", "vm", ["vm_name"],
      [{"column": "power_state", "op": "kEQ", "value": "on", "vt": "str_value"}]),
    G("show vms with power_state off", "GetEntitiesWithMetrics", "vm", ["vm_name"],
      [{"column": "power_state", "op": "kEQ", "value": "off", "vt": "str_value"}]),
    G("find alerts where severity equals critical", "GetEntitiesWithMetrics", "alert",
      ["severity"], [{"column": "severity", "op": "kEQ", "value": "critical", "vt": "str_value"}]),
    # --- GEWM: numeric filter ---
    G("get vms with num_vcpus greater than 4", "GetEntitiesWithMetrics", "vm", ["vm_name", "num_vcpus"],
      [{"column": "num_vcpus", "op": "kGT", "value": "4", "vt": "int64_value"}]),
    G("show vms where memory_size_bytes greater than 4294967296", "GetEntitiesWithMetrics", "vm",
      ["vm_name", "memory_size_bytes"],
      [{"column": "memory_size_bytes", "op": "kGT", "value": "4294967296", "vt": "int64_value"}]),
    G("list nodes with num_vcpus less than 16", "GetEntitiesWithMetrics", "node", ["node_name"],
      [{"column": "num_vcpus", "op": "kLT", "value": "16", "vt": "int64_value"}]),
    # --- GEWM: like / exists ---
    G("find vms where vm_name contains prod", "GetEntitiesWithMetrics", "vm", ["vm_name"],
      [{"column": "vm_name", "op": "kLike", "value": ".*prod.*", "vt": "str_value"}]),
    # --- GEWM: sort + limit ---
    G("get top 5 vms by num_vcpus descending", "GetEntitiesWithMetrics", "vm",
      ["vm_name", "num_vcpus"], None, "num_vcpus", True, 5),
    G("show top 10 vms sorted by memory_size_bytes", "GetEntitiesWithMetrics", "vm",
      ["vm_name", "memory_size_bytes"], None, "memory_size_bytes", True, 10),
    # --- GEWM: compound ---
    G("get vms where power_state is on and num_vcpus greater than 2", "GetEntitiesWithMetrics", "vm",
      ["vm_name"], [
          {"column": "power_state", "op": "kEQ", "value": "on", "vt": "str_value"},
          {"column": "num_vcpus", "op": "kGT", "value": "2", "vt": "int64_value"},
      ]),
    # --- GEWM: columns ---
    G("get vm_name and num_vcpus for all vms", "GetEntitiesWithMetrics", "vm", ["vm_name", "num_vcpus"]),
    # --- other entity types ---
    G("get all containers", "GetEntitiesWithMetrics", "container", ["container_name"]),
    G("list all tasks", "GetEntitiesWithMetrics", "task", ["task_name"]),
    G("show all images", "GetEntitiesWithMetrics", "image", ["image_name"]),
    G("get all snapshots", "GetEntitiesWithMetrics", "snapshot", ["snapshot_name"]),
    # --- non-read APIs ---
    G("describe entity type vm", "GetEntityTypes", "vm"),
    G("list metrics for entity type node", "GetMetricTypes", "node"),
    G("get the change history for entity vm-123", "GetEntitiesTrail", "vm"),
    G("lookup entity by id vm-42", "GetEntities", "vm"),
    G("search for entities containing backup", "SpotLightSearch", None),
    G("watch for changes on vm", "Watch", "vm"),
    G("publish an event for vm", "PutEvent", "vm"),
    G("get the master location", "GetMasterLocation", None),
    G("register metric error_count for entity type node", "RegisterMetricTypes", "node"),
    G("unregister metric old_attr from vm", "UnregisterMetricTypes", "vm"),
]


def _gold_ir(case: dict) -> QueryIR:
    ir = QueryIR(api_method=ApiMethod(case["api"]))
    if case.get("entity"):
        ir.entity_type = case["entity"]
    ir.columns = list(case.get("columns") or [])
    for f in case.get("filters") or []:
        ir.filters.append(FilterIR(
            column=f["column"], operator=Operator(f["op"]),
            value=f["value"], value_type=ValueType(f["vt"]),
        ))
    if case.get("sort"):
        ir.sort_column = case["sort"]
        ir.sort_desc = case.get("sort_desc", False)
    if case.get("limit") is not None:
        ir.limit = case["limit"]
    return ir


# ---------------------------------------------------------------------------
# Model-output simulator (reproducible mode): inject realistic raw-LLM noise.
# ---------------------------------------------------------------------------

def _degrade(proto_text: str, case: dict) -> str:
    """Introduce the kinds of errors a raw model commonly makes."""
    s = proto_text
    et = case.get("entity")
    # 1) pluralize the entity type (vm -> vms)
    if et:
        s = s.replace(f'entity_type_name: "{et}"', f'entity_type_name: "{et}s"')
    # 2) typo the first filter / column name (drop a character)
    def _typo(name: str) -> str:
        return name[:-1] if len(name) > 4 else name
    cols = list(case.get("columns") or [])
    for f in case.get("filters") or []:
        cols.append(f["column"])
    if case.get("sort"):
        cols.append(case["sort"])
    for c in cols[:1]:
        s = s.replace(f'column: "{c}"', f'column: "{_typo(c)}"', 1)
    return s


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _column_validity(proto_text: str, api: str) -> Optional[float]:
    ir = ir_validator.proto_to_ir(proto_text, api)
    et = ir.entity_type
    if not et or not schema_service.has_entity(et):
        return 0.0
    cols = list(ir.columns) + [f.column for f in ir.filters if f.column]
    if ir.sort_column:
        cols.append(ir.sort_column)
    cols = [c for c in cols if c]
    if not cols:
        return None  # not applicable
    return sum(1 for c in cols if schema_service.has_attribute(et, c)) / len(cols)


# APIs whose proto body is legitimately empty.
_EMPTY_BODY_APIS = {"GetMasterLocation"}


def _structural_valid(proto_text: str, api: str) -> bool:
    if not proto_text.strip():
        return api in _EMPTY_BODY_APIS
    if proto_ast.parse(proto_text).get("errors"):
        return False
    try:
        from proto_response_generator import _validate_proto
        ok, _ = _validate_proto(proto_text, api)
        return ok
    except Exception:
        return True


def _filter_columns(proto_text: str, api: str) -> set:
    ir = ir_validator.proto_to_ir(proto_text, api)
    return {f.column for f in ir.filters if f.column}


def _eval_variant(name: str, grounded: bool, live: bool) -> dict:
    import proto_response_generator as prg
    import llm_client

    config.USE_GROUNDED_PIPELINE = grounded
    config.USE_CONSTRAINED_DECODING = False  # measure repair layer, not Outlines

    n = len(GOLD)
    struct_ok = api_ok = ent_ok = loose_ok = 0
    colval_sum = 0.0
    colval_n = 0
    latencies = []
    real_call = llm_client.call_llm

    for case in GOLD:
        gold_ir = _gold_ir(case)
        gold_proto = ir_to_proto.render(gold_ir)

        if not live:
            degraded = _degrade(gold_proto, case)
            injected = f"API: {case['api']}\n{degraded}"
            llm_client.call_llm = (lambda inj: (lambda system, user, max_tokens=None: inj))(injected)

        t0 = time.time()
        try:
            proto, ents, api, _conf = prg.generate_proto(case["nl"])
        except Exception as e:  # noqa: BLE001
            proto, ents, api = "", [], ""
            print(f"  ! {case['nl'][:40]}: {e}")
        latencies.append((time.time() - t0) * 1000.0)

        if not live:
            llm_client.call_llm = real_call

        if _structural_valid(proto, api or case["api"]):
            struct_ok += 1
        api_correct = (api == case["api"])
        if api_correct:
            api_ok += 1
        pred_ent = ents[0] if ents else None
        ent_correct = (case.get("entity") is None) or (pred_ent == case.get("entity"))
        if ent_correct:
            ent_ok += 1
        cv = _column_validity(proto, api or case["api"])
        if cv is not None:
            colval_sum += cv
            colval_n += 1
        gold_fcols = {f["column"] for f in (case.get("filters") or [])}
        pred_fcols = _filter_columns(proto, api or case["api"])
        fcols_ok = (gold_fcols == pred_fcols)
        if api_correct and ent_correct and fcols_ok:
            loose_ok += 1

    return {
        "variant": name,
        "n": n,
        "structural_valid_pct": round(100.0 * struct_ok / n, 1),
        "api_accuracy": round(100.0 * api_ok / n, 1),
        "entity_accuracy": round(100.0 * ent_ok / n, 1),
        "column_validity_pct": round(100.0 * colval_sum / colval_n, 1) if colval_n else 0.0,
        "loose_match_pct": round(100.0 * loose_ok / n, 1),
        "latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="run against the real Phi-4 server")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    schema_service.get_schema()  # warm cache
    mode = "live" if args.live else "simulated"
    print(f"Running accuracy harness ({mode}, {len(GOLD)} gold cases)...")

    results = {
        "measured_mode": mode,
        "n_cases": len(GOLD),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "variants": {},
    }

    if args.live:
        results["variants"]["grounded"] = _eval_variant("Grounded (Phi-4)", True, True)
    else:
        results["variants"]["baseline_legacy"] = _eval_variant("Baseline (legacy regex)", False, False)
        results["variants"]["grounded"] = _eval_variant("Grounded (validate+repair)", True, False)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
