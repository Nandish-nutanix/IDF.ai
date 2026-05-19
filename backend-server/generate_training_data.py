"""
Generate high-quality IDF training data from real schema knowledge.

Sources:
- cluster_schemas/entity_attribute_config.proto (real entity types + attributes)
- idf_schema_reference.md (RPC definitions, message structures)
- nutest_extracted_queries.md (real-world query patterns)

Output: new_training_data.jsonl (to be merged into mlx_finetune_data/train.jsonl)
"""

import json
import re
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "new_training_data.jsonl"

SYSTEM_PROMPT = (
    'You are an IDF query generator. Output the API method on line 1 as '
    '"API: <Method>" then the protobuf text on subsequent lines.'
)

# Real entity types with their actual indexed/queryable attributes from the live cluster
ENTITY_SCHEMA = {
    "vm": {
        "str_attrs": ["vm_name", "power_state", "node", "cluster", "hypervisor_type",
                      "platform_type", "is_cvm", "vm_uuid", "guest_os", "owner_uuid",
                      "project_uuid", "protection_type", "host_name", "cluster_name"],
        "int_attrs": ["num_vcpus", "memory_mb", "memory_size_bytes", "disk_capacity_bytes",
                      "num_disks", "num_network_adapters", "cpu_usage_ppm", "memory_usage_ppm",
                      "hypervisor_cpu_usage_ppm", "controller_avg_io_latency_usecs"],
        "bool_attrs": ["is_cvm", "is_live_migratable", "is_agent_vm"],
    },
    "node": {
        "str_attrs": ["node_name", "cluster", "hypervisor_type", "bmc_version",
                      "hypervisor_full_name", "cpu_model", "serial_number", "block_serial",
                      "host_type", "maintenance_mode_type", "controller_vm_backplane_ip"],
        "int_attrs": ["num_vms", "num_cpu_cores", "num_cpu_sockets", "cpu_frequency_hz",
                      "memory_size_bytes", "num_disks", "cpu_usage_ppm", "memory_usage_ppm",
                      "hypervisor_cpu_usage_ppm", "controller_num_iops"],
        "bool_attrs": ["is_degraded", "is_secure_booted"],
    },
    "cluster": {
        "str_attrs": ["cluster_name", "_cluster_uuid_", "cluster_uuid", "version",
                      "timezone", "encryption_scope", "operation_mode",
                      "external_ip_address", "ncc_version", "hypervisor_types"],
        "int_attrs": ["num_nodes", "num_vms", "storage_capacity_bytes",
                      "storage_usage_bytes", "iops", "bandwidth_bytes",
                      "avg_io_latency_usecs", "cpu_usage_ppm", "memory_usage_ppm"],
        "bool_attrs": ["is_registered_to_pc", "is_degraded"],
    },
    "disk": {
        "str_attrs": ["disk_id", "serial_number", "model", "vendor", "node",
                      "storage_tier", "disk_status", "location", "disk_type"],
        "int_attrs": ["disk_size_bytes", "online_disk_size_bytes", "num_io",
                      "avg_io_latency_usecs", "io_bandwidth_bytes", "num_iops",
                      "read_io_bandwidth_bytes", "write_io_bandwidth_bytes"],
        "bool_attrs": ["is_mounted", "is_self_encrypting_drive"],
    },
    "container": {
        "str_attrs": ["container_name", "storage_pool_uuid", "cluster",
                      "replication_factor", "erasure_code", "compression_enabled"],
        "int_attrs": ["max_capacity_bytes", "usage_bytes", "free_space_bytes",
                      "reserved_capacity_bytes", "num_vdisks",
                      "controller_avg_io_latency_usecs", "controller_num_iops"],
        "bool_attrs": ["is_compressed", "is_deduplicated"],
    },
    "virtual_disk": {
        "str_attrs": ["vm", "container", "virtual_disk_id", "disk_address",
                      "storage_container_uuid", "attached_vm_uuid"],
        "int_attrs": ["disk_capacity_bytes", "usage_bytes", "num_iops",
                      "avg_io_latency_usecs", "io_bandwidth_bytes",
                      "controller_user_bytes", "read_io_ppm"],
        "bool_attrs": ["is_flash_mode_enabled"],
    },
    "virtual_network": {
        "str_attrs": ["subnet_name", "subnet_type", "overlay_network_uuid",
                      "vpc_uuid", "vswitch_name", "cluster", "network_function_chain_uuid"],
        "int_attrs": ["vlan_id", "ip_pool_count", "num_vms_connected"],
        "bool_attrs": ["is_external"],
    },
    "alert": {
        "str_attrs": ["alert_title", "severity", "alert_type_uuid", "source_entity_type",
                      "source_entity_uuid", "source_entity_name", "cluster",
                      "classification", "alert_status"],
        "int_attrs": ["severity_int", "creation_time_usecs", "last_occurred_timestamp_usecs",
                      "resolved_time_usecs"],
        "bool_attrs": ["acknowledged", "auto_resolved", "is_user_defined"],
    },
    "task": {
        "str_attrs": ["task_type", "status", "operation_type", "entity_type",
                      "entity_uuid", "parent_task_uuid", "cluster",
                      "owner_username", "subtask_uuid_list"],
        "int_attrs": ["start_time_usecs", "completion_time_usecs", "progress_pct",
                      "last_updated_timestamp_usecs"],
        "bool_attrs": ["is_internal", "is_cancelable"],
    },
    "storage_pool": {
        "str_attrs": ["storage_pool_name", "cluster", "disk_list"],
        "int_attrs": ["capacity_bytes", "usage_bytes", "free_space_bytes",
                      "num_disks", "iops", "avg_io_latency_usecs"],
        "bool_attrs": [],
    },
    "image": {
        "str_attrs": ["image_name", "image_type", "image_state", "source_uri",
                      "cluster_uuid", "checksum_type", "checksum_value"],
        "int_attrs": ["size_bytes", "creation_time_usecs", "last_update_time_usecs"],
        "bool_attrs": ["is_active"],
    },
    "protection_domain": {
        "str_attrs": ["pd_name", "type", "remote_site", "schedule_id",
                      "cluster", "status", "replication_link_uuid"],
        "int_attrs": ["num_protected_entities", "total_user_data_bytes",
                      "snapshot_frequency_secs", "retention_count"],
        "bool_attrs": ["is_active", "is_metro_availability"],
    },
    "volume_group_config": {
        "str_attrs": ["uuid", "name", "_master_cluster_uuid_", "protection_type",
                      "sharing_status", "iscsi_target_prefix"],
        "int_attrs": ["size_bytes", "num_virtual_disks", "creation_time_usecs",
                      "last_modified_time_usecs"],
        "bool_attrs": ["is_hidden", "flash_mode_enabled"],
    },
    "entity_snapshot": {
        "str_attrs": ["uuid", "name", "kind", "entity_uuid", "snapshot_uuid",
                      "cluster_uuid", "protection_domain_name", "recovery_point_uuid",
                      "consistency_group"],
        "int_attrs": ["creation_time_usecs", "expiration_time_usecs", "size_bytes"],
        "bool_attrs": ["is_application_consistent"],
    },
    "recovery_point": {
        "str_attrs": ["recovery_point_uuid", "name", "status", "recovery_point_type",
                      "cluster_uuid", "protection_domain_name", "vm_uuid"],
        "int_attrs": ["creation_time_usecs", "expiration_time_usecs",
                      "size_bytes", "replication_progress_pct"],
        "bool_attrs": [],
    },
    "category": {
        "str_attrs": ["name", "value", "description", "owner_uuid",
                      "system_defined_type"],
        "int_attrs": ["creation_time_usecs", "last_update_time_usecs",
                      "entity_count"],
        "bool_attrs": ["is_system_defined"],
    },
    "virtual_nic": {
        "str_attrs": ["vm", "virtual_network", "mac_address", "nic_uuid",
                      "ip_address", "network_function_chain_uuid"],
        "int_attrs": ["vlan_id", "rx_bytes", "tx_bytes",
                      "rx_packets", "tx_packets"],
        "bool_attrs": ["is_connected"],
    },
}

