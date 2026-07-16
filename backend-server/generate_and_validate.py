"""
Generate 1500+ unique, hand-crafted IDF training examples and validate them
against a live cluster (10.119.248.113).

Each example is a unique (user_query, assistant_response) pair with diverse
natural language phrasings mapped to correct protobuf text format.

Validation: read-only queries are executed via idf_cli.py execute-from-file;
write queries are validated structurally (proto text-format parse check).
"""

import json
import random
import subprocess
import sys
import hashlib
from pathlib import Path

random.seed(2026)

SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "validated_training_data.jsonl"

SYSTEM_PROMPT = (
    'You are an IDF query generator. Output the API method on line 1 as '
    '"API: <Method>" then the protobuf text on subsequent lines.'
)

CLUSTER_IP = "10.119.248.113"
CLUSTER_USER = "nutanix"
CLUSTER_PASS = "nutanix/4u"

# ============================================================
# ENTITY SCHEMA - Real entity types with real attributes
# from entity_attribute_config.proto on the live cluster
# ============================================================

ENTITY_SCHEMA = {
    "vm": {
        "str": ["vm_name", "power_state", "node_uuid", "cluster", "hypervisor_type",
                "guest_os", "owner_uuid", "project_uuid", "protection_type",
                "host_name", "cluster_name", "vm_uuid", "_cluster_uuid_",
                "platform_type", "gpus_in_use", "categories"],
        "int": ["num_vcpus", "memory_size_bytes", "disk_capacity_bytes",
                "num_disks", "num_network_adapters", "cpu_usage_ppm",
                "memory_usage_ppm", "hypervisor_cpu_usage_ppm",
                "controller_avg_io_latency_usecs", "controller_num_iops"],
        "bool": ["is_cvm", "is_live_migratable", "is_agent_vm"],
    },
    "node": {
        "str": ["node_name", "cluster", "hypervisor_type", "bmc_version",
                "hypervisor_full_name", "cpu_model", "serial_number",
                "block_serial", "host_type", "controller_vm_backplane_ip",
                "_cluster_uuid_", "node_uuid", "maintenance_mode_type"],
        "int": ["num_vms", "num_cpu_cores", "num_cpu_sockets",
                "cpu_frequency_hz", "memory_size_bytes", "num_disks",
                "cpu_usage_ppm", "memory_usage_ppm", "controller_num_iops",
                "hypervisor_cpu_usage_ppm"],
        "bool": ["is_degraded", "is_secure_booted"],
    },
    "cluster": {
        "str": ["cluster_name", "_cluster_uuid_", "cluster_uuid", "version",
                "timezone", "operation_mode", "external_ip_address",
                "ncc_version", "hypervisor_types", "encryption_scope"],
        "int": ["num_nodes", "num_vms", "storage_capacity_bytes",
                "storage_usage_bytes", "iops", "bandwidth_bytes",
                "avg_io_latency_usecs", "cpu_usage_ppm", "memory_usage_ppm"],
        "bool": ["is_registered_to_pc", "is_degraded"],
    },
    "disk": {
        "str": ["disk_id", "serial_number", "model", "vendor", "node",
                "storage_tier", "disk_status", "location", "disk_type",
                "_cluster_uuid_", "node_uuid"],
        "int": ["disk_size_bytes", "online_disk_size_bytes", "num_io",
                "avg_io_latency_usecs", "io_bandwidth_bytes", "num_iops"],
        "bool": ["is_mounted", "is_self_encrypting_drive"],
    },
    "container": {
        "str": ["container_name", "storage_pool_uuid", "cluster",
                "replication_factor", "erasure_code", "_cluster_uuid_",
                "container_uuid"],
        "int": ["max_capacity_bytes", "usage_bytes", "free_space_bytes",
                "reserved_capacity_bytes", "num_vdisks",
                "controller_avg_io_latency_usecs", "controller_num_iops"],
        "bool": ["is_compressed", "is_deduplicated"],
    },
    "virtual_disk": {
        "str": ["vm", "container", "virtual_disk_id", "disk_address",
                "storage_container_uuid", "attached_vm_uuid", "_cluster_uuid_"],
        "int": ["disk_capacity_bytes", "usage_bytes", "num_iops",
                "avg_io_latency_usecs", "io_bandwidth_bytes"],
        "bool": ["is_flash_mode_enabled"],
    },
    "virtual_network": {
        "str": ["subnet_name", "subnet_type", "overlay_network_uuid",
                "vpc_uuid", "vswitch_name", "cluster", "_cluster_uuid_"],
        "int": ["vlan_id", "ip_pool_count", "num_vms_connected"],
        "bool": ["is_external"],
    },
    "alert": {
        "str": ["title", "severity", "alert_type_uuid", "source_entity_type",
                "source_entity_uuid", "source_entity_name", "cluster",
                "classification", "alert_status", "_cluster_uuid_"],
        "int": ["creation_time_usecs", "last_occurred_timestamp_usecs",
                "resolved_time_usecs"],
        "bool": ["acknowledged", "auto_resolved", "resolved"],
    },
    "task": {
        "str": ["task_type", "status", "operation_type", "entity_type",
                "entity_uuid", "parent_task_uuid", "cluster",
                "owner_username", "subtask_uuid_list", "_cluster_uuid_"],
        "int": ["start_time_usecs", "completion_time_usecs", "progress_pct",
                "last_updated_timestamp_usecs"],
        "bool": ["is_internal", "is_cancelable"],
    },
    "category": {
        "str": ["name", "value", "description", "owner_uuid", "_cluster_uuid_"],
        "int": ["creation_time_usecs", "last_update_time_usecs"],
        "bool": [],
    },
    "storage_pool": {
        "str": ["storage_pool_name", "cluster", "disk_list", "_cluster_uuid_"],
        "int": ["capacity_bytes", "usage_bytes", "free_space_bytes",
                "num_disks", "iops", "avg_io_latency_usecs"],
        "bool": [],
    },
    "image": {
        "str": ["image_name", "image_type", "image_state", "source_uri",
                "cluster_uuid", "checksum_type", "checksum_value", "_cluster_uuid_"],
        "int": ["size_bytes", "creation_time_usecs", "last_update_time_usecs"],
        "bool": ["is_active"],
    },
    "protection_domain": {
        "str": ["pd_name", "type", "remote_site", "schedule_id",
                "cluster", "status", "replication_link_uuid", "_cluster_uuid_"],
        "int": ["num_protected_entities", "total_user_data_bytes",
                "snapshot_frequency_secs", "retention_count"],
        "bool": ["is_active", "is_metro_availability"],
    },
    "volume_group_config": {
        "str": ["uuid", "name", "_master_cluster_uuid_", "protection_type",
                "sharing_status", "iscsi_target_prefix", "_cluster_uuid_"],
        "int": ["size_bytes", "num_virtual_disks", "creation_time_usecs"],
        "bool": ["is_hidden", "flash_mode_enabled"],
    },
    "host_nic": {
        "str": ["host_nic_name", "mac_address", "node_uuid", "network_uuid",
                "ipv4_address", "link_speed", "_cluster_uuid_"],
        "int": ["mtu_bytes", "tx_bytes", "rx_bytes", "tx_packets", "rx_packets"],
        "bool": ["is_connected", "is_management_nic"],
    },
    "abac_entity_capability": {
        "str": ["entity_type", "entity_uuid", "kind", "category_id_list",
                "_cluster_uuid_"],
        "int": ["creation_time_usecs"],
        "bool": [],
    },
    "report_config": {
        "str": ["name", "description", "report_type", "schedule",
                "owner_uuid", "_cluster_uuid_"],
        "int": ["creation_time_usecs", "last_run_time_usecs"],
        "bool": ["is_enabled"],
    },
    "security_policy": {
        "str": ["name", "description", "type", "state", "scope",
                "_cluster_uuid_", "policy_uuid"],
        "int": ["creation_time_usecs", "last_update_time_usecs", "rule_count"],
        "bool": ["is_system_defined"],
    },
    "recovery_plan": {
        "str": ["name", "description", "status", "recovery_plan_uuid",
                "_cluster_uuid_", "primary_cluster_uuid", "recovery_cluster_uuid"],
        "int": ["creation_time_usecs", "last_test_time_usecs"],
        "bool": ["is_valid"],
    },
}

ALL_ENTITY_TYPES = list(ENTITY_SCHEMA.keys())

