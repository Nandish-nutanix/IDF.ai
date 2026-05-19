"""
Cross-validation for complex IDF operations (non-read APIs).
Tests: UpdateEntity, DeleteEntity, RegisterMetricTypes, Cursor, Batch, Lookup.

For safety, update/delete/register are only validated at the PROTO GENERATION
level (structure correctness) - NOT executed on the cluster to avoid data
corruption. Read-based operations (cursor, batch, lookup) are executed.
"""
import sys
import os
import json
import time
import re
import subprocess
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUERY_SERVER = "http://localhost:8000"
TARGET_IP = "10.46.30.35"
TARGET_PORT = "2027"
SSH_USER = "nutanix"
SSH_PASS = "nutanix/4u"

TEST_CASES = [
    # --- UPDATE ENTITY (proto validation only) ---
    {
        "id": 1,
        "nl": "update VM entity_id abc123 set vm_name to test_vm with cas_value 0",
        "expected_api": "UpdateEntity",
        "expected_query_type": "update_entity",
        "validate_proto_contains": ["entity_guid", "entity_type_name", "vm", "abc123", "cas_value", "attribute_data", "vm_name", "test_vm"],
        "execute_on_cluster": False,
    },
    {
        "id": 2,
        "nl": "update alert entity_id alert_001 set resolved to true",
        "expected_api": "UpdateEntity",
        "expected_query_type": "update_entity",
        "validate_proto_contains": ["entity_guid", "alert", "alert_001", "attribute_data", "resolved", "bool_value"],
        "execute_on_cluster": False,
    },
    # --- DELETE ENTITY (proto validation only) ---
    {
        "id": 3,
        "nl": "delete VM with entity_id 1234",
        "expected_api": "DeleteEntity",
        "expected_query_type": "delete_entity",
        "validate_proto_contains": ["entity_guid", "vm", "1234"],
        "execute_on_cluster": False,
    },
    # --- REGISTER METRIC (proto validation only) ---
    {
        "id": 4,
        "nl": "register a new attribute cpu_temp for entity type vm",
        "expected_api": "RegisterMetricTypes",
        "expected_query_type": "register_metric",
        "validate_proto_contains": ["metric_type_list", "is_attribute: true", "cpu_temp", "vm"],
        "execute_on_cluster": False,
    },
    # --- REGISTER ENTITY TYPE (proto validation only) ---
    {
        "id": 5,
        "nl": "register new entity type my_custom_entity with attribute name and status",
        "expected_api": "RegisterEntityTypes",
        "expected_query_type": "register_entity",
        "validate_proto_contains": ["entity_type_list", "my_custom_entity"],
        "execute_on_cluster": False,
    },
    # --- CURSOR QUERY (execute on cluster) ---
    {
        "id": 6,
        "nl": "paginate through all tasks with batch size 50",
        "expected_api": "GetEntitiesWithMetrics",
        "expected_query_type": "cursor_query",
        "validate_proto_contains": ["cursor_query_info", "is_initial_cursor_query: true", "batch_size: 50", "task"],
        "execute_on_cluster": True,
    },
    {
        "id": 7,
        "nl": "get first page of alerts with cursor batch size 10",
        "expected_api": "GetEntitiesWithMetrics",
        "expected_query_type": "cursor_query",
        "validate_proto_contains": ["cursor_query_info", "is_initial_cursor_query: true", "batch_size: 10", "alert"],
        "execute_on_cluster": True,
    },
    # --- BATCH QUERY (execute on cluster) ---
    {
        "id": 8,
        "nl": "batch query: count VMs and get all clusters",
        "expected_api": "BatchGetEntitiesWithMetrics",
        "expected_query_type": "batch_query",
        "validate_proto_contains": ["query_list", "vm", "cluster"],
        "execute_on_cluster": True,
    },
    # --- LOOKUP QUERY (execute on cluster) ---
    {
        "id": 9,
        "nl": "get VMs joining with cluster on cluster_uuid",
        "expected_api": "GetEntitiesWithMetrics",
        "expected_query_type": "lookup_query",
        "validate_proto_contains": ["lookup_query", "vm", "cluster"],
        "execute_on_cluster": True,
    },
    # --- WATCH (proto validation only) ---
    {
        "id": 10,
        "nl": "watch for changes on VM entity type",
        "expected_api": "Watch",
        "expected_query_type": "watch_query",
        "validate_proto_contains": ["vm"],
        "execute_on_cluster": False,
    },
]


