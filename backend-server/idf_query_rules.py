"""
IDF Query Knowledge Base - Comprehensive rules, operators, constraints, and examples.

Built from:
- Try Me Editor (80+ examples across all IDF API categories)
- nutest-py3-tests/workflows/insights/all_queries.py (production test queries)
- nutest-py3-tests/workflows/insights/prism_queries.py (Prism UI queries)
- nutest-py3-tests/testcases/insights/ (388+ test files)
"""

# =============================================================================
# OPERATORS
# =============================================================================

WHERE_CLAUSE_OPERATORS = {
    "kEQ": 0,       # equals
    "kNE": 1,       # not equals
    "kLT": 2,       # less than
    "kLE": 3,       # less than or equal
    "kGT": 4,       # greater than
    "kGE": 5,       # greater than or equal
    "kSubstring": 6,  # substring match (deprecated, use kLike)
    "kContainsAll": 7,  # list contains ALL specified values
    "kContainedIn": 8,  # value is contained in list
    "kContainsAny": 9,  # list contains ANY of specified values
    "kExists": 10,  # attribute exists (no rhs needed)
    "kLike": 11,    # regex match (.*pattern.*, ^pattern.*, ^pat.*end$)
    "kIN": 12,      # value is IN a list
    "kContains": 13,  # list contains value (alias for kContainsAll)
    "kAny": 14,     # any value matches (alias for kContainsAny)
    "kNot": 15,     # logical NOT (only lhs, no rhs)
}

LOGICAL_OPERATORS = {
    "kAnd": 0,
    "kOr": 1,
    "kNot": 2,  # unary - only lhs
}

SORT_ORDERS = {
    "kAscending": 0,
    "kDescending": 1,
}

AGGREGATE_OPERATORS = {
    "kSum": 0,
    "kAvg": 1,
    "kCount": 2,
    "kMin": 3,
    "kMax": 4,
}

GROUP_BY_COLUMN_TYPES = {
    "kDiscrete": 0,
    "kContinuous": 1,
}

# =============================================================================
# VALUE TYPES
# =============================================================================

VALUE_TYPES = {
    "str_value": "For string comparisons (kEQ, kNE, kLike)",
    "int64_value": "For integer comparisons (kEQ, kNE, kLT, kLE, kGT, kGE)",
    "uint64_value": "For unsigned int / timestamps",
    "bool_value": "For boolean comparisons (true/false)",
    "float_value": "For float comparisons",
    "double_value": "For double-precision comparisons",
    "bytes_value": "For bytes comparisons",
    "str_list": "For list operators (kContains, kAny, kIN with strings)",
    "int64_list": "For list operators (kContains, kAny, kIN with integers)",
    "bool_list": "For list operators with booleans",
}

# =============================================================================
# API METHODS
# =============================================================================

API_METHODS = {
    "GetEntitiesWithMetrics": {
        "arg_type": "GetEntitiesWithMetricsArg",
        "method": "insights_interface.GetEntitiesWithMetrics",
        "description": "Main query API for fetching entities with filtering, grouping, sorting, and aggregation",
        "proto_wrapper": "query { ... }",
    },
    "GetEntities": {
        "arg_type": "GetEntitiesArg",
        "method": "insights_interface.GetEntities",
        "description": "Fetch specific entities by type and/or ID",
        "proto_wrapper": None,  # direct entity_guid_list at top level
    },
    "BatchGetEntitiesWithMetrics": {
        "arg_type": "BatchGetEntitiesWithMetricsArg",
        "method": "insights_interface.BatchGetEntitiesWithMetrics",
        "description": "Execute multiple queries in a single batch call",
        "proto_wrapper": "query_list { query { ... } }",
    },
    "UpdateEntity": {
        "arg_type": "UpdateEntityArg",
        "method": "insights_interface.UpdateEntity",
        "description": "Update entity attributes (with or without CAS)",
        "proto_wrapper": None,
    },
    "DeleteEntity": {
        "arg_type": "DeleteEntityArg",
        "method": "insights_interface.DeleteEntity",
        "description": "Delete an entity (with or without CAS)",
        "proto_wrapper": None,
    },
    "BatchUpdateEntities": {
        "arg_type": "BatchUpdateEntitiesArg",
        "method": "insights_interface.BatchUpdateEntities",
        "description": "Batch update multiple entities",
        "proto_wrapper": None,
    },
    "BatchDeleteEntities": {
        "arg_type": "BatchDeleteEntitiesArg",
        "method": "insights_interface.BatchDeleteEntities",
        "description": "Batch delete multiple entities",
        "proto_wrapper": None,
    },
    "AttachEntity": {
        "arg_type": "AttachEntityArg",
        "method": "insights_interface.AttachEntity",
        "description": "Attach an entity (for distributed entity management)",
        "proto_wrapper": None,
    },
    "DetachEntity": {
        "arg_type": "DetachEntityArg",
        "method": "insights_interface.DetachEntity",
        "description": "Detach an entity",
        "proto_wrapper": None,
    },
    "RegisterEntityTypes": {
        "arg_type": "RegisterEntityTypesArg",
        "method": "insights_interface.RegisterEntityTypes",
        "description": "Register new entity types with configuration",
        "proto_wrapper": None,
    },
    "RegisterMetricTypes": {
        "arg_type": "RegisterMetricTypesArg",
        "method": "insights_interface.RegisterMetricTypes",
        "description": "Register attributes and metrics for entity types",
        "proto_wrapper": None,
    },
    "GetMetricData": {
        "arg_type": "GetMetricDataArg",
        "method": "insights_interface.GetMetricData",
        "description": "Get time-series metric data",
        "proto_wrapper": None,
    },
    "GetEntityTypes": {
        "arg_type": "GetEntityTypesArg",
        "method": "insights_interface.GetEntityTypes",
        "description": "Get registered entity type information",
        "proto_wrapper": None,
    },
    "GetMasterLocation": {
        "arg_type": "GetMasterLocationArg",
        "method": "insights_interface.GetMasterLocation",
        "description": "Get IDF master node location",
        "proto_wrapper": None,
    },
    "PutMetricData": {
        "arg_type": "PutMetricDataArg",
        "method": "insights_interface.PutMetricData",
        "description": "Insert time-series metric data",
        "proto_wrapper": None,
    },
}