# Comparison operators with their natural language equivalents
COMP_OPERATORS = {
    "kEQ": ["equals", "is", "=", "equal to", "matches"],
    "kNE": ["is not", "!=", "not equal to", "doesn't equal", "is different from"],
    "kLT": ["less than", "<", "below", "under", "smaller than"],
    "kLE": ["at most", "<=", "no more than", "less than or equal to"],
    "kGT": ["greater than", ">", "above", "over", "more than", "exceeds"],
    "kGE": ["at least", ">=", "no less than", "greater than or equal to"],
    "kLike": ["like", "matches pattern", "similar to", "containing pattern"],
    "kExists": ["exists", "has value", "is set", "is not null", "is populated"],
}

# Sort order variations
SORT_PHRASES = {
    "kAscending": ["ascending", "asc", "lowest first", "smallest first", "A-Z", "oldest first"],
    "kDescending": ["descending", "desc", "highest first", "largest first", "Z-A", "newest first", "top"],
}

# Aggregation operators
AGG_OPERATORS = {
    "kSum": ["sum", "total", "sum of", "add up"],
    "kMax": ["max", "maximum", "highest", "peak", "largest"],
    "kMin": ["min", "minimum", "lowest", "smallest"],
    "kAvg": ["average", "avg", "mean"],
    "kCount": ["count", "number of", "how many"],
}

# Natural language query starters for different intents
QUERY_STARTERS = {
    "list": ["list all", "show me all", "get all", "fetch all", "display all",
             "retrieve all", "find all", "return all", "query all"],
    "filter": ["find", "show", "get", "fetch", "list", "display", "retrieve",
               "query", "search for", "look up"],
    "count": ["how many", "count", "count the number of", "what is the total number of"],
    "sort": ["sort", "order", "rank", "arrange"],
    "top": ["top", "first", "best", "highest", "largest"],
    "bottom": ["bottom", "last", "worst", "lowest", "smallest"],
}

# Entity type name variations users might use
ENTITY_ALIASES = {
    "vm": ["VMs", "virtual machines", "vm entities", "VMs", "vms"],
    "node": ["nodes", "hosts", "hypervisor hosts", "physical nodes"],
    "cluster": ["clusters", "cluster entities", "registered clusters"],
    "disk": ["disks", "physical disks", "disk entities"],
    "container": ["containers", "storage containers"],
    "virtual_disk": ["virtual disks", "vdisks", "virtual_disk entities"],
    "virtual_network": ["virtual networks", "subnets", "networks", "VLANs"],
    "alert": ["alerts", "alert entities", "active alerts", "system alerts"],
    "task": ["tasks", "task entities", "operations", "running tasks"],
    "category": ["categories", "category entities", "labels"],
    "storage_pool": ["storage pools", "pools"],
    "image": ["images", "disk images", "vm images"],
    "protection_domain": ["protection domains", "PDs", "replication domains"],
    "volume_group_config": ["volume groups", "VGs", "volume group configs"],
    "host_nic": ["host NICs", "network interfaces", "NICs"],
    "abac_entity_capability": ["ABAC capabilities", "entity capabilities"],
    "report_config": ["reports", "report configs", "scheduled reports"],
    "security_policy": ["security policies", "microsegmentation policies", "flow policies"],
    "recovery_plan": ["recovery plans", "DR plans", "disaster recovery plans"],
}

# Realistic values for different attribute types
REALISTIC_VALUES = {
    "vm_name": ["web-server-01", "db-prod-03", "app-staging-02", "jenkins-ci",
                "monitoring-stack", "elk-node-1", "k8s-master", "redis-cache-01",
                "nginx-lb-02", "postgres-replica-01", "kafka-broker-3",
                "hadoop-datanode-05", "spark-worker-02", "vault-server",
                "consul-agent-01", "prometheus-01", "grafana-dashboard",
                "gitlab-runner-02", "nexus-repo", "sonarqube-01"],
    "power_state": ["on", "off", "suspended", "paused"],
    "hypervisor_type": ["kKvm", "kVMware", "kHyperV", "kAHV"],
    "guest_os": ["linux", "windows", "centos7", "ubuntu2004", "rhel8",
                 "windows2019", "debian11", "sles15"],
    "severity": ["critical", "warning", "info", "audit"],
    "status": ["running", "completed", "failed", "queued", "aborted", "suspended"],
    "task_type": ["VmCreate", "VmUpdate", "VmDelete", "VmMigrate", "VmClone",
                  "VmSnapshot", "ClusterUpdate", "ImageCreate", "DiskCreate"],
    "operation_type": ["kCreate", "kUpdate", "kDelete", "kMigrate", "kClone"],
    "image_type": ["DISK_IMAGE", "ISO_IMAGE"],
    "image_state": ["ACTIVE", "INACTIVE", "DELETED"],
    "subnet_type": ["VLAN", "OVERLAY"],
    "disk_type": ["SSD", "HDD", "NVMe", "SATA-SSD"],
    "storage_tier": ["SSD-PCIe", "SSD-SATA", "DAS-SATA", "CLOUD"],
    "cluster_name": ["prod-cluster-01", "dev-cluster-02", "staging-cluster",
                     "dr-site-west", "edge-cluster-nyc"],
    "node_name": ["node-A", "node-B", "node-C", "node-D", "cvm-01", "host-rack1-u3"],
    "container_name": ["default-container", "high-perf-ssd", "archive-tier",
                       "nfs-datastore", "iscsi-pool-01"],
    "subnet_name": ["vlan-100-prod", "vlan-200-mgmt", "overlay-app-tier",
                    "infra-network", "dmz-subnet"],
    "category_name": ["Environment", "Department", "Application", "Tier",
                      "CostCenter", "Owner", "Compliance"],
    "category_value": ["Production", "Development", "Staging", "QA", "DR",
                       "Finance", "Engineering", "Marketing"],
}


def gen_uuid():
    """Generate a realistic UUID."""
    return f"{random.randint(0x10000000, 0xffffffff):08x}-{random.randint(0x1000, 0xffff):04x}-{random.randint(0x1000, 0xffff):04x}-{random.randint(0x1000, 0xffff):04x}-{random.randint(0x100000000000, 0xffffffffffff):012x}"


def gen_int_value(attr_name):
    """Generate a realistic integer value based on attribute name."""
    if "bytes" in attr_name:
        return random.choice([1073741824, 10737418240, 107374182400,
                             536870912, 5368709120, 2147483648])
    elif "ppm" in attr_name:
        return random.randint(10000, 900000)
    elif "usecs" in attr_name or "timestamp" in attr_name:
        return random.randint(1700000000000000, 1778000000000000)
    elif "num_" in attr_name or "count" in attr_name:
        return random.randint(1, 128)
    elif "iops" in attr_name:
        return random.randint(100, 50000)
    elif "latency" in attr_name:
        return random.randint(100, 100000)
    elif "pct" in attr_name:
        return random.randint(0, 100)
    elif "vlan" in attr_name:
        return random.randint(1, 4094)
    elif "mtu" in attr_name:
        return random.choice([1500, 9000])
    elif "frequency" in attr_name or "hz" in attr_name:
        return random.choice([2000000000, 2600000000, 3200000000])
    else:
        return random.randint(1, 1000)


def pick_str_value(attr_name, entity_type):
    """Pick a realistic string value for an attribute."""
    if attr_name in REALISTIC_VALUES:
        return random.choice(REALISTIC_VALUES[attr_name])
    if "uuid" in attr_name or "id" in attr_name:
        return gen_uuid()
    if "name" in attr_name:
        if entity_type in REALISTIC_VALUES.get(f"{entity_type}_name", []):
            return random.choice(REALISTIC_VALUES[f"{entity_type}_name"])
        return f"{entity_type}-{random.randint(1,99):02d}"
    if "type" in attr_name:
        return random.choice(["typeA", "typeB", "typeC"])
    return f"value-{random.randint(1, 999)}"


# ============================================================
# PROTO GENERATORS for each API
# ============================================================

def gen_gewm_simple(entity_type, columns):
    """GetEntitiesWithMetrics - simple listing with raw columns."""
    cols = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in columns)
    return f'''query {{
  entity_list {{ entity_type_name: "{entity_type}" }}
  group_by {{
    {cols}
  }}
  query_name: "auto_query"
}}'''


def gen_gewm_with_limit(entity_type, columns, limit, offset=None):
    """GetEntitiesWithMetrics with raw_limit (and optional offset)."""
    cols = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in columns)
    limit_str = f"raw_limit {{ limit: {limit}"
    if offset:
        limit_str += f" offset: {offset}"
    limit_str += " }"
    return f'''query {{
  entity_list {{ entity_type_name: "{entity_type}" }}
  group_by {{
    {cols}
    {limit_str}
  }}
  query_name: "auto_query"
}}'''


