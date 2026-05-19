"""
Generate ~1000 validation questions from nutest insight test patterns.

Reads test files from:
  /Users/nandish.chokshi/Nutanix_New/nutest-py3-tests/testcases/insights/
  /Users/nandish.chokshi/Nutanix_New/nutest-py3-tests/workflows/insights/

Extracts IDF query patterns (RPCs, entity types, filters, sorts, watches, etc.)
and generates natural language questions that should produce those queries.

Output: validation_questions.json
"""

import json
import os
import re
import sys

TEST_DIR = "/Users/nandish.chokshi/Nutanix_New/nutest-py3-tests/testcases/insights"
WORKFLOW_DIR = "/Users/nandish.chokshi/Nutanix_New/nutest-py3-tests/workflows/insights"

# Patterns to extract from test files
RPC_PATTERN = re.compile(r'execute_rpc\(\s*["\'](\w+)["\']\s*,\s*(.+?)(?:\)|$)', re.DOTALL)
PROTO_PATTERN = re.compile(r'"""(.+?)"""', re.DOTALL)
GET_ENTITIES_PATTERN = re.compile(r'get_entities_with_metric_data\((.+?)\)', re.DOTALL)
UPDATE_PATTERN = re.compile(r'update_entities\((.+?)\)', re.DOTALL)
DELETE_PATTERN = re.compile(r'delete_entities\((.+?)\)', re.DOTALL)
BATCH_UPDATE_PATTERN = re.compile(r'batch_update\((.+?)\)', re.DOTALL)
BATCH_DELETE_PATTERN = re.compile(r'batch_delete\((.+?)\)', re.DOTALL)
PUT_METRIC_PATTERN = re.compile(r'put_metric\((.+?)\)', re.DOTALL)
WATCH_PATTERN = re.compile(r'watch_(\w+)\((.+?)\)', re.DOTALL)
SEARCH_PATTERN = re.compile(r'search_(\w+)\((.+?)\)', re.DOTALL)


