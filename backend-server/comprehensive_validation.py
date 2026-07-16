"""
Comprehensive IDF Query Pipeline Validation.

Tests ALL query types against the AI pipeline and cross-validates on CVM 10.46.30.35.
Covers: GetEntitiesWithMetrics (all patterns), UpdateEntity, DeleteEntity,
RegisterEntityTypes, RegisterMetricTypes, BatchGetEntitiesWithMetrics,
Watch (register/unregister/get), Cursor queries, SpotlightSearch, GetEntities,
GetMetricData, PutMetricData.

Each test:
1. Sends NL query to AI pipeline
2. Validates proto structure
3. Validates python code structure
4. Executes on CVM and checks for errors
"""

import json
import re
import subprocess
import sys
import requests

PIPELINE_URL = "http://127.0.0.1:8000/query"
CVM_IP = "10.46.30.35"
CVM_USER = "nutanix"
CVM_PASS = "nutanix/4u"

# ============================================================================
# TEST CASES - Organized by API type
# ============================================================================

TEST_CASES = [
    # =========================================================================
    # GROUP 1: GetEntitiesWithMetrics - Simple fetch
    # =========================================================================
    {
        "id": "G1_01",
        "query": "get all VMs",
        "expect_api": None,  # template path, no api_method
        "expect_in_proto": ["entity_type_name: \"vm\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G1_02",
        "query": "get all disks",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"disk\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G1_03",
        "query": "get all clusters",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"cluster\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G1_04",
        "query": "get all hosts",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"node\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G1_05",
        "query": "list all tasks",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"task\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G1_06",
        "query": "show all alerts",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"alert\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 2: GetEntitiesWithMetrics - Filters (equality, comparison, IN, kLike)
    # =========================================================================
    {
        "id": "G2_01",
        "query": "get VMs where power_state = on",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "power_state", "kEQ", "str_value"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G2_02",
        "query": "get VMs where num_vcpus > 2",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "num_vcpus", "kGT", "int64_value: 2"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G2_03",
        "query": "get VMs where memory_mb >= 4096",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "memory_mb", "kGE", "int64_value: 4096"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G2_04",
        "query": "get VMs where hypervisor_type = kKvm",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "hypervisor_type", "kEQ"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G2_05",
        "query": "get VMs where vm_name contains test",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "vm_name", "kLike", ".*test.*"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G2_06",
        "query": "get tasks where status IN kSucceeded, kFailed",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "status", "kIN", "str_list"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G2_07",
        "query": "get VMs where num_vcpus != 1",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "num_vcpus", "kNE"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 3: GetEntitiesWithMetrics - Compound filters (AND/OR)
    # =========================================================================
    {
        "id": "G3_01",
        "query": "get VMs where power_state = on AND num_vcpus > 2",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "kAnd", "power_state", "num_vcpus"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G3_02",
        "query": "get VMs where power_state = on OR power_state = off",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "kOr", "power_state"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 4: GetEntitiesWithMetrics - Sort + Limit
    # =========================================================================
    {
        "id": "G4_01",
        "query": "get top 5 VMs sorted by num_vcpus descending",
        "expect_api": None,
        "expect_in_proto": ["raw_sort_order", "sort_column", "num_vcpus", "kDescending", "raw_limit", "limit: 5"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G4_02",
        "query": "get top 10 tasks sorted by created_timestamp ascending",
        "expect_api": None,
        "expect_in_proto": ["raw_sort_order", "sort_column", "raw_limit", "limit: 10"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G4_03",
        "query": "get first 3 alerts sorted by severity descending",
        "expect_api": None,
        "expect_in_proto": ["raw_sort_order", "severity", "kDescending", "raw_limit", "limit: 3"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 5: GetEntitiesWithMetrics - Group By + Aggregation
    # =========================================================================
    {
        "id": "G5_01",
        "query": "count VMs grouped by power_state",
        "expect_api": None,
        "expect_in_proto": ["group_by", "group_by_column: \"power_state\""],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G5_02",
        "query": "count all VMs",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"vm\"", "raw_limit", "limit: 0"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G5_03",
        "query": "get average memory_mb of VMs grouped by cluster",
        "expect_api": None,
        "expect_in_proto": ["group_by", "aggregate_columns", "kAvg", "memory_mb"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G5_04",
        "query": "get sum of num_vcpus for all VMs",
        "expect_api": None,
        "expect_in_proto": ["aggregate_columns", "kSum", "num_vcpus"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 6: GetEntitiesWithMetrics - Cursor queries (pagination)
    # =========================================================================
    {
        "id": "G6_01",
        "query": "get VMs with pagination batch size 10",
        "expect_api": None,
        "expect_in_proto": ["cursor_query_info", "is_initial_cursor_query: true", "batch_size: 10"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 7: GetEntitiesWithMetrics - Evictable entity rules
    # =========================================================================
    {
        "id": "G7_01",
        "query": "get all alerts sorted by severity",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"alert\"", "raw_limit"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G7_02",
        "query": "get all events",
        "expect_api": None,
        "expect_in_proto": ["entity_type_name: \"event\"", "raw_limit"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 8: UpdateEntity (CAS)
    # =========================================================================
    {
        "id": "G8_01",
        "query": "update VM with entity_id abc123 set attribute vm_name to test_vm with cas_value 5",
        "expect_api": "UpdateEntity",
        "expect_in_proto": ["entity_guid", "entity_type_name", "entity_id", "attribute_data_arg_list", "cas_value"],
        "expect_in_code": ["UpdateEntity"],
        "execute_on_cvm": False,
    },
    {
        "id": "G8_02",
        "query": "update disk entity id disk001 set attribute storage_tier to SSD",
        "expect_api": "UpdateEntity",
        "expect_in_proto": ["entity_guid", "entity_type_name", "entity_id", "attribute_data_arg_list"],
        "expect_in_code": ["UpdateEntity"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 9: DeleteEntity
    # =========================================================================
    {
        "id": "G9_01",
        "query": "delete VM entity with id vm-uuid-001",
        "expect_api": "DeleteEntity",
        "expect_in_proto": ["entity_guid", "entity_type_name", "entity_id"],
        "expect_in_code": ["DeleteEntity"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 10: RegisterEntityTypes
    # =========================================================================
    {
        "id": "G10_01",
        "query": "register a new entity type called custom_sensor with parent node",
        "expect_api": "RegisterEntityTypes",
        "expect_in_proto": ["entity_type_info_list", "entity_type_name"],
        "expect_in_code": ["RegisterEntityTypes"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 11: RegisterMetricTypes
    # =========================================================================
    {
        "id": "G11_01",
        "query": "register a new attribute temperature for entity type vm",
        "expect_api": "RegisterMetricTypes",
        "expect_in_proto": ["metric_type_list", "metric_name", "entity_type_name", "is_attribute: true"],
        "expect_in_code": ["RegisterMetricTypes"],
        "execute_on_cvm": False,
    },
    {
        "id": "G11_02",
        "query": "register metric cpu_usage for entity type node with aggregation sum",
        "expect_api": "RegisterMetricTypes",
        "expect_in_proto": ["metric_type_list", "metric_name", "entity_type_name"],
        "expect_in_code": ["RegisterMetricTypes"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 12: BatchGetEntitiesWithMetrics
    # =========================================================================
    {
        "id": "G12_01",
        "query": "batch query: get all VMs and get all disks",
        "expect_api": "BatchGetEntitiesWithMetrics",
        "expect_in_proto": ["query_list"],
        "expect_in_code": ["BatchGetEntitiesWithMetrics"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 13: Watch - Register (composite)
    # =========================================================================
    {
        "id": "G13_01",
        "query": "register a watch on VM for create, update and delete events",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list", "entity_type_name", "watch_type_mask"],
        "expect_in_code": ["composite_watch_on_entities_of_type"],
        "execute_on_cvm": False,
    },
    {
        "id": "G13_02",
        "query": "watch for new alerts being created",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list", "entity_type_name: \"alert\""],
        "expect_in_code": ["watch_new_entities_of_type"],
        "execute_on_cvm": False,
    },
    {
        "id": "G13_03",
        "query": "watch for VM updates",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list", "entity_type_name: \"vm\""],
        "expect_in_code": ["watch_updated_entities_of_type"],
        "execute_on_cvm": False,
    },
    {
        "id": "G13_04",
        "query": "watch for deleted tasks",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list", "entity_type_name: \"task\""],
        "expect_in_code": ["watch_deleted_entities_of_type"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 14: Watch - Unregister/Delete
    # =========================================================================
    {
        "id": "G14_01",
        "query": "delete the watch named watch_vm_all",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list"],
        "expect_in_code": ["unregister_composite_watch_on_entities_of_type", "stop"],
        "execute_on_cvm": False,
    },
    {
        "id": "G14_02",
        "query": "unregister watch client for VMs",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list"],
        "expect_in_code": ["unregister_composite_watch_on_entities_of_type"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 15: Watch - Get/List
    # =========================================================================
    {
        "id": "G15_01",
        "query": "get watch status for watch_vm_all",
        "expect_api": "Watch",
        "expect_in_proto": ["watch_list"],
        "expect_in_code": ["GetFiredWatchList"],
        "execute_on_cvm": False,
    },

    # =========================================================================
    # GROUP 16: GetEntitiesWithMetrics - kExists operator
    # =========================================================================
    {
        "id": "G16_01",
        "query": "get VMs where attribute ip_address exists",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "ip_address", "kExists"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 17: GetEntitiesWithMetrics - Multiple raw_columns
    # =========================================================================
    {
        "id": "G17_01",
        "query": "get VM name, num_vcpus, memory_mb for all VMs",
        "expect_api": None,
        "expect_in_proto": ["raw_columns", "vm_name"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },

    # =========================================================================
    # GROUP 18: Combined complex queries
    # =========================================================================
    {
        "id": "G18_01",
        "query": "get top 5 VMs where power_state = on sorted by num_vcpus descending",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "power_state", "raw_sort_order", "num_vcpus", "kDescending", "raw_limit", "limit: 5"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
    {
        "id": "G18_02",
        "query": "count tasks where status = kSucceeded grouped by component",
        "expect_api": None,
        "expect_in_proto": ["where_clause", "status", "group_by", "group_by_column"],
        "expect_in_code": ["GetEntitiesWithMetrics"],
        "execute_on_cvm": True,
    },
]


def call_pipeline(query: str) -> dict:
    """Call the AI pipeline and return full response."""
    try:
        resp = requests.post(
            PIPELINE_URL,
            json={"query": query, "generate_python": True},
            timeout=90,
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def execute_on_cvm(python_code: str, timeout: int = 30) -> dict:
    """Execute Python code on CVM via SSH."""
    code = python_code.replace('InsightsInterface("127.0.0.1"',
                               'InsightsInterface("127.0.0.1"')
    code = re.sub(
        r'InsightsInterface\("[^"]*",\s*"[^"]*"\)',
        'InsightsInterface("127.0.0.1", "2027")',
        code
    )
    if 'sys.path.insert' not in code:
        code = 'import sys\nsys.path.insert(0, "/home/nutanix/cluster/bin")\n' + code
    if 'gflags.FLAGS(sys.argv)' not in code and 'gflags.FLAGS([])' in code:
        code = code.replace('gflags.FLAGS([])', 'gflags.FLAGS(sys.argv)')

    cmd = [
        "sshpass", "-p", CVM_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR",
        f"{CVM_USER}@{CVM_IP}",
        "source /home/nutanix/.venvs/bin/bin/activate && python3 -"
    ]
    try:
        result = subprocess.run(
            cmd, input=code, capture_output=True, text=True, timeout=timeout
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        stderr_clean = "\n".join(
            l for l in stderr.split("\n")
            if not any(x in l for x in ["ERROR:root", "RuntimeWarning", "UnparsedFlag", "WARNING:root"])
        ).strip()
        if result.returncode != 0 and stderr_clean:
            return {"success": False, "error": stderr_clean[:500], "output": stdout[:500]}
        return {"success": True, "output": stdout[:1000]}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def validate_test(test: dict) -> dict:
    """Run a single test case and return results."""
    result = {
        "id": test["id"],
        "query": test["query"],
        "passed": True,
        "failures": [],
    }

    resp = call_pipeline(test["query"])
    if "error" in resp:
        result["passed"] = False
        result["failures"].append(f"Pipeline error: {resp['error']}")
        return result

    proto = resp.get("query_proto", "")
    code = resp.get("python_code", "")
    api_method = resp.get("api_method")

    # Check api_method
    if test["expect_api"] is not None:
        if api_method != test["expect_api"]:
            result["passed"] = False
            result["failures"].append(
                f"api_method: expected '{test['expect_api']}', got '{api_method}'"
            )

    # Validate proto content
    for expected in test.get("expect_in_proto", []):
        if expected not in proto:
            result["passed"] = False
            result["failures"].append(f"Proto missing: '{expected}'")

    # Validate code content
    for expected in test.get("expect_in_code", []):
        if expected not in code:
            result["passed"] = False
            result["failures"].append(f"Code missing: '{expected}'")

    # Execute on CVM if requested
    if test.get("execute_on_cvm") and code:
        exec_result = execute_on_cvm(code)
        if not exec_result["success"]:
            result["passed"] = False
            result["failures"].append(f"CVM exec error: {exec_result['error'][:200]}")
        else:
            result["cvm_output"] = exec_result["output"][:200]

    result["proto_snippet"] = proto[:200]
    result["code_snippet"] = code[:150] if code else "(no code)"
    return result


def main():
    print("=" * 70)
    print("COMPREHENSIVE IDF QUERY PIPELINE VALIDATION")
    print(f"Pipeline: {PIPELINE_URL}")
    print(f"CVM: {CVM_IP}")
    print(f"Total tests: {len(TEST_CASES)}")
    print("=" * 70)
    print()

    results = []
    passed = 0
    failed = 0
    errors = []

    for i, test in enumerate(TEST_CASES):
        sys.stdout.write(f"[{i+1}/{len(TEST_CASES)}] {test['id']}: {test['query'][:50]}...")
        sys.stdout.flush()

        r = validate_test(test)
        results.append(r)

        if r["passed"]:
            passed += 1
            print(" PASS")
        else:
            failed += 1
            print(" FAIL")
            for f in r["failures"]:
                print(f"       -> {f}")
            errors.append(r)

    print()
    print("=" * 70)
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed, {failed} failed")
    print(f"Accuracy: {passed/len(TEST_CASES)*100:.1f}%")
    print("=" * 70)

    if errors:
        print("\nFAILED TESTS:")
        print("-" * 70)
        for e in errors:
            print(f"\n  {e['id']}: {e['query']}")
            for f in e["failures"]:
                print(f"    - {f}")
            print(f"    Proto: {e.get('proto_snippet', 'N/A')[:100]}")

    # Save detailed results
    with open("/tmp/validation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nDetailed results saved to /tmp/validation_results.json")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