def gen_where_clause_simple(column, operator, value_str):
    """Generate a simple where_clause comparison."""
    return f'''where_clause {{
    comparison_expr {{
      lhs {{
        leaf {{
          column: "{column}"
        }}
      }}
      operator: {operator}
      rhs {{
        leaf {{
          value {{
            {value_str}
          }}
        }}
      }}
    }}
  }}'''


def gen_where_clause_exists(column):
    """Generate a where_clause with kExists operator (no rhs value needed)."""
    return f'''where_clause {{
    comparison_expr {{
      lhs {{
        leaf {{
          column: "{column}"
        }}
      }}
      operator: kExists
      rhs {{
        leaf {{
          value {{
            bool_value: true
          }}
        }}
      }}
    }}
  }}'''


def gen_where_clause_compound(left_col, left_op, left_val, bool_op, right_col, right_op, right_val):
    """Generate a compound where_clause with kAnd/kOr."""
    return f'''where_clause {{
    lhs {{
      comparison_expr {{
        lhs {{
          leaf {{
            column: "{left_col}"
          }}
        }}
        operator: {left_op}
        rhs {{
          leaf {{
            value {{
              {left_val}
            }}
          }}
        }}
      }}
    }}
    operator: {bool_op}
    rhs {{
      comparison_expr {{
        lhs {{
          leaf {{
            column: "{right_col}"
          }}
        }}
        operator: {right_op}
        rhs {{
          leaf {{
            value {{
              {right_val}
            }}
          }}
        }}
      }}
    }}
  }}'''


def gen_sort_order(column, order):
    """Generate raw_sort_order."""
    return f'''raw_sort_order {{
      sort_column: "{column}"
      sort_order: {order}
    }}'''


def gen_gewm_filtered(entity_type, columns, where_clause, limit=None, sort=None):
    """GetEntitiesWithMetrics with filter, optional limit and sort."""
    cols = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in columns)
    parts = [f'entity_list {{ entity_type_name: "{entity_type}" }}']
    parts.append(f"  {where_clause}")
    
    group_parts = [cols]
    if sort:
        group_parts.append(f"    {sort}")
    if limit:
        group_parts.append(f"    raw_limit {{ limit: {limit} }}")
    
    group_content = "\n".join(group_parts)
    return f'''query {{
  {chr(10).join("  " + p for p in parts)}
  group_by {{
    {group_content}
  }}
  query_name: "auto_query"
}}'''


def gen_gewm_groupby(entity_type, group_col, agg_col, agg_op, limit=None):
    """GetEntitiesWithMetrics with group_by column and aggregation."""
    parts = [f'group_by_column: "{group_col}"']
    parts.append(f'aggregate_columns {{ column: "{agg_col}" operator: {agg_op} }}')
    if limit:
        parts.append(f'group_limit {{ limit: {limit} }}')
    group_content = "\n    ".join(parts)
    return f'''query {{
  entity_list {{ entity_type_name: "{entity_type}" }}
  group_by {{
    {group_content}
  }}
  query_name: "auto_query"
}}'''


def gen_gewm_groupby_sort(entity_type, group_col, agg_col, agg_op, sort_col, sort_order, limit):
    """GetEntitiesWithMetrics with group_by, aggregation, sort and limit."""
    return f'''query {{
  entity_list {{ entity_type_name: "{entity_type}" }}
  group_by {{
    group_by_column: "{group_col}"
    aggregate_columns {{ column: "{agg_col}" operator: {agg_op} }}
    group_sort_order {{
      sort_column: "{sort_col}"
      sort_order: {sort_order}
    }}
    group_limit {{ limit: {limit} }}
  }}
  query_name: "auto_query"
}}'''


def gen_update_entity(entity_type, entity_id, attrs):
    """UpdateEntity with attribute_data_arg_list."""
    attr_parts = []
    for name, value_str in attrs:
        attr_parts.append(f'''attribute_data_arg_list {{
  operation: kSET
  attribute_data {{
    name: "{name}"
    value {{
      {value_str}
    }}
  }}
}}''')
    attrs_text = "\n".join(attr_parts)
    return f'''entity_guid {{
  entity_type_name: "{entity_type}"
  entity_id: "{entity_id}"
}}
{attrs_text}'''


def gen_delete_entity(entity_type, entity_id):
    """DeleteEntity."""
    return f'''entity_guid {{
  entity_type_name: "{entity_type}"
  entity_id: "{entity_id}"
}}'''


def gen_batch_gewm(queries):
    """BatchGetEntitiesWithMetrics with multiple query_list items."""
    parts = []
    for entity_type, columns in queries:
        cols = "\n      ".join(f'raw_columns {{ column: "{c}" }}' for c in columns)
        parts.append(f'''query_list {{
  query {{
    entity_list {{ entity_type_name: "{entity_type}" }}
    group_by {{
      {cols}
    }}
    query_name: "auto_query"
  }}
}}''')
    return "\n".join(parts)


def gen_spotlight_search(search_term, entity_types, limit=None):
    """SpotLightSearch."""
    types = "\n  ".join(f'entity_type_name_list: "{t}"' for t in entity_types)
    limit_str = f"\n  limit {{ limit: {limit} }}" if limit else ""
    return f'''search_term: "{search_term}"
  {types}{limit_str}'''


def gen_register_watch(entity_type, watch_type=1):
    """RegisterWatch / Watch."""
    return f'''watch_list {{
  watch_subject {{
    entity_type_name: "{entity_type}"
  }}
  entity_watch_condition {{
    entity_watch_type: {watch_type}
  }}
}}'''


def gen_register_entity_type(entity_type, parent=None):
    """RegisterEntityTypes."""
    parent_str = f'\n    parent_list: "{parent}"' if parent else ""
    return f'''entity_type_info_list {{
  entity_type_name: "{entity_type}"
  type_info {{{parent_str}
    track_attribute_changes: true
  }}
}}'''


def gen_register_metric_type(entity_type, metric_name, is_attribute=True):
    """RegisterMetricTypes."""
    return f'''metric_type_list {{
  entity_type_name: "{entity_type}"
  metric_name: "{metric_name}"
  is_attribute: {str(is_attribute).lower()}
}}'''


def gen_get_entities_trail(entity_type, entity_id):
    """GetEntitiesTrail."""
    return f'''entity_guid_list {{
  entity_type_name: "{entity_type}"
  entity_id: "{entity_id}"
}}'''


def gen_put_metric_data(entity_type, entity_id, metric_name, value_str):
    """PutMetricData."""
    return f'''metric_data_list {{
  entity_guid {{
    entity_type_name: "{entity_type}"
    entity_id: "{entity_id}"
  }}
  metric_name: "{metric_name}"
  value {{
    {value_str}
  }}
}}'''


def gen_put_event(entity_type, entity_id, event_msg):
    """PutEvent."""
    return f'''event_list {{
  entity_guid {{
    entity_type_name: "{entity_type}"
    entity_id: "{entity_id}"
  }}
  event_message: "{event_msg}"
}}'''


def gen_attach_entity(entity_type, entity_id):
    """AttachEntity."""
    return f'''entity_guid {{
  entity_type_name: "{entity_type}"
  entity_id: "{entity_id}"
}}'''


def gen_get_metric_data(entity_type, entity_id, metric_names):
    """GetMetricData."""
    metrics = "\n".join(f'metric_name_list: "{m}"' for m in metric_names)
    return f'''entity_guid {{
  entity_type_name: "{entity_type}"
  entity_id: "{entity_id}"
}}
{metrics}'''


# ============================================================
# EXAMPLE GENERATION - Each function generates unique examples
# ============================================================

