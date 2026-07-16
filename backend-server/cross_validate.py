"""
Cross-validation script: Tests the AI pipeline against expected correct protos.
Executes both on the target cluster and compares results.
"""
import sys
import os
import time
import re
import requests
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUERY_SERVER = "http://localhost:8000"
TARGET_IP = "10.46.30.35"
TARGET_PORT = "2027"
SSH_USER = "nutanix"
SSH_PASS = "nutanix/4u"

TEST_CASES = [
    {
        "id": 1,
        "nl": "get all VMs",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } query_name: "fetch_all_vms" }',
    },
    {
        "id": 2,
        "nl": "count all disks",
        "expected_proto": 'query { entity_list { entity_type_name: "disk" } flags: 2 query_name: "disk_count" }',
    },
    {
        "id": 3,
        "nl": "VMs where num_vcpus > 4",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { comparison_expr { lhs { leaf { column: "num_vcpus" } } operator: kGT rhs { leaf { value { int64_value: 4 } } } } } query_name: "vms_vcpu_gt_4" }',
    },
    {
        "id": 4,
        "nl": "top 10 VMs sorted by hypervisor_cpu_usage_ppm descending",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } group_by { raw_columns { column: "vm_name" } raw_columns { column: "hypervisor_cpu_usage_ppm" } raw_sort_order { sort_column: "hypervisor_cpu_usage_ppm" sort_order: kDescending } raw_limit { limit: 10 offset: 0 } } query_name: "top_vms_by_cpu" }',
    },
    {
        "id": 5,
        "nl": "group VMs by cluster",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } group_by { group_by_column: "cluster" raw_columns { column: "cluster" } } query_name: "vm_group_by_cluster" }',
    },
    {
        "id": 6,
        "nl": "how many VMs are there",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } flags: 2 query_name: "vm_count" }',
    },
    {
        "id": 7,
        "nl": "VMs with power_state = ON",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { comparison_expr { lhs { leaf { column: "power_state" } } operator: kEQ rhs { leaf { value { str_value: "ON" } } } } } query_name: "powered_on_vms" }',
    },
    {
        "id": 8,
        "nl": "latest 5 alerts",
        "expected_proto": 'query { entity_list { entity_type_name: "alert" } group_by { raw_sort_order { sort_column: "_created_timestamp_usecs_" sort_order: kDescending } raw_limit { limit: 5 offset: 0 } } query_name: "latest_alerts" }',
    },
    {
        "id": 9,
        "nl": "get vm_name and num_vcpus for all VMs sorted by vm_name ascending",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } group_by { raw_columns { column: "vm_name" } raw_columns { column: "num_vcpus" } raw_sort_order { sort_column: "vm_name" sort_order: kAscending } } query_name: "vm_attrs_sorted" }',
    },
    {
        "id": 10,
        "nl": "VMs where memory_size_bytes >= 4294967296",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { comparison_expr { lhs { leaf { column: "memory_size_bytes" } } operator: kGE rhs { leaf { value { int64_value: 4294967296 } } } } } query_name: "vms_memory_ge" }',
    },
    {
        "id": 11,
        "nl": "first 20 clusters",
        "expected_proto": 'query { entity_list { entity_type_name: "cluster" } group_by { raw_limit { limit: 20 offset: 0 } } query_name: "first_20_clusters" }',
    },
    {
        "id": 12,
        "nl": "VMs where vm_name contains test",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { comparison_expr { lhs { leaf { column: "vm_name" } } operator: kLike rhs { leaf { value { str_value: ".*test.*" } } } } } query_name: "vms_name_contains_test" }',
    },
    {
        "id": 13,
        "nl": "VMs where power_state = ON and num_vcpus > 2",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { logical_expr { lhs { comparison_expr { lhs { leaf { column: "power_state" } } operator: kEQ rhs { leaf { value { str_value: "ON" } } } } } logical_operator: kAnd rhs { comparison_expr { lhs { leaf { column: "num_vcpus" } } operator: kGT rhs { leaf { value { int64_value: 2 } } } } } } } query_name: "powered_on_high_cpu" }',
    },
    {
        "id": 14,
        "nl": "get all hosts",
        "expected_proto": 'query { entity_list { entity_type_name: "node" } query_name: "fetch_all_hosts" }',
    },
    {
        "id": 15,
        "nl": "count all VMs grouped by power_state",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } group_by { group_by_column: "power_state" raw_columns { column: "power_state" } } flags: 2 query_name: "vm_count_by_power_state" }',
    },
    {
        "id": 16,
        "nl": "VMs sorted by memory_size_bytes descending limit 5",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } group_by { raw_columns { column: "vm_name" } raw_columns { column: "memory_size_bytes" } raw_sort_order { sort_column: "memory_size_bytes" sort_order: kDescending } raw_limit { limit: 5 offset: 0 } } query_name: "vms_by_memory_desc" }',
    },
    {
        "id": 17,
        "nl": "get all storage_containers",
        "expected_proto": 'query { entity_list { entity_type_name: "storage_container" } query_name: "fetch_all_containers" }',
    },
    {
        "id": 18,
        "nl": "VMs where hypervisor_type = kKvm",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { comparison_expr { lhs { leaf { column: "hypervisor_type" } } operator: kEQ rhs { leaf { value { str_value: "kKvm" } } } } } query_name: "kvm_vms" }',
    },
    {
        "id": 19,
        "nl": "average hypervisor_cpu_usage_ppm of all VMs",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } group_by { aggregate_columns { column: "hypervisor_cpu_usage_ppm" aggregate_operator: kAvg } } query_name: "avg_cpu_usage" }',
    },
    {
        "id": 20,
        "nl": "VMs where vm_name like ntnx",
        "expected_proto": 'query { entity_list { entity_type_name: "vm" } where_clause { comparison_expr { lhs { leaf { column: "vm_name" } } operator: kLike rhs { leaf { value { str_value: ".*ntnx.*" } } } } } query_name: "vms_name_like_ntnx" }',
    },
]