# =============================================================================
# ENTITY RULES
# =============================================================================

ENTITY_RULES = {
    "evictable_entities": ["alert", "event", "task", "audit_entry"],
    "unevictable_entities": ["vm", "cluster", "host", "disk", "container",
                             "node", "storage_pool", "volume_group", "subnet",
                             "image", "category", "protection_domain"],
    "evictable_constraints": [
        "MUST have raw_limit (cannot fetch ALL entities without limit)",
        "Returns kGetAllEvictableEntitiesUnsupported if no limit specified",
        "All group-by columns must be either ALL indexed or ALL non-indexed",
        "Cannot filter on non-indexed columns (kQueryGroupByInvalidComparisionExpr)",
        "Cannot do GROUP_BY without raw_limit on evictable entities",
    ],
    "special_attributes": [
        "_entity_id_",        # built-in entity ID attribute
        "_created_timestamp_usecs_",  # built-in creation timestamp (uint64)
        "_arithmos_id_",      # Arithmos internal ID
    ],
}

# =============================================================================
# QUERY CONSTRUCTION RULES (for LLM system prompt)
# =============================================================================

QUERY_RULES = [
    "Always wrap GetEntitiesWithMetrics queries in 'query { ... }'",
    "Always include query_name field for traceability",
    "Evictable entities (alert, event, task) MUST have raw_limit inside group_by",
    "raw_columns MUST be inside group_by { } block, not at query top level",
    "For sorting, the sorted column should also appear as a raw_columns entry",
    "kExists operator has NO rhs (only lhs with column name)",
    "kNot operator uses only lhs and operator: kNot (no rhs) - wraps another condition",
    "kLike uses regex patterns: '.*pattern.*' for substring, '^pattern.*' for starts-with, '^pat.*end$' for both",
    "kLike with multiple patterns: '.*pat1.*|.*pat2.*|.*pat3.*'",
    "kContains and kAny require list values (str_list or int64_list with value_list field)",
    "kIN requires list values (int64_list or str_list with value_list field)",
    "Namespace queries add column_namespace field to leaf, raw_columns, group_by_column_namespace, sort_column_namespace",
    "Lookup queries join entities via where_clause matching inner column to outer column reference",
    "For entity-specific queries, add entity_id inside entity_list",
    "entity_list can contain multiple entity types for cross-type queries",
    "Nested/complex where clauses use lhs/rhs with comparison_expr and logical operator (kAnd/kOr)",
    "Simple where clauses use comparison_expr directly (no lhs/rhs wrapper)",
    "flags: 2 returns only entity count (no entity data)",
    "cursor_query_info enables paginated iteration with batch_size",
    "time range queries use start_time_usecs and end_time_usecs at query level",
    "sub_group_by enables multi-dimensional grouping (nested group_by)",
    "having_clause filters groups after grouping (like SQL HAVING)",
    "ancestor_entity_type in aggregate_columns enables ancestor join queries",
    "bucket_interval_separators define custom bucket boundaries for continuous grouping",
    "down_sampling_interval_secs controls time-series downsampling",
    "Value types must match attribute types: str_value for strings, int64_value for integers, bool_value for booleans",
    "List values use nested structure: str_list { value_list: 'v1' value_list: 'v2' }",
    "include_deleted_entities: true in GetEntitiesArg returns soft-deleted entities",
]

# =============================================================================
# OPERATOR SYNTAX RULES
# =============================================================================