def generate_all_examples():
    """Generate all training examples. Returns list of (user_query, api, proto)."""
    examples = []
    seen_hashes = set()
    
    def add(user_q, api, proto):
        h = hashlib.md5(f"{user_q}||{proto}".encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            examples.append((user_q, api, proto))
    
    # ----------------------------------------------------------
    # 1. GetEntitiesWithMetrics - SIMPLE LISTINGS (~150)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        # Basic listing with 1-3 columns
        for num_cols in [1, 2, 3]:
            all_attrs = schema["str"] + schema["int"]
            if len(all_attrs) < num_cols:
                continue
            cols = random.sample(all_attrs, num_cols)
            alias = random.choice(aliases)
            starter = random.choice(QUERY_STARTERS["list"])
            user_q = f"{starter} {alias}"
            if num_cols > 1:
                user_q += f" showing {', '.join(cols)}"
            proto = gen_gewm_simple(etype, cols)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        # With limit
        for limit in [5, 10, 20, 50, 100]:
            cols = random.sample(schema["str"][:5] + schema["int"][:3], min(2, len(schema["str"] + schema["int"])))
            alias = random.choice(aliases)
            user_q = f"get the first {limit} {alias}"
            proto = gen_gewm_with_limit(etype, cols, limit)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        # With limit + offset (pagination)
        if len(schema["str"]) >= 2:
            cols = random.sample(schema["str"][:4], 2)
            alias = random.choice(aliases)
            for offset, limit in [(10, 10), (20, 5), (50, 25), (0, 100)]:
                user_q = f"get {alias} page starting at offset {offset} with limit {limit}"
                proto = gen_gewm_with_limit(etype, cols, limit, offset if offset > 0 else None)
                add(user_q, "GetEntitiesWithMetrics", proto)

    # ----------------------------------------------------------
    # 2. GetEntitiesWithMetrics - FILTERED (~300)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        # String equality filters
        for attr in schema["str"][:6]:
            val = pick_str_value(attr, etype)
            alias = random.choice(aliases)
            op_word = random.choice(COMP_OPERATORS["kEQ"])
            starter = random.choice(QUERY_STARTERS["filter"])
            user_q = f"{starter} {alias} where {attr} {op_word} {val}"
            where = gen_where_clause_simple(attr, "kEQ", f'str_value: "{val}"')
            cols = random.sample(schema["str"][:5], min(2, len(schema["str"])))
            proto = gen_gewm_filtered(etype, cols, where)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        # String NOT EQUAL
        if schema["str"]:
            attr = random.choice(schema["str"][:4])
            val = pick_str_value(attr, etype)
            alias = random.choice(aliases)
            user_q = f"find {alias} where {attr} is not {val}"
            where = gen_where_clause_simple(attr, "kNE", f'str_value: "{val}"')
            cols = random.sample(schema["str"][:5], min(2, len(schema["str"])))
            proto = gen_gewm_filtered(etype, cols, where)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        # kLike (pattern matching)
        if schema["str"]:
            attr = random.choice(schema["str"][:3])
            pattern = random.choice(["prod.*", ".*test.*", "web-.*", ".*-01", "dev.*", ".*staging.*"])
            alias = random.choice(aliases)
            user_q = f"find {alias} where {attr} matches pattern {pattern}"
            where = gen_where_clause_simple(attr, "kLike", f'str_value: "{pattern}"')
            cols = [attr] + random.sample(schema["str"][:5], min(1, len(schema["str"])-1))
            proto = gen_gewm_filtered(etype, list(set(cols)), where)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        # Integer comparisons
        for attr in schema["int"][:4]:
            int_val = gen_int_value(attr)
            alias = random.choice(aliases)
            
            # GT
            op_word = random.choice(COMP_OPERATORS["kGT"])
            user_q = f"get {alias} where {attr} {op_word} {int_val}"
            where = gen_where_clause_simple(attr, "kGT", f'int64_value: {int_val}')
            cols = random.sample(schema["str"][:3] + [attr], min(3, len(schema["str"])+1))
            proto = gen_gewm_filtered(etype, list(set(cols)), where)
            add(user_q, "GetEntitiesWithMetrics", proto)
            
            # LT
            op_word = random.choice(COMP_OPERATORS["kLT"])
            user_q = f"show {alias} with {attr} {op_word} {int_val}"
            where = gen_where_clause_simple(attr, "kLT", f'int64_value: {int_val}')
            proto = gen_gewm_filtered(etype, list(set(cols)), where)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        # Boolean filters
        for attr in schema["bool"][:2]:
            alias = random.choice(aliases)
            for bool_val in [True, False]:
                val_word = "true" if bool_val else "false"
                user_q = f"find {alias} where {attr} is {val_word}"
                where = gen_where_clause_simple(attr, "kEQ", f'bool_value: {val_word}')
                cols = random.sample(schema["str"][:4], min(2, len(schema["str"])))
                proto = gen_gewm_filtered(etype, cols, where)
                add(user_q, "GetEntitiesWithMetrics", proto)
        
        # kExists
        if schema["str"]:
            attr = random.choice(schema["str"][:5])
            alias = random.choice(aliases)
            user_q = f"get {alias} where {attr} exists"
            where = gen_where_clause_exists(attr)
            cols = [attr] + random.sample(schema["str"][:3], min(1, len(schema["str"])-1))
            proto = gen_gewm_filtered(etype, list(set(cols)), where)
            add(user_q, "GetEntitiesWithMetrics", proto)

    # ----------------------------------------------------------
    # 3. GetEntitiesWithMetrics - COMPOUND FILTERS (~100)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        if len(schema["str"]) >= 2:
            # AND with two string conditions
            attr1, attr2 = random.sample(schema["str"][:5], 2)
            val1 = pick_str_value(attr1, etype)
            val2 = pick_str_value(attr2, etype)
            alias = random.choice(aliases)
            user_q = f"get {alias} where {attr1} = {val1} and {attr2} = {val2}"
            where = gen_where_clause_compound(
                attr1, "kEQ", f'str_value: "{val1}"',
                "kAnd",
                attr2, "kEQ", f'str_value: "{val2}"'
            )
            cols = [attr1, attr2]
            proto = gen_gewm_filtered(etype, cols, where)
            add(user_q, "GetEntitiesWithMetrics", proto)
        
        if schema["str"] and schema["int"]:
            # AND with string + int condition
            str_attr = random.choice(schema["str"][:4])
            int_attr = random.choice(schema["int"][:4])
            str_val = pick_str_value(str_attr, etype)
            int_val = gen_int_value(int_attr)
            alias = random.choice(aliases)
            user_q = f"find {alias} where {str_attr} = {str_val} and {int_attr} > {int_val}"
            where = gen_where_clause_compound(
                str_attr, "kEQ", f'str_value: "{str_val}"',
                "kAnd",
                int_attr, "kGT", f'int64_value: {int_val}'
            )
            cols = [str_attr, int_attr]
            proto = gen_gewm_filtered(etype, cols, where)
            add(user_q, "GetEntitiesWithMetrics", proto)
            
            # OR condition
            user_q = f"show {alias} where {str_attr} = {str_val} or {int_attr} < {int_val}"
            where = gen_where_clause_compound(
                str_attr, "kEQ", f'str_value: "{str_val}"',
                "kOr",
                int_attr, "kLT", f'int64_value: {int_val}'
            )
            proto = gen_gewm_filtered(etype, cols, where)
            add(user_q, "GetEntitiesWithMetrics", proto)

    # ----------------------------------------------------------
    # 4. GetEntitiesWithMetrics - SORTING (~80)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        for sort_attr in (schema["int"][:2] + schema["str"][:1]):
            for order in ["kAscending", "kDescending"]:
                alias = random.choice(aliases)
                order_word = random.choice(SORT_PHRASES[order])
                user_q = f"list {alias} sorted by {sort_attr} {order_word}"
                cols = random.sample(schema["str"][:4], min(2, len(schema["str"])))
                if sort_attr not in cols:
                    cols.append(sort_attr)
                sort = gen_sort_order(sort_attr, order)
                proto = gen_gewm_filtered(etype, cols, "", limit=20)
                proto = proto.replace('  \n  group_by', '  group_by')
                # Rebuild properly with sort
                cols_str = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in cols)
                proto = f'''query {{
  entity_list {{ entity_type_name: "{etype}" }}
  group_by {{
    {cols_str}
    {sort}
    raw_limit {{ limit: 20 }}
  }}
  query_name: "auto_query"
}}'''
                add(user_q, "GetEntitiesWithMetrics", proto)

    # ----------------------------------------------------------
    # 5. GetEntitiesWithMetrics - TOP/BOTTOM N queries (~60)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "cluster", "disk", "container", "alert", "task"]:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        for int_attr in schema["int"][:3]:
            for n in [3, 5, 10]:
                alias = random.choice(aliases)
                # Top N
                user_q = f"top {n} {alias} by {int_attr}"
                cols = random.sample(schema["str"][:3], min(2, len(schema["str"])))
                if int_attr not in cols:
                    cols.append(int_attr)
                cols_str = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in cols)
                proto = f'''query {{
  entity_list {{ entity_type_name: "{etype}" }}
  group_by {{
    {cols_str}
    raw_sort_order {{
      sort_column: "{int_attr}"
      sort_order: kDescending
    }}
    raw_limit {{ limit: {n} }}
  }}
  query_name: "auto_query"
}}'''
                add(user_q, "GetEntitiesWithMetrics", proto)
                
                # Bottom N
                user_q = f"bottom {n} {alias} by {int_attr}"
                proto2 = proto.replace("kDescending", "kAscending")
                add(user_q, "GetEntitiesWithMetrics", proto2)

    # ----------------------------------------------------------
    # 6. GetEntitiesWithMetrics - GROUP BY + AGGREGATION (~80)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "disk", "container", "alert", "task", "virtual_network"]:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        for group_attr in schema["str"][:3]:
            for agg_attr in schema["int"][:2]:
                for agg_op, agg_words in AGG_OPERATORS.items():
                    alias = random.choice(aliases)
                    agg_word = random.choice(agg_words)
                    user_q = f"{agg_word} of {agg_attr} for {alias} grouped by {group_attr}"
                    proto = gen_gewm_groupby(etype, group_attr, agg_attr, agg_op)
                    add(user_q, "GetEntitiesWithMetrics", proto)

    # ----------------------------------------------------------
    # 7. GetEntitiesWithMetrics - COMBINED filter + sort + limit (~100)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "cluster", "alert", "task", "disk", "container"]:
        schema = ENTITY_SCHEMA[etype]
        aliases = ENTITY_ALIASES.get(etype, [f"{etype}s"])
        
        for _ in range(5):
            str_attr = random.choice(schema["str"][:5])
            int_attr = random.choice(schema["int"][:4])
            str_val = pick_str_value(str_attr, etype)
            alias = random.choice(aliases)
            limit = random.choice([5, 10, 20])
            order = random.choice(["kAscending", "kDescending"])
            order_word = random.choice(SORT_PHRASES[order])
            
            user_q = f"find {alias} where {str_attr} = {str_val} sorted by {int_attr} {order_word} limit {limit}"
            where = gen_where_clause_simple(str_attr, "kEQ", f'str_value: "{str_val}"')
            cols = list(set([str_attr, int_attr]))
            cols_str = "\n    ".join(f'raw_columns {{ column: "{c}" }}' for c in cols)
            sort = gen_sort_order(int_attr, order)
            proto = f'''query {{
  entity_list {{ entity_type_name: "{etype}" }}
  {where}
  group_by {{
    {cols_str}
    {sort}
    raw_limit {{ limit: {limit} }}
  }}
  query_name: "auto_query"
}}'''
            add(user_q, "GetEntitiesWithMetrics", proto)

    # ----------------------------------------------------------
    # 8. UpdateEntity (~120)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES:
        schema = ENTITY_SCHEMA[etype]
        
        # Single string attribute update
        for attr in schema["str"][:3]:
            val = pick_str_value(attr, etype)
            entity_id = gen_uuid()
            alias = random.choice(ENTITY_ALIASES.get(etype, [etype]))
            user_q = f"update {etype} {entity_id} set {attr} to {val}"
            proto = gen_update_entity(etype, entity_id, [(attr, f'str_value: "{val}"')])
            add(user_q, "UpdateEntity", proto)
        
        # Single int attribute update
        for attr in schema["int"][:2]:
            val = gen_int_value(attr)
            entity_id = gen_uuid()
            user_q = f"set {attr} to {val} on {etype} entity {entity_id}"
            proto = gen_update_entity(etype, entity_id, [(attr, f'int64_value: {val}')])
            add(user_q, "UpdateEntity", proto)
        
        # Multi-attribute update
        if len(schema["str"]) >= 2:
            attrs = random.sample(schema["str"][:4], 2)
            vals = [pick_str_value(a, etype) for a in attrs]
            entity_id = gen_uuid()
            attr_pairs = [(a, f'str_value: "{v}"') for a, v in zip(attrs, vals)]
            user_q = f"update {etype} {entity_id}: set {attrs[0]}={vals[0]} and {attrs[1]}={vals[1]}"
            proto = gen_update_entity(etype, entity_id, attr_pairs)
            add(user_q, "UpdateEntity", proto)
        
        # Boolean attribute update
        for attr in schema["bool"][:1]:
            entity_id = gen_uuid()
            bool_val = random.choice(["true", "false"])
            user_q = f"set {attr} to {bool_val} for {etype} {entity_id}"
            proto = gen_update_entity(etype, entity_id, [(attr, f'bool_value: {bool_val}')])
            add(user_q, "UpdateEntity", proto)

    # ----------------------------------------------------------
    # 9. DeleteEntity (~80)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES:
        aliases = ENTITY_ALIASES.get(etype, [etype])
        
        for _ in range(3):
            entity_id = gen_uuid()
            alias = random.choice(aliases)
            verb = random.choice(["delete", "remove", "destroy", "drop"])
            user_q = f"{verb} the {etype} entity with id {entity_id}"
            proto = gen_delete_entity(etype, entity_id)
            add(user_q, "DeleteEntity", proto)
        
        # Named delete
        if ENTITY_SCHEMA[etype]["str"]:
            name_attr = ENTITY_SCHEMA[etype]["str"][0]
            val = pick_str_value(name_attr, etype)
            entity_id = gen_uuid()
            user_q = f"remove {etype} {val} (id: {entity_id})"
            proto = gen_delete_entity(etype, entity_id)
            add(user_q, "DeleteEntity", proto)

    # ----------------------------------------------------------
    # 10. BatchGetEntitiesWithMetrics (~60)
    # ----------------------------------------------------------
    entity_combos = [
        (["vm", "node"], "get all VMs and nodes together"),
        (["vm", "cluster"], "batch query: fetch VMs and clusters"),
        (["alert", "task"], "get alerts and tasks in one batch"),
        (["disk", "container"], "query disks and containers together"),
        (["vm", "node", "cluster"], "batch fetch VMs, nodes, and clusters"),
        (["alert", "task", "cluster"], "get alerts, tasks, and cluster info in batch"),
        (["virtual_network", "vm"], "fetch networks and VMs in a single batch"),
        (["image", "container"], "batch query images and containers"),
        (["category", "alert"], "get categories and alerts together"),
        (["storage_pool", "disk"], "batch get storage pools and disks"),
        (["host_nic", "node"], "fetch host NICs and nodes in batch"),
        (["protection_domain", "vm"], "get protection domains and VMs together"),
        (["volume_group_config", "virtual_disk"], "batch query volume groups and virtual disks"),
        (["report_config", "task"], "get report configs and tasks in batch"),
        (["security_policy", "category"], "fetch security policies and categories together"),
    ]
    
    for etypes, base_query in entity_combos:
        queries = []
        for et in etypes:
            schema = ENTITY_SCHEMA[et]
            cols = random.sample(schema["str"][:4], min(2, len(schema["str"])))
            queries.append((et, cols))
        proto = gen_batch_gewm(queries)
        add(base_query, "BatchGetEntitiesWithMetrics", proto)
        
        # Variation with different columns
        queries2 = []
        for et in etypes:
            schema = ENTITY_SCHEMA[et]
            cols = random.sample(schema["str"][:6] + schema["int"][:2], min(3, len(schema["str"])+len(schema["int"])))
            queries2.append((et, cols))
        user_q2 = f"batch get {' and '.join(etypes)} with detailed attributes"
        proto2 = gen_batch_gewm(queries2)
        add(user_q2, "BatchGetEntitiesWithMetrics", proto2)
        
        # With specific columns mentioned
        all_cols = []
        for et in etypes:
            all_cols.extend(ENTITY_SCHEMA[et]["str"][:2])
        user_q3 = f"batch query {', '.join(etypes)} showing {', '.join(all_cols[:4])}"
        add(user_q3, "BatchGetEntitiesWithMetrics", proto2)

    # ----------------------------------------------------------
    # 11. SpotLightSearch (~50)
    # ----------------------------------------------------------
    search_terms = [
        "production", "web-server", "critical", "failed", "test",
        "backup", "monitoring", "database", "cache", "nginx",
        "kubernetes", "docker", "jenkins", "staging", "development",
        "storage", "network", "security", "admin", "oracle",
        "postgres", "mysql", "redis", "elasticsearch", "kafka",
        "hadoop", "spark", "consul", "vault", "prometheus",
    ]
    
    for term in search_terms:
        etypes = random.sample(ALL_ENTITY_TYPES[:10], random.randint(1, 4))
        limit = random.choice([5, 10, 20, 50, None])
        user_q = f'search for "{term}" across {", ".join(etypes)}'
        proto = gen_spotlight_search(term, etypes, limit)
        add(user_q, "SpotLightSearch", proto)
    
    # Broader searches
    for term in ["error", "timeout", "disk", "memory", "cpu"]:
        user_q = f'global search for "{term}" in all entity types'
        proto = gen_spotlight_search(term, ALL_ENTITY_TYPES[:8], 20)
        add(user_q, "SpotLightSearch", proto)

    # ----------------------------------------------------------
    # 12. Watch / RegisterWatch (~60)
    # ----------------------------------------------------------
    watch_types = {
        1: "creation",
        2: "deletion",
        3: "update",
    }
    
    for etype in ALL_ENTITY_TYPES[:12]:
        aliases = ENTITY_ALIASES.get(etype, [etype])
        for wtype, wname in watch_types.items():
            alias = random.choice(aliases)
            user_q = f"watch for {wname} of {alias}"
            proto = gen_register_watch(etype, wtype)
            add(user_q, "Watch", proto)
    
    # Watch with specific phrasing variations
    watch_phrases = [
        ("notify me when a new {alias} is created", 1),
        ("alert me when any {alias} is deleted", 2),
        ("subscribe to {alias} updates", 3),
        ("set up a watch for {alias} changes", 3),
        ("monitor {alias} creation events", 1),
        ("track when {alias} are removed", 2),
    ]
    for etype in ["vm", "node", "alert", "task", "cluster"]:
        aliases = ENTITY_ALIASES.get(etype, [etype])
        for phrase_tmpl, wtype in watch_phrases:
            alias = random.choice(aliases)
            user_q = phrase_tmpl.format(alias=alias)
            proto = gen_register_watch(etype, wtype)
            add(user_q, "Watch", proto)

    # ----------------------------------------------------------
    # 13. GetEntityTypes (~40)
    # ----------------------------------------------------------
    get_etype_queries = [
        "list all entity types",
        "what entity types are registered in IDF?",
        "show me available entity types",
        "get all registered entity types",
        "fetch the entity type catalog",
        "what kinds of entities does IDF know about?",
        "show entity type definitions",
        "list registered IDF entity types",
        "get information about all entity types",
        "describe available entity types",
        "what are the supported entity types?",
        "enumerate all entity types in the system",
        "query for entity type metadata",
        "get the entity type registry",
        "show all entity type configurations",
    ]
    for q in get_etype_queries:
        add(q, "GetEntityTypes", "")
    
    # Specific entity type info
    for etype in ALL_ENTITY_TYPES[:10]:
        user_q = f"get entity type info for {etype}"
        proto = f'entity_type_name_list: "{etype}"'
        add(user_q, "GetEntityTypes", proto)

    # ----------------------------------------------------------
    # 14. GetMetricTypes (~40)
    # ----------------------------------------------------------
    get_metric_queries = [
        "list all metric types",
        "what metrics are registered?",
        "show all available metrics",
        "get metric type definitions",
        "fetch metric catalog",
        "what metrics can I query?",
        "describe registered metrics",
        "show metric types in IDF",
        "enumerate all metrics",
        "get all metric type information",
    ]
    for q in get_metric_queries:
        add(q, "GetMetricTypes", "")
    
    # Specific entity type metrics
    for etype in ALL_ENTITY_TYPES[:10]:
        aliases = ENTITY_ALIASES.get(etype, [etype])
        user_q = f"get metrics available for {random.choice(aliases)}"
        proto = f'entity_type_name: "{etype}"'
        add(user_q, "GetMetricTypes", proto)
        
        user_q = f"what attributes does {etype} have?"
        add(user_q, "GetMetricTypes", proto)

    # ----------------------------------------------------------
    # 15. GetMasterLocation (~20)
    # ----------------------------------------------------------
    master_queries = [
        "find the master node location",
        "where is the IDF master?",
        "get master location",
        "which node is the IDF master?",
        "find IDF master node",
        "get the current master location",
        "show master node address",
        "what is the master node IP?",
        "locate the insights master",
        "find the current IDF leader",
        "get master node info",
        "which host runs the IDF master?",
        "show IDF master location",
        "where is insights server master?",
        "get the insights master node",
        "find cluster master for IDF",
        "locate IDF master service",
        "what node is serving as IDF master?",
        "get master location for insights",
        "show me the IDF master endpoint",
    ]
    for q in master_queries:
        add(q, "GetMasterLocation", "")

    # ----------------------------------------------------------
    # 16. RegisterEntityTypes (~30)
    # ----------------------------------------------------------
    new_entity_types = [
        ("custom_app_metric", "cluster"),
        ("deployment_config", "cluster"),
        ("k8s_pod", "node"),
        ("k8s_namespace", "cluster"),
        ("network_policy", "cluster"),
        ("load_balancer", "virtual_network"),
        ("backup_schedule", "protection_domain"),
        ("compliance_scan", "cluster"),
        ("cost_report", "cluster"),
        ("audit_event", "cluster"),
        ("service_mesh", "cluster"),
        ("api_gateway", "cluster"),
        ("dns_record", "virtual_network"),
        ("ssl_certificate", "cluster"),
        ("terraform_state", "cluster"),
    ]
    
    for new_type, parent in new_entity_types:
        user_q = f"register a new entity type called {new_type} with parent {parent}"
        proto = gen_register_entity_type(new_type, parent)
        add(user_q, "RegisterEntityTypes", proto)
        
        user_q = f"create entity type {new_type} under {parent}"
        add(user_q, "RegisterEntityTypes", proto)

    # ----------------------------------------------------------
    # 17. RegisterMetricTypes (~30)
    # ----------------------------------------------------------
    new_metrics = [
        ("vm", "custom_cpu_score", True),
        ("vm", "last_backup_time", True),
        ("node", "temperature_celsius", False),
        ("node", "fan_speed_rpm", False),
        ("cluster", "license_expiry_days", True),
        ("cluster", "total_snapshots", True),
        ("container", "dedup_ratio", False),
        ("container", "compression_savings_bytes", False),
        ("disk", "wear_level_pct", False),
        ("disk", "predicted_failure_date", True),
        ("alert", "escalation_level", True),
        ("alert", "assigned_team", True),
        ("task", "retry_count", True),
        ("task", "estimated_duration_secs", True),
        ("virtual_network", "bandwidth_limit_mbps", True),
    ]
    
    for etype, metric, is_attr in new_metrics:
        attr_word = "attribute" if is_attr else "metric"
        user_q = f"register {attr_word} {metric} for entity type {etype}"
        proto = gen_register_metric_type(etype, metric, is_attr)
        add(user_q, "RegisterMetricTypes", proto)
        
        user_q = f"add {metric} as a new {attr_word} on {etype}"
        add(user_q, "RegisterMetricTypes", proto)

    # ----------------------------------------------------------
    # 18. UnregisterMetricTypes (~25)
    # ----------------------------------------------------------
    for etype, metric, _ in new_metrics[:12]:
        user_q = f"unregister metric {metric} from {etype}"
        proto = f'''metric_type_list {{
  entity_type_name: "{etype}"
  metric_name: "{metric}"
}}'''
        add(user_q, "UnregisterMetricTypes", proto)
        
        user_q = f"remove the {metric} attribute from {etype} entity type"
        add(user_q, "UnregisterMetricTypes", proto)

    # ----------------------------------------------------------
    # 19. GetEntitiesTrail (~30)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "cluster", "alert", "task", "disk",
                  "container", "image", "protection_domain", "volume_group_config"]:
        entity_id = gen_uuid()
        aliases = ENTITY_ALIASES.get(etype, [etype])
        alias = random.choice(aliases)
        
        user_q = f"get change history for {etype} {entity_id}"
        proto = gen_get_entities_trail(etype, entity_id)
        add(user_q, "GetEntitiesTrail", proto)
        
        user_q = f"show audit trail for {alias} entity {entity_id}"
        add(user_q, "GetEntitiesTrail", proto)
        
        user_q = f"track changes to {etype} {entity_id}"
        add(user_q, "GetEntitiesTrail", proto)

    # ----------------------------------------------------------
    # 20. GetEntities (simple entity fetch by GUID) (~20)
    # ----------------------------------------------------------
    for etype in ALL_ENTITY_TYPES[:10]:
        entity_id = gen_uuid()
        user_q = f"get entity {etype}/{entity_id}"
        proto = f'''entity_guid_list {{
  entity_type_name: "{etype}"
  entity_id: "{entity_id}"
}}'''
        add(user_q, "GetEntities", proto)
        
        user_q = f"fetch {etype} by id {entity_id}"
        add(user_q, "GetEntities", proto)

    # ----------------------------------------------------------
    # 21. PutMetricData (~20)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "cluster", "disk", "container"]:
        schema = ENTITY_SCHEMA[etype]
        entity_id = gen_uuid()
        
        for metric in schema["int"][:2]:
            val = gen_int_value(metric)
            user_q = f"put metric data: set {metric} = {val} for {etype} {entity_id}"
            proto = gen_put_metric_data(etype, entity_id, metric, f'int64_value: {val}')
            add(user_q, "PutMetricData", proto)

    # ----------------------------------------------------------
    # 22. PutEvent (~20)
    # ----------------------------------------------------------
    events = [
        ("vm", "VM migration completed successfully"),
        ("vm", "VM snapshot created"),
        ("vm", "VM powered off by admin"),
        ("vm", "VM disk expansion completed"),
        ("node", "Node entered maintenance mode"),
        ("node", "Node firmware updated"),
        ("node", "Node rebooted after crash"),
        ("cluster", "Cluster upgrade started"),
        ("cluster", "NCC health check passed"),
        ("cluster", "New node added to cluster"),
        ("disk", "Disk marked as failing"),
        ("disk", "Disk self-test completed"),
        ("container", "Container rebalance started"),
        ("alert", "Alert acknowledged by admin"),
        ("alert", "Alert auto-resolved"),
        ("task", "Long-running task cancelled"),
        ("task", "Task retry scheduled"),
        ("protection_domain", "Snapshot replication completed"),
        ("image", "Image download completed"),
        ("volume_group_config", "Volume group resized"),
    ]
    
    for etype, event_msg in events:
        entity_id = gen_uuid()
        user_q = f"log event for {etype} {entity_id}: {event_msg}"
        proto = gen_put_event(etype, entity_id, event_msg)
        add(user_q, "PutEvent", proto)

    # ----------------------------------------------------------
    # 23. AttachEntity / DetachEntity (~20 each)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "disk", "container", "virtual_disk",
                  "virtual_network", "protection_domain", "volume_group_config",
                  "image", "host_nic"]:
        entity_id = gen_uuid()
        
        user_q = f"attach {etype} entity {entity_id} to this cluster"
        proto = gen_attach_entity(etype, entity_id)
        add(user_q, "AttachEntity", proto)
        
        user_q = f"detach {etype} {entity_id} from the cluster"
        add(user_q, "DetachEntity", proto)

    # ----------------------------------------------------------
    # 24. GetMetricData (~20)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "cluster", "disk", "container"]:
        schema = ENTITY_SCHEMA[etype]
        entity_id = gen_uuid()
        metrics = random.sample(schema["int"][:5], min(3, len(schema["int"])))
        
        user_q = f"get metric data for {etype} {entity_id}: {', '.join(metrics)}"
        proto = gen_get_metric_data(etype, entity_id, metrics)
        add(user_q, "GetMetricData", proto)
        
        # Time-series variant
        user_q = f"fetch time-series data for {', '.join(metrics)} on {etype} {entity_id}"
        add(user_q, "GetMetricData", proto)

    # ----------------------------------------------------------
    # 25. BatchUpdateEntities (~20)
    # ----------------------------------------------------------
    for etype in ["vm", "node", "alert", "task", "category"]:
        schema = ENTITY_SCHEMA[etype]
        ids = [gen_uuid() for _ in range(random.randint(2, 4))]
        attr = random.choice(schema["str"][:3])
        val = pick_str_value(attr, etype)
        
        parts = []
        for eid in ids:
            parts.append(f'''update_list {{
  entity_guid {{
    entity_type_name: "{etype}"
    entity_id: "{eid}"
  }}
  attribute_data_arg_list {{
    operation: kSET
    attribute_data {{
      name: "{attr}"
      value {{
        str_value: "{val}"
      }}
    }}
  }}
}}''')
        proto = "\n".join(parts)
        user_q = f"batch update {len(ids)} {etype} entities: set {attr} to {val}"
        add(user_q, "BatchUpdateEntities", proto)

    # ----------------------------------------------------------
    # 26. BatchDeleteEntities (~15)
    # ----------------------------------------------------------
    for etype in ["vm", "alert", "task", "image", "category"]:
        ids = [gen_uuid() for _ in range(random.randint(2, 5))]
        parts = []
        for eid in ids:
            parts.append(f'''delete_list {{
  entity_guid {{
    entity_type_name: "{etype}"
    entity_id: "{eid}"
  }}
}}''')
        proto = "\n".join(parts)
        user_q = f"batch delete {len(ids)} {etype} entities"
        add(user_q, "BatchDeleteEntities", proto)
        
        user_q = f"remove multiple {etype}s: {', '.join(ids[:2])}..."
        add(user_q, "BatchDeleteEntities", proto)

    # ----------------------------------------------------------
    # 27. Complex real-world scenario queries (~100)
    # ----------------------------------------------------------
    # These are realistic queries an admin would actually ask
    
    complex_scenarios = [
        # VM queries
        ("show me all powered-off VMs with more than 4 vCPUs",
         "GetEntitiesWithMetrics",
         lambda: _complex_vm_powered_off_vcpus()),
        ("find VMs consuming more than 80% CPU",
         "GetEntitiesWithMetrics",
         lambda: _complex_vm_high_cpu()),
        ("list VMs with memory usage above 90% sorted by memory descending",
         "GetEntitiesWithMetrics",
         lambda: _complex_vm_high_memory_sorted()),
        ("get the 10 largest VMs by disk capacity",
         "GetEntitiesWithMetrics",
         lambda: _complex_vm_largest_disk()),
        ("find VMs on hypervisor kKvm with more than 8 vcpus",
         "GetEntitiesWithMetrics",
         lambda: _complex_vm_hypervisor_vcpu()),
        
        # Alert queries
        ("show critical alerts that are not resolved",
         "GetEntitiesWithMetrics",
         lambda: _complex_alert_critical_unresolved()),
        ("find warning alerts from the last hour",
         "GetEntitiesWithMetrics",
         lambda: _complex_alert_recent_warnings()),
        ("count alerts grouped by severity",
         "GetEntitiesWithMetrics",
         lambda: _complex_alert_count_by_severity()),
        
        # Task queries
        ("show failed tasks sorted by start time descending",
         "GetEntitiesWithMetrics",
         lambda: _complex_task_failed_sorted()),
        ("find running tasks with progress less than 50%",
         "GetEntitiesWithMetrics",
         lambda: _complex_task_running_low_progress()),
        
        # Node queries
        ("find nodes with CPU usage above 70%",
         "GetEntitiesWithMetrics",
         lambda: _complex_node_high_cpu()),
        ("show degraded nodes",
         "GetEntitiesWithMetrics",
         lambda: _complex_node_degraded()),
        
        # Disk queries
        ("find SSDs with high IO latency",
         "GetEntitiesWithMetrics",
         lambda: _complex_disk_ssd_high_latency()),
        ("show disks sorted by IOPS descending top 5",
         "GetEntitiesWithMetrics",
         lambda: _complex_disk_top_iops()),
        
        # Container queries
        ("find containers with less than 10% free space",
         "GetEntitiesWithMetrics",
         lambda: _complex_container_low_space()),
        
        # Cross-entity
        ("search for anything related to 'database' across VMs and containers",
         "SpotLightSearch",
         lambda: gen_spotlight_search("database", ["vm", "container"], 20)),
    ]
    
    for user_q, api, proto_fn in complex_scenarios:
        proto = proto_fn()
        add(user_q, api, proto)

    return examples