def query_ai_pipeline(nl_query: str) -> dict:
    """Send query to our AI pipeline and get response."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER}/query",
            json={"query": nl_query, "idf_ip": TARGET_IP, "idf_port": TARGET_PORT},
            timeout=90,
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def execute_on_cluster(proto: str) -> dict:
    """Execute a proto query on the target cluster via SSH piping code to stdin."""
    python_code = f"""import sys
sys.path.insert(0, '/home/nutanix/bin')
try:
    import env
    import gflags
    gflags.FLAGS([])
except:
    pass
from google.protobuf.text_format import Merge
from insights_interface.insights_interface_pb2 import GetEntitiesWithMetricsArg
from insights_interface.insights_interface import InsightsInterface, InsightsInterfaceError
insights_interface = InsightsInterface('127.0.0.1', '{TARGET_PORT}')
arg = GetEntitiesWithMetricsArg()
query_text = \"\"\"{proto}\"\"\"
Merge(query_text, arg)
try:
    ret = insights_interface.GetEntitiesWithMetrics(arg)
    result_count = sum(len(g.raw_results) for g in ret.group_results_list)
    group_count = len(ret.group_results_list)
    print('SUCCESS: groups=%d, entities=%d' % (group_count, result_count))
except InsightsInterfaceError as ex:
    print('IDF_ERROR: %s' % ex.message)
except Exception as ex:
    print('ERROR: %s' % str(ex))