OPERATOR_SYNTAX = {
    "kEQ": {
        "description": "Equals comparison",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kEQ\nrhs { leaf { value { int64_value: 4 } } }',
    },
    "kNE": {
        "description": "Not equals comparison",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kNE\nrhs { leaf { value { str_value: "node_1" } } }',
    },
    "kLT": {
        "description": "Less than comparison",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kLT\nrhs { leaf { value { int64_value: 60 } } }',
    },
    "kLE": {
        "description": "Less than or equal comparison",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kLE\nrhs { leaf { value { int64_value: 100 } } }',
    },
    "kGT": {
        "description": "Greater than comparison",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kGT\nrhs { leaf { value { int64_value: 80 } } }',
    },
    "kGE": {
        "description": "Greater than or equal comparison",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kGE\nrhs { leaf { value { int64_value: 60 } } }',
    },
    "kExists": {
        "description": "Attribute exists check (no rhs needed)",
        "requires_rhs": False,
        "rhs_type": None,
        "example": 'operator: kExists',
    },
    "kLike": {
        "description": "Regex pattern match",
        "requires_rhs": True,
        "rhs_type": "single_value",
        "example": 'operator: kLike\nrhs { leaf { value { str_value: ".*pattern.*" } } }',
    },
    "kIN": {
        "description": "Value is in a list",
        "requires_rhs": True,
        "rhs_type": "list_value",
        "example": 'operator: kIN\nrhs { leaf { value { int64_list { value_list: 0 value_list: 1 } } } }',
    },
    "kContains": {
        "description": "List attribute contains all specified values",
        "requires_rhs": True,
        "rhs_type": "list_value",
        "example": 'operator: kContains\nrhs { leaf { value { str_list { value_list: "Performance" } } } }',
    },
    "kAny": {
        "description": "List attribute contains any of specified values",
        "requires_rhs": True,
        "rhs_type": "list_value",
        "example": 'operator: kAny\nrhs { leaf { value { str_list { value_list: "Availability" value_list: "Performance" } } } }',
    },
    "kNot": {
        "description": "Logical NOT (wraps a condition in lhs, no rhs)",
        "requires_rhs": False,
        "rhs_type": None,
        "example": 'lhs { comparison_expr { lhs { leaf { column: "disks" } } operator: kExists } }\noperator: kNot',
    },
}

# =============================================================================
# QUERY EXAMPLES - categorized proto-only examples
# =============================================================================