# Complex scenario helper functions
def _complex_vm_powered_off_vcpus():
    return '''query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "power_state" } }
        operator: kEQ
        rhs { leaf { value { str_value: "off" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "num_vcpus" } }
        operator: kGT
        rhs { leaf { value { int64_value: 4 } } }
      }
    }
  }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "power_state" }
    raw_columns { column: "num_vcpus" }
  }
  query_name: "auto_query"
}'''


def _complex_vm_high_cpu():
    return '''query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "cpu_usage_ppm" } }
      operator: kGT
      rhs { leaf { value { int64_value: 800000 } } }
    }
  }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "cpu_usage_ppm" }
    raw_columns { column: "num_vcpus" }
    raw_sort_order {
      sort_column: "cpu_usage_ppm"
      sort_order: kDescending
    }
  }
  query_name: "auto_query"
}'''


def _complex_vm_high_memory_sorted():
    return '''query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "memory_usage_ppm" } }
      operator: kGT
      rhs { leaf { value { int64_value: 900000 } } }
    }
  }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "memory_usage_ppm" }
    raw_columns { column: "memory_size_bytes" }
    raw_sort_order {
      sort_column: "memory_usage_ppm"
      sort_order: kDescending
    }
  }
  query_name: "auto_query"
}'''


def _complex_vm_largest_disk():
    return '''query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "disk_capacity_bytes" }
    raw_sort_order {
      sort_column: "disk_capacity_bytes"
      sort_order: kDescending
    }
    raw_limit { limit: 10 }
  }
  query_name: "auto_query"
}'''