def scan_files():
    """Scan test and workflow files for query patterns."""
    patterns_found = {
        "register_entity_types": [],
        "register_metric_types": [],
        "get_entities_with_metrics": [],
        "update_entity": [],
        "delete_entity": [],
        "batch_update": [],
        "batch_delete": [],
        "put_metric": [],
        "watch": [],
        "search": [],
        "where_clause": [],
        "sorting": [],
        "aggregation": [],
        "cursor_query": [],
        "entity_types_used": set(),
        "attributes_used": set(),
        "operators_used": set(),
    }

    all_files = []
    for root, dirs, files in os.walk(TEST_DIR):
        for f in files:
            if f.endswith(".py"):
                all_files.append(os.path.join(root, f))
    for root, dirs, files in os.walk(WORKFLOW_DIR):
        for f in files:
            if f.endswith(".py"):
                all_files.append(os.path.join(root, f))

    print(f"Scanning {len(all_files)} files...")

    for filepath in all_files:
        try:
            with open(filepath, "r", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        # Extract entity types used
        for m in re.finditer(r'entity_type(?:_name)?\s*[:=]\s*["\'](\w+)["\']', content):
            patterns_found["entity_types_used"].add(m.group(1))

        # Extract attributes
        for m in re.finditer(r"data_map\s*=\s*\{(.+?)\}", content, re.DOTALL):
            for attr in re.finditer(r"'(\w+)'", m.group(1)):
                patterns_found["attributes_used"].add(attr.group(1))

        # Extract operators
        for op in ["kEQ", "kNE", "kLT", "kLE", "kGT", "kGE", "kLike", "kIN",
                   "kExists", "kAnd", "kOr", "kSum", "kAvg", "kCount", "kMin", "kMax"]:
            if op in content:
                patterns_found["operators_used"].add(op)

        # Check for specific patterns
        if "where" in content.lower() and "where_clause" in content:
            patterns_found["where_clause"].append(filepath)
        if "raw_sort_order" in content or "group_sort_order" in content:
            patterns_found["sorting"].append(filepath)
        if "aggregate" in content or "kSum" in content or "kAvg" in content:
            patterns_found["aggregation"].append(filepath)
        if "cursor_query" in content or "is_initial_cursor_query" in content:
            patterns_found["cursor_query"].append(filepath)
        if "watch" in content.lower():
            patterns_found["watch"].append(filepath)
        if "search" in content.lower() and "spotlight" in content.lower():
            patterns_found["search"].append(filepath)

    # Convert sets to lists for JSON
    patterns_found["entity_types_used"] = sorted(patterns_found["entity_types_used"])
    patterns_found["attributes_used"] = sorted(patterns_found["attributes_used"])
    patterns_found["operators_used"] = sorted(patterns_found["operators_used"])

    print(f"Entity types found: {len(patterns_found['entity_types_used'])}")
    print(f"Attributes found: {len(patterns_found['attributes_used'])}")
    print(f"Operators found: {len(patterns_found['operators_used'])}")
    print(f"Files with where clauses: {len(patterns_found['where_clause'])}")
    print(f"Files with sorting: {len(patterns_found['sorting'])}")
    print(f"Files with watches: {len(patterns_found['watch'])}")

    return patterns_found


def generate_questions(patterns):
    """Generate comprehensive NL questions covering all IDF query patterns."""
    questions = []
    qid = 0

    # =================================================================
    # SECTION 1: GetEntitiesWithMetrics - Basic reads
    # =================================================================
    entity_types = ["vm", "node", "cluster", "disk", "container",
                    "volume_group", "storage_pool", "protection_domain",
                    "virtual_disk", "snapshot", "network", "subnet",
                    "image", "category", "project", "ngt"]

    for et in entity_types:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": f"get all {et} entities",
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": ["entity_type_name", et],
            "category": "basic_read"
        })
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": f"show all {et}s",
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": ["entity_type_name", et],
            "category": "basic_read"
        })

    # Alternative phrasings for basic reads
    basic_phrasings = [
        ("list all VMs on the cluster", "vm"),
        ("fetch all virtual machines", "vm"),
        ("display all disks", "disk"),
        ("retrieve all nodes", "node"),
        ("get all hosts in the system", "node"),
        ("show me all storage containers", "container"),
        ("get all volume groups", "volume_group"),
        ("list protection domains", "protection_domain"),
        ("show snapshots", "snapshot"),
        ("get all network interfaces", "network"),
        ("list all subnets", "subnet"),
        ("show all images available", "image"),
        ("get all alerts", "alert"),
        ("list recent events", "event"),
        ("show all tasks", "task"),
        ("get all categories", "category"),
    ]
    for query, et in basic_phrasings:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": ["entity_type_name"],
            "category": "basic_read"
        })

    # =================================================================
    # SECTION 2: Where clause - EQ operator
    # =================================================================
    eq_queries = [
        ("get VMs where power_state equals on", "vm", ["where_clause", "power_state", "kEQ"]),
        ("show VMs with power_state = off", "vm", ["where_clause", "power_state", "kEQ"]),
        ("find nodes where hypervisor_type = kKvm", "node", ["where_clause", "hypervisor_type", "kEQ"]),
        ("get clusters where version = 5.0.1", "cluster", ["where_clause", "version", "kEQ"]),
        ("show disks where storage_tier = SSD", "disk", ["where_clause", "storage_tier", "kEQ"]),
        ("find VMs where is_cvm = 0", "vm", ["where_clause", "is_cvm", "kEQ"]),
        ("get nodes where node_status = normal", "node", ["where_clause", "node_status", "kEQ"]),
        ("list containers where container_name = default", "container", ["where_clause", "container_name", "kEQ"]),
        ("get alerts where severity = critical", "alert", ["where_clause", "severity", "kEQ"]),
        ("show tasks where status = completed", "task", ["where_clause", "status", "kEQ"]),
        ("find VMs with memory_mb = 4096", "vm", ["where_clause", "memory_mb", "kEQ"]),
        ("get clusters where hypervisor_types = ESXi", "cluster", ["where_clause", "hypervisor_types", "kEQ"]),
        ("show VMs where num_vcpus = 4", "vm", ["where_clause", "num_vcpus", "kEQ"]),
        ("list nodes where hypervisor_type equals kVMWare", "node", ["where_clause", "hypervisor_type", "kEQ"]),
        ("get VMs with vm_name = production-vm-01", "vm", ["where_clause", "vm_name", "kEQ"]),
    ]
    for query, et, must_have in eq_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_eq"
        })

    # =================================================================
    # SECTION 3: Where clause - Comparison operators (GT, GE, LT, LE, NE)
    # =================================================================
    comparison_queries = [
        ("get VMs where memory_mb > 4096", "vm", ["where_clause", "memory_mb", "kGT"]),
        ("show VMs with memory_mb greater than 8192", "vm", ["where_clause", "memory_mb", "kGT"]),
        ("find VMs where num_vcpus >= 4", "vm", ["where_clause", "num_vcpus", "kGE"]),
        ("get VMs where num_vcpus less than 8", "vm", ["where_clause", "num_vcpus", "kLT"]),
        ("show VMs with memory_mb <= 2048", "vm", ["where_clause", "memory_mb", "kLE"]),
        ("find nodes where num_vms > 10", "node", ["where_clause", "num_vms", "kGT"]),
        ("get disks where capacity_bytes >= 1000000000", "disk", ["where_clause", "capacity_bytes", "kGE"]),
        ("show VMs where num_vcpus != 2", "vm", ["where_clause", "num_vcpus", "kNE"]),
        ("find clusters where num_nodes > 3", "cluster", ["where_clause", "num_nodes", "kGT"]),
        ("get alerts where check.score >= 76", "alert", ["where_clause", "check.score", "kGE"]),
        ("show alerts where check.score < 26", "alert", ["where_clause", "check.score", "kLT"]),
        ("get VMs where disk_capacity > 500", "vm", ["where_clause", "disk_capacity", "kGT"]),
        ("find nodes with cpu_usage_ppm greater than 800000", "node", ["where_clause", "cpu_usage_ppm", "kGT"]),
        ("show containers where usage_bytes > 1073741824", "container", ["where_clause", "usage_bytes", "kGT"]),
        ("get VMs where memory_usage_ppm >= 900000", "vm", ["where_clause", "memory_usage_ppm", "kGE"]),
    ]
    for query, et, must_have in comparison_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_comparison"
        })

    # =================================================================
    # SECTION 4: Where clause - kLike (regex/contains)
    # =================================================================
    like_queries = [
        ("get VMs where vm_name contains test", "vm", ["where_clause", "vm_name", "kLike"]),
        ("find VMs with name matching production", "vm", ["where_clause", "vm_name", "kLike"]),
        ("show nodes where node_name contains HOST", "node", ["where_clause", "node_name", "kLike"]),
        ("get clusters where cluster_name contains TEST", "cluster", ["where_clause", "cluster_name", "kLike"]),
        ("find VMs where vm_name matches .*[p|P][c|C].*", "vm", ["where_clause", "vm_name", "kLike"]),
        ("show disks where disk_label contains ssd", "disk", ["where_clause", "disk_label", "kLike"]),
        ("get nodes with hostname containing ntnx", "node", ["where_clause", "kLike"]),
        ("find VMs where name starts with prod", "vm", ["where_clause", "kLike"]),
        ("show clusters where name contains nutanix", "cluster", ["where_clause", "kLike"]),
        ("get alerts where message contains timeout", "alert", ["where_clause", "kLike"]),
        ("find VMs with vm_name like .*dev.*", "vm", ["where_clause", "vm_name", "kLike"]),
        ("show nodes where node_name matches Block-1", "node", ["where_clause", "node_name", "kLike"]),
        ("get VMs where vm_name contains PrismCentral", "vm", ["where_clause", "vm_name", "kLike"]),
        ("find containers where name contains default", "container", ["where_clause", "kLike"]),
        ("show clusters with version containing 5.0", "cluster", ["where_clause", "version", "kLike"]),
    ]
    for query, et, must_have in like_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_like"
        })

    # =================================================================
    # SECTION 5: Compound where clauses (AND/OR)
    # =================================================================
    compound_queries = [
        ("get VMs where power_state = on and is_cvm = 0", "vm",
         ["where_clause", "power_state", "is_cvm"]),
        ("show VMs where memory_mb > 4096 and num_vcpus >= 4", "vm",
         ["where_clause", "memory_mb", "num_vcpus"]),
        ("find nodes where hypervisor_type = kKvm or hypervisor_type = kVMWare", "node",
         ["where_clause", "hypervisor_type"]),
        ("get VMs where power_state = on or power_state = off", "vm",
         ["where_clause", "power_state"]),
        ("show clusters where version = 5.0.1 and hypervisor_types = ESXi", "cluster",
         ["where_clause", "version", "hypervisor_types"]),
        ("find alerts where severity = critical and check.score >= 76", "alert",
         ["where_clause", "severity", "check.score"]),
        ("get VMs where is_cvm = 0 and vm_name contains PC", "vm",
         ["where_clause", "is_cvm", "vm_name"]),
        ("show nodes where num_vms > 5 and hypervisor_type = kKvm", "node",
         ["where_clause", "num_vms", "hypervisor_type"]),
        ("find disks where storage_tier = SSD and capacity_bytes > 1000000000", "disk",
         ["where_clause", "storage_tier", "capacity_bytes"]),
        ("get VMs where memory_mb >= 2048 and memory_mb <= 8192", "vm",
         ["where_clause", "memory_mb"]),
        ("show tasks where status = running or status = queued", "task",
         ["where_clause", "status"]),
        ("find clusters where num_nodes >= 3 and version contains 6.", "cluster",
         ["where_clause", "num_nodes", "version"]),
        ("get VMs where power_state = on and num_vcpus > 2 and memory_mb >= 4096", "vm",
         ["where_clause", "power_state", "num_vcpus"]),
        ("show nodes where cpu_usage_ppm > 500000 or memory_usage_ppm > 800000", "node",
         ["where_clause"]),
        ("find alerts where check.score >= 26 and check.score < 76", "alert",
         ["where_clause", "check.score"]),
    ]
    for query, et, must_have in compound_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_compound"
        })

    # =================================================================
    # SECTION 6: Sorting (raw_sort_order)
    # =================================================================
    sort_queries = [
        ("get top 5 VMs sorted by num_vcpus descending", "vm",
         ["raw_sort_order", "num_vcpus", "kDescending"]),
        ("show VMs sorted by memory_mb ascending", "vm",
         ["raw_sort_order", "memory_mb", "kAscending"]),
        ("list top 10 nodes by cpu_usage_ppm descending", "node",
         ["raw_sort_order", "cpu_usage_ppm", "kDescending"]),
        ("get disks sorted by capacity_bytes descending limit 5", "disk",
         ["raw_sort_order", "capacity_bytes", "kDescending"]),
        ("show VMs ordered by vm_name ascending", "vm",
         ["raw_sort_order", "vm_name", "kAscending"]),
        ("find top 3 clusters by num_nodes descending", "cluster",
         ["raw_sort_order", "num_nodes", "kDescending"]),
        ("get VMs sorted by creation_time descending limit 10", "vm",
         ["raw_sort_order", "creation_time", "kDescending"]),
        ("show alerts sorted by severity descending", "alert",
         ["raw_sort_order", "severity", "kDescending"]),
        ("list nodes sorted by node_name ascending", "node",
         ["raw_sort_order", "node_name", "kAscending"]),
        ("get top 20 VMs by memory_usage_ppm descending", "vm",
         ["raw_sort_order", "memory_usage_ppm", "kDescending"]),
        ("show containers sorted by usage_bytes descending", "container",
         ["raw_sort_order", "usage_bytes", "kDescending"]),
        ("find top 5 disks by io_latency descending", "disk",
         ["raw_sort_order", "io_latency", "kDescending"]),
        ("get VMs sorted by num_vcpus ascending with limit 15", "vm",
         ["raw_sort_order", "num_vcpus", "kAscending"]),
        ("show top 100 alerts sorted by created_time_usecs descending", "alert",
         ["raw_sort_order", "created_time_usecs", "kDescending"]),
        ("list clusters ordered by cluster_name ascending", "cluster",
         ["raw_sort_order", "cluster_name", "kAscending"]),
    ]
    for query, et, must_have in sort_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "sorting"
        })

    # =================================================================
    # SECTION 7: Aggregation (kSum, kAvg, kCount, kMin, kMax)
    # =================================================================
    agg_queries = [
        ("get average memory_mb for VMs", "vm", ["aggregate_columns", "memory_mb", "kAvg"]),
        ("count all VMs", "vm", ["vm"]),
        ("show total disk capacity for all disks", "disk", ["aggregate_columns", "kSum"]),
        ("get minimum num_vcpus across all VMs", "vm", ["aggregate_columns", "num_vcpus", "kMin"]),
        ("find maximum memory_mb among VMs", "vm", ["aggregate_columns", "memory_mb", "kMax"]),
        ("count nodes in the cluster", "node", ["node"]),
        ("get sum of capacity_bytes for all disks", "disk", ["aggregate_columns", "capacity_bytes", "kSum"]),
        ("show average cpu_usage_ppm for nodes", "node", ["aggregate_columns", "cpu_usage_ppm", "kAvg"]),
        ("count VMs where power_state = on", "vm", ["vm", "where_clause"]),
        ("get total storage used across all containers", "container", ["aggregate_columns", "kSum"]),
        ("find average io_latency for disks", "disk", ["aggregate_columns", "kAvg"]),
        ("count alerts with severity = critical", "alert", ["alert", "where_clause"]),
        ("show max disk_capacity across all VMs", "vm", ["aggregate_columns", "kMax"]),
        ("get count of tasks with status running", "task", ["task", "where_clause"]),
        ("find sum of num_vcpus for all VMs", "vm", ["aggregate_columns", "num_vcpus", "kSum"]),
    ]
    for query, et, must_have in agg_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "aggregation"
        })

    # =================================================================
    # SECTION 8: Pagination / Limit / Offset
    # =================================================================
    pagination_queries = [
        ("get first 10 VMs", "vm", ["raw_limit", "limit: 10"]),
        ("show VMs with limit 50", "vm", ["raw_limit", "limit: 50"]),
        ("get VMs page 2 with page size 20", "vm", ["raw_limit", "limit: 20", "offset"]),
        ("list first 5 alerts", "alert", ["raw_limit", "limit: 5"]),
        ("show top 100 events", "event", ["raw_limit", "limit: 100"]),
        ("get next 25 tasks starting from offset 25", "task", ["raw_limit", "offset: 25"]),
        ("list 10 VMs starting from position 30", "vm", ["raw_limit", "offset"]),
        ("show first 50 nodes", "node", ["raw_limit", "limit: 50"]),
        ("get disks with limit 10 offset 0", "disk", ["raw_limit", "limit: 10"]),
        ("paginate through alerts with batch size 100", "alert", ["raw_limit", "limit: 100"]),
    ]
    for query, et, must_have in pagination_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "pagination"
        })

    # =================================================================
    # SECTION 9: Cursor queries
    # =================================================================
    cursor_queries = [
        ("paginate through all tasks using cursor query with batch size 50", "task",
         ["cursor_query_info", "batch_size: 50"]),
        ("get VMs using cursor pagination batch 100", "vm",
         ["cursor_query_info", "batch_size: 100"]),
        ("start cursor query for all alerts with batch size 200", "alert",
         ["cursor_query_info", "is_initial_cursor_query"]),
        ("cursor query all events batch 500", "event",
         ["cursor_query_info", "batch_size: 500"]),
        ("paginate through nodes using cursor with batch 25", "node",
         ["cursor_query_info", "batch_size: 25"]),
    ]
    for query, et, must_have in cursor_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "cursor_query"
        })

    # =================================================================
    # SECTION 10: kIN operator (list membership)
    # =================================================================
    in_queries = [
        ("get VMs where power_state in [on, off]", "vm",
         ["where_clause", "power_state", "kIN"]),
        ("show nodes where hypervisor_type in [kKvm, kVMWare, kHyperv]", "node",
         ["where_clause", "hypervisor_type", "kIN"]),
        ("find VMs where vm_name in [vm-1, vm-2, vm-3]", "vm",
         ["where_clause", "vm_name", "kIN"]),
        ("get clusters where version in [5.0, 5.5, 6.0]", "cluster",
         ["where_clause", "version", "kIN"]),
        ("show alerts where severity in [critical, warning]", "alert",
         ["where_clause", "severity", "kIN"]),
    ]
    for query, et, must_have in in_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_in"
        })

    # =================================================================
    # SECTION 11: kExists operator
    # =================================================================
    exists_queries = [
        ("get VMs where vm_name exists", "vm",
         ["where_clause", "vm_name", "kExists"]),
        ("show nodes where hypervisor_type exists", "node",
         ["where_clause", "hypervisor_type", "kExists"]),
        ("find VMs where ngt_status attribute exists", "vm",
         ["where_clause", "ngt_status", "kExists"]),
        ("get clusters where external_ip_address exists", "cluster",
         ["where_clause", "external_ip_address", "kExists"]),
        ("show disks where disk_label exists", "disk",
         ["where_clause", "disk_label", "kExists"]),
    ]
    for query, et, must_have in exists_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_exists"
        })

    # =================================================================
    # SECTION 12: Group by
    # =================================================================
    groupby_queries = [
        ("get VMs grouped by cluster_name", "vm",
         ["group_by", "raw_columns", "cluster_name"]),
        ("show nodes grouped by hypervisor_type", "node",
         ["group_by", "raw_columns", "hypervisor_type"]),
        ("group VMs by power_state and show count", "vm",
         ["group_by", "power_state"]),
        ("get disks grouped by storage_tier", "disk",
         ["group_by", "raw_columns", "storage_tier"]),
        ("show alerts grouped by severity", "alert",
         ["group_by", "raw_columns", "severity"]),
        ("group tasks by status", "task",
         ["group_by", "raw_columns", "status"]),
        ("get VMs grouped by node showing vm_name", "vm",
         ["group_by", "raw_columns"]),
        ("show containers grouped by container_name with usage_bytes", "container",
         ["group_by", "raw_columns", "container_name"]),
        ("group nodes by cluster showing node_name and cpu_usage_ppm", "node",
         ["group_by", "raw_columns"]),
        ("get clusters grouped by version", "cluster",
         ["group_by", "raw_columns", "version"]),
    ]
    for query, et, must_have in groupby_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "group_by"
        })

    # =================================================================
    # SECTION 13: Specific columns selection
    # =================================================================
    column_queries = [
        ("get vm_name and power_state for all VMs", "vm",
         ["raw_columns", "vm_name", "power_state"]),
        ("show node_name and hypervisor_type for all nodes", "node",
         ["raw_columns", "node_name", "hypervisor_type"]),
        ("get cluster_name and version for all clusters", "cluster",
         ["raw_columns", "cluster_name", "version"]),
        ("show vm_name, num_vcpus, and memory_mb for VMs", "vm",
         ["raw_columns", "vm_name", "num_vcpus", "memory_mb"]),
        ("get disk_label and capacity_bytes for all disks", "disk",
         ["raw_columns", "disk_label", "capacity_bytes"]),
        ("show container_name and usage_bytes for containers", "container",
         ["raw_columns", "container_name", "usage_bytes"]),
        ("get vm_name and cluster for all VMs", "vm",
         ["raw_columns", "vm_name", "cluster"]),
        ("show node_name, num_vms, cpu_usage_ppm for nodes", "node",
         ["raw_columns", "node_name", "num_vms"]),
        ("get _entity_id_ and vm_name for VMs", "vm",
         ["raw_columns", "_entity_id_", "vm_name"]),
        ("show alert_title and severity for alerts", "alert",
         ["raw_columns", "alert_title", "severity"]),
    ]
    for query, et, must_have in column_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "column_selection"
        })

    # =================================================================
    # SECTION 14: Combined (where + sort + limit)
    # =================================================================
    combined_queries = [
        ("get top 5 VMs where power_state = on sorted by memory_mb descending", "vm",
         ["where_clause", "power_state", "raw_sort_order", "memory_mb"]),
        ("show first 10 nodes sorted by cpu_usage_ppm descending where num_vms > 5", "node",
         ["where_clause", "num_vms", "raw_sort_order", "cpu_usage_ppm"]),
        ("get VMs where memory_mb > 4096 sorted by num_vcpus descending limit 3", "vm",
         ["where_clause", "memory_mb", "raw_sort_order", "num_vcpus"]),
        ("show top 5 alerts sorted by severity descending where check.score >= 76", "alert",
         ["where_clause", "check.score", "raw_sort_order", "severity"]),
        ("find first 20 VMs where is_cvm = 0 ordered by vm_name ascending", "vm",
         ["where_clause", "is_cvm", "raw_sort_order", "vm_name"]),
        ("get top 10 disks where storage_tier = SSD sorted by capacity_bytes descending", "disk",
         ["where_clause", "storage_tier", "raw_sort_order", "capacity_bytes"]),
        ("show first 5 clusters sorted by num_nodes descending where num_nodes > 1", "cluster",
         ["where_clause", "num_nodes", "raw_sort_order"]),
        ("get VMs where vm_name contains prod sorted by creation_time descending limit 10", "vm",
         ["where_clause", "vm_name", "kLike", "raw_sort_order"]),
    ]
    for query, et, must_have in combined_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "combined_read"
        })

    # =================================================================
    # SECTION 15: UpdateEntity
    # =================================================================
    update_queries = [
        ("update VM entity vm-001 setting power_state to on", "vm",
         ["entity_guid", "vm", "vm-001", "attribute_data", "power_state"]),
        ("modify VM vm-test setting memory_mb to 8192", "vm",
         ["entity_guid", "vm", "vm-test", "attribute_data", "memory_mb"]),
        ("set node_name to NTNX-HOST-1 for node entity abc-123", "node",
         ["entity_guid", "node", "abc-123", "attribute_data", "node_name"]),
        ("update cluster entity cluster-001 setting version to 6.0", "cluster",
         ["entity_guid", "cluster", "cluster-001", "attribute_data", "version"]),
        ("change power_state to off for VM entity vm-prod-1", "vm",
         ["entity_guid", "vm", "vm-prod-1", "attribute_data", "power_state"]),
        ("update disk disk-001 setting storage_tier to SSD", "disk",
         ["entity_guid", "disk", "disk-001", "attribute_data", "storage_tier"]),
        ("set vm_name to production-vm for VM entity vm-99", "vm",
         ["entity_guid", "vm", "vm-99", "attribute_data", "vm_name"]),
        ("update VM entity my-vm-id setting num_vcpus to 4", "vm",
         ["entity_guid", "vm", "my-vm-id", "attribute_data", "num_vcpus"]),
        ("modify node entity node-5 setting hypervisor_type to kKvm", "node",
         ["entity_guid", "node", "node-5", "attribute_data", "hypervisor_type"]),
        ("update container entity ctr-1 setting container_name to backup", "container",
         ["entity_guid", "container", "ctr-1", "attribute_data", "container_name"]),
        ("set is_cvm to 1 for VM entity cvm-001 with cas value 3", "vm",
         ["entity_guid", "vm", "cvm-001", "attribute_data", "is_cvm", "cas_value"]),
        ("update VM vm-001 setting power_state to off with cas value 5", "vm",
         ["entity_guid", "vm", "vm-001", "attribute_data", "power_state", "cas_value"]),
        ("modify cluster cluster-abc setting external_ip to 10.0.0.1", "cluster",
         ["entity_guid", "cluster", "cluster-abc", "attribute_data"]),
        ("update VM entity vm-x setting memory_mb to 16384 and num_vcpus to 8", "vm",
         ["entity_guid", "vm", "vm-x", "attribute_data", "memory_mb"]),
        ("set node_status to maintenance for node entity node-repair", "node",
         ["entity_guid", "node", "node-repair", "attribute_data"]),
    ]
    for query, et, must_have in update_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "UpdateEntity",
            "proto_must_have": must_have,
            "category": "update_entity"
        })

    # =================================================================
    # SECTION 16: DeleteEntity
    # =================================================================
    delete_queries = [
        ("delete VM entity vm-test-123", "vm", ["entity_guid", "vm", "vm-test-123"]),
        ("remove node entity node-old-1", "node", ["entity_guid", "node", "node-old-1"]),
        ("delete cluster entity cluster-decom", "cluster", ["entity_guid", "cluster", "cluster-decom"]),
        ("remove disk entity disk-broken", "disk", ["entity_guid", "disk", "disk-broken"]),
        ("delete VM entity prod-vm-99", "vm", ["entity_guid", "vm", "prod-vm-99"]),
        ("remove container entity old-container", "container", ["entity_guid", "container", "old-container"]),
        ("delete alert entity alert-001", "alert", ["entity_guid", "alert", "alert-001"]),
        ("remove event entity event-xyz", "event", ["entity_guid", "event", "event-xyz"]),
        ("delete VM vm-cleanup-target", "vm", ["entity_guid", "vm", "vm-cleanup-target"]),
        ("remove entity of type task with id task-complete", "task", ["entity_guid", "task", "task-complete"]),
        ("delete VM entity test-vm-001", "vm", ["entity_guid", "vm", "test-vm-001"]),
        ("remove snapshot entity snap-old", "snapshot", ["entity_guid", "snapshot", "snap-old"]),
        ("delete image entity unused-image", "image", ["entity_guid", "image", "unused-image"]),
        ("remove volume_group entity vg-retired", "volume_group", ["entity_guid", "volume_group", "vg-retired"]),
        ("delete protection_domain entity pd-test", "protection_domain", ["entity_guid", "protection_domain", "pd-test"]),
    ]
    for query, et, must_have in delete_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "DeleteEntity",
            "proto_must_have": must_have,
            "category": "delete_entity"
        })

    # =================================================================
    # SECTION 17: RegisterEntityTypes
    # =================================================================
    register_entity_queries = [
        ("register new entity type custom_sensor with parent node", None,
         ["entity_type_info_list", "custom_sensor"]),
        ("create entity type test_entity with parent cluster", None,
         ["entity_type_info_list", "test_entity"]),
        ("register entity type my_plugin", None,
         ["entity_type_info_list", "my_plugin"]),
        ("register new entity type monitoring_agent with parent node", None,
         ["entity_type_info_list", "monitoring_agent"]),
        ("create new entity type non_cas_type", None,
         ["entity_type_info_list", "non_cas_type"]),
        ("register entity type backup_target", None,
         ["entity_type_info_list", "backup_target"]),
        ("create entity type evictable_logs with is_evictable true", None,
         ["entity_type_info_list", "evictable_logs"]),
        ("register new entity type device_sensor", None,
         ["entity_type_info_list", "device_sensor"]),
        ("register entity type test_metric_source with parent node", None,
         ["entity_type_info_list", "test_metric_source"]),
        ("create new entity type custom_alert_type", None,
         ["entity_type_info_list", "custom_alert_type"]),
    ]
    for query, et, must_have in register_entity_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "RegisterEntityTypes",
            "proto_must_have": must_have,
            "category": "register_entity_types"
        })

    # =================================================================
    # SECTION 18: RegisterMetricTypes
    # =================================================================
    register_metric_queries = [
        ("register attribute cpu_temp for entity type node", None,
         ["metric_type_list", "cpu_temp", "node"]),
        ("register metric disk_iops for entity type disk", None,
         ["metric_type_list", "disk_iops", "disk"]),
        ("add new attribute custom_label for vm entity type", None,
         ["metric_type_list", "custom_label", "vm"]),
        ("register attribute is_encrypted as boolean for disk", None,
         ["metric_type_list", "is_encrypted", "disk"]),
        ("register metric num_io for entity type node", None,
         ["metric_type_list", "num_io", "node"]),
        ("add attribute status_message for task entity type", None,
         ["metric_type_list", "status_message", "task"]),
        ("register new metric total_io_time_usecs for custom_sensor", None,
         ["metric_type_list", "total_io_time_usecs", "custom_sensor"]),
        ("register attribute location for node entity type", None,
         ["metric_type_list", "location", "node"]),
        ("add metric read_bytes for disk entity type", None,
         ["metric_type_list", "read_bytes", "disk"]),
        ("register attribute firmware_version for node", None,
         ["metric_type_list", "firmware_version", "node"]),
    ]
    for query, et, must_have in register_metric_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "RegisterMetricTypes",
            "proto_must_have": must_have,
            "category": "register_metric_types"
        })

    # =================================================================
    # SECTION 19: UnregisterMetricTypes
    # =================================================================
    unreg_metric_queries = [
        ("unregister metric cpu_temp from node entity type", None,
         ["metric_type_list", "cpu_temp", "node"]),
        ("remove attribute custom_label from vm", None,
         ["metric_type_list", "custom_label", "vm"]),
        ("unregister metric disk_iops from disk", None,
         ["metric_type_list", "disk_iops", "disk"]),
        ("remove metric old_attribute from cluster", None,
         ["metric_type_list", "old_attribute", "cluster"]),
        ("unregister attribute deprecated_field from vm", None,
         ["metric_type_list", "deprecated_field", "vm"]),
    ]
    for query, et, must_have in unreg_metric_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "UnregisterMetricTypes",
            "proto_must_have": must_have,
            "category": "unregister_metric_types"
        })

    # =================================================================
    # SECTION 20: GetEntityTypes
    # =================================================================
    get_entity_type_queries = [
        ("show all entity types", None, []),
        ("describe entity type vm", None, ["entity_type_name", "vm"]),
        ("get info about node entity type", None, ["entity_type_name", "node"]),
        ("what is the schema for cluster entity type", None, ["entity_type_name", "cluster"]),
        ("describe entity type disk", None, ["entity_type_name", "disk"]),
        ("get entity type definition for container", None, ["entity_type_name", "container"]),
        ("show entity type info for alert", None, ["entity_type_name", "alert"]),
        ("describe entity type volume_group", None, ["entity_type_name", "volume_group"]),
        ("get info about custom_sensor entity type", None, ["entity_type_name", "custom_sensor"]),
        ("show all registered entity types", None, []),
        ("list available entity types", None, []),
        ("get info about lattice-0 entity type", None, ["entity_type_name", "lattice-0"]),
        ("describe the task entity type schema", None, ["entity_type_name", "task"]),
        ("what entity types are registered in IDF", None, []),
        ("show entity type details for snapshot", None, ["entity_type_name", "snapshot"]),
    ]
    for query, et, must_have in get_entity_type_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntityTypes",
            "proto_must_have": must_have,
            "category": "get_entity_types"
        })

    # =================================================================
    # SECTION 21: GetMetricTypes
    # =================================================================
    get_metric_type_queries = [
        ("list all metrics for entity type vm", None, ["regex"]),
        ("show attributes for disk entity type", None, ["regex", "disk"]),
        ("what metrics does node have", None, ["regex", "node"]),
        ("get all attributes for cluster entity type", None, ["regex", "cluster"]),
        ("list metrics available for container", None, ["regex", "container"]),
        ("show all metric types for alert", None, ["regex", "alert"]),
        ("what attributes does vm entity type have", None, ["regex", "vm"]),
        ("get metrics for volume_group entity type", None, ["regex", "volume_group"]),
        ("list all available metrics", None, ["regex"]),
        ("show what metrics are registered for task", None, ["regex", "task"]),
        ("get all indexed attributes for vm", None, ["regex", "vm"]),
        ("list columns for disk entity type", None, ["regex", "disk"]),
        ("what fields does the node entity type have", None, ["regex", "node"]),
        ("show metrics for protection_domain", None, ["regex", "protection_domain"]),
        ("get all metrics and attributes for snapshot", None, ["regex", "snapshot"]),
    ]
    for query, et, must_have in get_metric_type_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMetricTypes",
            "proto_must_have": must_have,
            "category": "get_metric_types"
        })

    # =================================================================
    # SECTION 22: Watch (Register/Monitor)
    # =================================================================
    watch_queries = [
        ("watch for changes on VM entity type", None, ["vm"]),
        ("monitor new VMs being created", None, ["vm"]),
        ("subscribe to updates on node entities", None, ["node"]),
        ("watch for VM deletions", None, ["vm"]),
        ("register a watch for new alerts", None, ["alert"]),
        ("watch for changes on disk entity type", None, ["disk"]),
        ("subscribe to create events for VM type", None, ["vm"]),
        ("watch for any changes on cluster entities", None, ["cluster"]),
        ("monitor updates to container entities", None, ["container"]),
        ("register watch for new tasks", None, ["task"]),
        ("watch for entity changes on type vm for creates and updates", None, ["vm"]),
        ("subscribe to delete events on VM entities", None, ["vm"]),
        ("watch for new volume_group entities", None, ["volume_group"]),
        ("monitor all changes on alert entity type", None, ["alert"]),
        ("register composite watch on VM entity type", None, ["vm"]),
    ]
    for query, et, must_have in watch_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "Watch",
            "proto_must_have": must_have,
            "category": "watch"
        })

    # =================================================================
    # SECTION 23: SpotLightSearch
    # =================================================================
    search_queries = [
        ("search for entities containing production", None, ["search_term", "production"]),
        ("find entities matching test-vm", None, ["search_term", "test-vm"]),
        ("search for VMs with name containing dev", None, ["search_term", "dev"]),
        ("spotlight search for ntnx", None, ["search_term", "ntnx"]),
        ("find entities matching cluster-01", None, ["search_term", "cluster-01"]),
        ("search for nodes containing HOST", None, ["search_term", "HOST"]),
        ("find all entities matching backup", None, ["search_term", "backup"]),
        ("search IDF for entities containing prod-vm", None, ["search_term", "prod-vm"]),
        ("spotlight search for TEST_CLUSTER", None, ["search_term", "TEST_CLUSTER"]),
        ("find entities named like staging", None, ["search_term", "staging"]),
        ("search for entities containing 10.0.0", None, ["search_term", "10.0.0"]),
        ("find entities matching nutanix across all types", None, ["search_term", "nutanix"]),
        ("search for HyperV entities", None, ["search_term", "HyperV"]),
        ("spotlight search for ESXi", None, ["search_term", "ESXi"]),
        ("find entities matching Block-1", None, ["search_term", "Block-1"]),
    ]
    for query, et, must_have in search_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "SpotLightSearch",
            "proto_must_have": must_have,
            "category": "spotlight_search"
        })

    # =================================================================
    # SECTION 24: GetMasterLocation
    # =================================================================
    master_queries = [
        ("get master location", None, []),
        ("who is the IDF master", None, []),
        ("show master node location", None, []),
        ("find the IDF master", None, []),
        ("get insights master location", None, []),
    ]
    for query, et, must_have in master_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMasterLocation",
            "proto_must_have": must_have,
            "category": "get_master_location"
        })

    # =================================================================
    # SECTION 25: BatchGetEntitiesWithMetrics
    # =================================================================
    batch_get_queries = [
        ("batch query: get all VMs and all nodes", None, ["query_list"]),
        ("get VMs and clusters in one batch call", None, ["query_list"]),
        ("batch get VMs, disks, and containers", None, ["query_list"]),
        ("run multiple queries: get all nodes and all alerts", None, ["query_list"]),
        ("batch query for VMs where power_state = on and nodes", None, ["query_list"]),
    ]
    for query, et, must_have in batch_get_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "BatchGetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "batch_get"
        })

    # =================================================================
    # SECTION 26: BatchUpdateEntities
    # =================================================================
    batch_update_queries = [
        ("batch update VMs vm-1 and vm-2 setting power_state to off", None,
         ["entity_list"]),
        ("bulk update nodes node-1, node-2, node-3 setting status to maintenance", None,
         ["entity_list"]),
        ("batch update multiple VMs setting is_cvm to 0", None,
         ["entity_list"]),
        ("batch set power_state to on for VMs vm-a, vm-b, vm-c", None,
         ["entity_list"]),
        ("bulk update disks disk-1 and disk-2 setting storage_tier to SSD", None,
         ["entity_list"]),
    ]
    for query, et, must_have in batch_update_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "BatchUpdateEntities",
            "proto_must_have": must_have,
            "category": "batch_update"
        })

    # =================================================================
    # SECTION 27: BatchDeleteEntities
    # =================================================================
    batch_delete_queries = [
        ("batch delete VMs vm-old-1 and vm-old-2", None,
         ["entity_list", "vm-old-1", "vm-old-2"]),
        ("bulk delete nodes node-x, node-y, node-z", None,
         ["entity_list"]),
        ("batch remove VMs vm-test-1, vm-test-2, vm-test-3", None,
         ["entity_list"]),
        ("bulk delete alerts alert-1, alert-2", None,
         ["entity_list"]),
        ("batch delete disks disk-bad-1 and disk-bad-2", None,
         ["entity_list"]),
    ]
    for query, et, must_have in batch_delete_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "BatchDeleteEntities",
            "proto_must_have": must_have,
            "category": "batch_delete"
        })

    # =================================================================
    # SECTION 28: GetEntities (by GUID)
    # =================================================================
    get_entities_queries = [
        ("get entity by id abc-123-uuid of type vm", None,
         ["entity_guid_list", "vm", "abc-123-uuid"]),
        ("fetch entity with guid node-uuid-1 type node", None,
         ["entity_guid_list", "node", "node-uuid-1"]),
        ("get specific entity disk-id-001 of type disk", None,
         ["entity_guid_list", "disk", "disk-id-001"]),
        ("fetch VM entity by id vm-specific-99", None,
         ["entity_guid_list", "vm", "vm-specific-99"]),
        ("get entity by guid cluster-main-id type cluster", None,
         ["entity_guid_list", "cluster", "cluster-main-id"]),
    ]
    for query, et, must_have in get_entities_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntities",
            "proto_must_have": must_have,
            "category": "get_entities_by_guid"
        })

    # =================================================================
    # SECTION 29: GetMetricData (time-series)
    # =================================================================
    get_metric_data_queries = [
        ("get metric data for cpu_usage of vm entity vm-001", None,
         ["entity_type_name", "vm", "cpu_usage"]),
        ("fetch time-series data for disk_iops of disk disk-1", None,
         ["entity_type_name", "disk", "disk_iops"]),
        ("get metric values for memory_usage_ppm of node node-abc", None,
         ["entity_type_name", "node", "memory_usage_ppm"]),
        ("read metric data for check.score of alert alert-x", None,
         ["entity_type_name", "check.score"]),
        ("get time series for num_io metric of custom_sensor sensor-1", None,
         ["entity_type_name", "num_io"]),
    ]
    for query, et, must_have in get_metric_data_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMetricData",
            "proto_must_have": must_have,
            "category": "get_metric_data"
        })

    # =================================================================
    # SECTION 30: PutMetricData (time-series write)
    # =================================================================
    put_metric_data_queries = [
        ("write metric data cpu_usage value 85 for vm entity vm-001", None,
         ["entity_with_metric_list", "cpu_usage", "vm-001"]),
        ("publish metric disk_iops value 1200 for disk disk-1", None,
         ["entity_with_metric_list", "disk_iops", "disk-1"]),
        ("put metric memory_usage value 8192 for node node-abc", None,
         ["entity_with_metric_list", "memory_usage", "node-abc"]),
        ("write metric num_io value 500 for entity custom_sensor sensor-1", None,
         ["entity_with_metric_list", "num_io", "sensor-1"]),
        ("publish metric check.score value 95 for vm vm-test", None,
         ["entity_with_metric_list", "check.score", "vm-test"]),
    ]
    for query, et, must_have in put_metric_data_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "PutMetricData",
            "proto_must_have": must_have,
            "category": "put_metric_data"
        })

    # =================================================================
    # SECTION 31: GetEntitiesTrail (change history)
    # =================================================================
    trail_queries = [
        ("get change history for VM entity vm-001", None,
         ["entity_guid_list", "vm", "vm-001"]),
        ("show audit trail for node node-abc", None,
         ["entity_guid_list", "node", "node-abc"]),
        ("get entity trail for cluster cluster-main", None,
         ["entity_guid_list", "cluster", "cluster-main"]),
        ("show change log for disk entity disk-1", None,
         ["entity_guid_list", "disk", "disk-1"]),
        ("get history of changes for VM vm-prod", None,
         ["entity_guid_list", "vm", "vm-prod"]),
    ]
    for query, et, must_have in trail_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesTrail",
            "proto_must_have": must_have,
            "category": "get_entities_trail"
        })

    # =================================================================
    # SECTION 32: AttachEntity / DetachEntity
    # =================================================================
    attach_detach_queries = [
        ("attach entity VM vm-001 with incarnation 5", None,
         ["entity_guid", "vm", "vm-001"]),
        ("detach entity VM vm-migrate moving to cluster uuid-abc", None,
         ["entity_guid", "vm"]),
        ("attach node entity node-new to cluster", None,
         ["entity_guid", "node"]),
        ("detach disk entity disk-old moving to cluster uuid-xyz", None,
         ["entity_guid", "disk"]),
        ("attach VM vm-replicated with incarnation 10", None,
         ["entity_guid", "vm"]),
    ]
    attach_apis = ["AttachEntity", "DetachEntity", "AttachEntity", "DetachEntity", "AttachEntity"]
    for i, (query, et, must_have) in enumerate(attach_detach_queries):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": attach_apis[i],
            "proto_must_have": must_have,
            "category": "attach_detach"
        })

    # =================================================================
    # SECTION 33: PutEvent
    # =================================================================
    put_event_queries = [
        ("publish event vm_created for VM entity vm-001", None,
         ["event_type", "vm"]),
        ("create event node_joined for node entity node-new", None,
         ["event_type", "node"]),
        ("put event disk_failure for disk disk-bad", None,
         ["event_type", "disk"]),
        ("publish event backup_completed for protection_domain pd-1", None,
         ["event_type"]),
        ("create event maintenance_started for cluster cluster-1", None,
         ["event_type", "cluster"]),
    ]
    for query, et, must_have in put_event_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "PutEvent",
            "proto_must_have": must_have,
            "category": "put_event"
        })

    # =================================================================
    # SECTION 34: Complex multi-entity scenarios from tests
    # =================================================================
    complex_queries = [
        ("get VMs where is_cvm = 0 and power_state = on and check.score >= 26 and check.score < 76",
         "vm", ["where_clause", "is_cvm", "power_state", "check.score"]),
        ("show VMs where vm_name matches .*[p|P][c|C].* and power_state = on",
         "vm", ["where_clause", "vm_name", "kLike", "power_state"]),
        ("get nodes where hypervisor_type = kKvm and node_name contains TEST-HOST",
         "node", ["where_clause", "hypervisor_type", "node_name", "kLike"]),
        ("show clusters where version = 5.0.1 and hypervisor_types contains ESXi",
         "cluster", ["where_clause", "version", "hypervisor_types"]),
        ("get VMs where check.score >= 76 and check.score < 101 and power_state = off",
         "vm", ["where_clause", "check.score", "power_state"]),
        ("show nodes where check.score >= 0 and check.score < 26 and hypervisor_type = kVMWare",
         "node", ["where_clause", "check.score", "hypervisor_type"]),
        ("get clusters where check.overall_score >= 76 and check.overall_score < 101 and version = 4.7.1",
         "cluster", ["where_clause", "check.overall_score", "version"]),
        ("show VMs sorted by cluster_name ascending grouped by cluster_name",
         "vm", ["raw_sort_order", "cluster_name", "group_by"]),
        ("get nodes with num_io metric sorted by num_io descending with limit 3 and bucket boundaries",
         "node", ["raw_sort_order", "num_io"]),
        ("show evictable entities of type alert sorted by signature ascending",
         "alert", ["raw_sort_order", "signature"]),
    ]
    for query, et, must_have in complex_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "complex_where"
        })

    # =================================================================
    # SECTION 35: Non-CAS update scenarios (from test_non_cas.py)
    # =================================================================
    non_cas_queries = [
        ("update non_cas_type entity abc-123 setting attr_1 to value_1 without cas", None,
         ["entity_guid", "non_cas_type", "abc-123", "attribute_data"]),
        ("update evictable entity event-001 of type event setting message to done", None,
         ["entity_guid", "event", "event-001", "attribute_data"]),
        ("modify VM vm-x setting power_state to off without cas value", None,
         ["entity_guid", "vm", "vm-x", "attribute_data", "power_state"]),
    ]
    for query, et, must_have in non_cas_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "UpdateEntity",
            "proto_must_have": must_have,
            "category": "update_non_cas"
        })

    # =================================================================
    # SECTION 36: Lookup queries (join)
    # =================================================================
    lookup_queries = [
        ("get VMs joining with cluster on cluster_uuid", "vm",
         ["lookup_query", "vm", "cluster"]),
        ("show VMs with their cluster names using lookup on cluster_uuid", "vm",
         ["lookup_query", "vm", "cluster"]),
        ("get nodes joining with cluster on cluster field", "node",
         ["lookup_query", "node", "cluster"]),
        ("join VMs with nodes on node field", "vm",
         ["lookup_query", "vm", "node"]),
        ("get disks with their node info using lookup", "disk",
         ["lookup_query", "disk", "node"]),
    ]
    for query, et, must_have in lookup_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "lookup_query"
        })

    # =================================================================
    # SECTION 37: Specific attribute value types
    # =================================================================
    value_type_queries = [
        ("get VMs where num_vcpus = 4", "vm",
         ["where_clause", "num_vcpus"]),
        ("show nodes where is_degraded = true", "node",
         ["where_clause", "is_degraded"]),
        ("find VMs where memory_mb = 8192", "vm",
         ["where_clause", "memory_mb"]),
        ("get disks where online = true", "disk",
         ["where_clause", "online"]),
        ("show alerts where auto_resolved = false", "alert",
         ["where_clause", "auto_resolved"]),
    ]
    for query, et, must_have in value_type_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "value_types"
        })

    # =================================================================
    # SECTION 38: Alternative phrasings for same queries (robustness)
    # =================================================================
    robustness_queries = [
        ("how many VMs are there", "vm", ["vm"]),
        ("what VMs have more than 4 CPUs", "vm", ["where_clause", "num_vcpus"]),
        ("which nodes are running kKvm", "node", ["where_clause", "hypervisor_type"]),
        ("tell me about all storage containers", "container", ["container"]),
        ("give me the top VMs by memory usage", "vm", ["raw_sort_order", "memory"]),
        ("I want to see powered off VMs", "vm", ["where_clause", "power_state"]),
        ("can you show me all VMs with name containing test", "vm", ["where_clause", "kLike"]),
        ("get me nodes that have ESXi hypervisor", "node", ["where_clause", "hypervisor"]),
        ("what are the biggest disks by capacity", "disk", ["raw_sort_order", "capacity"]),
        ("show me VMs that have exactly 8 vCPUs", "vm", ["where_clause", "num_vcpus"]),
        ("fetch clusters running version 6.0", "cluster", ["where_clause", "version"]),
        ("how many alerts are critical", "alert", ["where_clause", "severity"]),
        ("which VMs are powered on", "vm", ["where_clause", "power_state"]),
        ("give me all nodes sorted alphabetically", "node", ["raw_sort_order"]),
        ("get VMs with at least 16GB RAM", "vm", ["where_clause", "memory"]),
        ("show top disks by IOPS", "disk", ["raw_sort_order"]),
        ("list powered on VMs sorted by name", "vm", ["where_clause", "power_state", "raw_sort_order"]),
        ("count how many nodes are in each cluster", "node", ["group_by"]),
        ("what is the total memory across all VMs", "vm", ["aggregate_columns"]),
        ("average CPU usage for all nodes", "node", ["aggregate_columns"]),
    ]
    for query, et, must_have in robustness_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "robustness"
        })

    # =================================================================
    # SECTION 39: Edge cases and specific test patterns
    # =================================================================
    edge_case_queries = [
        # From test_unfiltered_query_count - getting entity counts
        ("get unfiltered count of all vm entities", "vm", ["vm"]),
        ("count total entities of type node", "node", ["node"]),
        # From test_nested_proto - nested attribute queries
        ("get VMs with nested attribute ngt.installed_version", "vm", ["vm"]),
        # From test_point_query_where_clause - exact point queries
        ("get specific VM by entity_id equals abc-123", "vm", ["where_clause", "_entity_id_"]),
        # From test_query_non_existent_ids
        ("get VM entities by id list vm-1, vm-2, vm-3", "vm", ["vm"]),
        # From test_update_entity_ret_nested_attributes
        ("get VM vm-001 showing all nested attributes", "vm", ["vm"]),
        # Multi-metric selection
        ("get vm_name, memory_mb, num_vcpus, power_state for all VMs", "vm",
         ["raw_columns", "vm_name", "memory_mb", "num_vcpus", "power_state"]),
        # Empty result queries
        ("get VMs where vm_name = nonexistent_vm_xyz", "vm", ["where_clause", "vm_name", "kEQ"]),
        # Group by with aggregation
        ("get count of VMs grouped by power_state", "vm",
         ["group_by", "power_state"]),
        ("show sum of memory_mb grouped by cluster for VMs", "vm",
         ["group_by", "aggregate_columns", "memory_mb", "kSum"]),
    ]
    for query, et, must_have in edge_case_queries:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "edge_cases"
        })

    # =================================================================
    # SECTION 40: Additional watch sub-types from basic_watches_test.py
    # =================================================================
    watch_subtypes = [
        ("watch for new VM entities being created", None, ["vm"]),
        ("watch for updates on VM entity type", None, ["vm"]),
        ("watch for deletions of VM entities", None, ["vm"]),
        ("register composite watch for all changes on alert type", None, ["alert"]),
        ("watch for metric changes on vm_name attribute for VMs", None, ["vm"]),
        ("unregister watch named watch_vm_all", None, []),
        ("stop watching VM entity changes", None, ["vm"]),
        ("get all registered watches", None, []),
        ("delete the watch named monitor_alerts", None, []),
        ("register watch for new nodes with get current entities", None, ["node"]),
    ]
    for query, et, must_have in watch_subtypes:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "Watch",
            "proto_must_have": must_have,
            "category": "watch_subtypes"
        })

    # =================================================================
    # SECTION 41: More alternative phrasings (natural conversation style)
    # =================================================================
    conversational = [
        ("I need to find all VMs that have more than 2 vCPUs and are powered on", "vm",
         ["where_clause", "num_vcpus", "power_state"]),
        ("can you show me hosts sorted by CPU usage", "node",
         ["raw_sort_order"]),
        ("what's the average memory for virtual machines", "vm",
         ["aggregate_columns", "memory"]),
        ("I want to delete the VM called test-vm-cleanup", "vm",
         ["entity_guid", "vm", "test-vm-cleanup"]),
        ("please register a new entity type called iot_device", None,
         ["entity_type_info_list", "iot_device"]),
        ("show me VMs from the production cluster", "vm",
         ["where_clause", "cluster"]),
        ("list the 10 most recently created alerts", "alert",
         ["raw_sort_order", "raw_limit"]),
        ("update VM prod-vm-1 to have 16 vCPUs", "vm",
         ["entity_guid", "vm", "prod-vm-1", "attribute_data"]),
        ("search for anything containing database", None,
         ["search_term", "database"]),
        ("get the top 5 busiest nodes", "node",
         ["raw_sort_order", "raw_limit"]),
        ("how many disks do we have total", "disk", ["disk"]),
        ("which clusters are running version 5.5", "cluster",
         ["where_clause", "version"]),
        ("show me containers that are more than 80% full", "container",
         ["where_clause"]),
        ("I want to monitor for any new VM creations", None, ["vm"]),
        ("what entity types are available in this system", None, []),
    ]
    conv_apis = [
        "GetEntitiesWithMetrics", "GetEntitiesWithMetrics", "GetEntitiesWithMetrics",
        "DeleteEntity", "RegisterEntityTypes", "GetEntitiesWithMetrics",
        "GetEntitiesWithMetrics", "UpdateEntity", "SpotLightSearch",
        "GetEntitiesWithMetrics", "GetEntitiesWithMetrics", "GetEntitiesWithMetrics",
        "GetEntitiesWithMetrics", "Watch", "GetEntityTypes"
    ]
    for i, (query, et, must_have) in enumerate(conversational):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": conv_apis[i],
            "proto_must_have": must_have,
            "category": "conversational"
        })

    # =================================================================
    # SECTION 42: Additional where clause patterns from test files
    # =================================================================
    more_where = [
        ("get VMs where vm_name not equal to test-vm", "vm", ["where_clause", "vm_name", "kNE"]),
        ("show nodes where node_name != NTNX-Block-1-A", "node", ["where_clause", "node_name", "kNE"]),
        ("find VMs where is_cvm not equals 1", "vm", ["where_clause", "is_cvm", "kNE"]),
        ("get alerts where resolved = false", "alert", ["where_clause", "resolved"]),
        ("show VMs where cluster_uuid = abc-def-ghi", "vm", ["where_clause", "cluster_uuid", "kEQ"]),
        ("find tasks where operation_type = create", "task", ["where_clause", "operation_type", "kEQ"]),
        ("get disks where tier_name != cold", "disk", ["where_clause", "tier_name", "kNE"]),
        ("show VMs where ip_address_list contains 10.0", "vm", ["where_clause", "ip_address_list", "kLike"]),
        ("find nodes where maintenance_mode = true", "node", ["where_clause", "maintenance_mode"]),
        ("get clusters where encryption_status = enabled", "cluster", ["where_clause", "encryption_status"]),
    ]
    for query, et, must_have in more_where:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_additional"
        })

    # =================================================================
    # SECTION 43: Multi-sort patterns from test_sort_multiple_raw_cols
    # =================================================================
    multi_sort = [
        ("get VMs sorted by cluster_name ascending then vm_name ascending", "vm",
         ["raw_sort_order", "cluster_name", "vm_name"]),
        ("show nodes sorted by hypervisor_type descending then node_name ascending", "node",
         ["raw_sort_order", "hypervisor_type", "node_name"]),
        ("list VMs sorted by power_state then num_vcpus descending", "vm",
         ["raw_sort_order", "power_state", "num_vcpus"]),
        ("get disks sorted by storage_tier ascending then capacity_bytes descending", "disk",
         ["raw_sort_order", "storage_tier", "capacity_bytes"]),
        ("show alerts sorted by severity descending then created_time ascending", "alert",
         ["raw_sort_order", "severity", "created_time"]),
    ]
    for query, et, must_have in multi_sort:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "multi_sort"
        })

    # =================================================================
    # SECTION 44: Evictable entity patterns
    # =================================================================
    evictable = [
        ("get first 100 alerts sorted by severity descending", "alert",
         ["alert", "raw_limit", "raw_sort_order", "severity"]),
        ("show last 50 events by creation time", "event",
         ["event", "raw_limit"]),
        ("get first 200 tasks sorted by start_time descending", "task",
         ["task", "raw_limit", "raw_sort_order"]),
        ("list 10 most recent audit entries", "audit_entry",
         ["audit_entry", "raw_limit"]),
        ("get alerts with limit 500", "alert", ["alert", "raw_limit", "limit: 500"]),
    ]
    for query, et, must_have in evictable:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "evictable_entities"
        })

    # =================================================================
    # SECTION 45: More phrasings for GetEntitiesWithMetrics (NL variation)
    # =================================================================
    nl_variations = [
        ("display all virtual machines in the cluster", "vm", ["vm"]),
        ("retrieve node information", "node", ["node"]),
        ("pull up all disk data", "disk", ["disk"]),
        ("query VMs from IDF", "vm", ["vm"]),
        ("get me a list of storage containers", "container", ["container"]),
        ("show me snapshots available", "snapshot", ["snapshot"]),
        ("list out all images", "image", ["image"]),
        ("give me info on all subnets", "subnet", ["subnet"]),
        ("pull all volume group data", "volume_group", ["volume_group"]),
        ("get network entities", "network", ["network"]),
        ("retrieve all cluster information", "cluster", ["cluster"]),
        ("show me all the protection domains", "protection_domain", ["protection_domain"]),
        ("list projects in the system", "project", ["project"]),
        ("get all available categories", "category", ["category"]),
        ("display blueprints", "blueprint", ["blueprint"]),
        ("show me apps", "app", ["app"]),
        ("get recovery point entities", "recovery_point", ["recovery_point"]),
        ("list availability zones", "availability_zone", ["availability_zone"]),
        ("show me remote connections", "remote_connection", ["remote_connection"]),
        ("get all runbooks", "runbook", ["runbook"]),
    ]
    for query, et, must_have in nl_variations:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "nl_variations"
        })

    # =================================================================
    # SECTION 46: More where clause EQ variations
    # =================================================================
    more_eq = [
        ("find VMs where cluster = cluster-abc", "vm", ["where_clause", "cluster", "kEQ"]),
        ("get nodes where cpu_model = Intel", "node", ["where_clause", "cpu_model", "kEQ"]),
        ("show disks where device_type = HDD", "disk", ["where_clause", "device_type", "kEQ"]),
        ("find containers where replication_factor = 2", "container", ["where_clause", "replication_factor", "kEQ"]),
        ("get VMs where hypervisor_type = AHV", "vm", ["where_clause", "hypervisor_type", "kEQ"]),
        ("show alerts where acknowledged = true", "alert", ["where_clause", "acknowledged", "kEQ"]),
        ("find tasks where operation = snapshot", "task", ["where_clause", "operation", "kEQ"]),
        ("get VMs where protection_type = async", "vm", ["where_clause", "protection_type", "kEQ"]),
        ("show clusters where is_available = true", "cluster", ["where_clause", "is_available", "kEQ"]),
        ("find nodes where degraded = false", "node", ["where_clause", "degraded", "kEQ"]),
        ("get VMs where boot_type = uefi", "vm", ["where_clause", "boot_type", "kEQ"]),
        ("show disks where location = ssd_tier", "disk", ["where_clause", "location", "kEQ"]),
        ("find VMs where timezone = UTC", "vm", ["where_clause", "timezone", "kEQ"]),
        ("get alerts where source = ncc", "alert", ["where_clause", "source", "kEQ"]),
        ("show nodes where bmc_version = 7.09", "node", ["where_clause", "bmc_version", "kEQ"]),
        ("find VMs where guest_os = linux", "vm", ["where_clause", "guest_os", "kEQ"]),
        ("get clusters where cluster_type = production", "cluster", ["where_clause", "cluster_type", "kEQ"]),
        ("show containers where erasure_coded = true", "container", ["where_clause", "erasure_coded", "kEQ"]),
        ("find VMs where agent_version = 2.0", "vm", ["where_clause", "agent_version", "kEQ"]),
        ("get disks where firmware = latest", "disk", ["where_clause", "firmware", "kEQ"]),
    ]
    for query, et, must_have in more_eq:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_eq_extended"
        })

    # =================================================================
    # SECTION 47: More comparison variations
    # =================================================================
    more_comparisons = [
        ("get VMs with more than 32GB memory", "vm", ["where_clause", "memory"]),
        ("show nodes with CPU usage above 90%", "node", ["where_clause"]),
        ("find disks with capacity greater than 2TB", "disk", ["where_clause", "capacity"]),
        ("get VMs using less than 1GB memory", "vm", ["where_clause", "memory"]),
        ("show containers with at least 500GB used", "container", ["where_clause"]),
        ("find alerts newer than 24 hours", "alert", ["where_clause"]),
        ("get VMs with at most 2 vCPUs", "vm", ["where_clause", "num_vcpus"]),
        ("show nodes with more than 50 VMs", "node", ["where_clause", "num_vms"]),
        ("find clusters with fewer than 4 nodes", "cluster", ["where_clause", "num_nodes"]),
        ("get disks with IOPS above 10000", "disk", ["where_clause"]),
        ("show VMs with uptime greater than 7 days", "vm", ["where_clause"]),
        ("find nodes with free memory above 64GB", "node", ["where_clause"]),
        ("get containers with utilization below 50%", "container", ["where_clause"]),
        ("show VMs with disk_count greater than 5", "vm", ["where_clause", "disk_count"]),
        ("find clusters with storage over 100TB", "cluster", ["where_clause"]),
    ]
    for query, et, must_have in more_comparisons:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "comparison_natural"
        })

    # =================================================================
    # SECTION 48: More sorting variations
    # =================================================================
    more_sorting = [
        ("get VMs ordered by creation time newest first", "vm", ["raw_sort_order"]),
        ("show nodes by memory usage highest to lowest", "node", ["raw_sort_order"]),
        ("list disks from largest to smallest", "disk", ["raw_sort_order"]),
        ("get clusters alphabetically by name", "cluster", ["raw_sort_order", "cluster_name"]),
        ("show VMs by CPU count high to low limit 10", "vm", ["raw_sort_order", "raw_limit"]),
        ("list alerts by creation time newest first", "alert", ["raw_sort_order"]),
        ("get nodes ranked by number of VMs", "node", ["raw_sort_order", "num_vms"]),
        ("show containers by free space descending", "container", ["raw_sort_order"]),
        ("list VMs alphabetically by vm_name", "vm", ["raw_sort_order", "vm_name", "kAscending"]),
        ("get top 3 nodes by storage capacity", "node", ["raw_sort_order", "raw_limit"]),
        ("show busiest 10 VMs by CPU usage", "vm", ["raw_sort_order", "raw_limit"]),
        ("list last 5 created tasks", "task", ["raw_sort_order", "raw_limit"]),
        ("get disks ordered by read latency", "disk", ["raw_sort_order"]),
        ("show VMs sorted by IP address", "vm", ["raw_sort_order"]),
        ("list clusters by number of hosts descending", "cluster", ["raw_sort_order"]),
    ]
    for query, et, must_have in more_sorting:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "sorting_natural"
        })

    # =================================================================
    # SECTION 49: More aggregation variations
    # =================================================================
    more_agg = [
        ("what is the total number of VMs", "vm", ["vm"]),
        ("how many nodes are in the cluster", "node", ["node"]),
        ("total disk capacity in the system", "disk", ["aggregate_columns"]),
        ("average vCPU count per VM", "vm", ["aggregate_columns", "kAvg"]),
        ("maximum memory assigned to any VM", "vm", ["aggregate_columns", "kMax"]),
        ("minimum disk IOPS", "disk", ["aggregate_columns", "kMin"]),
        ("total memory across all nodes", "node", ["aggregate_columns", "kSum"]),
        ("average alert score", "alert", ["aggregate_columns", "kAvg"]),
        ("count disks by storage tier", "disk", ["group_by"]),
        ("count VMs per node", "vm", ["group_by"]),
        ("total storage per container", "container", ["aggregate_columns", "kSum"]),
        ("average CPUs per cluster", "cluster", ["aggregate_columns", "kAvg"]),
        ("maximum IO latency for disks", "disk", ["aggregate_columns", "kMax"]),
        ("count alerts by severity level", "alert", ["group_by", "severity"]),
        ("sum of all disk capacities", "disk", ["aggregate_columns", "kSum"]),
    ]
    for query, et, must_have in more_agg:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "aggregation_natural"
        })

    # =================================================================
    # SECTION 50: More update variations
    # =================================================================
    more_updates = [
        ("change the name of VM vm-old to production-vm", "vm",
         ["entity_guid", "vm", "vm-old", "attribute_data", "vm_name"]),
        ("set memory to 32768 for VM vm-scale-up", "vm",
         ["entity_guid", "vm", "vm-scale-up", "attribute_data"]),
        ("update cluster cluster-main setting maintenance_mode to true", "cluster",
         ["entity_guid", "cluster", "cluster-main", "attribute_data"]),
        ("change disk status to offline for disk disk-failing", "disk",
         ["entity_guid", "disk", "disk-failing", "attribute_data"]),
        ("set replication_factor to 3 for container ctr-prod", "container",
         ["entity_guid", "container", "ctr-prod", "attribute_data"]),
        ("update node node-01 setting maintenance_mode to true", "node",
         ["entity_guid", "node", "node-01", "attribute_data"]),
        ("change vm-dev power_state to off", "vm",
         ["entity_guid", "vm", "vm-dev", "attribute_data", "power_state"]),
        ("update alert alert-123 setting acknowledged to true", "alert",
         ["entity_guid", "alert", "alert-123", "attribute_data"]),
        ("set description to test-snapshot for snapshot snap-001", "snapshot",
         ["entity_guid", "snapshot", "snap-001", "attribute_data"]),
        ("update image img-old setting is_active to false", "image",
         ["entity_guid", "image", "img-old", "attribute_data"]),
    ]
    for query, et, must_have in more_updates:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "UpdateEntity",
            "proto_must_have": must_have,
            "category": "update_variations"
        })

    # =================================================================
    # SECTION 51: More delete variations
    # =================================================================
    more_deletes = [
        ("remove VM vm-deprecated from IDF", "vm", ["entity_guid", "vm", "vm-deprecated"]),
        ("delete the node entity named node-decommissioned", "node", ["entity_guid", "node", "node-decommissioned"]),
        ("remove cluster cluster-test from the database", "cluster", ["entity_guid", "cluster", "cluster-test"]),
        ("delete disk entity disk-replaced", "disk", ["entity_guid", "disk", "disk-replaced"]),
        ("remove container old-backup-ctr", "container", ["entity_guid", "container", "old-backup-ctr"]),
        ("delete network entity net-unused", "network", ["entity_guid", "network", "net-unused"]),
        ("remove subnet sub-deprecated", "subnet", ["entity_guid", "subnet", "sub-deprecated"]),
        ("delete category cat-temp", "category", ["entity_guid", "category", "cat-temp"]),
        ("remove project proj-archive", "project", ["entity_guid", "project", "proj-archive"]),
        ("delete volume_group vg-old-data", "volume_group", ["entity_guid", "volume_group", "vg-old-data"]),
    ]
    for query, et, must_have in more_deletes:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "DeleteEntity",
            "proto_must_have": must_have,
            "category": "delete_variations"
        })

    # =================================================================
    # SECTION 52: More watch variations
    # =================================================================
    more_watches = [
        ("set up a watch for new disk entities", None, ["disk"]),
        ("monitor for cluster changes", None, ["cluster"]),
        ("subscribe to node create events", None, ["node"]),
        ("watch for container deletions", None, ["container"]),
        ("register a watch for snapshot creation", None, ["snapshot"]),
        ("monitor network entity changes", None, ["network"]),
        ("watch for new alerts being created", None, ["alert"]),
        ("subscribe to task completions", None, ["task"]),
        ("watch for any changes to image entities", None, ["image"]),
        ("monitor VM power state changes", None, ["vm"]),
        ("set up watch for volume_group modifications", None, ["volume_group"]),
        ("subscribe to protection domain events", None, ["protection_domain"]),
        ("watch for subnet changes", None, ["subnet"]),
        ("monitor for new project entities", None, ["project"]),
        ("register watch for category modifications", None, ["category"]),
    ]
    for query, et, must_have in more_watches:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "Watch",
            "proto_must_have": must_have,
            "category": "watch_extended"
        })

    # =================================================================
    # SECTION 53: More search variations
    # =================================================================
    more_searches = [
        ("search for entities named web-server", None, ["search_term", "web-server"]),
        ("find anything matching mysql", None, ["search_term", "mysql"]),
        ("search IDF for oracle", None, ["search_term", "oracle"]),
        ("find entities containing kubernetes", None, ["search_term", "kubernetes"]),
        ("search for docker entities", None, ["search_term", "docker"]),
        ("find entities matching mongodb", None, ["search_term", "mongodb"]),
        ("search for production-db", None, ["search_term", "production-db"]),
        ("find entities containing backup-2024", None, ["search_term", "backup-2024"]),
        ("search for entities with redis in name", None, ["search_term", "redis"]),
        ("find all entities matching load-balancer", None, ["search_term", "load-balancer"]),
        ("search for nginx entities", None, ["search_term", "nginx"]),
        ("find entities containing test-cluster", None, ["search_term", "test-cluster"]),
        ("search for dev-environment", None, ["search_term", "dev-environment"]),
        ("find entities matching staging-vm", None, ["search_term", "staging-vm"]),
        ("search for entities containing monitoring", None, ["search_term", "monitoring"]),
    ]
    for query, et, must_have in more_searches:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "SpotLightSearch",
            "proto_must_have": must_have,
            "category": "search_extended"
        })

    # =================================================================
    # SECTION 54: More entity type introspection
    # =================================================================
    more_entity_types = [
        ("what is the vm entity type definition", None, ["entity_type_name", "vm"]),
        ("describe the disk entity type", None, ["entity_type_name", "disk"]),
        ("get schema for alert entity type", None, ["entity_type_name", "alert"]),
        ("show me the event entity type info", None, ["entity_type_name", "event"]),
        ("describe task entity type", None, ["entity_type_name", "task"]),
        ("get details of network entity type", None, ["entity_type_name", "network"]),
        ("show subnet entity type definition", None, ["entity_type_name", "subnet"]),
        ("describe image entity type schema", None, ["entity_type_name", "image"]),
        ("what is the category entity type", None, ["entity_type_name", "category"]),
        ("get info about protection_domain entity type", None, ["entity_type_name", "protection_domain"]),
    ]
    for query, et, must_have in more_entity_types:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntityTypes",
            "proto_must_have": must_have,
            "category": "entity_type_extended"
        })

    # =================================================================
    # SECTION 55: More metric type queries
    # =================================================================
    more_metric_types = [
        ("what columns does the disk entity type have", None, ["regex", "disk"]),
        ("show fields for alert entity type", None, ["regex", "alert"]),
        ("list available attributes for event", None, ["regex", "event"]),
        ("get metric definitions for task", None, ["regex", "task"]),
        ("what attributes are registered for network", None, ["regex", "network"]),
        ("show schema columns for subnet", None, ["regex", "subnet"]),
        ("list all fields for image entity", None, ["regex", "image"]),
        ("get available metrics for category", None, ["regex", "category"]),
        ("what metrics exist for project type", None, ["regex", "project"]),
        ("show metric types for storage_pool", None, ["regex", "storage_pool"]),
    ]
    for query, et, must_have in more_metric_types:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMetricTypes",
            "proto_must_have": must_have,
            "category": "metric_type_extended"
        })

    # =================================================================
    # SECTION 56: More combined filter+sort+limit patterns
    # =================================================================
    more_combined = [
        ("get top 10 powered on VMs sorted by memory descending", "vm",
         ["where_clause", "power_state", "raw_sort_order", "raw_limit"]),
        ("show first 5 critical alerts sorted by time", "alert",
         ["where_clause", "severity", "raw_sort_order", "raw_limit"]),
        ("list top 3 largest disks of type SSD", "disk",
         ["where_clause", "raw_sort_order", "raw_limit"]),
        ("get 10 busiest nodes with more than 20 VMs", "node",
         ["where_clause", "num_vms", "raw_sort_order", "raw_limit"]),
        ("show VMs where memory > 8192 sorted by name limit 20", "vm",
         ["where_clause", "memory", "raw_sort_order", "raw_limit"]),
        ("list first 50 VMs sorted by creation time where cluster = prod", "vm",
         ["where_clause", "cluster", "raw_sort_order", "raw_limit"]),
        ("get top 5 containers by usage where replication_factor = 2", "container",
         ["where_clause", "replication_factor", "raw_sort_order", "raw_limit"]),
        ("show 10 newest events where severity = critical", "event",
         ["where_clause", "severity", "raw_sort_order", "raw_limit"]),
        ("list top 20 VMs by vCPU count where power_state = on", "vm",
         ["where_clause", "power_state", "raw_sort_order", "raw_limit"]),
        ("get first 100 tasks where status = failed sorted by start_time", "task",
         ["where_clause", "status", "raw_sort_order", "raw_limit"]),
    ]
    for query, et, must_have in more_combined:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "combined_extended"
        })

    # =================================================================
    # SECTION 57: More register/unregister metric patterns
    # =================================================================
    more_register_metrics = [
        ("register new attribute temperature for entity type node as integer", None,
         ["metric_type_list", "temperature", "node"]),
        ("add metric write_iops for disk entity type", None,
         ["metric_type_list", "write_iops", "disk"]),
        ("register attribute custom_tag for vm", None,
         ["metric_type_list", "custom_tag", "vm"]),
        ("add attribute alert_count for cluster entity type", None,
         ["metric_type_list", "alert_count", "cluster"]),
        ("register metric network_throughput for node", None,
         ["metric_type_list", "network_throughput", "node"]),
        ("unregister metric temperature from node", None,
         ["metric_type_list", "temperature", "node"]),
        ("remove attribute custom_tag from vm", None,
         ["metric_type_list", "custom_tag", "vm"]),
        ("unregister attribute write_iops from disk", None,
         ["metric_type_list", "write_iops", "disk"]),
        ("remove metric alert_count from cluster", None,
         ["metric_type_list", "alert_count", "cluster"]),
        ("unregister attribute network_throughput from node", None,
         ["metric_type_list", "network_throughput", "node"]),
    ]
    reg_unreg_apis = ["RegisterMetricTypes"] * 5 + ["UnregisterMetricTypes"] * 5
    for i, (query, et, must_have) in enumerate(more_register_metrics):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": reg_unreg_apis[i],
            "proto_must_have": must_have,
            "category": "register_unregister_extended"
        })

    # =================================================================
    # SECTION 58: More batch operations
    # =================================================================
    more_batch = [
        ("batch get VMs, nodes, and disks information", None, ["query_list"]),
        ("get all VMs and all clusters in one call", None, ["query_list"]),
        ("batch query for alerts, events, and tasks", None, ["query_list"]),
        ("batch update VMs vm-a, vm-b, vm-c setting status to active", None, ["entity_list"]),
        ("bulk update nodes node-1 through node-5 setting maintenance to false", None, ["entity_list"]),
        ("batch delete alerts alert-old-1, alert-old-2, alert-old-3", None, ["entity_list"]),
        ("bulk remove VMs vm-temp-1, vm-temp-2, vm-temp-3, vm-temp-4", None, ["entity_list"]),
        ("batch get VMs where power=on and nodes where hypervisor=kKvm", None, ["query_list"]),
        ("batch delete nodes node-decom-1 and node-decom-2", None, ["entity_list"]),
        ("bulk update disks disk-1, disk-2 setting tier to cold", None, ["entity_list"]),
    ]
    batch_apis = [
        "BatchGetEntitiesWithMetrics", "BatchGetEntitiesWithMetrics",
        "BatchGetEntitiesWithMetrics", "BatchUpdateEntities",
        "BatchUpdateEntities", "BatchDeleteEntities",
        "BatchDeleteEntities", "BatchGetEntitiesWithMetrics",
        "BatchDeleteEntities", "BatchUpdateEntities"
    ]
    for i, (query, et, must_have) in enumerate(more_batch):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": batch_apis[i],
            "proto_must_have": must_have,
            "category": "batch_extended"
        })

    # =================================================================
    # SECTION 59: Derived metrics and complex query patterns
    # =================================================================
    derived_patterns = [
        ("get VMs with derived metric avg_io_latency", "vm", ["vm"]),
        ("show average io latency for all VMs", "vm", ["aggregate_columns", "kAvg"]),
        ("get VMs where avg_io_latency > 1000", "vm", ["where_clause"]),
        ("show top VMs by IO latency", "vm", ["raw_sort_order"]),
        ("get nodes with total_io_time_usecs metric", "node", ["node"]),
    ]
    for query, et, must_have in derived_patterns:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "derived_metrics"
        })

    # =================================================================
    # SECTION 60: Error scenario phrasings (should still work)
    # =================================================================
    tricky_phrasings = [
        ("can I see all the VMs please", "vm", ["vm"]),
        ("what virtual machines do we have", "vm", ["vm"]),
        ("get me everything about VMs", "vm", ["vm"]),
        ("I need all node data", "node", ["node"]),
        ("show disk information", "disk", ["disk"]),
        ("pull up cluster details", "cluster", ["cluster"]),
        ("what are the storage containers", "container", ["container"]),
        ("tell me about alerts", "alert", ["alert"]),
        ("fetch task list", "task", ["task"]),
        ("get event data", "event", ["event"]),
        ("show all virtual disks", "virtual_disk", ["virtual_disk"]),
        ("list volume groups please", "volume_group", ["volume_group"]),
        ("I want to see protection domains", "protection_domain", ["protection_domain"]),
        ("what snapshots exist", "snapshot", ["snapshot"]),
        ("get all images from IDF", "image", ["image"]),
    ]
    for query, et, must_have in tricky_phrasings:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "tricky_phrasings"
        })

    # =================================================================
    # SECTION 61: Column selection with where clause
    # =================================================================
    col_where = [
        ("get vm_name and power_state for VMs where is_cvm = 0", "vm",
         ["raw_columns", "vm_name", "power_state", "where_clause", "is_cvm"]),
        ("show node_name for nodes where hypervisor_type = kKvm", "node",
         ["raw_columns", "node_name", "where_clause", "hypervisor_type"]),
        ("get cluster_name and version for clusters where num_nodes > 3", "cluster",
         ["raw_columns", "cluster_name", "version", "where_clause", "num_nodes"]),
        ("show vm_name, memory_mb for VMs where power_state = on", "vm",
         ["raw_columns", "vm_name", "memory_mb", "where_clause", "power_state"]),
        ("get disk_label for disks where capacity_bytes > 1000000000", "disk",
         ["raw_columns", "disk_label", "where_clause", "capacity_bytes"]),
        ("show container_name for containers where usage > 50%", "container",
         ["raw_columns", "container_name", "where_clause"]),
        ("get vm_name, num_vcpus for VMs where memory_mb >= 4096", "vm",
         ["raw_columns", "vm_name", "num_vcpus", "where_clause", "memory_mb"]),
        ("show node_name, cpu_usage for nodes where num_vms > 10", "node",
         ["raw_columns", "node_name", "where_clause", "num_vms"]),
        ("get cluster_name for clusters where version contains 6.", "cluster",
         ["raw_columns", "cluster_name", "where_clause", "version"]),
        ("show severity and message for alerts where resolved = false", "alert",
         ["raw_columns", "severity", "where_clause", "resolved"]),
    ]
    for query, et, must_have in col_where:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "column_where_combined"
        })

    # =================================================================
    # SECTION 62: More GetMasterLocation variations
    # =================================================================
    more_master = [
        ("which node is the IDF master", None, []),
        ("where is the insights master running", None, []),
        ("show IDF master node", None, []),
        ("get the insights server master", None, []),
        ("find the master location for IDF", None, []),
    ]
    for query, et, must_have in more_master:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMasterLocation",
            "proto_must_have": must_have,
            "category": "master_location_extended"
        })

    # =================================================================
    # SECTION 63: More GetEntities by GUID
    # =================================================================
    more_guid = [
        ("get the specific VM with id prod-vm-uuid-001", None,
         ["entity_guid_list", "vm", "prod-vm-uuid-001"]),
        ("fetch node entity with guid abc-def-123", None,
         ["entity_guid_list", "node", "abc-def-123"]),
        ("retrieve specific disk by id ssd-disk-id-999", None,
         ["entity_guid_list", "disk", "ssd-disk-id-999"]),
        ("get cluster by guid main-cluster-uuid", None,
         ["entity_guid_list", "cluster", "main-cluster-uuid"]),
        ("fetch container entity with id backup-ctr-uuid", None,
         ["entity_guid_list", "container", "backup-ctr-uuid"]),
    ]
    for query, et, must_have in more_guid:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntities",
            "proto_must_have": must_have,
            "category": "guid_extended"
        })

    # =================================================================
    # SECTION 64: More GetMetricData / PutMetricData
    # =================================================================
    more_metric_data = [
        ("get time-series data for read_iops of disk disk-ssd-1", None,
         ["entity_type_name", "disk", "read_iops"]),
        ("fetch metric history for memory_usage of node node-01", None,
         ["entity_type_name", "node", "memory_usage"]),
        ("get metric data for network_bytes_in of vm vm-web", None,
         ["entity_type_name", "vm", "network_bytes_in"]),
        ("read time series for storage_used of container ctr-main", None,
         ["entity_type_name", "container", "storage_used"]),
        ("get historical data for cpu_frequency of node node-5", None,
         ["entity_type_name", "node", "cpu_frequency"]),
        ("write metric read_iops value 5000 for disk disk-ssd-1", None,
         ["entity_with_metric_list", "read_iops", "disk-ssd-1"]),
        ("publish metric memory_usage value 70 for node node-01", None,
         ["entity_with_metric_list", "memory_usage", "node-01"]),
        ("put metric cpu_temp value 65 for node node-hot", None,
         ["entity_with_metric_list", "cpu_temp", "node-hot"]),
        ("write metric bandwidth value 1000 for network net-1", None,
         ["entity_with_metric_list", "bandwidth", "net-1"]),
        ("publish metric io_latency value 5 for disk disk-fast", None,
         ["entity_with_metric_list", "io_latency", "disk-fast"]),
    ]
    metric_data_apis = ["GetMetricData"] * 5 + ["PutMetricData"] * 5
    for i, (query, et, must_have) in enumerate(more_metric_data):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": metric_data_apis[i],
            "proto_must_have": must_have,
            "category": "metric_data_extended"
        })

    # =================================================================
    # SECTION 65: More trail/history queries
    # =================================================================
    more_trail = [
        ("show modification history for VM vm-prod-1", None,
         ["entity_guid_list", "vm", "vm-prod-1"]),
        ("get audit log for node node-critical", None,
         ["entity_guid_list", "node", "node-critical"]),
        ("show change trail for cluster main-cluster", None,
         ["entity_guid_list", "cluster", "main-cluster"]),
        ("get entity modification history for disk disk-replaced", None,
         ["entity_guid_list", "disk", "disk-replaced"]),
        ("show version history for container ctr-backup", None,
         ["entity_guid_list", "container", "ctr-backup"]),
    ]
    for query, et, must_have in more_trail:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesTrail",
            "proto_must_have": must_have,
            "category": "trail_extended"
        })

    # =================================================================
    # SECTION 66: More register entity type patterns
    # =================================================================
    more_register_types = [
        ("register new entity type load_balancer", None,
         ["entity_type_info_list", "load_balancer"]),
        ("create entity type kubernetes_pod with parent node", None,
         ["entity_type_info_list", "kubernetes_pod"]),
        ("register entity type docker_container", None,
         ["entity_type_info_list", "docker_container"]),
        ("create new entity type service_endpoint", None,
         ["entity_type_info_list", "service_endpoint"]),
        ("register entity type config_rule with parent cluster", None,
         ["entity_type_info_list", "config_rule"]),
        ("create entity type metric_collector", None,
         ["entity_type_info_list", "metric_collector"]),
        ("register new entity type alert_policy", None,
         ["entity_type_info_list", "alert_policy"]),
        ("create entity type backup_schedule", None,
         ["entity_type_info_list", "backup_schedule"]),
        ("register entity type replication_job", None,
         ["entity_type_info_list", "replication_job"]),
        ("create new entity type health_check", None,
         ["entity_type_info_list", "health_check"]),
    ]
    for query, et, must_have in more_register_types:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "RegisterEntityTypes",
            "proto_must_have": must_have,
            "category": "register_types_extended"
        })

    # =================================================================
    # SECTION 67: More put event patterns
    # =================================================================
    more_events = [
        ("publish event upgrade_started for cluster cluster-prod", None,
         ["event_type", "cluster"]),
        ("create event vm_migrated for VM vm-moved", None,
         ["event_type", "vm"]),
        ("put event disk_replaced for disk disk-new", None,
         ["event_type", "disk"]),
        ("publish event node_rebooted for node node-01", None,
         ["event_type", "node"]),
        ("create event container_resized for container ctr-expanded", None,
         ["event_type", "container"]),
        ("put event snapshot_created for snapshot snap-latest", None,
         ["event_type", "snapshot"]),
        ("publish event network_change for network net-prod", None,
         ["event_type", "network"]),
        ("create event alert_resolved for alert alert-fixed", None,
         ["event_type", "alert"]),
        ("put event task_completed for task task-done", None,
         ["event_type", "task"]),
        ("publish event image_uploaded for image img-new", None,
         ["event_type", "image"]),
    ]
    for query, et, must_have in more_events:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "PutEvent",
            "proto_must_have": must_have,
            "category": "put_event_extended"
        })

    # =================================================================
    # SECTION 67B: More complex where + like combinations
    # =================================================================
    complex_like = [
        ("get VMs where vm_name matches .*prod.* and power_state = on", "vm",
         ["where_clause", "vm_name", "kLike", "power_state"]),
        ("show nodes where node_name like .*NTNX.* and hypervisor_type = kKvm", "node",
         ["where_clause", "node_name", "kLike", "hypervisor_type"]),
        ("find clusters where cluster_name contains test and version = 6.0", "cluster",
         ["where_clause", "cluster_name", "kLike", "version"]),
        ("get disks where disk_label matches .*ssd.* and capacity > 1000000000", "disk",
         ["where_clause", "disk_label", "kLike"]),
        ("show alerts where message contains timeout and severity = critical", "alert",
         ["where_clause", "kLike", "severity"]),
        ("get VMs where vm_name like .*dev.* sorted by memory_mb descending", "vm",
         ["where_clause", "vm_name", "kLike", "raw_sort_order", "memory_mb"]),
        ("find nodes where node_name contains Block and num_vms > 10", "node",
         ["where_clause", "node_name", "kLike", "num_vms"]),
        ("show VMs where vm_name matches .*web.* limit 20", "vm",
         ["where_clause", "vm_name", "kLike", "raw_limit"]),
        ("get clusters where cluster_name like .*prod.* and num_nodes >= 3", "cluster",
         ["where_clause", "cluster_name", "kLike", "num_nodes"]),
        ("find VMs where description contains kubernetes and power_state = on", "vm",
         ["where_clause", "kLike", "power_state"]),
    ]
    for query, et, must_have in complex_like:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "complex_like"
        })

    # =================================================================
    # SECTION 67C: More group_by with aggregation
    # =================================================================
    groupby_agg = [
        ("get count of VMs grouped by cluster_name", "vm",
         ["group_by", "cluster_name"]),
        ("show sum of memory_mb per power_state for VMs", "vm",
         ["group_by", "power_state", "aggregate_columns", "memory_mb"]),
        ("count nodes per hypervisor_type", "node",
         ["group_by", "hypervisor_type"]),
        ("get average capacity_bytes per storage_tier for disks", "disk",
         ["group_by", "storage_tier", "aggregate_columns", "capacity_bytes"]),
        ("count alerts per severity level", "alert",
         ["group_by", "severity"]),
        ("show total num_vcpus grouped by power_state for VMs", "vm",
         ["group_by", "power_state", "aggregate_columns", "num_vcpus"]),
        ("average memory per cluster for VMs", "vm",
         ["group_by", "cluster", "aggregate_columns"]),
        ("count containers grouped by replication_factor", "container",
         ["group_by", "replication_factor"]),
        ("max io_latency per disk tier", "disk",
         ["group_by", "aggregate_columns", "kMax"]),
        ("count tasks by status", "task",
         ["group_by", "status"]),
    ]
    for query, et, must_have in groupby_agg:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "groupby_aggregation"
        })

    # =================================================================
    # SECTION 67D: More exists/not-exists patterns
    # =================================================================
    more_exists = [
        ("get VMs where ngt_version attribute exists", "vm",
         ["where_clause", "ngt_version", "kExists"]),
        ("show nodes where bmc_ip exists", "node",
         ["where_clause", "bmc_ip", "kExists"]),
        ("find clusters where external_ip_address exists", "cluster",
         ["where_clause", "external_ip_address", "kExists"]),
        ("get VMs where protection_domain_name exists", "vm",
         ["where_clause", "protection_domain_name", "kExists"]),
        ("show disks where serial_number attribute exists", "disk",
         ["where_clause", "serial_number", "kExists"]),
        ("find VMs where snapshot_id exists", "vm",
         ["where_clause", "snapshot_id", "kExists"]),
        ("get containers where encryption_key exists", "container",
         ["where_clause", "encryption_key", "kExists"]),
        ("show nodes where ipmi_ip exists", "node",
         ["where_clause", "ipmi_ip", "kExists"]),
        ("find VMs where guest_tools exists", "vm",
         ["where_clause", "guest_tools", "kExists"]),
        ("get clusters where proxy_config exists", "cluster",
         ["where_clause", "proxy_config", "kExists"]),
    ]
    for query, et, must_have in more_exists:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_exists_extended"
        })

    # =================================================================
    # SECTION 67E: More phrasings for updates and deletes
    # =================================================================
    action_phrasings = [
        ("I want to update VM test-1 and set memory to 4096", "vm",
         ["entity_guid", "vm", "test-1", "attribute_data", "memory"]),
        ("please delete the node entity old-node-x", "node",
         ["entity_guid", "node", "old-node-x"]),
        ("can you update cluster main-cluster setting version to 7.0", "cluster",
         ["entity_guid", "cluster", "main-cluster", "attribute_data", "version"]),
        ("remove the VM named legacy-vm from IDF", "vm",
         ["entity_guid", "vm", "legacy-vm"]),
        ("set the power state of VM app-server to off", "vm",
         ["entity_guid", "vm", "app-server", "attribute_data", "power_state"]),
        ("delete cluster entity decommissioned-cl", "cluster",
         ["entity_guid", "cluster", "decommissioned-cl"]),
        ("update node host-05 setting cpu_model to Xeon", "node",
         ["entity_guid", "node", "host-05", "attribute_data", "cpu_model"]),
        ("remove disk bad-ssd from the system", "disk",
         ["entity_guid", "disk", "bad-ssd"]),
        ("change container backup-ctr name to archive-ctr", "container",
         ["entity_guid", "container", "backup-ctr", "attribute_data"]),
        ("delete the image entity unused-iso", "image",
         ["entity_guid", "image", "unused-iso"]),
        ("update VM db-server setting num_vcpus to 16", "vm",
         ["entity_guid", "vm", "db-server", "attribute_data", "num_vcpus"]),
        ("remove snapshot old-snap-001", "snapshot",
         ["entity_guid", "snapshot", "old-snap-001"]),
        ("update disk fast-disk setting tier to hot", "disk",
         ["entity_guid", "disk", "fast-disk", "attribute_data", "tier"]),
        ("delete protection_domain pd-deprecated", "protection_domain",
         ["entity_guid", "protection_domain", "pd-deprecated"]),
        ("set maintenance_mode to true for node node-repair-2", "node",
         ["entity_guid", "node", "node-repair-2", "attribute_data", "maintenance_mode"]),
        ("remove the volume_group entity vg-legacy", "volume_group",
         ["entity_guid", "volume_group", "vg-legacy"]),
        ("update alert alert-99 setting acknowledged to true", "alert",
         ["entity_guid", "alert", "alert-99", "attribute_data", "acknowledged"]),
        ("delete task entity completed-task-xyz", "task",
         ["entity_guid", "task", "completed-task-xyz"]),
        ("update project proj-alpha setting status to active", "project",
         ["entity_guid", "project", "proj-alpha", "attribute_data", "status"]),
        ("remove category cat-unused from IDF", "category",
         ["entity_guid", "category", "cat-unused"]),
    ]
    action_apis = [
        "UpdateEntity", "DeleteEntity", "UpdateEntity", "DeleteEntity",
        "UpdateEntity", "DeleteEntity", "UpdateEntity", "DeleteEntity",
        "UpdateEntity", "DeleteEntity", "UpdateEntity", "DeleteEntity",
        "UpdateEntity", "DeleteEntity", "UpdateEntity", "DeleteEntity",
        "UpdateEntity", "DeleteEntity", "UpdateEntity", "DeleteEntity",
    ]
    for i, (query, et, must_have) in enumerate(action_phrasings):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": action_apis[i],
            "proto_must_have": must_have,
            "category": "action_phrasings"
        })

    # =================================================================
    # SECTION 67F: Specific proto field patterns from test files
    # =================================================================
    proto_field_patterns = [
        ("get VMs showing _entity_id_ field", "vm", ["_entity_id_"]),
        ("show _entity_id_ and vm_name for all VMs", "vm", ["_entity_id_", "vm_name"]),
        ("get _entity_id_ for nodes", "node", ["_entity_id_"]),
        ("show query_name for VM query", "vm", ["query_name"]),
        ("get VMs with a specific query_name get_all_vms", "vm", ["query_name"]),
    ]
    for query, et, must_have in proto_field_patterns:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "proto_fields"
        })

    # =================================================================
    # SECTION 67G: Additional conversational/natural language
    # =================================================================
    more_natural = [
        ("how many VMs are powered on right now", "vm", ["where_clause", "power_state"]),
        ("which hosts have the most VMs running on them", "node", ["raw_sort_order", "num_vms"]),
        ("are there any critical alerts I should know about", "alert", ["where_clause", "severity"]),
        ("what's the storage utilization across containers", "container", ["container"]),
        ("show me VMs that haven't been powered on", "vm", ["where_clause", "power_state"]),
        ("which disk is running out of space", "disk", ["where_clause"]),
        ("how much total memory do we have in the cluster", "node", ["aggregate_columns"]),
        ("find me the biggest VM by memory allocation", "vm", ["raw_sort_order", "memory"]),
        ("are there any failed tasks I need to look at", "task", ["where_clause", "status"]),
        ("what version are our clusters running", "cluster", ["raw_columns", "version"]),
        ("show me VMs on a specific host node-01", "vm", ["where_clause", "node"]),
        ("which containers are using deduplication", "container", ["where_clause"]),
        ("find VMs without any protection domain", "vm", ["where_clause"]),
        ("what is our total VM count per cluster", "vm", ["group_by", "cluster"]),
        ("show me nodes that are in maintenance mode", "node", ["where_clause", "maintenance"]),
        ("how many different hypervisor types do we have", "node", ["group_by", "hypervisor_type"]),
        ("get me the list of powered on VMs sorted by name", "vm",
         ["where_clause", "power_state", "raw_sort_order", "vm_name"]),
        ("what VMs were created most recently", "vm", ["raw_sort_order"]),
        ("find containers with compression enabled", "container", ["where_clause"]),
        ("show the health status of all nodes", "node", ["node"]),
    ]
    for query, et, must_have in more_natural:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "natural_language_extended"
        })

    # =================================================================
    # SECTION 68: Cursor query patterns from cursor_query_eid_sort.py
    # =================================================================
    more_cursor = [
        ("use cursor query to paginate through all VMs sorted by entity_id batch 100", "vm",
         ["cursor_query_info", "batch_size"]),
        ("cursor paginate alerts with batch size 200", "alert",
         ["cursor_query_info", "batch_size"]),
        ("paginate events using cursor query batch 1000", "event",
         ["cursor_query_info", "batch_size"]),
        ("cursor query for tasks batch 50 sorted by entity_id", "task",
         ["cursor_query_info", "batch_size"]),
        ("initial cursor query for all nodes batch 500", "node",
         ["cursor_query_info", "is_initial_cursor_query"]),
        ("cursor paginate through disks batch 200", "disk",
         ["cursor_query_info", "batch_size"]),
        ("use cursor to iterate over containers batch 100", "container",
         ["cursor_query_info", "batch_size"]),
        ("cursor query all VMs with filter power_state = on batch 50", "vm",
         ["cursor_query_info", "where_clause", "power_state"]),
        ("paginate through cluster entities using cursor batch 25", "cluster",
         ["cursor_query_info", "batch_size"]),
        ("initial cursor query for all images batch 100", "image",
         ["cursor_query_info", "is_initial_cursor_query"]),
    ]
    for query, et, must_have in more_cursor:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "cursor_extended"
        })

    # =================================================================
    # SECTION 69: kIN with str_list patterns
    # =================================================================
    more_in = [
        ("get VMs where cluster_uuid in [uuid-1, uuid-2, uuid-3]", "vm",
         ["where_clause", "cluster_uuid", "kIN"]),
        ("show nodes where node_id in [node-a, node-b]", "node",
         ["where_clause", "node_id", "kIN"]),
        ("find disks where status in [online, degraded, offline]", "disk",
         ["where_clause", "status", "kIN"]),
        ("get alerts where category in [hardware, software, network]", "alert",
         ["where_clause", "category", "kIN"]),
        ("show VMs where vm_name in [web-1, web-2, web-3, web-4]", "vm",
         ["where_clause", "vm_name", "kIN"]),
        ("find containers where name in [default, backup, archive]", "container",
         ["where_clause", "name", "kIN"]),
        ("get tasks where type in [create, update, delete, migrate]", "task",
         ["where_clause", "type", "kIN"]),
        ("show clusters where version in [6.0, 6.1, 6.5]", "cluster",
         ["where_clause", "version", "kIN"]),
        ("find VMs where power_state in [on, suspended]", "vm",
         ["where_clause", "power_state", "kIN"]),
        ("get events where type in [error, warning, info]", "event",
         ["where_clause", "type", "kIN"]),
    ]
    for query, et, must_have in more_in:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "where_in_extended"
        })

    # =================================================================
    # SECTION 70: Scenario-based questions (real-world use cases)
    # =================================================================
    scenarios = [
        ("find overprovisioned VMs with more vCPUs than needed", "vm",
         ["where_clause", "num_vcpus"]),
        ("show VMs that might need more memory", "vm", ["where_clause", "memory"]),
        ("identify nodes at risk of running out of storage", "node", ["where_clause"]),
        ("find powered off VMs wasting resources", "vm", ["where_clause", "power_state"]),
        ("show clusters approaching capacity", "cluster", ["where_clause"]),
        ("identify disks with high IO latency", "disk", ["where_clause"]),
        ("find VMs running on specific hypervisor", "vm", ["where_clause", "hypervisor"]),
        ("show unresolved critical alerts", "alert", ["where_clause", "severity"]),
        ("identify large VMs consuming most resources", "vm", ["raw_sort_order", "raw_limit"]),
        ("find VMs matching a naming convention prod-*", "vm", ["where_clause", "kLike"]),
        ("show all VMs in the production cluster", "vm", ["where_clause", "cluster"]),
        ("find nodes with hardware issues", "node", ["where_clause"]),
        ("identify idle containers with no usage", "container", ["where_clause"]),
        ("show tasks that have been running too long", "task", ["where_clause"]),
        ("find VMs without NGT installed", "vm", ["where_clause"]),
    ]
    for query, et, must_have in scenarios:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "scenarios"
        })

    # =================================================================
    # SECTION 71: More API-specific phrasings (filling gaps)
    # =================================================================
    # More GetEntityTypes phrasings
    more_get_types = [
        ("show entity type schema for vm", None, ["entity_type_name", "vm"]),
        ("get entity type definition for node", None, ["entity_type_name", "node"]),
        ("describe cluster entity type", None, ["entity_type_name", "cluster"]),
        ("what is the definition of disk entity type", None, ["entity_type_name", "disk"]),
        ("show info about container entity type", None, ["entity_type_name", "container"]),
        ("get details for virtual_disk entity type", None, ["entity_type_name", "virtual_disk"]),
        ("describe network entity type", None, ["entity_type_name", "network"]),
        ("show entity type for subnet", None, ["entity_type_name", "subnet"]),
        ("info about image entity type", None, ["entity_type_name", "image"]),
        ("describe volume_group entity type schema", None, ["entity_type_name", "volume_group"]),
    ]
    for query, et, must_have in more_get_types:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntityTypes",
            "proto_must_have": must_have,
            "category": "entity_types_more"
        })

    # More GetMetricTypes phrasings
    more_get_metrics = [
        ("show all metrics registered for vm", None, ["regex", "vm"]),
        ("get available fields for node entity", None, ["regex", "node"]),
        ("what metrics can I query for disk", None, ["regex", "disk"]),
        ("list registered metrics for cluster", None, ["regex", "cluster"]),
        ("show attributes of container entity", None, ["regex", "container"]),
        ("get queryable fields for alert type", None, ["regex", "alert"]),
        ("what attributes can I filter on for vm", None, ["regex", "vm"]),
        ("list indexed fields for node entity type", None, ["regex", "node"]),
        ("show all queryable metrics in the system", None, ["regex"]),
        ("get list of all registered metric types", None, ["regex"]),
    ]
    for query, et, must_have in more_get_metrics:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMetricTypes",
            "proto_must_have": must_have,
            "category": "metric_types_more"
        })

    # More Watch phrasings
    more_watch = [
        ("I want to be notified when new VMs are created", None, ["vm"]),
        ("set up notifications for node failures", None, ["node"]),
        ("alert me when disks are deleted", None, ["disk"]),
        ("start monitoring for cluster changes", None, ["cluster"]),
        ("I need real-time updates on VM changes", None, ["vm"]),
        ("register for notifications on alert creation", None, ["alert"]),
        ("subscribe to real-time task updates", None, ["task"]),
        ("watch for any modifications to network entities", None, ["network"]),
        ("notify me of new image uploads", None, ["image"]),
        ("monitor for snapshot deletions", None, ["snapshot"]),
    ]
    for query, et, must_have in more_watch:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "Watch",
            "proto_must_have": must_have,
            "category": "watch_more"
        })

    # More SpotLightSearch phrasings
    more_search = [
        ("search the entire system for anything named proxy", None, ["search_term", "proxy"]),
        ("look up entities matching firewall", None, ["search_term", "firewall"]),
        ("search IDF for ansible", None, ["search_term", "ansible"]),
        ("find any entity with terraform in the name", None, ["search_term", "terraform"]),
        ("look for entities containing vault", None, ["search_term", "vault"]),
        ("search all entities for consul", None, ["search_term", "consul"]),
        ("find anything matching prometheus", None, ["search_term", "prometheus"]),
        ("search for grafana entities", None, ["search_term", "grafana"]),
        ("look up entities with jenkins in name", None, ["search_term", "jenkins"]),
        ("search for anything containing postgres", None, ["search_term", "postgres"]),
    ]
    for query, et, must_have in more_search:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "SpotLightSearch",
            "proto_must_have": must_have,
            "category": "search_more"
        })

    # More RegisterEntityTypes phrasings
    more_reg_types = [
        ("add a new entity type called network_policy", None,
         ["entity_type_info_list", "network_policy"]),
        ("register entity type storage_class", None,
         ["entity_type_info_list", "storage_class"]),
        ("create a new entity type firewall_rule", None,
         ["entity_type_info_list", "firewall_rule"]),
        ("register entity type dns_record", None,
         ["entity_type_info_list", "dns_record"]),
        ("add entity type certificate to IDF", None,
         ["entity_type_info_list", "certificate"]),
        ("register new entity type audit_log with parent cluster", None,
         ["entity_type_info_list", "audit_log"]),
        ("create entity type security_group", None,
         ["entity_type_info_list", "security_group"]),
        ("register entity type route_table", None,
         ["entity_type_info_list", "route_table"]),
        ("add new entity type access_control_policy", None,
         ["entity_type_info_list", "access_control_policy"]),
        ("register entity type user_group", None,
         ["entity_type_info_list", "user_group"]),
    ]
    for query, et, must_have in more_reg_types:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "RegisterEntityTypes",
            "proto_must_have": must_have,
            "category": "register_more"
        })

    # More RegisterMetricTypes phrasings
    more_reg_metrics = [
        ("add attribute ip_address for vm entity type", None,
         ["metric_type_list", "ip_address", "vm"]),
        ("register metric packets_in for node", None,
         ["metric_type_list", "packets_in", "node"]),
        ("add metric write_latency for disk entity type", None,
         ["metric_type_list", "write_latency", "disk"]),
        ("register attribute owner for cluster", None,
         ["metric_type_list", "owner", "cluster"]),
        ("add attribute compression_ratio for container", None,
         ["metric_type_list", "compression_ratio", "container"]),
        ("register metric error_count for node entity type", None,
         ["metric_type_list", "error_count", "node"]),
        ("add attribute last_backup_time for vm", None,
         ["metric_type_list", "last_backup_time", "vm"]),
        ("register metric connection_count for network", None,
         ["metric_type_list", "connection_count", "network"]),
        ("add attribute creation_time for snapshot entity type", None,
         ["metric_type_list", "creation_time", "snapshot"]),
        ("register metric queue_depth for disk", None,
         ["metric_type_list", "queue_depth", "disk"]),
    ]
    for query, et, must_have in more_reg_metrics:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "RegisterMetricTypes",
            "proto_must_have": must_have,
            "category": "register_metrics_more"
        })

    # More GetMasterLocation phrasings
    more_master_loc = [
        ("get IDF master", None, []),
        ("show insights master", None, []),
        ("who is master", None, []),
        ("master location query", None, []),
        ("get the IDF leader node", None, []),
    ]
    for query, et, must_have in more_master_loc:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetMasterLocation",
            "proto_must_have": must_have,
            "category": "master_more"
        })

    # =================================================================
    # SECTION 72: Complex multi-clause scenarios inspired by test_where_clause.py
    # =================================================================
    test_where_inspired = [
        ("get VMs where is_cvm equals 0 and check.score between 26 and 76 and vm_name contains PC and power_state = on",
         "vm", ["where_clause", "is_cvm", "check.score", "vm_name", "power_state"]),
        ("show nodes where hypervisor_type = kKvm and node_name contains TEST-HOST and check.score between 26 and 76",
         "node", ["where_clause", "hypervisor_type", "node_name", "check.score"]),
        ("get clusters where version = 5.0.1 and cluster_name not contains box and check.overall_score between 26 and 76",
         "cluster", ["where_clause", "version", "cluster_name", "check.overall_score"]),
        ("show VMs where check.score >= 76 and check.score < 101 and power_state = off and is_cvm = 0",
         "vm", ["where_clause", "check.score", "power_state", "is_cvm"]),
        ("get nodes where hypervisor_type = kVMWare and node_name contains TEST-HOST-2 and check.score between 0 and 26",
         "node", ["where_clause", "hypervisor_type", "node_name", "check.score"]),
    ]
    for query, et, must_have in test_where_inspired:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "test_where_complex"
        })

    # =================================================================
    # SECTION 73: More batch and specific patterns
    # =================================================================
    more_specific = [
        ("get all VMs that belong to cluster cluster-uuid-main", "vm",
         ["where_clause", "cluster"]),
        ("show nodes belonging to cluster main-cluster-id", "node",
         ["where_clause", "cluster"]),
        ("list VMs on node host-uuid-1", "vm",
         ["where_clause", "node"]),
        ("get disks attached to node node-id-5", "disk",
         ["where_clause", "node"]),
        ("show VMs in subnet subnet-prod", "vm",
         ["where_clause", "subnet"]),
        ("list VMs with category production", "vm",
         ["where_clause", "category"]),
        ("get VMs protected by protection_domain pd-main", "vm",
         ["where_clause", "protection_domain"]),
        ("show all VMs of project proj-alpha", "vm",
         ["where_clause", "project"]),
        ("list containers on storage_pool pool-1", "container",
         ["where_clause", "storage_pool"]),
        ("get nodes in availability_zone az-east", "node",
         ["where_clause", "availability_zone"]),
        ("show VMs with NGT installed", "vm",
         ["where_clause"]),
        ("get VMs without agent installed", "vm",
         ["where_clause"]),
        ("find VMs managed by PC", "vm",
         ["where_clause"]),
        ("show unprotected VMs", "vm",
         ["where_clause"]),
        ("list VMs not in any protection domain", "vm",
         ["where_clause"]),
        ("get VMs with thin provisioning enabled", "vm",
         ["where_clause"]),
        ("show clusters in connected state", "cluster",
         ["where_clause"]),
        ("find nodes with SSD tier disks", "node",
         ["where_clause"]),
        ("list containers with deduplication on", "container",
         ["where_clause"]),
        ("get VMs with more than 1 NIC", "vm",
         ["where_clause"]),
    ]
    for query, et, must_have in more_specific:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "GetEntitiesWithMetrics",
            "proto_must_have": must_have,
            "category": "specific_patterns"
        })

    # =================================================================
    # SECTION 74: More UnregisterMetricTypes
    # =================================================================
    more_unreg = [
        ("remove metric packets_in from node", None,
         ["metric_type_list", "packets_in", "node"]),
        ("unregister attribute ip_address from vm", None,
         ["metric_type_list", "ip_address", "vm"]),
        ("delete metric write_latency from disk", None,
         ["metric_type_list", "write_latency", "disk"]),
        ("remove attribute owner from cluster", None,
         ["metric_type_list", "owner", "cluster"]),
        ("unregister metric compression_ratio from container", None,
         ["metric_type_list", "compression_ratio", "container"]),
    ]
    for query, et, must_have in more_unreg:
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": "UnregisterMetricTypes",
            "proto_must_have": must_have,
            "category": "unregister_more"
        })

    # =================================================================
    # SECTION 75: Attach/Detach additional
    # =================================================================
    more_attach_detach = [
        ("attach cluster entity cluster-new with incarnation 1", None,
         ["entity_guid", "cluster"]),
        ("detach VM vm-old moving to cluster target-uuid", None,
         ["entity_guid", "vm"]),
        ("attach node node-joined with incarnation 3", None,
         ["entity_guid", "node"]),
        ("detach container ctr-migrate to cluster dest-uuid", None,
         ["entity_guid", "container"]),
        ("attach VM vm-replicated with incarnation id 7", None,
         ["entity_guid", "vm"]),
    ]
    ad_apis = ["AttachEntity", "DetachEntity", "AttachEntity", "DetachEntity", "AttachEntity"]
    for i, (query, et, must_have) in enumerate(more_attach_detach):
        qid += 1
        questions.append({
            "id": f"Q{qid:04d}",
            "query": query,
            "expected_api": ad_apis[i],
            "proto_must_have": must_have,
            "category": "attach_detach_more"
        })

    return questions


def main():
    print("=" * 70)
    print("IDF TEST QUESTION GENERATOR")
    print("=" * 70)

    # Scan files for patterns
    patterns = scan_files()

    # Generate questions
    questions = generate_questions(patterns)

    print(f"\nTotal questions generated: {len(questions)}")

    # Category breakdown
    categories = {}
    for q in questions:
        cat = q["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print("\nCategory breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # API breakdown
    apis = {}
    for q in questions:
        api = q["expected_api"]
        apis[api] = apis.get(api, 0) + 1
    print("\nAPI coverage:")
    for api, count in sorted(apis.items(), key=lambda x: -x[1]):
        print(f"  {api}: {count}")

    # Save to JSON
    output_path = os.path.join(os.path.dirname(__file__), "validation_questions.json")
    with open(output_path, "w") as f:
        json.dump(questions, f, indent=2)
    print(f"\nSaved to: {output_path}")

    return questions


if __name__ == "__main__":
    main()