QUERY_EXAMPLES = {
    # --- Basic Fetch ---
    "fetch_all_entities": {
        "description": "Fetch all entities of a type (simplest query)",
        "natural_language": "Get all VMs",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  query_name: "fetch_all_vms"
}''',
    },
    "fetch_specific_entity": {
        "description": "Fetch a specific entity by ID",
        "natural_language": "Get VM with ID abc-123",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
    entity_id: "abc-123"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_vcpus"
    }
  }
  query_name: "entity_specific_query"
}''',
    },
    "entity_count": {
        "description": "Count entities of a type (flags: 2)",
        "natural_language": "Count all disks",
        "proto": '''query {
  entity_list {
    entity_type_name: "disk"
  }
  flags: 2
  query_name: "entity_count_query"
}''',
    },

    # --- Raw Columns (Projection) ---
    "fetch_raw_columns": {
        "description": "Fetch specific attributes of entities",
        "natural_language": "Get VM names and vCPU count",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_vcpus"
    }
  }
  query_name: "fetching_raw_columns"
}''',
    },

    # --- Where Clause: Simple ---
    "where_equal": {
        "description": "Filter with equality operator",
        "natural_language": "VMs with 4 vCPUs",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "num_vcpus"
        }
      }
      operator: kEQ
      rhs {
        leaf {
          value {
            int64_value: 4
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_vcpus"
    }
  }
  query_name: "where_clause"
}''',
    },
    "where_not_equal": {
        "description": "Filter with not-equals operator",
        "natural_language": "VMs not on node_1",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "node"
        }
      }
      operator: kNE
      rhs {
        leaf {
          value {
            str_value: "node_1"
          }
        }
      }
    }
  }
  query_name: "where_clause_not_equal"
}''',
    },
    "where_greater_than": {
        "description": "Filter with greater-than operator",
        "natural_language": "VMs with CPU usage above 80",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "cpu_usage"
        }
      }
      operator: kGT
      rhs {
        leaf {
          value {
            int64_value: 80
          }
        }
      }
    }
  }
  query_name: "where_clause_greater_than"
}''',
    },
    "where_greater_equal": {
        "description": "Filter with >= operator",
        "natural_language": "VMs with CPU usage >= 60",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "cpu_usage"
        }
      }
      operator: kGE
      rhs {
        leaf {
          value {
            int64_value: 60
          }
        }
      }
    }
  }
  query_name: "where_clause_greater_than_equal"
}''',
    },
    "where_less_than": {
        "description": "Filter with < operator",
        "natural_language": "VMs with CPU usage below 60",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "cpu_usage"
        }
      }
      operator: kLT
      rhs {
        leaf {
          value {
            int64_value: 60
          }
        }
      }
    }
  }
  query_name: "where_clause_less_than"
}''',
    },
    "where_exists": {
        "description": "Filter entities where an attribute exists",
        "natural_language": "VMs that have disks attribute",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "disks"
        }
      }
      operator: kExists
    }
  }
  query_name: "where_clause_kExists"
}''',
    },
    "where_contains": {
        "description": "Filter where list attribute contains a value",
        "natural_language": "VMs with impact type containing Performance",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "impact_type"
        }
      }
      operator: kContains
      rhs {
        leaf {
          value {
            str_list {
              value_list: "Performance"
            }
          }
        }
      }
    }
  }
  query_name: "where_clause_kContains"
}''',
    },
    "where_any": {
        "description": "Filter where list attribute contains any of multiple values",
        "natural_language": "VMs with any impact type from list",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "impact_type"
        }
      }
      operator: kAny
      rhs {
        leaf {
          value {
            str_list {
              value_list: "Availability"
              value_list: "Capacity"
              value_list: "Configuration"
              value_list: "Performance"
              value_list: "SystemIndicator"
            }
          }
        }
      }
    }
  }
  query_name: "where_clause_kAny"
}''',
    },
    "where_in": {
        "description": "Filter where value is IN a list",
        "natural_language": "VMs where m1 is 0 or 1",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "m1"
        }
      }
      operator: kIN
      rhs {
        leaf {
          value {
            int64_list {
              value_list: 0
              value_list: 1
            }
          }
        }
      }
    }
  }
  query_name: "where_clause_kIN"
}''',
    },
    "where_like_substring": {
        "description": "Regex match for substring (kLike with .*pattern.*)",
        "natural_language": "VMs with vdisk capacity containing 1000",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "vdisk_capacity_list"
        }
      }
      operator: kLike
      rhs {
        leaf {
          value {
            str_value: ".*1000.*"
          }
        }
      }
    }
  }
  query_name: "where_clause_kLike_match_by_substr"
}''',
    },
    "where_like_startswith": {
        "description": "Regex match for starts-with (kLike with ^pattern.*)",
        "natural_language": "VMs with vdisk capacity starting with 1000",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "vdisk_capacity_list"
        }
      }
      operator: kLike
      rhs {
        leaf {
          value {
            str_value: "^1000.*"
          }
        }
      }
    }
  }
  query_name: "where_clause_kLike_match_by_start_of_str"
}''',
    },
    "where_like_multiple": {
        "description": "Regex match for multiple patterns (OR)",
        "natural_language": "VMs with vdisk capacity matching 1000 or 900 or 800",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "vdisk_capacity_list"
        }
      }
      operator: kLike
      rhs {
        leaf {
          value {
            str_value: ".*1000.*|.*900.*|.*800.*"
          }
        }
      }
    }
  }
  query_name: "where_clause_kLike_match_multiple_substrs"
}''',
    },
    "where_not": {
        "description": "Logical NOT (negate a condition)",
        "natural_language": "VMs that do NOT have disks",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs {
          leaf {
            column: "disks"
          }
        }
        operator: kExists
      }
    }
    operator: kNot
  }
  query_name: "where_clause_kNot"
}''',
    },

    # --- Complex/Nested Where Clause ---
    "where_nested_and": {
        "description": "Nested where clause with AND operator",
        "natural_language": "VMs where node != node_1 AND vm_name exists",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs {
          leaf {
            column: "node"
          }
        }
        operator: kNE
        rhs {
          leaf {
            value {
              str_value: "node_1"
            }
          }
        }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs {
          leaf {
            column: "vm_name"
          }
        }
        operator: kExists
      }
    }
  }
  query_name: "nested_where_clause"
}''',
    },

    # --- Group By ---
    "group_by_basic": {
        "description": "Group entities by an attribute",
        "natural_language": "Group VMs by cluster",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "cluster"
    raw_columns {
      column: "_created_timestamp_usecs_"
    }
    raw_sort_order {
      sort_column: "_created_timestamp_usecs_"
      sort_order: kDescending
    }
    raw_limit {
      limit: 10
      offset: 0
    }
  }
  query_name: "prism:alert_group"
}''',
    },
    "group_by_with_aggregation": {
        "description": "Group by with aggregate function",
        "natural_language": "Average memory usage per VM name",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "vm_name"
    raw_columns {
      column: "_created_timestamp_usecs_"
    }
    aggregate_columns {
      column: "memory_usage_bytes"
      operator: kAvg
    }
    raw_sort_order {
      sort_column: "_created_timestamp_usecs_"
      sort_order: kDescending
    }
    raw_limit {
      limit: 10
      offset: 0
    }
  }
  query_name: "aggregation"
}''',
    },
    "multi_dimensional_grouping": {
        "description": "Multi-level grouping with sub_group_by",
        "natural_language": "Group VMs by memory size, then by IP address",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "memory_size_bytes"
    sub_group_by {
      group_by_column: "ip_addresses"
      raw_columns {
        column: "memory_size_bytes"
      }
      raw_columns {
        column: "ip_addresses"
      }
    }
  }
  query_name: "multi_dimensional_grouping"
}''',
    },
    "continuous_grouping": {
        "description": "Continuous grouping with buckets",
        "natural_language": "Group VMs by memory usage in 3 buckets",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "memory_usage_bytes"
    group_by_column_type: kContinuous
    group_sort_order {
      sort_column: "memory_usage_bytes"
    }
    raw_limit {
      limit: 10
      offset: 0
    }
    num_buckets: 3
    bucket_boundary: 70
  }
  query_name: "continous_grouping"
}''',
    },
    "bucket_interval_separators": {
        "description": "Custom bucket boundaries for continuous grouping",
        "natural_language": "Group VMs by CPU usage with custom interval separators",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "hypervisor_cpu_usage_ppm"
    group_by_column_type: kContinuous
    raw_columns {
      column: "_entity_id_"
    }
    raw_sort_order {
      sort_column: "_entity_id_"
    }
    bucket_interval_separators {
      int64_value: 1
    }
    bucket_interval_separators {
      int64_value: 2
    }
    bucket_interval_separators {
      int64_value: 3
    }
    bucket_interval_separators {
      int64_value: 4
    }
  }
  query_name: "continous_grouping_with_bucket_intervals"
}''',
    },
    "having_clause": {
        "description": "Filter groups with having clause (like SQL HAVING)",
        "natural_language": "Group VMs by cluster, keep only clusters containing UUID-0",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "cluster"
    having_clause {
      comparison_expr {
        lhs {
          leaf {
            column: "cluster"
          }
        }
        operator: kContains
        rhs {
          leaf {
            value {
              str_list {
                value_list: "UUID-0"
              }
            }
          }
        }
      }
    }
  }
  query_name: "having_clause_group_by_query"
}''',
    },

    # --- Sorting ---
    "raw_sort": {
        "description": "Sort entities by a column",
        "natural_language": "Get VMs sorted by name ascending",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_vcpus"
    }
    raw_sort_order {
      sort_column: "vm_name"
      sort_order: kAscending
    }
  }
  query_name: "fetching_raw_columns_and_sorting"
}''',
    },
    "group_sort": {
        "description": "Sort groups by aggregate value",
        "natural_language": "Group VMs by CPU usage, sort groups ascending",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "hypervisor_cpu_usage_ppm"
    group_by_column_type: kContinuous
    aggregate_columns {
      column: "memory_usage_bytes"
      operator: kCount
    }
    group_sort_order {
      sort_column: "hypervisor_cpu_usage_ppm"
      sort_order: kAscending
    }
    bucket_interval_separators {
      int64_value: 1
    }
    bucket_interval_separators {
      int64_value: 2
    }
    bucket_interval_separators {
      int64_value: 3
    }
  }
  query_name: "group_sort"
}''',
    },

    # --- Pagination ---
    "raw_limit": {
        "description": "Limit and offset for pagination",
        "natural_language": "Get 2 VMs starting from offset 4",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_limit {
      limit: 2
      offset: 4
    }
  }
  query_name: "limit_and_offset"
}''',
    },
    "group_limit": {
        "description": "Limit groups and raw results independently",
        "natural_language": "Group VMs by CPU, limit 10 groups, 2 per group at offset 10",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "hypervisor_cpu_usage_ppm"
    group_by_column_type: kContinuous
    group_sort_order {
      sort_column: "hypervisor_cpu_usage_ppm"
    }
    raw_sort_order {
      sort_column: "num_vcpus"
    }
    raw_columns {
      column: "num_vcpus"
    }
    group_limit {
      limit: 10
      offset: 0
    }
    raw_limit {
      limit: 2
      offset: 10
    }
    num_buckets: 4
    bucket_boundary: 150
  }
  query_name: "group_and_raw_limit_and_offset"
}''',
    },

    # --- Cursor Queries ---
    "cursor_primary": {
        "description": "Initial cursor query for paginated iteration",
        "natural_language": "Get tasks in batches of 2 (initial cursor)",
        "proto": '''query {
  entity_list {
    entity_type_name: "task"
  }
  group_by {
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 2
  }
  query_name: "primary_cursor_query"
}''',
    },
    "cursor_secondary": {
        "description": "Continue cursor query with next_cursor",
        "natural_language": "Get next batch using cursor ID",
        "proto": '''query {
  entity_list {
    entity_type_name: "task"
  }
  group_by {
  }
  cursor_query_info {
    next_cursor {
      cursor_query_id: "142471:10.46.51.249:2027:1"
      cursor_query_chunk_number: 0
      chunks_remaining: true
    }
  }
  query_name: "secondary_cursor_query"
}''',
    },

    # --- Time Range ---
    "time_range": {
        "description": "Query with time range filter",
        "natural_language": "Get VM read bytes in specific time window",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "controller.read_source_oplog_bytes"
    }
  }
  start_time_usecs: 1571702400000000
  end_time_usecs: 1571702400020000
  query_name: "time_range_queries"
}''',
    },

    # --- Downsampling ---
    "downsampling": {
        "description": "Time-series downsampling at intervals",
        "natural_language": "Get VM IO count with 5-minute downsampling",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "num_io"
    }
    down_sampling_interval_secs: 300
  }
  query_name: "downsampling_interval"
}''',
    },

    # --- Lookup Query (Join) ---
    "lookup_query": {
        "description": "Join between entity types using lookup_query",
        "natural_language": "Get top 100 VMs by CPU with their unresolved alerts and cluster names",
        "proto": '''query {
  entity_list { entity_type_name: "vm" }
  group_by {
    raw_sort_order {
      sort_column: "cpu_usage"
      sort_order: kDescending
    }
    raw_limit { limit: 100 }
    raw_columns { column: "_entity_id_" }
    raw_columns { column: "cluster" }
    raw_columns { column: "name" }
    raw_columns { column: "cpu_usage" }
    lookup_query {
      entity_list { entity_type_name: "alert" }
      group_by {
        raw_limit { limit: 5 }
        raw_columns { column: "title" }
        raw_columns { column: "default_message" }
      }
      where_clause {
        lhs { comparison_expr {
          lhs { leaf { column: "vm" } }
          operator: kEQ
          rhs { leaf { column: "_entity_id_" } }
        } }
        operator: kAnd
        rhs { comparison_expr {
          lhs { leaf { column: "resolved" } }
          operator: kEQ
          rhs { leaf { value { bool_value: false } } }
        } }
      }
    }
    lookup_query {
      entity_list { entity_type_name: "cluster" }
      group_by {
        raw_columns { column: "name" }
      }
      where_clause {
        comparison_expr {
          lhs { leaf { column: "_entity_id_" } }
          operator: kEQ
          rhs { leaf { column: "cluster" } }
        }
      }
    }
  }
  query_name: "vm_with_alerts_and_cluster"
}''',
    },

    # --- Ancestor Join ---
    "ancestor_join": {
        "description": "Query with ancestor entity type join",
        "natural_language": "Get VMs grouped by cluster with ancestor node data",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "cluster"
    aggregate_columns {
      column: "node"
      ancestor_entity_type: "cluster"
    }
    suppress_ancestor_tree_traversal: false
  }
  query_name: "ancestor_join_query"
}''',
    },

    # --- Shard IDs ---
    "shard_ids": {
        "description": "Query specific shards",
        "natural_language": "Get VMs from specific shard IDs",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_vcpus"
    }
  }
  shard_id_list: "10"
  shard_id_list: "89"
  shard_id_list: "107"
  query_name: "shard_ids"
}''',
    },

    # --- Batch Query ---
    "batch_query": {
        "description": "Multiple queries in a single batch call",
        "natural_language": "Batch: get cluster IDs + VMs with 8 vCPUs + disk count",
        "proto": '''query_list {
  query {
    entity_list {
      entity_type_name: "cluster"
    }
    group_by {
      raw_columns {
        column: "_entity_id_"
      }
    }
    query_name: "fetching_cluster_entity_id"
  }
}
query_list {
  query {
    entity_list {
      entity_type_name: "vm"
    }
    where_clause {
      comparison_expr {
        lhs {
          leaf {
            column: "num_vcpus"
          }
        }
        operator: kEQ
        rhs {
          leaf {
            value {
              int64_value: 8
            }
          }
        }
      }
    }
    group_by {
      raw_columns {
        column: "vm_name"
      }
      raw_columns {
        column: "num_vcpus"
      }
    }
    query_name: "where_clause"
  }
}
query_list {
  query {
    entity_list {
      entity_type_name: "disk"
    }
    flags: 2
    query_name: "entity_count_query"
  }
}''',
    },

    # --- Namespace Queries ---
    "namespace_where": {
        "description": "Where clause with namespace-scoped attribute",
        "natural_language": "Filter entities by namespaced attribute",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm_test"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "namespace_attr_1"
          column_namespace: "np1"
        }
      }
      operator: kEQ
      rhs {
        leaf {
          value {
            str_value: "attr_value_1"
          }
        }
      }
    }
  }
  query_name: "where_clause"
}''',
    },
    "namespace_group_by": {
        "description": "Group by with namespace-scoped column",
        "natural_language": "Group entities by namespaced attribute",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm_test"
  }
  group_by {
    group_by_column: "namespace_attr_1"
    group_by_column_namespace: "np1"
  }
  query_name: "group_by"
}''',
    },
    "namespace_raw_columns": {
        "description": "Fetch raw columns with namespace",
        "natural_language": "Get namespaced attribute values",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm_test"
  }
  group_by {
    raw_columns {
      column: "namespace_attr_1"
      column_namespace: "np1"
    }
  }
  query_name: "fetching_raw_columns"
}''',
    },
    "namespace_aggregation": {
        "description": "Aggregation with namespaced columns",
        "natural_language": "Average of namespaced attribute grouped by another",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm_test"
  }
  group_by {
    group_by_column: "namespace_attr_1"
    group_by_column_namespace: "np1"
    aggregate_columns {
      column: "namespace_attr_2"
      column_namespace: "np2"
      operator: kAvg
    }
  }
  query_name: "aggregation"
}''',
    },
    "namespace_group_sort": {
        "description": "Group sort with namespace",
        "natural_language": "Sort groups by namespaced attribute",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm_test"
  }
  group_by {
    group_by_column: "namespace_attr_2"
    group_by_column_namespace: "np2"
    group_by_column_type: kDiscrete
    group_sort_order {
      sort_column: "namespace_attr_2"
      sort_column_namespace: "np2"
      sort_order: kAscending
    }
  }
  query_name: "group_sort"
}''',
    },
    "namespace_lookup": {
        "description": "Lookup query with namespaced columns",
        "natural_language": "Join parent and lookup entity types with namespace matching",
        "proto": '''query {
  entity_list { entity_type_name: "parent_etype" }
  group_by {
    raw_columns {
      column: "attr1_parent"
      column_namespace: "ns1"
    }
    raw_columns {
      column: "attr2_parent"
    }
    lookup_query {
      entity_list { entity_type_name: "lookup_etype" }
      group_by {
        raw_columns {
          column: "attr1_lookup"
          column_namespace: "ns2"
        }
        raw_columns {
          column: "atrr2_lookup"
        }
      }
      where_clause {
        comparison_expr {
          lhs {
            leaf {
              column: "attr1_lookup"
              column_namespace: "ns2"
            }
          }
          operator: kEQ
          rhs {
            leaf {
              column: "attr1_parent"
              column_namespace: "ns1"
            }
          }
        }
      }
    }
  }
  query_name: "namespace_lookup"
}''',
    },

    # --- Prism UI Queries (real production patterns) ---
    "prism_vm_list": {
        "description": "Prism VM list page query with sorting and pagination",
        "natural_language": "Get VM list page sorted by name with limit 120",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: " "
    group_limit {
      limit: 7
      offset: 0
    }
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "hypervisor_memory_usage_ppm"
    }
    raw_columns {
      column: "num_vcpus"
    }
    raw_columns {
      column: "power_state"
    }
    raw_columns {
      column: "cluster_name"
    }
    raw_columns {
      column: "cluster"
    }
    raw_sort_order {
      sort_column: "vm_name"
      sort_order: kAscending
    }
    raw_limit {
      limit: 120
      offset: 0
    }
  }
  query_name: "Focus_performance_vm_query"
}''',
    },
    "prism_vm_count": {
        "description": "Quick VM count for dashboard",
        "natural_language": "Count VMs (single result)",
        "proto": '''query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_limit {
      limit: 1
    }
  }
  query_name: "Login_vm_count_query"
}''',
    },

    # --- Evictable Entity Queries ---
    "evictable_with_limit": {
        "description": "Query evictable entity (MUST have raw_limit)",
        "natural_language": "Get latest 100 tasks",
        "proto": '''query {
  entity_list {
    entity_type_name: "task"
  }
  group_by {
    raw_columns {
      column: "task_name"
    }
    raw_columns {
      column: "status"
    }
    raw_columns {
      column: "component"
    }
    raw_sort_order {
      sort_column: "_created_timestamp_usecs_"
      sort_order: kDescending
    }
    raw_limit {
      limit: 100
      offset: 0
    }
  }
  query_name: "evictable_tasks_query"
}''',
    },

    # --- GetEntities API ---
    "get_entities_by_id": {
        "description": "Get specific entities by type and ID (GetEntitiesArg)",
        "natural_language": "Fetch VM entities 1 and 2 by ID",
        "api_method": "GetEntities",
        "proto": '''entity_guid_list {
  entity_type_name: "vm"
  entity_id: "1"
}
entity_guid_list {
  entity_type_name: "vm"
  entity_id: "2"
}''',
    },
    "get_entities_by_type": {
        "description": "Get all entities of a type (GetEntitiesArg)",
        "natural_language": "Fetch all VM entities",
        "api_method": "GetEntities",
        "proto": '''entity_guid_list {
  entity_type_name: "vm"
}''',
    },
    "get_entities_multiple_types": {
        "description": "Get entities of multiple types",
        "natural_language": "Fetch VMs, clusters, and node 1",
        "api_method": "GetEntities",
        "proto": '''entity_guid_list {
  entity_type_name: "vm"
}
entity_guid_list {
  entity_type_name: "cluster"
}
entity_guid_list {
  entity_type_name: "node"
  entity_id: "1"
}''',
    },
    "get_entities_deleted": {
        "description": "Include deleted entities in results",
        "natural_language": "Fetch all VMs including deleted ones",
        "api_method": "GetEntities",
        "proto": '''entity_guid_list {
  entity_type_name: "vm"
}
include_deleted_entities: true''',
    },

    # --- Data Modification ---
    "update_entity_cas": {
        "description": "Update entity with CAS (optimistic concurrency)",
        "natural_language": "Update VM attributes with CAS value 0",
        "api_method": "UpdateEntity",
        "proto": '''entity_guid {
  entity_type_name: "vm"
  entity_id: "entity_id"
}
cas_value: 0
attribute_data_arg_list {
  attribute_data {
    name: "vm_name"
    value {
      str_value: "my_vm_name"
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "node"
    value {
      str_value: "node_1"
    }
  }
}''',
    },
    "update_entity_no_cas": {
        "description": "Update entity without CAS (no concurrency check)",
        "natural_language": "Update VM attributes without CAS",
        "api_method": "UpdateEntity",
        "proto": '''entity_guid {
  entity_type_name: "vm"
  entity_id: "entity_id"
}
expiration_timestamp_usecs: 86400
full_update: false
attribute_data_arg_list {
  attribute_data {
    name: "vm_name"
    value {
      str_value: "my_vm_name"
    }
  }
}''',
    },
    "delete_entity_cas": {
        "description": "Delete entity with CAS verification",
        "natural_language": "Delete VM 1234 with CAS value 3",
        "api_method": "DeleteEntity",
        "proto": '''entity_guid {
  entity_type_name: "vm"
  entity_id: "1234"
}
cas_value: 3''',
    },
    "delete_entity_no_cas": {
        "description": "Delete entity without CAS",
        "natural_language": "Delete VM 1234",
        "api_method": "DeleteEntity",
        "proto": '''entity_guid {
  entity_type_name: "vm"
  entity_id: "1234"
}''',
    },

    # --- Register APIs ---
    "register_metric_types": {
        "description": "Register attributes and metrics for an entity type",
        "natural_language": "Register 3 attributes and 1 metric for VM",
        "api_method": "RegisterMetricTypes",
        "proto": '''metric_type_list {
  is_attribute: true
  metric_name: "attr1"
  entity_type_name: "vm"
}
metric_type_list {
  is_attribute: true
  metric_name: "attr2"
  entity_type_name: "vm"
}
metric_type_list {
  is_attribute: false
  metric_name: "cpu_metric"
  entity_type_name: "vm"
  ttl_calculation: kCurrentTimeBased
  down_sampling_operator: kAvg
  down_sampling_interval_in_secs: 86400
  raw_retention_in_weeks: 13
  hourly_retention_in_weeks: 14
}''',
    },

    # --- GetMetricData ---
    "get_metric_data": {
        "description": "Get time-series metric data for entities",
        "natural_language": "Get metric 'a' for disk 94612 in time range",
        "api_method": "GetMetricData",
        "proto": '''entity_type_name: "DISK"
entity_id_list: "94612"
metric_name_list: "a"
start_time_usecs: 1442908800000000
end_time_usecs: 1442912400000000
ds_interval {
  type: kHourly
}''',
    },

    # --- GetEntityTypes ---
    "get_entity_types": {
        "description": "Get entity type schema information",
        "natural_language": "Get schema for VM entity type",
        "api_method": "GetEntityTypes",
        "proto": '''entity_type_name: "vm"''',
    },
}

# =============================================================================
# FEATURE PATTERN REFERENCE (for system prompt context)
# =============================================================================

FEATURE_PATTERNS = {
    "cursor_query": {
        "description": "Paginated iteration through large result sets",
        "fields": ["cursor_query_info", "is_initial_cursor_query", "batch_size", "next_cursor"],
        "note": "First query sets is_initial_cursor_query: true. Subsequent queries use next_cursor from response.",
    },
    "lookup_query": {
        "description": "Join between entity types (like SQL JOIN)",
        "fields": ["lookup_query", "entity_list", "group_by", "where_clause"],
        "note": "Inner where_clause matches inner column to outer column: rhs { leaf { column: 'outer_col' } }",
    },
    "sub_group_by": {
        "description": "Multi-dimensional grouping (nested GROUP BY)",
        "fields": ["sub_group_by", "group_by_column"],
        "note": "Nests inside group_by. raw_columns/raw_limit go in the deepest sub_group_by.",
    },
    "having_clause": {
        "description": "Filter groups after aggregation (like SQL HAVING)",
        "fields": ["having_clause", "comparison_expr"],
        "note": "Goes inside group_by block. Same syntax as where_clause comparison_expr.",
    },
    "time_range": {
        "description": "Query entities within a time window",
        "fields": ["start_time_usecs", "end_time_usecs"],
        "note": "Timestamps in microseconds (usecs). Goes at query level, not inside group_by.",
    },
    "namespaces": {
        "description": "Multi-tenant attribute isolation",
        "fields": ["column_namespace", "group_by_column_namespace", "sort_column_namespace"],
        "note": "Added to leaf, raw_columns, group_by, and sort_order fields for namespace-scoped attributes.",
    },
    "continuous_grouping": {
        "description": "Bucket-based grouping for numeric attributes",
        "fields": ["group_by_column_type: kContinuous", "num_buckets", "bucket_boundary", "bucket_interval_separators"],
        "note": "Use num_buckets + bucket_boundary for uniform buckets, or bucket_interval_separators for custom boundaries.",
    },
    "ancestor_join": {
        "description": "Join with parent entity type in hierarchy",
        "fields": ["ancestor_entity_type", "suppress_ancestor_tree_traversal"],
        "note": "In aggregate_columns, set ancestor_entity_type to pull data from parent entity.",
    },
    "flags": {
        "description": "Query behavior flags",
        "values": {"2": "Return only entity count (no entity data)"},
    },
    "downsampling": {
        "description": "Time-series data aggregation at intervals",
        "fields": ["down_sampling_interval_secs"],
        "note": "Inside group_by. Value in seconds (e.g., 300 = 5 minutes).",
    },
}


def get_examples_for_category(category: str) -> list:
    """Get all examples matching a category prefix."""
    return [
        (key, val) for key, val in QUERY_EXAMPLES.items()
        if key.startswith(category)
    ]


def get_rules_text() -> str:
    """Get formatted rules text for the LLM system prompt."""
    return "\n".join(f"- {rule}" for rule in QUERY_RULES)


def get_operator_reference() -> str:
    """Get operator quick-reference for the LLM."""
    lines = ["IDF Where Clause Operators:"]
    for op, info in OPERATOR_SYNTAX.items():
        rhs = "NO rhs" if not info["requires_rhs"] else info["rhs_type"]
        lines.append(f"  {op}: {info['description']} ({rhs})")
    return "\n".join(lines)