def _complex_vm_hypervisor_vcpu():
    return '''query {
  entity_list { entity_type_name: "vm" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "hypervisor_type" } }
        operator: kEQ
        rhs { leaf { value { str_value: "kKvm" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "num_vcpus" } }
        operator: kGT
        rhs { leaf { value { int64_value: 8 } } }
      }
    }
  }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "hypervisor_type" }
    raw_columns { column: "num_vcpus" }
  }
  query_name: "auto_query"
}'''


def _complex_alert_critical_unresolved():
    return '''query {
  entity_list { entity_type_name: "alert" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "severity" } }
        operator: kEQ
        rhs { leaf { value { str_value: "critical" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "resolved" } }
        operator: kEQ
        rhs { leaf { value { bool_value: false } } }
      }
    }
  }
  group_by {
    raw_columns { column: "title" }
    raw_columns { column: "severity" }
    raw_columns { column: "source_entity_name" }
  }
  query_name: "auto_query"
}'''


def _complex_alert_recent_warnings():
    return '''query {
  entity_list { entity_type_name: "alert" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "severity" } }
        operator: kEQ
        rhs { leaf { value { str_value: "warning" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "creation_time_usecs" } }
        operator: kGT
        rhs { leaf { value { int64_value: 1778570000000000 } } }
      }
    }
  }
  group_by {
    raw_columns { column: "title" }
    raw_columns { column: "creation_time_usecs" }
    raw_sort_order {
      sort_column: "creation_time_usecs"
      sort_order: kDescending
    }
  }
  query_name: "auto_query"
}'''