"""

    try:
        ssh_cmd = [
            "sshpass", "-p", SSH_PASS,
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=15",
            f"{SSH_USER}@{TARGET_IP}",
            "source /home/nutanix/.venvs/bin/bin/activate && python3 -"
        ]
        result = subprocess.run(
            ssh_cmd, input=python_code, capture_output=True, text=True, timeout=45
        )
        output = result.stdout.strip()
        if output:
            for line in output.split('\n'):
                if line.startswith(('SUCCESS:', 'IDF_ERROR:', 'ERROR:')):
                    return {"output": line, "success": True}
            return {"output": output[-100:], "success": False}
        stderr = result.stderr.strip()
        return {"output": stderr[:100] if stderr else "(no output)", "success": False}
    except subprocess.TimeoutExpired:
        return {"output": "TIMEOUT (45s)", "success": False}
    except Exception as e:
        return {"output": str(e)[:100], "success": False}


def check_structural_match(ai_proto: str, expected_proto: str) -> tuple:
    """Check if AI proto structurally matches expected."""
    issues = []

    expected_entities = re.findall(r'entity_type_name:\s*"([^"]+)"', expected_proto)
    ai_entities = re.findall(r'entity_type_name:\s*"([^"]+)"', ai_proto)
    if set(expected_entities) != set(ai_entities):
        issues.append(f"entity mismatch: want {expected_entities}, got {ai_entities}")

    if 'where_clause' in expected_proto and 'where_clause' not in ai_proto:
        issues.append("missing where_clause")
    if 'where_clause' not in expected_proto and 'where_clause' in ai_proto:
        issues.append("extra where_clause")

    if 'group_by' in expected_proto and 'group_by' not in ai_proto:
        issues.append("missing group_by")

    if 'flags: 2' in expected_proto and 'flags: 2' not in ai_proto:
        issues.append("missing flags: 2 (count)")

    if 'raw_limit' in expected_proto and 'raw_limit' not in ai_proto:
        issues.append("missing raw_limit")

    if 'raw_sort_order' in expected_proto and 'raw_sort_order' not in ai_proto:
        issues.append("missing raw_sort_order")

    if 'logical_expr' in expected_proto and 'logical_expr' not in ai_proto:
        issues.append("missing logical_expr (AND/OR)")

    if 'aggregate_columns' in expected_proto and 'aggregate_columns' not in ai_proto:
        issues.append("missing aggregate_columns")

    expected_ops = re.findall(r'operator:\s*(\w+)', expected_proto)
    ai_ops = re.findall(r'operator:\s*(\w+)', ai_proto)
    if expected_ops and not ai_ops:
        issues.append(f"missing operators: {expected_ops}")
    elif expected_ops and ai_ops:
        for op in expected_ops:
            if op not in ai_ops:
                issues.append(f"wrong/missing operator: {op}")

    if 'query_name' not in ai_proto:
        issues.append("missing query_name")

    if not ai_proto.strip().startswith('query'):
        issues.append("missing query { } wrapper")

    score = max(0, 100 - len(issues) * 15)
    return score, issues


def main():
    print("=" * 90)
    print("IDF AI Query Pipeline - Cross Validation Report")
    print(f"Target Cluster: {TARGET_IP}:{TARGET_PORT}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    print()

    results = []

    for test in TEST_CASES:
        test_id = test["id"]
        nl = test["nl"]
        expected = test["expected_proto"]

        print(f"[{test_id:02d}/{len(TEST_CASES)}] \"{nl}\"")

        # Step 1: Query AI pipeline
        ai_response = query_ai_pipeline(nl)
        ai_proto = ai_response.get("query_proto", "")
        ai_latency = ai_response.get("latency_ms", 0)
        ai_used_template = ai_response.get("used_template", False)

        if "error" in ai_response and not ai_proto:
            print(f"  AI ERROR: {ai_response['error'][:100]}")
            results.append({
                "id": test_id, "nl": nl, "struct_score": 0,
                "ai_exec": "PIPELINE_ERROR", "expected_exec": "N/A",
                "exec_match": False, "latency": 0, "template": False,
                "issues": ["AI pipeline error"]
            })
            continue

        # Step 2: Structural comparison
        score, issues = check_structural_match(ai_proto, expected)

        # Step 3: Execute AI-generated proto on cluster
        ai_exec = execute_on_cluster(ai_proto)

        # Step 4: Execute expected correct proto on cluster
        expected_exec = execute_on_cluster(expected)

        # Step 5: Compare execution results
        ai_out = ai_exec.get("output", "")
        exp_out = expected_exec.get("output", "")

        exec_match = False
        if ai_out.startswith("SUCCESS") and exp_out.startswith("SUCCESS"):
            ai_counts = re.findall(r'groups=(\d+), entities=(\d+)', ai_out)
            exp_counts = re.findall(r'groups=(\d+), entities=(\d+)', exp_out)
            if ai_counts and exp_counts:
                exec_match = (ai_counts[0] == exp_counts[0])
        elif ai_out.startswith("IDF_ERROR") and exp_out.startswith("IDF_ERROR"):
            exec_match = True

        results.append({
            "id": test_id,
            "nl": nl,
            "struct_score": score,
            "ai_exec": ai_out[:80],
            "expected_exec": exp_out[:80],
            "exec_match": exec_match,
            "latency": ai_latency,
            "template": ai_used_template,
            "issues": issues,
            "ai_proto_short": ai_proto[:120] if ai_proto else "(empty)",
        })

        status_emoji = "PASS" if exec_match and score >= 70 else "FAIL"
        print(f"  Struct: {score}% | ExecMatch: {exec_match} | {ai_latency:.0f}ms | {status_emoji}")
        print(f"  AI  -> {ai_out[:70]}")
        print(f"  Exp -> {exp_out[:70]}")
        if issues:
            print(f"  Issues: {', '.join(issues[:3])}")
        print()

    # Print final summary table
    print()
    print("=" * 90)
    print("FINAL COMPARISON TABLE")
    print("=" * 90)
    header = f"{'#':<3} {'Query':<40} {'Struct%':<8} {'AI Result':<30} {'Expected Result':<30} {'Match':<6} {'ms':<8} {'Status'}"
    print(header)
    print("-" * 90)

    total_pass = 0
    total_struct_score = 0
    total_exec_match = 0

    for r in results:
        nl_short = r["nl"][:37] + "..." if len(r["nl"]) > 37 else r["nl"]
        ai_exec_short = r["ai_exec"][:27] + "..." if len(r["ai_exec"]) > 27 else r["ai_exec"]
        exp_exec_short = r["expected_exec"][:27] + "..." if len(r["expected_exec"]) > 27 else r["expected_exec"]

        overall_pass = r["exec_match"] and r["struct_score"] >= 70
        status = "PASS" if overall_pass else "FAIL"
        if overall_pass:
            total_pass += 1
        if r["exec_match"]:
            total_exec_match += 1
        total_struct_score += r["struct_score"]

        print(f"{r['id']:<3} {nl_short:<40} {r['struct_score']:<8} {ai_exec_short:<30} {exp_exec_short:<30} {str(r['exec_match']):<6} {r['latency']:<8.0f} {status}")

    print("-" * 90)
    n = len(results)
    avg_score = total_struct_score / n if n else 0
    avg_latency = sum(r['latency'] for r in results) / n if n else 0
    tmpl_rate = sum(1 for r in results if r['template'])

    print("\nOVERALL ACCURACY")
    print(f"  Structural accuracy (proto shape): {avg_score:.1f}%")
    print(f"  Execution match (same results):    {total_exec_match}/{n} ({total_exec_match/n*100:.0f}%)")
    print(f"  Full pass (struct >= 70 + match):   {total_pass}/{n} ({total_pass/n*100:.0f}%)")
    print(f"  Template bypass rate:              {tmpl_rate}/{n} ({tmpl_rate/n*100:.0f}%)")
    print(f"  Average latency:                   {avg_latency:.0f}ms")

    # Detailed failures
    failures = [r for r in results if not (r["exec_match"] and r["struct_score"] >= 70)]
    if failures:
        print(f"\n{'='*90}")
        print(f"FAILED TESTS ({len(failures)} failures)")
        print(f"{'='*90}")
        for r in failures:
            print(f"\n  Test {r['id']}: \"{r['nl']}\"")
            print(f"    Struct Score: {r['struct_score']}%")
            print(f"    Issues: {', '.join(r['issues']) if r['issues'] else 'none (execution mismatch only)'}")
            print(f"    AI Execution:       {r['ai_exec']}")
            print(f"    Expected Execution: {r['expected_exec']}")
            print(f"    AI Proto (start):   {r.get('ai_proto_short', 'N/A')}")

    # Return results for programmatic use
    return results


if __name__ == "__main__":
    main()