# Common natural language patterns for each API
NL_PATTERNS = {
    "GetEntitiesWithMetrics": {
        "basic": [
            "get all {etype}s",
            "show me all {etype} entities",
            "list all {etype}s in the system",
            "fetch all {etype} records",
            "retrieve every {etype}",
            "display all {etype}s",
        ],
        "filter_eq": [
            "get {etype}s where {attr} = {val}",
            "show {etype}s with {attr} equal to {val}",
            "find {etype}s where {attr} is {val}",
            "list {etype}s filtered by {attr} = {val}",
            "which {etype}s have {attr} set to {val}?",
        ],
        "filter_gt": [
            "get {etype}s where {attr} > {val}",
            "show {etype}s with {attr} greater than {val}",
            "find {etype}s where {attr} exceeds {val}",
            "{etype}s with {attr} above {val}",
        ],
        "filter_lt": [
            "get {etype}s where {attr} < {val}",
            "show {etype}s with {attr} less than {val}",
            "find {etype}s where {attr} is below {val}",
            "{etype}s with {attr} under {val}",
        ],
        "filter_like": [
            "find {etype}s where {attr} contains {val}",
            "get {etype}s where {attr} matches {val}",
            "search {etype}s with {attr} like {val}",
            "show {etype}s where {attr} includes {val}",
        ],
        "filter_exists": [
            "get {etype}s where {attr} exists",
            "find {etype}s that have {attr} set",
            "show {etype}s with {attr} attribute present",
        ],
        "sort_desc": [
            "get top {n} {etype}s by {attr} descending",
            "show top {n} {etype}s sorted by {attr} highest first",
            "list the {n} {etype}s with highest {attr}",
            "top {n} {etype}s by {attr}",
        ],
        "sort_asc": [
            "get {etype}s sorted by {attr} ascending limit {n}",
            "show bottom {n} {etype}s by {attr}",
            "list {n} {etype}s with lowest {attr}",
        ],
        "count": [
            "count all {etype}s",
            "how many {etype}s are there?",
            "total number of {etype}s",
            "get {etype} count",
        ],
        "aggregate": [
            "get average {attr} for {etype}s",
            "what is the average {attr} across all {etype}s?",
            "compute avg {attr} for {etype}",
            "show sum of {attr} for {etype}s",
            "get total {attr} across {etype}s",
            "get maximum {attr} among {etype}s",
            "what is the min {attr} for {etype}s?",
        ],
        "compound_and": [
            "get {etype}s where {attr1} = {val1} and {attr2} > {val2}",
            "show {etype}s with {attr1} equal to {val1} and {attr2} less than {val2}",
            "find {etype}s where {attr1} is {val1} and {attr2} >= {val2}",
        ],
        "columns": [
            "get {attr1} and {attr2} for all {etype}s",
            "show {attr1}, {attr2}, {attr3} of all {etype}s",
            "fetch {attr1} and {attr2} columns from {etype}",
        ],
        "by_id": [
            "get {etype} with id {id}",
            "fetch {etype} entity {id}",
            "show details of {etype} {id}",
            "lookup {etype} named {id}",
        ],
        "cursor": [
            "paginate through {etype}s with batch size {n}",
            "get {etype}s using cursor pagination, batch {n}",
        ],
    },
}


def make_example(user_content: str, assistant_content: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ]
    }