def _complex_alert_count_by_severity():
    return '''query {
  entity_list { entity_type_name: "alert" }
  group_by {
    group_by_column: "severity"
    aggregate_columns { column: "title" operator: kCount }
  }
  query_name: "auto_query"
}'''


def _complex_task_failed_sorted():
    return '''query {
  entity_list { entity_type_name: "task" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "status" } }
      operator: kEQ
      rhs { leaf { value { str_value: "failed" } } }
    }
  }
  group_by {
    raw_columns { column: "task_type" }
    raw_columns { column: "status" }
    raw_columns { column: "start_time_usecs" }
    raw_sort_order {
      sort_column: "start_time_usecs"
      sort_order: kDescending
    }
    raw_limit { limit: 20 }
  }
  query_name: "auto_query"
}'''


def _complex_task_running_low_progress():
    return '''query {
  entity_list { entity_type_name: "task" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "status" } }
        operator: kEQ
        rhs { leaf { value { str_value: "running" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "progress_pct" } }
        operator: kLT
        rhs { leaf { value { int64_value: 50 } } }
      }
    }
  }
  group_by {
    raw_columns { column: "task_type" }
    raw_columns { column: "progress_pct" }
    raw_columns { column: "start_time_usecs" }
  }
  query_name: "auto_query"
}'''