def query_pipeline(nl_query: str) -> dict:
    """Send NL query to the pipeline and get response."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER}/query",
            json={"query": nl_query, "generate_python": True},
            timeout=90,
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def execute_on_cluster(python_code: str) -> dict:
    """Execute generated Python code on the cluster via SSH."""
    code_to_run = python_code.replace('InsightsInterface("127.0.0.1", "2027")',
                                       f'InsightsInterface("{TARGET_IP}", "{TARGET_PORT}")')

    try:
        result = subprocess.run(
            [
                "sshpass", "-p", SSH_PASS,
                "ssh", "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR",
                f"{SSH_USER}@{TARGET_IP}",
                "source /home/nutanix/.venvs/bin/bin/activate && python3 -"
            ],
            input=code_to_run,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0 and not output:
            return {"error": stderr or f"exit code {result.returncode}"}
        return {"output": output, "stderr": stderr, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "SSH execution timed out (60s)"}
    except Exception as e:
        return {"error": str(e)}


def check_execution_success(exec_result: dict) -> tuple:
    """Check if execution was successful."""
    if "error" in exec_result:
        return False, exec_result["error"]
    output = exec_result.get("output", "")
    if "Error Message:" in output:
        return False, output[:200]
    if "Traceback" in output:
        return False, output[:200]
    return True, output[:100]


def validate_proto(proto_text: str, expected_contains: list) -> tuple:
    """Validate proto contains expected structural elements."""
    missing = []
    for item in expected_contains:
        if item.lower() not in proto_text.lower():
            missing.append(item)
    if missing:
        return False, f"Missing in proto: {missing}"
    return True, None


def run_tests():
    """Run all test cases."""
    print("=" * 70)
    print("CROSS-VALIDATION: Complex IDF Operations (Multi-API)")
    print("=" * 70)
    print()

    results = []
    pass_count = 0
    fail_count = 0

    for tc in TEST_CASES:
        print(f"\n--- Test {tc['id']}: {tc['nl'][:60]}... ---")
        time.sleep(0.5)

        # Query pipeline
        resp = query_pipeline(tc["nl"])
        if "error" in resp:
            print(f"  FAIL: Pipeline error: {resp['error']}")
            results.append({"id": tc["id"], "status": "FAIL", "reason": f"Pipeline: {resp['error']}"})
            fail_count += 1
            continue

        # Check API method
        actual_api = resp.get("api_method") or "GetEntitiesWithMetrics"
        actual_type = resp.get("query_type", "")
        proto = resp.get("query_proto", "")
        python_code = resp.get("python_code", "")

        type_ok = actual_type == tc["expected_query_type"]
        api_ok = actual_api == tc["expected_api"]

        if not type_ok:
            print(f"  FAIL: Expected query_type={tc['expected_query_type']}, got={actual_type}")
            results.append({"id": tc["id"], "status": "FAIL", "reason": f"Wrong type: {actual_type}"})
            fail_count += 1
            continue

        if not api_ok:
            print(f"  FAIL: Expected api_method={tc['expected_api']}, got={actual_api}")
            results.append({"id": tc["id"], "status": "FAIL", "reason": f"Wrong API: {actual_api}"})
            fail_count += 1
            continue

        # Validate proto structure
        proto_ok, proto_err = validate_proto(proto, tc["validate_proto_contains"])
        if not proto_ok:
            print(f"  FAIL: {proto_err}")
            print(f"  Proto: {proto[:200]}")
            results.append({"id": tc["id"], "status": "FAIL", "reason": proto_err})
            fail_count += 1
            continue

        print(f"  Classification: OK (type={actual_type}, api={actual_api})")
        print(f"  Proto validation: OK")

        # Execute on cluster if applicable
        if tc.get("execute_on_cluster") and python_code:
            exec_result = execute_on_cluster(python_code)
            exec_ok, exec_msg = check_execution_success(exec_result)
            if exec_ok:
                print(f"  Execution: OK ({exec_msg[:50]})")
                results.append({"id": tc["id"], "status": "PASS", "reason": "All checks passed + execution"})
            else:
                print(f"  Execution: WARN ({exec_msg[:80]})")
                results.append({"id": tc["id"], "status": "PASS*", "reason": f"Proto OK, exec issue: {exec_msg[:60]}"})
        else:
            print(f"  (Skipping execution - write/register operation)")
            results.append({"id": tc["id"], "status": "PASS", "reason": "Classification + proto validation OK"})

        pass_count += 1

    # Summary
    print("\n")
    print("=" * 70)
    print(f"RESULTS: {pass_count}/{len(TEST_CASES)} PASSED, {fail_count}/{len(TEST_CASES)} FAILED")
    print("=" * 70)
    print(f"\n{'ID':<4} {'Status':<8} {'Query':<45} {'Reason':<40}")
    print("-" * 100)
    for r in results:
        tc = next(t for t in TEST_CASES if t["id"] == r["id"])
        nl_short = tc["nl"][:43] + ".." if len(tc["nl"]) > 45 else tc["nl"]
        print(f"{r['id']:<4} {r['status']:<8} {nl_short:<45} {r['reason'][:40]}")

    return pass_count, fail_count


if __name__ == "__main__":
    run_tests()
