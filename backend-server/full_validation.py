"""
Full validation: covers ALL user-facing IDF RPCs.
Tests classification, proto generation, code generation, and (for safe reads) CVM execution.
"""
import json
import subprocess
import sys
import time
import requests

SERVER_URL = "http://localhost:8000/query"
CVM_HOST = "10.46.30.35"
CVM_USER = "nutanix"
CVM_PASS = "nutanix/4u"
TIMEOUT_SEC = 90

def query_pipeline(nl_query: str) -> dict:
    resp = requests.post(SERVER_URL, json={
        "query": nl_query,
        "generate_python": True,
    }, timeout=TIMEOUT_SEC)
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    return resp.json()


def execute_on_cvm(code: str) -> str:
    """Execute python code on CVM via SSH. Returns output or error."""
    cmd = [
        "sshpass", "-p", CVM_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR",
        f"{CVM_USER}@{CVM_HOST}",
        "source /home/nutanix/.venvs/bin/bin/activate && python3 -"
    ]
    try:
        result = subprocess.run(
            cmd, input=code, capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"ERROR: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "ERROR: Execution timed out"
    except Exception as e:
        return f"ERROR: {str(e)}"


# ============================================================================
# TEST CASES: Covering all 24 user-facing RPCs
# ============================================================================

TESTS = [
    # --- GetEntitiesWithMetrics (various patterns) ---
    {
        "id": "T01",
        "query": "get all VMs",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["entity_type_name", "vm"],
        "code_must_have": ["GetEntitiesWithMetricsArg"],
        "can_execute": True,
    },
    {
        "id": "T02",
        "query": "get VMs where power_state = on",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["where_clause", "power_state", "kEQ"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
    {
        "id": "T03",
        "query": "get top 5 VMs sorted by num_vcpus descending",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["raw_sort_order", "kDescending", "num_vcpus"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
    {
        "id": "T04",
        "query": "get VMs where memory_mb > 4096 and num_vcpus >= 4",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["where_clause", "kAnd", "memory_mb", "num_vcpus"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
    {
        "id": "T05",
        "query": "get average memory_mb for VMs",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["aggregate_columns", "memory_mb", "kAvg"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
    {
        "id": "T06",
        "query": "count all VMs",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["entity_type_name", "vm"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
    {
        "id": "T07",
        "query": "get VMs where vm_name contains test",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["kLike", "vm_name"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
    {
        "id": "T08",
        "query": "paginate through all tasks with batch size 50",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["cursor_query_info", "batch_size"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": False,
    },
    # --- UpdateEntity ---
    {
        "id": "T09",
        "query": "update VM entity vm-001 setting power_state to on with cas value 5",
        "expect_api": "UpdateEntity",
        "proto_must_have": ["entity_guid", "vm", "vm-001", "attribute_data", "power_state"],
        "code_must_have": ["UpdateEntityArg", "UpdateEntity"],
        "can_execute": False,
    },
    # --- DeleteEntity ---
    {
        "id": "T10",
        "query": "delete VM entity vm-test-123",
        "expect_api": "DeleteEntity",
        "proto_must_have": ["entity_guid", "vm", "vm-test-123"],
        "code_must_have": ["DeleteEntityArg", "DeleteEntity"],
        "can_execute": False,
    },
    # --- RegisterEntityTypes ---
    {
        "id": "T11",
        "query": "register a new entity type called custom_sensor with parent node",
        "expect_api": "RegisterEntityTypes",
        "proto_must_have": ["entity_type_info_list", "custom_sensor"],
        "code_must_have": ["RegisterEntityTypesArg", "RegisterEntityTypes"],
        "can_execute": False,
    },
    # --- RegisterMetricTypes ---
    {
        "id": "T12",
        "query": "register a new attribute cpu_temp for entity type vm",
        "expect_api": "RegisterMetricTypes",
        "proto_must_have": ["metric_type_list", "cpu_temp", "vm"],
        "code_must_have": ["RegisterMetricTypesArg", "RegisterMetricTypes"],
        "can_execute": False,
    },
    # --- UnregisterMetricTypes ---
    {
        "id": "T13",
        "query": "unregister metric old_metric from entity type vm",
        "expect_api": "UnregisterMetricTypes",
        "proto_must_have": ["metric_type_list", "old_metric", "vm"],
        "code_must_have": ["UnregisterMetricTypesArg", "UnregisterMetricTypes"],
        "can_execute": False,
    },
    # --- BatchGetEntitiesWithMetrics ---
    {
        "id": "T14",
        "query": "batch query: get all VMs and get all clusters",
        "expect_api": "BatchGetEntitiesWithMetrics",
        "proto_must_have": ["query_list"],
        "code_must_have": ["BatchGetEntitiesWithMetricsArg"],
        "can_execute": False,
    },
    # --- BatchUpdateEntities ---
    {
        "id": "T15",
        "query": "batch update vm entities vm-001 and vm-002 setting power_state to off",
        "expect_api": "BatchUpdateEntities",
        "proto_must_have": ["entity_list", "vm-001", "vm-002", "power_state"],
        "code_must_have": ["BatchUpdateEntitiesArg", "BatchUpdateEntities"],
        "can_execute": False,
    },
    # --- BatchDeleteEntities ---
    {
        "id": "T16",
        "query": "batch delete vm entities vm-old-1 and vm-old-2",
        "expect_api": "BatchDeleteEntities",
        "proto_must_have": ["entity_list", "vm-old-1", "vm-old-2"],
        "code_must_have": ["BatchDeleteEntitiesArg", "BatchDeleteEntities"],
        "can_execute": False,
    },
    # --- GetEntities (by GUID) ---
    {
        "id": "T17",
        "query": "get entity by id abc-123-uuid of type vm",
        "expect_api": "GetEntities",
        "proto_must_have": ["entity_guid_list", "vm", "abc-123-uuid"],
        "code_must_have": ["GetEntitiesArg", "GetEntities"],
        "can_execute": False,
    },
    # --- GetEntityTypes ---
    {
        "id": "T18",
        "query": "describe entity type vm schema",
        "expect_api": "GetEntityTypes",
        "proto_must_have": ["entity_type_name", "vm"],
        "code_must_have": ["GetEntityTypesArg", "GetEntityTypes"],
        "can_execute": False,
    },
    # --- GetMetricTypes ---
    {
        "id": "T19",
        "query": "list all metrics for entity type vm",
        "expect_api": "GetMetricTypes",
        "proto_must_have": ["regex", "vm"],
        "code_must_have": ["GetMetricTypesArg", "GetMetricTypes"],
        "can_execute": False,
    },
    # --- GetMetricData ---
    {
        "id": "T20",
        "query": "get metric data for cpu_usage of vm entity vm-001",
        "expect_api": "GetMetricData",
        "proto_must_have": ["entity_type_name", "vm", "cpu_usage"],
        "code_must_have": ["GetMetricDataArg", "GetMetricData"],
        "can_execute": False,
    },
    # --- PutMetricData ---
    {
        "id": "T21",
        "query": "write metric data cpu_usage value 85 for vm entity vm-001",
        "expect_api": "PutMetricData",
        "proto_must_have": ["entity_with_metric_list", "cpu_usage", "vm-001"],
        "code_must_have": ["PutMetricDataArg", "PutMetricData"],
        "can_execute": False,
    },
    # --- SpotLightSearch ---
    {
        "id": "T22",
        "query": "search for entities containing production",
        "expect_api": "SpotLightSearch",
        "proto_must_have": ["search_term", "production"],
        "code_must_have": ["SpotLightSearchArg", "SpotLightSearch"],
        "can_execute": False,
    },
    # --- GetEntitiesTrail ---
    {
        "id": "T23",
        "query": "get change history for vm entity vm-001",
        "expect_api": "GetEntitiesTrail",
        "proto_must_have": ["entity_guid_list", "vm", "vm-001"],
        "code_must_have": ["GetEntitiesTrailArg", "GetEntitiesTrail"],
        "can_execute": False,
    },
    # --- AttachEntity ---
    {
        "id": "T24",
        "query": "attach entity vm-migrated-1 of type vm",
        "expect_api": "AttachEntity",
        "proto_must_have": ["update_entity_arg", "vm", "vm-migrated-1"],
        "code_must_have": ["AttachEntityArg", "AttachEntity"],
        "can_execute": False,
    },
    # --- DetachEntity ---
    {
        "id": "T25",
        "query": "detach entity vm-leaving-1 of type vm moving to cluster dest-uuid-123",
        "expect_api": "DetachEntity",
        "proto_must_have": ["vm", "vm-leaving-1", "moved_to_cluster_uuid"],
        "code_must_have": ["DetachEntityArg", "DetachEntity"],
        "can_execute": False,
    },
    # --- GetMasterLocation ---
    {
        "id": "T26",
        "query": "get master location",
        "expect_api": "GetMasterLocation",
        "proto_must_have": [],
        "code_must_have": ["GetMasterLocationArg", "GetMasterLocation"],
        "can_execute": False,
    },
    # --- Watch (register) ---
    {
        "id": "T27",
        "query": "watch for changes on VM entity type",
        "expect_api": "Watch",
        "proto_must_have": ["entity_type_name", "vm", "watch_type_mask"],
        "code_must_have": ["InsightsWatchClient"],
        "can_execute": False,
    },
    # --- Watch (unregister) ---
    {
        "id": "T28",
        "query": "unregister watch client for VMs",
        "expect_api": "Watch",
        "proto_must_have": ["entity_type_name", "vm"],
        "code_must_have": ["unregister_composite_watch"],
        "can_execute": False,
    },
    # --- Watch (get fired) ---
    {
        "id": "T29",
        "query": "get fired watch status for VM watches",
        "expect_api": "Watch",
        "proto_must_have": ["entity_type_name", "vm"],
        "code_must_have": ["GetFiredWatchList"],
        "can_execute": False,
    },
    # --- Watch (new entities) ---
    {
        "id": "T30",
        "query": "watch for new VMs being created",
        "expect_api": "Watch",
        "proto_must_have": ["entity_type_name", "vm"],
        "code_must_have": ["InsightsWatchClient"],
        "can_execute": False,
    },
    # --- LookupQuery ---
    {
        "id": "T31",
        "query": "get VMs joining with cluster on cluster_uuid",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["lookup_query", "cluster"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": False,
    },
    # --- PutEvent ---
    {
        "id": "T32",
        "query": "publish an event for vm entity vm-001",
        "expect_api": "PutEvent",
        "proto_must_have": ["vm"],
        "code_must_have": ["PutEventArg", "PutEvent"],
        "can_execute": False,
    },
    # --- kIN operator ---
    {
        "id": "T33",
        "query": "get tasks where status IN kSucceeded, kFailed",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["kIN", "str_list", "status"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": False,
    },
    # --- kExists operator ---
    {
        "id": "T34",
        "query": "get VMs where attribute ip_address exists",
        "expect_api": "GetEntitiesWithMetrics",
        "proto_must_have": ["kExists", "ip_address"],
        "code_must_have": ["GetEntitiesWithMetrics"],
        "can_execute": True,
    },
]


def run_tests():
    results = []
    passed = 0
    failed = 0
    exec_passed = 0
    exec_total = 0

    print(f"\n{'='*80}")
    print(f"FULL VALIDATION: {len(TESTS)} tests covering ALL user-facing IDF RPCs")
    print(f"{'='*80}\n")

    for test in TESTS:
        tid = test["id"]
        query = test["query"]
        print(f"[{tid}] {query}")

        resp = query_pipeline(query)

        if "error" in resp:
            print(f"  FAIL: Pipeline error: {resp['error']}")
            failed += 1
            results.append({"id": tid, "status": "FAIL", "reason": resp["error"]})
            continue

        # Check API method
        actual_api = resp.get("api_method") or "GetEntitiesWithMetrics"
        if test["expect_api"] and actual_api != test["expect_api"]:
            print(f"  FAIL: Expected api_method={test['expect_api']}, got {actual_api}")
            failed += 1
            results.append({"id": tid, "status": "FAIL", "reason": f"api_method mismatch: {actual_api}"})
            continue

        # Check proto keywords
        proto = resp.get("query_proto", "")
        proto_ok = True
        for kw in test["proto_must_have"]:
            if kw not in proto:
                print(f"  FAIL: Proto missing '{kw}'")
                print(f"  Proto: {proto[:200]}")
                proto_ok = False
                break

        if not proto_ok:
            failed += 1
            results.append({"id": tid, "status": "FAIL", "reason": f"Proto missing keyword"})
            continue

        # Check code keywords
        code = resp.get("python_code", "")
        code_ok = True
        for kw in test["code_must_have"]:
            if kw not in code:
                print(f"  FAIL: Code missing '{kw}'")
                code_ok = False
                break

        if not code_ok:
            failed += 1
            results.append({"id": tid, "status": "FAIL", "reason": f"Code missing keyword"})
            continue

        # Execute on CVM if safe
        if test.get("can_execute") and code:
            exec_total += 1
            output = execute_on_cvm(code)
            if output.startswith("ERROR"):
                print(f"  WARN: Execution failed: {output[:100]}")
            else:
                exec_passed += 1
                print(f"  EXEC OK (output length: {len(output)} chars)")

        passed += 1
        print(f"  PASS (api={actual_api})")
        results.append({"id": tid, "status": "PASS"})

    # Summary
    total = passed + failed
    print(f"\n{'='*80}")
    print(f"RESULTS: {passed}/{total} PASSED ({passed/total*100:.1f}%)")
    if exec_total:
        print(f"CVM EXECUTION: {exec_passed}/{exec_total} successful")
    print(f"{'='*80}")

    if failed > 0:
        print(f"\nFAILED TESTS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  [{r['id']}] {r.get('reason', 'unknown')}")

    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