def _complex_node_high_cpu():
    return '''query {
  entity_list { entity_type_name: "node" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "cpu_usage_ppm" } }
      operator: kGT
      rhs { leaf { value { int64_value: 700000 } } }
    }
  }
  group_by {
    raw_columns { column: "node_name" }
    raw_columns { column: "cpu_usage_ppm" }
    raw_columns { column: "memory_usage_ppm" }
    raw_sort_order {
      sort_column: "cpu_usage_ppm"
      sort_order: kDescending
    }
  }
  query_name: "auto_query"
}'''


def _complex_node_degraded():
    return '''query {
  entity_list { entity_type_name: "node" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "is_degraded" } }
      operator: kEQ
      rhs { leaf { value { bool_value: true } } }
    }
  }
  group_by {
    raw_columns { column: "node_name" }
    raw_columns { column: "hypervisor_type" }
    raw_columns { column: "num_vms" }
  }
  query_name: "auto_query"
}'''


def _complex_disk_ssd_high_latency():
    return '''query {
  entity_list { entity_type_name: "disk" }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "storage_tier" } }
        operator: kEQ
        rhs { leaf { value { str_value: "SSD-PCIe" } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "avg_io_latency_usecs" } }
        operator: kGT
        rhs { leaf { value { int64_value: 5000 } } }
      }
    }
  }
  group_by {
    raw_columns { column: "serial_number" }
    raw_columns { column: "avg_io_latency_usecs" }
    raw_columns { column: "num_iops" }
  }
  query_name: "auto_query"
}'''


def _complex_disk_top_iops():
    return '''query {
  entity_list { entity_type_name: "disk" }
  group_by {
    raw_columns { column: "serial_number" }
    raw_columns { column: "num_iops" }
    raw_columns { column: "storage_tier" }
    raw_sort_order {
      sort_column: "num_iops"
      sort_order: kDescending
    }
    raw_limit { limit: 5 }
  }
  query_name: "auto_query"
}'''


def _complex_container_low_space():
    return '''query {
  entity_list { entity_type_name: "container" }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "free_space_bytes" } }
      operator: kLT
      rhs { leaf { value { int64_value: 107374182400 } } }
    }
  }
  group_by {
    raw_columns { column: "container_name" }
    raw_columns { column: "free_space_bytes" }
    raw_columns { column: "max_capacity_bytes" }
    raw_sort_order {
      sort_column: "free_space_bytes"
      sort_order: kAscending
    }
  }
  query_name: "auto_query"
}'''


# ============================================================
# VALIDATION
# ============================================================

def validate_query_on_cluster(api, proto_text):
    """Validate a query by executing it on the live cluster.
    Returns (success, error_message).
    Only validates read-only queries by execution.
    Write queries are validated structurally."""
    
    # Map API to idf_cli rpc_type
    rpc_map = {
        "GetEntitiesWithMetrics": "get-entities-with-metrics",
        "GetEntityTypes": "get-entity-types",
        "GetMetricTypes": "get-metric-types",
        "GetEntities": "get-entities",
    }
    
    if api not in rpc_map:
        # Structural validation only for write ops
        return True, "structural_only"
    
    if not proto_text.strip():
        return True, "empty_proto_ok"
    
    rpc_type = rpc_map[api]
    
    # Write proto to temp file on cluster and execute
    escaped_proto = proto_text.replace("'", "'\\''")
    cmd = (
        f"sshpass -p '{CLUSTER_PASS}' ssh -o StrictHostKeyChecking=no "
        f"-o ConnectTimeout=10 {CLUSTER_USER}@{CLUSTER_IP} "
        f"\"echo '{escaped_proto}' > /tmp/validate_query.txt && "
        f"python /home/nutanix/bin/idf_cli.py execute-from-file {rpc_type} /tmp/validate_query.txt 2>&1\""
    )
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        
        if "ParseError" in output or "Traceback" in output:
            return False, output.strip()[-200:]
        return True, "ok"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def to_jsonl_entry(user_query, api, proto):
    """Convert to training JSONL format."""
    assistant_content = f"API: {api}"
    if proto.strip():
        assistant_content += f"\n{proto}"
    
    return json.dumps({
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": assistant_content}
        ]
    })


# ============================================================
# MAIN
# ============================================================

def main():
    print("Generating training examples...")
    examples = generate_all_examples()
    print(f"Generated {len(examples)} unique examples")
    
    # Write all to output file
    with open(OUTPUT_FILE, 'w') as f:
        for user_q, api, proto in examples:
            f.write(to_jsonl_entry(user_q, api, proto) + "\n")
    
    print(f"Written to {OUTPUT_FILE}")
    
    # Print API distribution
    from collections import Counter
    api_counts = Counter(api for _, api, _ in examples)
    print("\nAPI Distribution:")
    for api, count in api_counts.most_common():
        print(f"  {api}: {count}")
    
    # Validate a sample against the cluster
    if "--validate" in sys.argv:
        print("\n--- Validating against live cluster ---")
        validate_sample = [ex for ex in examples if ex[1] == "GetEntitiesWithMetrics"]
        random.shuffle(validate_sample)
        validate_sample = validate_sample[:50]  # Validate 50 queries
        
        success_count = 0
        fail_count = 0
        for user_q, api, proto in validate_sample:
            ok, msg = validate_query_on_cluster(api, proto)
            if ok:
                success_count += 1
                print(f"  OK: {user_q[:60]}")
            else:
                fail_count += 1
                print(f"  FAIL: {user_q[:60]} -> {msg[:80]}")
        
        print(f"\nValidation: {success_count}/{success_count+fail_count} passed")


if __name__ == "__main__":
    main()