def gen_gewm_basic(etype, schema):
    """Generate basic GetEntitiesWithMetrics queries."""
    examples = []
    attrs = schema["str_attrs"] + schema["int_attrs"]
    col = attrs[0] if attrs else "_entity_summary_"

    for pattern in NL_PATTERNS["GetEntitiesWithMetrics"]["basic"]:
        nl = pattern.format(etype=etype)
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  group_by {{ raw_columns {{ column: "{col}" }} }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_gewm_filter_eq(etype, schema):
    """Generate filter equality queries with real attributes."""
    examples = []
    str_attrs = schema["str_attrs"]

    sample_values = {
        "power_state": ["on", "off"],
        "status": ["running", "completed", "failed", "queued"],
        "severity": ["critical", "warning", "info"],
        "hypervisor_type": ["kKvm", "kVMware", "kHyperv"],
        "disk_status": ["online", "offline", "failed"],
        "subnet_type": ["VLAN", "OVERLAY"],
        "image_type": ["DISK_IMAGE", "ISO_IMAGE"],
        "task_type": ["vm_create", "vm_delete", "snapshot_create", "vm_migrate"],
        "protection_type": ["ASYNC", "SYNC", "METRO"],
        "operation_type": ["kCreate", "kUpdate", "kDelete", "kClone"],
        "alert_status": ["active", "resolved", "suppressed"],
        "maintenance_mode_type": ["entering", "entered", "none"],
    }

    for attr in str_attrs[:4]:
        vals = sample_values.get(attr, [f"sample_{attr}_value"])
        val = random.choice(vals)
        patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["filter_eq"]
        nl = random.choice(patterns).format(etype=etype, attr=attr, val=val)
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  where_clause {{\n'
            f'    comparison_expr {{\n'
            f'      lhs {{ leaf {{ column: "{attr}" }} }}\n'
            f'      operator: kEQ\n'
            f'      rhs {{ leaf {{ value {{ str_value: "{val}" }} }} }}\n'
            f'    }}\n'
            f'  }}\n'
            f'  group_by {{ raw_columns {{ column: "{attr}" }} }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_gewm_filter_numeric(etype, schema):
    """Generate numeric comparison filter queries."""
    examples = []
    int_attrs = schema["int_attrs"]

    for attr in int_attrs[:3]:
        # Greater than
        val = random.choice([100, 500, 1000, 4096, 8192, 50000, 1000000])
        patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["filter_gt"]
        nl = random.choice(patterns).format(etype=etype, attr=attr, val=val)
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  where_clause {{\n'
            f'    comparison_expr {{\n'
            f'      lhs {{ leaf {{ column: "{attr}" }} }}\n'
            f'      operator: kGT\n'
            f'      rhs {{ leaf {{ value {{ uint64_value: {val} }} }} }}\n'
            f'    }}\n'
            f'  }}\n'
            f'  group_by {{ raw_columns {{ column: "{attr}" }} }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

        # Less than
        val2 = random.choice([50, 200, 1024, 2048, 10000])
        patterns_lt = NL_PATTERNS["GetEntitiesWithMetrics"]["filter_lt"]
        nl2 = random.choice(patterns_lt).format(etype=etype, attr=attr, val=val2)
        proto2 = proto.replace(f"kGT", "kLT").replace(f"uint64_value: {val}", f"uint64_value: {val2}")
        examples.append(make_example(nl2, proto2))
    return examples


def gen_gewm_filter_like(etype, schema):
    """Generate pattern matching (kLike) queries."""
    examples = []
    str_attrs = schema["str_attrs"]

    for attr in str_attrs[:2]:
        val = random.choice(["prod", "test", "dev", "staging", "backup"])
        patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["filter_like"]
        nl = random.choice(patterns).format(etype=etype, attr=attr, val=val)
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  where_clause {{\n'
            f'    comparison_expr {{\n'
            f'      lhs {{ leaf {{ column: "{attr}" }} }}\n'
            f'      operator: kLike\n'
            f'      rhs {{ leaf {{ value {{ str_value: ".*{val}.*" }} }} }}\n'
            f'    }}\n'
            f'  }}\n'
            f'  group_by {{ raw_columns {{ column: "{attr}" }} }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_gewm_filter_exists(etype, schema):
    """Generate kExists filter queries."""
    examples = []
    attrs = schema["str_attrs"] + schema["int_attrs"]

    attr = random.choice(attrs[:5]) if attrs else "_entity_summary_"
    patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["filter_exists"]
    nl = random.choice(patterns).format(etype=etype, attr=attr)
    proto = (
        f'API: GetEntitiesWithMetrics\n'
        f'query {{\n'
        f'  entity_list {{ entity_type_name: "{etype}" }}\n'
        f'  where_clause {{\n'
        f'    comparison_expr {{\n'
        f'      lhs {{ leaf {{ column: "{attr}" }} }}\n'
        f'      operator: kExists\n'
        f'    }}\n'
        f'  }}\n'
        f'  group_by {{ raw_columns {{ column: "{attr}" }} }}\n'
        f'  query_name: "auto_query"\n'
        f'}}'
    )
    examples.append(make_example(nl, proto))
    return examples


def gen_gewm_sort(etype, schema):
    """Generate sorted/top-N queries."""
    examples = []
    int_attrs = schema["int_attrs"]
    str_attrs = schema["str_attrs"]

    if int_attrs:
        attr = random.choice(int_attrs[:3])
        n = random.choice([5, 10, 20, 50])
        display_col = str_attrs[0] if str_attrs else attr

        # Descending (top N)
        patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["sort_desc"]
        nl = random.choice(patterns).format(etype=etype, attr=attr, n=n)
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  group_by {{\n'
            f'    raw_columns {{ column: "{display_col}" }}\n'
            f'    raw_columns {{ column: "{attr}" }}\n'
            f'    raw_sort_order {{ column: "{attr}" order: kDescending }}\n'
            f'    raw_limit {{ limit: {n} offset: 0 }}\n'
            f'  }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

        # Ascending (bottom N)
        attr2 = random.choice(int_attrs[:3])
        n2 = random.choice([5, 10, 20])
        patterns_asc = NL_PATTERNS["GetEntitiesWithMetrics"]["sort_asc"]
        nl2 = random.choice(patterns_asc).format(etype=etype, attr=attr2, n=n2)
        proto2 = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  group_by {{\n'
            f'    raw_columns {{ column: "{display_col}" }}\n'
            f'    raw_columns {{ column: "{attr2}" }}\n'
            f'    raw_sort_order {{ column: "{attr2}" order: kAscending }}\n'
            f'    raw_limit {{ limit: {n2} offset: 0 }}\n'
            f'  }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl2, proto2))
    return examples


def gen_gewm_count(etype, schema):
    """Generate count queries."""
    examples = []
    patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["count"]
    nl = random.choice(patterns).format(etype=etype)
    proto = (
        f'API: GetEntitiesWithMetrics\n'
        f'query {{\n'
        f'  entity_list {{ entity_type_name: "{etype}" }}\n'
        f'  group_by {{ raw_limit {{ limit: 0 }} }}\n'
        f'  query_name: "count_{etype}s"\n'
        f'}}'
    )
    examples.append(make_example(nl, proto))
    return examples


def gen_gewm_aggregate(etype, schema):
    """Generate aggregation queries."""
    examples = []
    int_attrs = schema["int_attrs"]

    if int_attrs:
        for op, op_word in [("kAvg", "average"), ("kSum", "sum"), ("kMax", "maximum"), ("kMin", "minimum")]:
            attr = random.choice(int_attrs[:4])
            if op == "kAvg":
                nl = f"get average {attr} for {etype}s"
            elif op == "kSum":
                nl = f"get total {attr} across all {etype}s"
            elif op == "kMax":
                nl = f"what is the maximum {attr} among {etype}s?"
            else:
                nl = f"what is the minimum {attr} for {etype}s?"

            proto = (
                f'API: GetEntitiesWithMetrics\n'
                f'query {{\n'
                f'  entity_list {{ entity_type_name: "{etype}" }}\n'
                f'  group_by {{\n'
                f'    aggregate_columns {{\n'
                f'      column: "{attr}"\n'
                f'      operator: {op}\n'
                f'    }}\n'
                f'  }}\n'
                f'  query_name: "auto_query"\n'
                f'}}'
            )
            examples.append(make_example(nl, proto))
    return examples


def gen_gewm_compound(etype, schema):
    """Generate compound AND/OR filter queries."""
    examples = []
    str_attrs = schema["str_attrs"]
    int_attrs = schema["int_attrs"]

    if str_attrs and int_attrs:
        attr1 = str_attrs[0]
        attr2 = int_attrs[0]
        val1_options = {
            "power_state": "on", "status": "running", "severity": "critical",
            "hypervisor_type": "kKvm", "disk_status": "online",
        }
        val1 = val1_options.get(attr1, f"active")
        val2 = random.choice([4, 8, 16, 1024, 4096, 8192])

        # AND query
        nl = f"get {etype}s where {attr1} = {val1} and {attr2} > {val2}"
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  where_clause {{\n'
            f'    lhs {{\n'
            f'      comparison_expr {{\n'
            f'        lhs {{ leaf {{ column: "{attr1}" }} }}\n'
            f'        operator: kEQ\n'
            f'        rhs {{ leaf {{ value {{ str_value: "{val1}" }} }} }}\n'
            f'      }}\n'
            f'    }}\n'
            f'    operator: kAnd\n'
            f'    rhs {{\n'
            f'      comparison_expr {{\n'
            f'        lhs {{ leaf {{ column: "{attr2}" }} }}\n'
            f'        operator: kGT\n'
            f'        rhs {{ leaf {{ value {{ uint64_value: {val2} }} }} }}\n'
            f'      }}\n'
            f'    }}\n'
            f'  }}\n'
            f'  group_by {{\n'
            f'    raw_columns {{ column: "{attr1}" }}\n'
            f'    raw_columns {{ column: "{attr2}" }}\n'
            f'  }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

        # OR query
        if len(str_attrs) >= 2:
            attr_a = str_attrs[0]
            attr_b = str_attrs[1] if len(str_attrs) > 1 else str_attrs[0]
            nl2 = f"get {etype}s where {attr_a} = {val1} or {attr_b} = test"
            proto2 = (
                f'API: GetEntitiesWithMetrics\n'
                f'query {{\n'
                f'  entity_list {{ entity_type_name: "{etype}" }}\n'
                f'  where_clause {{\n'
                f'    lhs {{\n'
                f'      comparison_expr {{\n'
                f'        lhs {{ leaf {{ column: "{attr_a}" }} }}\n'
                f'        operator: kEQ\n'
                f'        rhs {{ leaf {{ value {{ str_value: "{val1}" }} }} }}\n'
                f'      }}\n'
                f'    }}\n'
                f'    operator: kOr\n'
                f'    rhs {{\n'
                f'      comparison_expr {{\n'
                f'        lhs {{ leaf {{ column: "{attr_b}" }} }}\n'
                f'        operator: kEQ\n'
                f'        rhs {{ leaf {{ value {{ str_value: "test" }} }} }}\n'
                f'      }}\n'
                f'    }}\n'
                f'  }}\n'
                f'  group_by {{\n'
                f'    raw_columns {{ column: "{attr_a}" }}\n'
                f'    raw_columns {{ column: "{attr_b}" }}\n'
                f'  }}\n'
                f'  query_name: "auto_query"\n'
                f'}}'
            )
            examples.append(make_example(nl2, proto2))
    return examples


def gen_gewm_columns(etype, schema):
    """Generate column-selection queries."""
    examples = []
    all_attrs = schema["str_attrs"] + schema["int_attrs"]

    if len(all_attrs) >= 3:
        cols = random.sample(all_attrs[:8], min(3, len(all_attrs)))
        nl = f"get {', '.join(cols)} for all {etype}s"
        raw_cols = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in cols)
        proto = (
            f'API: GetEntitiesWithMetrics\n'
            f'query {{\n'
            f'  entity_list {{ entity_type_name: "{etype}" }}\n'
            f'  group_by {{\n'
            f'    {raw_cols}\n'
            f'  }}\n'
            f'  query_name: "auto_query"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_gewm_by_id(etype, schema):
    """Generate entity-by-id queries."""
    examples = []
    sample_ids = {
        "vm": ["vm-prod-001", "app-server-02", "db-primary"],
        "node": ["node-01", "hypervisor-host-3"],
        "cluster": ["prod-cluster-east", "dev-cluster-01"],
        "disk": ["disk-ssd-001", "hdd-backup-04"],
        "container": ["default-container", "high-perf-storage"],
        "alert": ["alert-critical-001", "alert-disk-failure"],
        "task": ["task-migrate-vm-001", "task-snapshot-daily"],
    }
    ids = sample_ids.get(etype, [f"{etype}-sample-001"])
    entity_id = random.choice(ids)

    patterns = NL_PATTERNS["GetEntitiesWithMetrics"]["by_id"]
    nl = random.choice(patterns).format(etype=etype, id=entity_id)
    proto = (
        f'API: GetEntitiesWithMetrics\n'
        f'query {{\n'
        f'  entity_list {{\n'
        f'    entity_type_name: "{etype}"\n'
        f'    entity_id: "{entity_id}"\n'
        f'  }}\n'
        f'  query_name: "auto_query"\n'
        f'}}'
    )
    examples.append(make_example(nl, proto))
    return examples


def gen_gewm_cursor(etype, schema):
    """Generate cursor pagination queries."""
    examples = []
    col = schema["str_attrs"][0] if schema["str_attrs"] else "_entity_summary_"
    n = random.choice([50, 100, 200])

    nl = f"paginate through {etype}s with batch size {n}"
    proto = (
        f'API: GetEntitiesWithMetrics\n'
        f'query {{\n'
        f'  entity_list {{ entity_type_name: "{etype}" }}\n'
        f'  group_by {{\n'
        f'    raw_columns {{ column: "{col}" }}\n'
        f'    raw_limit {{ limit: {n} offset: 0 }}\n'
        f'  }}\n'
        f'  cursor_query_info {{\n'
        f'    is_initial_cursor_query: true\n'
        f'    batch_size: {n}\n'
        f'  }}\n'
        f'  query_name: "cursor_{etype}s"\n'
        f'}}'
    )
    examples.append(make_example(nl, proto))
    return examples


def gen_update_entity(etype, schema):
    """Generate UpdateEntity examples."""
    examples = []
    str_attrs = schema["str_attrs"]
    int_attrs = schema["int_attrs"]
    bool_attrs = schema.get("bool_attrs", [])

    sample_ids = [f"{etype}-001", f"{etype}-prod-02", f"my-{etype}"]

    # String attribute update
    if str_attrs:
        attr = random.choice(str_attrs[1:3] if len(str_attrs) > 1 else str_attrs)
        entity_id = random.choice(sample_ids)
        val = f"new_{attr}_value"
        nl = f"update {etype} {entity_id} setting {attr} to {val}"
        proto = (
            f'API: UpdateEntity\n'
            f'entity_guid {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{entity_id}"\n'
            f'}}\n'
            f'cas_value: 0\n'
            f'attribute_data_arg_list {{\n'
            f'  attribute_data {{\n'
            f'    name: "{attr}"\n'
            f'    value {{ str_value: "{val}" }}\n'
            f'  }}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

    # Integer attribute update
    if int_attrs:
        attr = random.choice(int_attrs[:3])
        entity_id = random.choice(sample_ids)
        val = random.choice([4, 8, 16, 1024, 4096, 8192, 16384])
        nl = f"update {etype} entity {entity_id} set {attr} to {val}"
        proto = (
            f'API: UpdateEntity\n'
            f'entity_guid {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{entity_id}"\n'
            f'}}\n'
            f'cas_value: 0\n'
            f'attribute_data_arg_list {{\n'
            f'  attribute_data {{\n'
            f'    name: "{attr}"\n'
            f'    value {{ uint64_value: {val} }}\n'
            f'  }}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

    # Boolean attribute update
    if bool_attrs:
        attr = random.choice(bool_attrs)
        entity_id = random.choice(sample_ids)
        val = random.choice([True, False])
        nl = f"set {attr} to {'true' if val else 'false'} on {etype} {entity_id}"
        proto = (
            f'API: UpdateEntity\n'
            f'entity_guid {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{entity_id}"\n'
            f'}}\n'
            f'cas_value: 0\n'
            f'attribute_data_arg_list {{\n'
            f'  attribute_data {{\n'
            f'    name: "{attr}"\n'
            f'    value {{ bool_value: {"true" if val else "false"} }}\n'
            f'  }}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

    # Multi-attribute update
    if len(str_attrs) >= 2 and int_attrs:
        entity_id = random.choice(sample_ids)
        a1 = str_attrs[1]
        a2 = int_attrs[0]
        v1 = "updated_value"
        v2 = random.choice([8, 16, 32])
        nl = f"update {etype} {entity_id} setting {a1} to {v1} and {a2} to {v2}"
        proto = (
            f'API: UpdateEntity\n'
            f'entity_guid {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{entity_id}"\n'
            f'}}\n'
            f'cas_value: 0\n'
            f'attribute_data_arg_list {{\n'
            f'  attribute_data {{\n'
            f'    name: "{a1}"\n'
            f'    value {{ str_value: "{v1}" }}\n'
            f'  }}\n'
            f'}}\n'
            f'attribute_data_arg_list {{\n'
            f'  attribute_data {{\n'
            f'    name: "{a2}"\n'
            f'    value {{ uint64_value: {v2} }}\n'
            f'  }}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))

    return examples


def gen_delete_entity(etype, schema):
    """Generate DeleteEntity examples."""
    examples = []
    sample_ids = [f"{etype}-decom-01", f"old-{etype}-legacy", f"{etype}-temp-test"]

    nl_patterns = [
        f"delete {etype} entity {{id}}",
        f"remove {etype} {{id}} from the system",
        f"delete the {etype} named {{id}}",
    ]

    for entity_id in sample_ids[:2]:
        nl = random.choice(nl_patterns).format(id=entity_id)
        proto = (
            f'API: DeleteEntity\n'
            f'entity_guid {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{entity_id}"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_get_entity_types():
    """Generate GetEntityTypes examples."""
    examples = []

    # Get all entity types
    for nl in ["show all entity types", "list registered entity types",
               "what entity types are available?", "describe all IDF entity types"]:
        proto = "API: GetEntityTypes"
        examples.append(make_example(nl, proto))

    # Get specific entity type
    for etype in ["vm", "node", "cluster", "disk", "container", "alert", "task",
                  "virtual_network", "image", "protection_domain"]:
        nl_options = [
            f"get info about {etype} entity type",
            f"describe {etype} entity type",
            f"what is the {etype} entity type definition?",
            f"show schema for entity type {etype}",
        ]
        nl = random.choice(nl_options)
        proto = f'API: GetEntityTypes\nentity_type_name: "{etype}"'
        examples.append(make_example(nl, proto))
    return examples


def gen_get_metric_types():
    """Generate GetMetricTypes examples."""
    examples = []

    for etype in ["vm", "node", "cluster", "disk", "container", "alert",
                  "task", "virtual_disk", "virtual_network", "image",
                  "storage_pool", "protection_domain", "volume_group_config"]:
        nl_options = [
            f"list all metrics for entity type {etype}",
            f"what attributes does {etype} have?",
            f"show metrics registered for {etype}",
            f"get all fields/columns for {etype}",
            f"describe attributes of {etype} entity type",
        ]
        nl = random.choice(nl_options)
        proto = f'API: GetMetricTypes\nregex: ".*:{etype}"'
        examples.append(make_example(nl, proto))

    # Get all metrics
    for nl in ["list all metrics", "show all registered metrics across all entity types"]:
        proto = 'API: GetMetricTypes\nregex: ".*"'
        examples.append(make_example(nl, proto))
    return examples


def gen_register_entity_types():
    """Generate RegisterEntityTypes examples."""
    examples = []
    new_types = [
        ("custom_sensor", "node", "register new entity type custom_sensor with parent node"),
        ("gpu_device", "node", "create entity type gpu_device as child of node"),
        ("backup_policy", "cluster", "register entity type called backup_policy with parent cluster"),
        ("network_flow", "virtual_network", "define new entity type network_flow under virtual_network"),
        ("license_key", "cluster", "register entity type license_key with parent cluster"),
    ]

    for etype, parent, nl in new_types:
        proto = (
            f'API: RegisterEntityTypes\n'
            f'entity_type_info_list {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  type_info {{\n'
            f'    parent_list: "{parent}"\n'
            f'  }}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_register_metric_types():
    """Generate RegisterMetricTypes examples."""
    examples = []
    new_metrics = [
        ("gpu_utilization_ppm", "node", True, "register attribute gpu_utilization_ppm for node"),
        ("ssd_wear_level", "disk", True, "add attribute ssd_wear_level to disk entity type"),
        ("backup_count", "vm", False, "register metric backup_count for vm"),
        ("network_latency_usecs", "virtual_network", True, "register attribute network_latency_usecs for virtual_network"),
        ("last_login_time", "vm", True, "add attribute last_login_time to vm"),
        ("error_count", "node", False, "register metric error_count for entity type node"),
        ("encryption_enabled", "container", True, "register attribute encryption_enabled for container"),
    ]

    for metric_name, etype, is_attr, nl in new_metrics:
        proto = (
            f'API: RegisterMetricTypes\n'
            f'metric_type_list {{\n'
            f'  is_attribute: {"true" if is_attr else "false"}\n'
            f'  metric_name: "{metric_name}"\n'
            f'  entity_type_name: "{etype}"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_unregister_metric_types():
    """Generate UnregisterMetricTypes examples."""
    examples = []
    removals = [
        ("deprecated_attr", "vm", "unregister attribute deprecated_attr from vm"),
        ("old_metric", "node", "remove metric old_metric from node"),
        ("temp_counter", "disk", "unregister metric temp_counter from disk entity type"),
        ("legacy_field", "cluster", "delete attribute legacy_field from cluster"),
        ("unused_stat", "container", "remove attribute unused_stat from container"),
    ]

    for metric_name, etype, nl in removals:
        proto = (
            f'API: UnregisterMetricTypes\n'
            f'metric_type_list {{\n'
            f'  metric_name: "{metric_name}"\n'
            f'  entity_type_name: "{etype}"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_watch():
    """Generate Watch examples."""
    examples = []
    watch_configs = [
        ("vm", 7, "watch for all changes on VM entities"),
        ("vm", 1, "notify me when new VMs are created"),
        ("vm", 4, "watch for VM deletions"),
        ("node", 7, "monitor all changes on node entities"),
        ("alert", 1, "subscribe to new alert creation events"),
        ("disk", 7, "watch for changes on disk entities"),
        ("task", 1, "watch for new tasks being created"),
        ("cluster", 2, "notify me when cluster settings are updated"),
        ("container", 7, "monitor all container changes"),
        ("virtual_network", 7, "watch for subnet/network changes"),
        ("image", 1, "alert me when new images are uploaded"),
        ("protection_domain", 2, "watch for protection domain updates"),
    ]

    for etype, mask, nl in watch_configs:
        proto = (
            f'API: Watch\n'
            f'client_id: "idf_watch_client"\n'
            f'session_id: "session_001"\n'
            f'watch_list {{\n'
            f'  watch_name: "watch_{etype}_all"\n'
            f'  entity_type_name: "{etype}"\n'
            f'  watch_type_mask: {mask}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_get_master_location():
    """Generate GetMasterLocation examples (empty proto body)."""
    examples = []
    for nl in ["get master location", "who is the IDF master?", "which node is the IDF leader?",
               "get the IDF master node", "show master location"]:
        proto = "API: GetMasterLocation"
        examples.append(make_example(nl, proto))
    return examples


def gen_spotlight_search():
    """Generate SpotLightSearch examples."""
    examples = []
    searches = [
        ("production", "vm", "search for entities containing production"),
        ("backup", "vm", "find any entities matching backup"),
        ("critical", "alert", "full text search for critical across alerts"),
        ("SSD", "disk", "spotlight search for SSD in disks"),
        ("maintenance", "node", "search for maintenance in node entities"),
        ("failed", "task", "text search for failed across tasks"),
    ]

    for term, etype, nl in searches:
        proto = (
            f'API: SpotLightSearch\n'
            f'search_term: "{term}"\n'
            f'entity_type_name_list: "{etype}"\n'
            f'limit {{\n'
            f'  limit: 20\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_get_entities():
    """Generate GetEntities (by ID) examples."""
    examples = []
    lookups = [
        ("vm", "vm-prod-001", "lookup VM entity with id vm-prod-001"),
        ("node", "node-03", "get entity by id node-03 of type node"),
        ("disk", "disk-ssd-05", "fetch specific disk entity disk-ssd-05"),
        ("cluster", "cluster-east-01", "retrieve cluster entity by id cluster-east-01"),
        ("alert", "alert-abc-123", "get alert entity with guid alert-abc-123"),
        ("task", "task-xyz-789", "lookup task by id task-xyz-789"),
    ]

    for etype, eid, nl in lookups:
        proto = (
            f'API: GetEntities\n'
            f'entity_guid_list {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{eid}"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_get_entities_trail():
    """Generate GetEntitiesTrail examples."""
    examples = []
    trails = [
        ("vm", "vm-prod-001", "get change history for VM vm-prod-001"),
        ("vm", "app-server", "show audit trail for VM app-server"),
        ("disk", "disk-001", "what changes were made to disk disk-001?"),
        ("node", "node-05", "show modification history for node node-05"),
        ("cluster", "prod-cluster", "get entity trail for cluster prod-cluster"),
        ("container", "default-ct", "audit trail for container default-ct"),
    ]

    for etype, eid, nl in trails:
        proto = (
            f'API: GetEntitiesTrail\n'
            f'entity_guid_list {{\n'
            f'  entity_type_name: "{etype}"\n'
            f'  entity_id: "{eid}"\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_batch_get():
    """Generate BatchGetEntitiesWithMetrics examples."""
    examples = []
    batches = [
        (["vm", "node"], "batch query: get all VMs and all nodes"),
        (["disk", "container"], "batch get disks and containers in one call"),
        (["alert", "task"], "get alerts and tasks in a single batch"),
        (["vm", "virtual_disk", "virtual_nic"], "batch query: VMs, virtual disks, and NICs"),
        (["cluster", "node", "vm"], "multiple queries: clusters, nodes, and VMs together"),
    ]

    for etypes, nl in batches:
        query_lists = []
        for et in etypes:
            query_lists.append(
                f'query_list {{\n'
                f'  query {{\n'
                f'    entity_list {{ entity_type_name: "{et}" }}\n'
                f'    group_by {{ raw_columns {{ column: "_entity_summary_" }} }}\n'
                f'    query_name: "batch_{et}"\n'
                f'  }}\n'
                f'}}'
            )
        proto = "API: BatchGetEntitiesWithMetrics\n" + "\n".join(query_lists)
        examples.append(make_example(nl, proto))
    return examples


def gen_batch_update():
    """Generate BatchUpdateEntities examples."""
    examples = []

    # Batch update VMs
    nl = "batch update VMs vm-1 and vm-2 setting power_state to off"
    proto = (
        'API: BatchUpdateEntities\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "vm"\n'
        '    entity_id: "vm-1"\n'
        '  }\n'
        '  attribute_data_arg_list {\n'
        '    attribute_data {\n'
        '      name: "power_state"\n'
        '      value { str_value: "off" }\n'
        '    }\n'
        '  }\n'
        '}\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "vm"\n'
        '    entity_id: "vm-2"\n'
        '  }\n'
        '  attribute_data_arg_list {\n'
        '    attribute_data {\n'
        '      name: "power_state"\n'
        '      value { str_value: "off" }\n'
        '    }\n'
        '  }\n'
        '}'
    )
    examples.append(make_example(nl, proto))

    nl2 = "bulk update nodes node-a and node-b setting maintenance_mode_type to entering"
    proto2 = (
        'API: BatchUpdateEntities\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "node"\n'
        '    entity_id: "node-a"\n'
        '  }\n'
        '  attribute_data_arg_list {\n'
        '    attribute_data {\n'
        '      name: "maintenance_mode_type"\n'
        '      value { str_value: "entering" }\n'
        '    }\n'
        '  }\n'
        '}\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "node"\n'
        '    entity_id: "node-b"\n'
        '  }\n'
        '  attribute_data_arg_list {\n'
        '    attribute_data {\n'
        '      name: "maintenance_mode_type"\n'
        '      value { str_value: "entering" }\n'
        '    }\n'
        '  }\n'
        '}'
    )
    examples.append(make_example(nl2, proto2))
    return examples


def gen_batch_delete():
    """Generate BatchDeleteEntities examples."""
    examples = []

    nl = "batch delete VMs vm-old-1, vm-old-2, and vm-old-3"
    proto = (
        'API: BatchDeleteEntities\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "vm"\n'
        '    entity_id: "vm-old-1"\n'
        '  }\n'
        '}\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "vm"\n'
        '    entity_id: "vm-old-2"\n'
        '  }\n'
        '}\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "vm"\n'
        '    entity_id: "vm-old-3"\n'
        '  }\n'
        '}'
    )
    examples.append(make_example(nl, proto))

    nl2 = "bulk delete disks disk-failed-1 and disk-failed-2"
    proto2 = (
        'API: BatchDeleteEntities\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "disk"\n'
        '    entity_id: "disk-failed-1"\n'
        '  }\n'
        '}\n'
        'entity_list {\n'
        '  entity_guid {\n'
        '    entity_type_name: "disk"\n'
        '    entity_id: "disk-failed-2"\n'
        '  }\n'
        '}'
    )
    examples.append(make_example(nl2, proto2))
    return examples


def gen_put_metric_data():
    """Generate PutMetricData examples."""
    examples = []
    metrics = [
        ("vm", "vm-001", "cpu_usage_ppm", 750000, "write metric cpu_usage_ppm value 750000 for VM vm-001"),
        ("node", "node-02", "memory_usage_ppm", 850000, "record metric memory_usage_ppm 850000 for node node-02"),
        ("disk", "disk-ssd-01", "num_iops", 15000, "publish metric num_iops value 15000 for disk disk-ssd-01"),
        ("container", "ct-01", "controller_num_iops", 5000, "put metric controller_num_iops value 5000 for container ct-01"),
    ]

    for etype, eid, metric, val, nl in metrics:
        proto = (
            f'API: PutMetricData\n'
            f'entity_with_metric_list {{\n'
            f'  entity_guid {{\n'
            f'    entity_type_name: "{etype}"\n'
            f'    entity_id: "{eid}"\n'
            f'  }}\n'
            f'  metric_data_list {{\n'
            f'    name: "{metric}"\n'
            f'    value_list {{\n'
            f'      value {{ uint64_value: {val} }}\n'
            f'    }}\n'
            f'  }}\n'
            f'}}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_get_metric_data():
    """Generate GetMetricData examples."""
    examples = []
    queries = [
        ("vm", "vm-001", "cpu_usage_ppm", "get time-series data for cpu_usage_ppm of VM vm-001"),
        ("node", "node-02", "memory_usage_ppm", "fetch historical metric memory_usage_ppm for node node-02"),
        ("disk", "disk-01", "num_iops", "get metric data for num_iops of disk disk-01"),
        ("container", "ct-01", "controller_avg_io_latency_usecs", "get time series for controller_avg_io_latency_usecs of container ct-01"),
    ]

    for etype, eid, metric, nl in queries:
        proto = (
            f'API: GetMetricData\n'
            f'entity_type_name: "{etype}"\n'
            f'entity_id_list: "{eid}"\n'
            f'metric_name_list: "{metric}"'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_put_event():
    """Generate PutEvent examples."""
    examples = []
    events = [
        ("vm_created", "vm", "vm-new-001", "publish event vm_created for VM vm-new-001"),
        ("vm_powered_off", "vm", "app-server", "fire event vm_powered_off for VM app-server"),
        ("disk_failure", "disk", "disk-bad-01", "create event disk_failure for disk disk-bad-01"),
        ("node_maintenance_enter", "node", "node-05", "publish event node_maintenance_enter for node node-05"),
        ("snapshot_completed", "vm", "vm-prod", "fire event snapshot_completed for VM vm-prod"),
        ("alert_resolved", "alert", "alert-001", "create event alert_resolved for alert alert-001"),
    ]

    for event_type, etype, eid, nl in events:
        proto = (
            f'API: PutEvent\n'
            f'event_type: "{event_type}"\n'
            f'entity_type_name: "{etype}"\n'
            f'entity_id: "{eid}"'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_attach_entity():
    """Generate AttachEntity examples."""
    examples = []
    attaches = [
        ("vm", "vm-replicated-01", 5, "attach entity VM vm-replicated-01 with incarnation 5"),
        ("disk", "disk-moved-01", 3, "attach disk disk-moved-01 incarnation 3"),
        ("container", "ct-replicated", 1, "attach container ct-replicated with incarnation id 1"),
    ]

    for etype, eid, inc, nl in attaches:
        proto = (
            f'API: AttachEntity\n'
            f'update_entity_arg {{\n'
            f'  entity_guid {{\n'
            f'    entity_type_name: "{etype}"\n'
            f'    entity_id: "{eid}"\n'
            f'  }}\n'
            f'}}\n'
            f'incarnation_id: {inc}'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_detach_entity():
    """Generate DetachEntity examples."""
    examples = []
    detaches = [
        ("vm", "vm-migrate-01", "cluster-uuid-west", "detach VM vm-migrate-01 moving to cluster cluster-uuid-west"),
        ("disk", "disk-transfer", "uuid-remote-site", "detach disk disk-transfer moving to cluster uuid-remote-site"),
        ("container", "ct-old", "cluster-decom-uuid", "detach container ct-old moving to cluster cluster-decom-uuid"),
    ]

    for etype, eid, cluster_uuid, nl in detaches:
        proto = (
            f'API: DetachEntity\n'
            f'delete_entity_arg {{\n'
            f'  entity_guid {{\n'
            f'    entity_type_name: "{etype}"\n'
            f'    entity_id: "{eid}"\n'
            f'  }}\n'
            f'}}\n'
            f'moved_to_cluster_uuid: "{cluster_uuid}"'
        )
        examples.append(make_example(nl, proto))
    return examples


def gen_host_mapping_examples():
    """Generate examples that test the host->node entity mapping."""
    examples = []
    queries = [
        ("show all hosts", "node"),
        ("get all hosts in the cluster", "node"),
        ("list hosts sorted by memory usage", "node"),
        ("how many hosts are there?", "node"),
        ("get host details for node-01", "node"),
    ]

    for nl, etype in queries:
        if "sorted" in nl:
            proto = (
                f'API: GetEntitiesWithMetrics\n'
                f'query {{\n'
                f'  entity_list {{ entity_type_name: "{etype}" }}\n'
                f'  group_by {{\n'
                f'    raw_columns {{ column: "node_name" }}\n'
                f'    raw_columns {{ column: "memory_usage_ppm" }}\n'
                f'    raw_sort_order {{ column: "memory_usage_ppm" order: kDescending }}\n'
                f'    raw_limit {{ limit: 100 offset: 0 }}\n'
                f'  }}\n'
                f'  query_name: "auto_query"\n'
                f'}}'
            )
        elif "how many" in nl or "count" in nl:
            proto = (
                f'API: GetEntitiesWithMetrics\n'
                f'query {{\n'
                f'  entity_list {{ entity_type_name: "{etype}" }}\n'
                f'  group_by {{ raw_limit {{ limit: 0 }} }}\n'
                f'  query_name: "count_{etype}s"\n'
                f'}}'
            )
        elif "details" in nl or "node-01" in nl:
            proto = (
                f'API: GetEntitiesWithMetrics\n'
                f'query {{\n'
                f'  entity_list {{\n'
                f'    entity_type_name: "{etype}"\n'
                f'    entity_id: "node-01"\n'
                f'  }}\n'
                f'  query_name: "auto_query"\n'
                f'}}'
            )
        else:
            proto = (
                f'API: GetEntitiesWithMetrics\n'
                f'query {{\n'
                f'  entity_list {{ entity_type_name: "{etype}" }}\n'
                f'  group_by {{ raw_columns {{ column: "node_name" }} }}\n'
                f'  query_name: "auto_query"\n'
                f'}}'
            )
        examples.append(make_example(nl, proto))
    return examples


def main():
    random.seed(42)
    all_examples = []

    # Generate GEWM examples for each major entity type
    for etype, schema in ENTITY_SCHEMA.items():
        all_examples.extend(gen_gewm_basic(etype, schema)[:2])
        all_examples.extend(gen_gewm_filter_eq(etype, schema))
        all_examples.extend(gen_gewm_filter_numeric(etype, schema))
        all_examples.extend(gen_gewm_filter_like(etype, schema))
        all_examples.extend(gen_gewm_filter_exists(etype, schema))
        all_examples.extend(gen_gewm_sort(etype, schema))
        all_examples.extend(gen_gewm_count(etype, schema))
        all_examples.extend(gen_gewm_aggregate(etype, schema))
        all_examples.extend(gen_gewm_compound(etype, schema))
        all_examples.extend(gen_gewm_columns(etype, schema))
        all_examples.extend(gen_gewm_by_id(etype, schema))
        all_examples.extend(gen_gewm_cursor(etype, schema))
        all_examples.extend(gen_update_entity(etype, schema))
        all_examples.extend(gen_delete_entity(etype, schema))

    # Non-entity-specific APIs
    all_examples.extend(gen_get_entity_types())
    all_examples.extend(gen_get_metric_types())
    all_examples.extend(gen_register_entity_types())
    all_examples.extend(gen_register_metric_types())
    all_examples.extend(gen_unregister_metric_types())
    all_examples.extend(gen_watch())
    all_examples.extend(gen_get_master_location())
    all_examples.extend(gen_spotlight_search())
    all_examples.extend(gen_get_entities())
    all_examples.extend(gen_get_entities_trail())
    all_examples.extend(gen_batch_get())
    all_examples.extend(gen_batch_update())
    all_examples.extend(gen_batch_delete())
    all_examples.extend(gen_put_metric_data())
    all_examples.extend(gen_get_metric_data())
    all_examples.extend(gen_put_event())
    all_examples.extend(gen_attach_entity())
    all_examples.extend(gen_detach_entity())
    all_examples.extend(gen_host_mapping_examples())

    # Shuffle for training diversity
    random.shuffle(all_examples)

    # Write output
    with open(OUTPUT_FILE, 'w') as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + '\n')

    print(f"Generated {len(all_examples)} training examples -> {OUTPUT_FILE}")

    # Print API distribution
    api_counts = {}
    for ex in all_examples:
        content = ex["messages"][-1]["content"]
        api = content.split('\n')[0].replace("API: ", "")
        api_counts[api] = api_counts.get(api, 0) + 1
    print("\nAPI Distribution:")
    for api, count in sorted(api_counts.items(), key=lambda x: -x[1]):
        print(f"  {api}: {count}")


if __name__ == "__main__":
    main()
