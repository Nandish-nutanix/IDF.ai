# IDF Queries Extracted from Nutest Insights Test Files

> **Companion document**: See [idf_schema_reference.md](idf_schema_reference.md) for the complete proto schema reference (RPC definitions, message structures, enums, entity type registry, attribute/metric registry, and Arithmos operations).

## Source: `/Users/nandish.chokshi/Nutanix_New/nutest-py3-tests/testcases/insights/` and `/workflows/insights/`

---

## 1. RegisterEntityTypes

### Basic Entity Type Registration
```
entity_type_info_list {
  entity_type_name: "vm"
  type_info {
    is_evictable: false
  }
}
```

### Evictable Entity Type Registration
```
entity_type_info_list {
  entity_type_name: "evictable_entity"
  type_info {
    is_evictable: true
  }
}
```

### Non-CAS Entity Type with TypeInfo
```
entity_type_info_list {
  entity_type_name: "non_cas_type"
  type_info {
    track_attribute_changes: false
    suppress_replication: false
  }
}
```

### Non-CAS Evictable Entity Type
```
entity_type_info_list {
  entity_type_name: "non_cas_type_evictable"
  type_info {
    track_attribute_changes: false
    suppress_replication: false
    is_evictable: true
  }
}
```

### Entity Type with Parent
```
entity_type_info_list {
  entity_type_name: "child_entity"
  type_info {
    parent_list: "parent_entity"
  }
}
```

---

## 2. RegisterMetricTypes

### Register Attribute (string)
```
metric_type_list {
  is_attribute: true
  metric_name: "vm_name"
  entity_type_name: "vm"
}
```

### Register Indexed Attribute (string)
```
metric_type_list {
  is_attribute: true
  is_index_column: true
  index_type: 1
  metric_name: "vm_name"
  entity_type_name: "vm"
}
```

### Register Indexed Attribute (int64)
```
metric_type_list {
  is_attribute: true
  is_index_column: true
  index_type: 0
  metric_name: "num_cpu_cores"
  entity_type_name: "node"
}
```

### Register Indexed Attribute (bool)
```
metric_type_list {
  is_attribute: true
  is_index_column: true
  index_type: 3
  metric_name: "is_active"
  entity_type_name: "vm"
}
```

### Register Indexed Attribute (uint64)
```
metric_type_list {
  is_attribute: true
  is_index_column: true
  index_type: 2
  metric_name: "timestamp_usecs"
  entity_type_name: "vm"
}
```

### Register Indexed Attribute (bytes)
```
metric_type_list {
  is_attribute: true
  is_index_column: true
  index_type: 4
  metric_name: "data_bytes"
  entity_type_name: "storage"
}
```

### Register Metric (non-attribute)
```
metric_type_list {
  is_attribute: false
  metric_name: "cpu_usage_ppm"
  entity_type_name: "vm"
}
```

### Register Serialized Proto Attribute
```
metric_type_list {
  is_attribute: true
  bucketize_timestamps_in_tsdb: false
  metric_name: "base_attribute"
  entity_type_name: "test_entity"
  contains_serialised_proto: true
  persist_attribute_as_time_series: false
}
```

### Register Nested Attribute
```
metric_type_list {
  is_attribute: true
  is_index_column: true
  index_type: 1
  bucketize_timestamps_in_tsdb: false
  metric_name: "nested_attr_string"
  entity_type_name: "test_entity"
  contains_serialised_proto: false
  persist_attribute_as_time_series: false
  nested_field_info {
    base_attribute: "base_attribute"
    nested_field_index: 7
    nested_field_index: 4
    nested_field_index: 16
    nested_field_type: 0
    has_repeated_fields: false
  }
}
```

### Register Multiple Attributes in One Call
```
metric_type_list {
  is_attribute: true
  metric_name: "attr1"
  entity_type_name: "test_entity"
}
metric_type_list {
  is_attribute: true
  metric_name: "attr2"
  entity_type_name: "test_entity"
}
metric_type_list {
  is_attribute: true
  metric_name: "attr3"
  entity_type_name: "test_entity"
}
```

### Register Attribute with User Metadata (float type)
```
metric_type_list {
  is_attribute: true
  is_index_column: false
  bucketize_timestamps_in_tsdb: false
  metric_name: "attr_float_value"
  entity_type_name: "test_entity"
  contains_serialised_proto: false
  persist_attribute_as_time_series: false
  user_metadata: "{\"data_type\":\"float\"}"
}
```

---

## 3. UpdateEntity

### Simple Entity Update
```
entity_guid {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
attribute_data_arg_list {
  attribute_data {
    name: "vm_name"
    value {
      str_value: "test-vm-1"
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "power_state"
    value {
      str_value: "on"
    }
  }
}
```

### Update with CAS Value
```
entity_guid {
  entity_type_name: "cas_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
cas_value: 0
attribute_data_arg_list {
  attribute_data {
    name: "attr1"
    value {
      str_value: "cas_value_1"
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "attr2"
    value {
      str_value: "cas_value_2"
    }
  }
}
```

### Update with Timestamps
```
entity_guid {
  entity_type_name: "non_cas_type"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
  tenant_id: ""
}
timestamp_usecs: 1620000000000000
created_timestamp_usecs: 1620000000000000
```

### Update with CAS and Timestamps
```
entity_guid {
  entity_type_name: "cas_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
timestamp_usecs: 1620000000000000
created_timestamp_usecs: 1620000000000000
cas_value: 0
attribute_data_arg_list {
  attribute_data {
    name: "attr1"
    value {
      str_value: "value1"
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "attr2"
    value {
      str_value: "value2"
    }
  }
}
```

### Full Update with Multiple Data Types
```
entity_guid {
  entity_type_name: "test_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
full_update: true
attribute_data_arg_list {
  attribute_data {
    name: "str_attr"
    value {
      str_value: "Apple"
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "int_attr"
    value {
      int64_value: 1610000000000010
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "str_list_attr"
    value {
      str_list {
        value_list: "Apple"
        value_list: "Banana"
      }
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "int_list_attr"
    value {
      int64_list {
        value_list: 0
        value_list: 1
      }
    }
  }
}
```

### Update with Float/Double Values
```
entity_guid {
  entity_type_name: "test_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
attribute_data_arg_list {
  attribute_data {
    name: "float_attr"
    value {
      float_value: 3.14
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "double_attr"
    value {
      double_value: 1.61803398875
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "float_list_attr"
    value {
      float_list {
        value_list: 1.1
        value_list: 2.2
      }
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "double_list_attr"
    value {
      double_list {
        value_list: 1.61
        value_list: 2.72
      }
    }
  }
}
```

### Update with Bool and Bytes Values
```
entity_guid {
  entity_type_name: "test_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
attribute_data_arg_list {
  attribute_data {
    name: "is_active"
    value {
      bool_value: true
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "data_bytes"
    value {
      bytes_value: "binary_data_here"
    }
  }
}
```

### Update with uint64 Value
```
entity_guid {
  entity_type_name: "test_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
attribute_data_arg_list {
  attribute_data {
    name: "timestamp_usecs"
    value {
      uint64_value: 1620000000000000
    }
  }
}
```

---

## 4. DeleteEntity

### Simple Delete
```
entity_guid {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
```

### Delete with CAS Value
```
entity_guid {
  entity_type_name: "cas_entity"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
cas_value: 3
```

---

## 5. BatchDeleteEntities

### Batch Delete Multiple Entities
```
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440001"
  }
}
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440002"
  }
}
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440003"
  }
}
```

---

## 6. GetEntitiesWithMetrics

### Simple Raw Column Fetch (All Attributes)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "power_state"
    }
    raw_columns {
      column: "num_cpu_cores"
    }
  }
  query_name: "fetch_all_raw_columns"
}
```

### Raw Column Fetch with Limit/Offset
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "power_state"
    }
    raw_limit {
      limit: 1000
      offset: 0
    }
  }
  query_name: "fetch_with_limit"
}
```

### Where Clause - kEQ (equals)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "power_state"
        }
      }
      operator: kEQ
      rhs {
        leaf {
          value {
            str_value: "on"
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
      column: "power_state"
    }
  }
  query_name: "where_clause_eq"
}
```

### Where Clause - kNE (not equals)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "power_state"
        }
      }
      operator: kNE
      rhs {
        leaf {
          value {
            str_value: "off"
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
  }
  query_name: "where_clause_ne"
}
```

### Where Clause - kLT (less than) on integer
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "num_cpu_cores"
        }
      }
      operator: kLT
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
      column: "num_cpu_cores"
    }
  }
  query_name: "where_clause_lt"
}
```

### Where Clause - kGT (greater than) on integer
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "num_cpu_cores"
        }
      }
      operator: kGT
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
      column: "num_cpu_cores"
    }
    raw_limit {
      limit: 100
      offset: 0
    }
  }
  query_name: "where_clause_gt"
}
```

### Where Clause - kLE (less than or equal)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "num_cpu_cores"
        }
      }
      operator: kLE
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
      column: "num_cpu_cores"
    }
  }
  query_name: "where_clause_le"
}
```

### Where Clause - kGE (greater than or equal)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "num_cpu_cores"
        }
      }
      operator: kGE
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
      column: "num_cpu_cores"
    }
  }
  query_name: "where_clause_ge"
}
```

### Where Clause - kLike (string pattern match)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "vm_name"
        }
      }
      operator: kLike
      rhs {
        leaf {
          value {
            str_value: "test"
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
  }
  query_name: "where_clause_like"
}
```

### Where Clause - kContains (list contains all elements)
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "str_list_attr"
        }
      }
      operator: kContains
      rhs {
        leaf {
          value {
            str_list {
              value_list: "Apple"
            }
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "str_list_attr"
    }
  }
  query_name: "where_clause_contains"
}
```

### Where Clause - kIN (value in list)
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "int_list_attr"
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
  query_name: "where_clause_in"
}
```

### Where Clause - kAny (any element matches)
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "str_list_attr"
        }
      }
      operator: kAny
      rhs {
        leaf {
          value {
            str_list {
              value_list: "Apple"
              value_list: "Banana"
            }
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "str_list_attr"
    }
  }
  query_name: "where_clause_any"
}
```

### Where Clause - kExists (check attribute exists)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "vm_name"
        }
      }
      operator: kExists
    }
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
  }
  query_name: "where_clause_exists"
}
```

### Complex Where Clause - AND (two conditions)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs {
          leaf {
            column: "power_state"
          }
        }
        operator: kEQ
        rhs {
          leaf {
            value {
              str_value: "on"
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
        operator: kLike
        rhs {
          leaf {
            value {
              str_value: "prod"
            }
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
      column: "power_state"
    }
  }
  query_name: "complex_where_clause_and"
}
```

### Complex Where Clause - OR (two conditions)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs {
          leaf {
            column: "power_state"
          }
        }
        operator: kEQ
        rhs {
          leaf {
            value {
              str_value: "on"
            }
          }
        }
      }
    }
    operator: kOr
    rhs {
      comparison_expr {
        lhs {
          leaf {
            column: "num_cpu_cores"
          }
        }
        operator: kGT
        rhs {
          leaf {
            value {
              int64_value: 8
            }
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
      column: "power_state"
    }
    raw_columns {
      column: "num_cpu_cores"
    }
  }
  query_name: "complex_where_clause_or"
}
```

### Where Clause on uint64 (_created_timestamp_usecs_)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "_created_timestamp_usecs_"
        }
      }
      operator: kGT
      rhs {
        leaf {
          value {
            uint64_value: 1620000000000000
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
      column: "_created_timestamp_usecs_"
    }
  }
  query_name: "where_clause_timestamp"
}
```

### Group By - Single Attribute
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "power_state"
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "power_state"
    }
    raw_limit {
      limit: 1000
      offset: 0
    }
  }
  query_name: "group_by_power_state"
}
```

### Multi-level Group By (Nested Sub-groups)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "power_state"
    sub_group_by {
      group_by_column: "cluster_name"
      sub_group_by {
        group_by_column: "hypervisor_type"
        raw_columns {
          column: "vm_name"
        }
        raw_columns {
          column: "num_cpu_cores"
        }
        raw_limit {
          limit: 1000
          offset: 0
        }
      }
    }
  }
  query_name: "multi_group_by"
}
```

### Sort - Raw Sort (Ascending)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_cpu_cores"
    }
    raw_sort_order {
      sort_column: "num_cpu_cores"
      sort_order: kAscending
    }
    raw_limit {
      limit: 100
      offset: 0
    }
  }
  query_name: "sort_ascending"
}
```

### Sort - Raw Sort (Descending)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "num_cpu_cores"
    }
    raw_sort_order {
      sort_column: "num_cpu_cores"
      sort_order: kDescending
    }
    raw_limit {
      limit: 10
      offset: 0
    }
  }
  query_name: "sort_descending"
}
```

### Group Sort - Group By with Sort on Groups
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "power_state"
    group_sort_order {
      sort_column: "power_state"
      sort_order: kAscending
    }
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "power_state"
    }
    raw_limit {
      limit: 100
      offset: 0
    }
  }
  query_name: "group_sort"
}
```

### Cursor Query - Initial (Paginated)
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 999
  }
  query_name: "primary_cursor_query"
}
```

### Cursor Query - With Where Clause and Raw Columns
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "power_state"
        }
      }
      operator: kEQ
      rhs {
        leaf {
          value {
            str_value: "on"
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
      column: "power_state"
    }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 100
  }
  query_name: "cursor_with_where_clause"
  flags: 144
}
```

### Cursor Query - With Raw Sort and Columns
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "vm_name"
      column: "num_cpu_cores"
      column: "power_state"
    }
    raw_sort_order {
      sort_column: "num_cpu_cores"
      sort_order: kAscending
    }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 500
  }
  query_name: "cursor_with_sort"
}
```

### Cursor Query - With Unfiltered Count Flags
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 749
  }
  query_name: "cursor_with_unfiltered_count"
  flags: 16
}
```

### Cursor Query - With Unfiltered Group Count Flags
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 749
  }
  query_name: "cursor_with_group_count"
  flags: 144
}
```

### Aggregate Columns
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns {
      column: "num_cpu_cores"
    }
    aggregate_columns {
      column: "num_cpu_cores"
      operator: kAvg
    }
  }
  query_name: "aggregate_avg"
}
```

### Having Clause - kEQ on String Attribute (Group Filter)
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "str_attr"
    having_clause {
      comparison_expr {
        lhs {
          leaf {
            column: "str_attr"
          }
        }
        operator: kEQ
        rhs {
          leaf {
            value {
              str_value: "Apple"
            }
          }
        }
      }
    }
  }
  query_name: "having_clause_eq"
}
```

### Having Clause - kExists (Groups Where Attribute Exists)
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "str_attr"
    having_clause {
      comparison_expr {
        lhs {
          leaf {
            column: "str_attr"
          }
        }
        operator: kExists
      }
    }
  }
  query_name: "having_clause_exists"
}
```

### Having Clause - kNE on List Attribute
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "str_list_attr"
    having_clause {
      comparison_expr {
        lhs {
          leaf {
            column: "str_list_attr"
          }
        }
        operator: kNE
        rhs {
          leaf {
            value {
              str_list {
                value_list: "Apple"
              }
            }
          }
        }
      }
    }
  }
  query_name: "having_clause_ne_list"
}
```

### Having Clause - kContains on List Attribute
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "str_list_attr"
    having_clause {
      comparison_expr {
        lhs {
          leaf {
            column: "str_list_attr"
          }
        }
        operator: kContains
        rhs {
          leaf {
            value {
              str_list {
                value_list: "Apple"
              }
            }
          }
        }
      }
    }
  }
  query_name: "having_clause_contains"
}
```

### Lookup Query (Join)
```
query {
  query_name: "lookup_join"
  entity_list {
    entity_type_name: "child_entity"
  }
  group_by {
    raw_columns {
      column: "str_attr"
    }
    raw_columns {
      column: "int_attr"
    }
    raw_sort_order {
      sort_order: kAscending
      sort_column: "str_attr"
    }
    raw_limit {
      limit: 10
    }
    lookup_query {
      entity_list {
        entity_type_name: "parent_entity"
      }
      where_clause {
        comparison_expr {
          lhs {
            leaf {
              column: "str_list_attr"
            }
          }
          operator: kEQ
          rhs {
            leaf {
              column: "str_list_attr"
            }
          }
        }
      }
      group_by {
        raw_columns {
          column: "str_attr"
        }
        raw_columns {
          column: "int_attr"
        }
        raw_sort_order {
          sort_order: kDescending
          sort_column: "str_attr"
        }
      }
    }
  }
}
```

### Time-Scoped Metric Query
```
query {
  entity_list {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440000"
  }
  start_time_usecs: 1620000000000000
  end_time_usecs: 1620003000000000
  group_by {
    raw_columns {
      column: "cpu_usage_ppm"
    }
  }
  query_name: "metric_time_range"
}
```

### Query with Entity ID (specific entity)
```
query {
  entity_list {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440000"
  }
  group_by {
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "power_state"
    }
    raw_columns {
      column: "num_cpu_cores"
    }
  }
  query_name: "specific_entity_query"
}
```

---

## 7. BatchGetEntitiesWithMetrics

### Batch Query (Multiple Queries)
```
query_list {
  query {
    entity_list {
      entity_type_name: "vm"
    }
    group_by {
      raw_columns {
        column: "vm_name"
      }
    }
    query_name: "batch_query_1"
  }
}
query_list {
  query {
    entity_list {
      entity_type_name: "node"
    }
    group_by {
      raw_columns {
        column: "node_name"
      }
    }
    query_name: "batch_query_2"
  }
}
```

---

## 8. GetEntities (Simple Entity Retrieval by GUID)

### Get Entity by GUID
```
entity_guid_list {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440000"
}
```

### Get Multiple Entities by GUID
```
entity_guid_list {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440001"
}
entity_guid_list {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440002"
}
```

---

## 9. SpotLightSearch

### Basic Search with Limit
```
search_term: "name"
limit {
  limit: 5
  offset: 0
}
```

### Search with Entity Type Filter
```
search_term: "name"
entity_type_name_list: "vm"
limit {
  limit: 1
  offset: 3
}
```

### Search with Entity Type Only
```
search_term: "name"
entity_type_name_list: "vm"
```

### Search with Scope Entity List
```
search_term: "name"
entity_type_name_list: "vm"
scope_entity_list {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440001"
}
scope_entity_list {
  entity_type_name: "vm"
  entity_id: "550e8400-e29b-41d4-a716-446655440002"
}
```

### Search with Extra Return Attributes
```
search_term: "name"
entity_type_name_list: "vm"
limit {
  limit: 3
  offset: 0
}
extra_return_attribute_list: "vm_name"
extra_return_attribute_list: "cluster_name"
```

---

## 10. PutMetricData

### Put Metric Data with Time-Value Pairs
```
entity_with_metric_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440000"
  }
  metric_data_list {
    name: "cpu_usage_ppm"
    value_list {
      timestamp_usecs: 1620000030000000
      value {
        int64_value: 5000
      }
    }
  }
}
```

---

## 11. BatchUpdateEntities

### Batch Update Multiple Entities
```
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440001"
  }
  full_update: false
  attribute_data_arg_list {
    attribute_data {
      name: "power_state"
      value {
        str_value: "on"
      }
    }
  }
}
entity_list {
  entity_guid {
    entity_type_name: "vm"
    entity_id: "550e8400-e29b-41d4-a716-446655440002"
  }
  full_update: false
  attribute_data_arg_list {
    attribute_data {
      name: "power_state"
      value {
        str_value: "off"
      }
    }
  }
}
```

---

## 12. Watch API Patterns (from watches_scenarios.py and composite_watches.py)

### Simple Watch - watch_new_entities_of_type
Uses `InsightsWatchClient` with callbacks:
```python
watch_client = InsightsWatchClient(client_id, error_callback, ip, port)
watch_client.start()
watch_client.watch_new_entities_of_type("vm", callback_function)
```

### Unregister Watch
```python
watch_client.unregister_watch_new_entities_of_type("vm")
```

### Composite Watch - Watch on Entity Type (Create/Update/Delete)
```python
watch_client = InsightsWatchClient(client_id, error_callback, ip, port)
watch_client.start()
bool_expr = BooleanExpression()
watch_client.composite_watch_on_entities_of_type(
    "vm",
    watch_callback,
    register_create_watch=True,
    register_update_watch=True,
    register_delete_watch=True,
    get_current_entities=True,
    return_previous_entity=True,
    metric_name="vm_name",
    filter_expr=bool_expr
)
```

### Composite Watch - Watch on Specific Entity (by GUID)
```python
entity_guid = EntityGuid()
entity_guid.entity_type_name = "vm"
entity_guid.entity_id = "550e8400-e29b-41d4-a716-446655440000"
bool_expr = BooleanExpression()
watch_client.composite_watch_on_entity(
    entity_guid,
    watch_callback,
    register_create_watch=True,
    register_update_watch=True,
    register_delete_watch=False,
    get_current_entity=True,
    return_previous_entity=True,
    metric_name="",
    filter_expr=bool_expr
)
```

### Stop Watch Client
```python
watch_client.stop()
```

---

## Summary of All Operators Referenced

### Where Clause Operators (from all_queries.py):
- `kEQ = 0` - Equals
- `kNE = 1` - Not Equals
- `kLT = 2` - Less Than
- `kLE = 3` - Less Than or Equal
- `kGT = 4` - Greater Than
- `kGE = 5` - Greater Than or Equal
- `kLike = 6` - String pattern match (only for str attributes)
- `kContains = 7` - List contains all (only for list attributes)
- `kIN = 8` - Value in list (only for list attributes)
- `kAny = 9` - Any element matches (only for list attributes)
- `kExists = 10` - Attribute exists

### Complex Where Clause Operators:
- `kAnd = 0` - AND operation
- `kOr = 1` - OR operation

### Sort Orders:
- `kAscending = 0`
- `kDescending = 1`

### Aggregate Operators:
- `kAvg`
- `kSum`
- `kCount`
- `kMin`
- `kMax`

### Index Types:
- `0` = int
- `1` = str
- `2` = uint64
- `3` = bool
- `4` = bytes

### Data Value Types:
- `str_value` - String
- `int64_value` - Integer (64-bit signed)
- `uint64_value` - Unsigned integer (64-bit)
- `bool_value` - Boolean
- `float_value` - Float
- `double_value` - Double
- `bytes_value` - Bytes
- `str_list { value_list: ... }` - String list
- `int64_list { value_list: ... }` - Int64 list
- `bool_list { value_list: ... }` - Bool list
- `float_list { value_list: ... }` - Float list
- `double_list { value_list: ... }` - Double list

### Query Flags:
- `16` - Return unfiltered entity count
- `144` - Return unfiltered entity count + group count

---

## Additional Patterns from Extended Search

### 16. Namespace Queries (column_namespace)
Source: `workflows/insights/nutest_namespace_queries.py`

#### GetEntities with metadata_only:
```
entity_guid_list {
  entity_type_name: "test_entity"
}
meta_data_only: true
```

#### GetEntitiesWithMetrics with column_namespace (Multiphase Queries):
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "str_unindex_attr1"
          column_namespace: "np2"
        }
      }
      operator: kNE
      rhs {
        leaf {
          value {
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "int_index_attr1"
      column_namespace: "np2"
    }
    raw_columns {
      column: "bool_unindex_attr1"
      column_namespace: "np2"
    }
    raw_columns {
      column: "str_unindex_attr1"
      column_namespace: "np2"
    }
    raw_columns {
      column: "int_unindex_attr1"
      column_namespace: "np1"
    }
    raw_columns {
      column: "str_index_attr1"
      column_namespace: "np1"
    }
    raw_columns {
      column: "bool_index_attr1"
      column_namespace: "np1"
    }
    raw_columns {
      column: "dummy_immutable"
    }
    raw_sort_order {
      sort_column: "bool_index_attr1"
      sort_column_namespace: "np1"
    }
    raw_limit {
      offset: 0
      limit: 100
    }
  }
  query_name: "multiphase-namespace"
}
```

### 17. Multi-Column Sort with raw_sort_order_list
Source: `workflows/insights/sort_on_multiple_columns/query_unevictable_data.py`

#### Two-column sort (ascending/descending):
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    raw_columns {
      column: "str_list_attr"
    }
    raw_columns {
      column: "int_attr"
    }
    raw_sort_order_list {
      sort_column: "str_list_attr"
      sort_order: kAscending
    }
    raw_sort_order_list {
      sort_column: "int_attr"
      sort_order: kDescending
    }
  }
  query_name: "query_sort"
}
```

#### Three-column sort:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    raw_columns {
      column: "str_list_attr"
    }
    raw_columns {
      column: "int_attr"
    }
    raw_columns {
      column: "bool_list_attr"
    }
    raw_sort_order_list {
      sort_column: "str_list_attr"
      sort_order: kAscending
    }
    raw_sort_order_list {
      sort_column: "int_attr"
      sort_order: kAscending
    }
    raw_sort_order_list {
      sort_column: "bool_list_attr"
      sort_order: kDescending
    }
  }
  query_name: "query_sort"
}
```

#### Multi-column sort combined with complex where clause (kContains, kIN, kNot):
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    lhs {
      lhs {
        comparison_expr {
          lhs { leaf { column: "bool_attr" } }
          operator: kEQ
          rhs { leaf { value { bool_value: false } } }
        }
      }
      operator: kAnd
      rhs {
        comparison_expr {
          lhs { leaf { column: "str_list_attr" } }
          operator: kContains
          rhs { leaf { value { str_list { value_list: "str_value15" } } } }
        }
      }
    }
    operator: kAnd
    rhs {
      lhs {
        comparison_expr {
          lhs { leaf { column: "int_list_attr" } }
          operator: kContains
          rhs { leaf { value { int64_list { value_list: 48 } } } }
        }
      }
      operator: kAnd
      rhs {
        lhs {
          comparison_expr {
            lhs { leaf { column: "bool_list_attr" } }
            operator: kIN
            rhs { leaf { value { bool_list { value_list: true value_list: false } } } }
          }
        }
        operator: kNot
      }
    }
  }
  group_by {
    raw_columns { column: "str_list_attr" }
    raw_columns { column: "int_attr" }
    raw_columns { column: "bool_list_attr" }
    raw_sort_order_list {
      sort_column: "str_list_attr"
      sort_order: kAscending
    }
    raw_sort_order_list {
      sort_column: "int_attr"
      sort_order: kAscending
    }
    raw_sort_order_list {
      sort_column: "bool_list_attr"
      sort_order: kDescending
    }
  }
  query_name: "query_sort"
}
```

### 18. Metric Sort Key (kFirst, kLast, kMin, kMax)
Source: `workflows/insights/metric_sort_key/metric_sort_key.py`

#### Default sort key (kLast):
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  start_time_usecs: 1668545107000000
  end_time_usecs: 1668631507000000
  group_by {
    raw_columns {
      column: "int_metric_1"
    }
    raw_sort_order_list {
      sort_column: "int_metric_1"
    }
  }
  query_name: "metric_sort_key_query_1"
}
```

#### kFirst sort key:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  start_time_usecs: 1668545107000000
  end_time_usecs: 1668631507000000
  group_by {
    raw_columns {
      column: "int_metric_1"
    }
    raw_sort_order_list {
      sort_column: "int_metric_1"
      sort_order: kDescending
      sort_key: kFirst
    }
  }
  query_name: "metric_sort_key_query_2"
}
```

#### kMin sort key:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  start_time_usecs: 1668545107000000
  end_time_usecs: 1668631507000000
  group_by {
    raw_columns {
      column: "int_metric_1"
    }
    raw_sort_order_list {
      sort_column: "int_metric_1"
      sort_order: kDescending
      sort_key: kMin
    }
  }
  query_name: "metric_sort_key_query_3"
}
```

#### kMax sort key:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  start_time_usecs: 1668545107000000
  end_time_usecs: 1668631507000000
  group_by {
    raw_columns {
      column: "int_metric_1"
    }
    raw_sort_order_list {
      sort_column: "int_metric_1"
      sort_order: kAscending
      sort_key: kMax
    }
  }
  query_name: "metric_sort_key_query_4"
}
```

### 19. Cursor Queries with Entity ID Sort
Source: `workflows/insights/cursor_query_eid_sort.py`

#### Sort by _entity_id_ (descending):
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    raw_columns {
      column: "_entity_id_"
    }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kDescending
    }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 999
  }
  query_name: "primary_cursor_query"
}
```

#### Group-by with cursor (NOT SUPPORTED - returns error):
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "int_attr"
    raw_columns {
      column: "_entity_id_"
    }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kDescending
    }
    raw_limit {
      limit: 10
      offset: 0
    }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 2
  }
  query_name: "primary_cursor_query"
}
```

### 20. BatchGetEntitiesWithMetrics Patterns
Source: `workflows/insights/batch_get_entities_with_metrics.py`

#### Multiple queries for different entity types:
```
query_list {
  query {
    entity_list {
      entity_type_name: "entity_type_1"
    }
    flags: 2
    query_name: "entity_count_query"
  }
}
query_list {
  query {
    entity_list {
      entity_type_name: "entity_type_2"
    }
    flags: 2
    query_name: "entity_count_query"
  }
}
```

#### Multiple queries in same query_list block:
```
query_list {
  query {
    entity_list {
      entity_type_name: "entity_type_1"
    }
    flags: 2
    query_name: "entity_count_query"
  }
  query {
    entity_list {
      entity_type_name: "entity_type_2"
    }
    flags: 2
    query_name: "entity_count_query"
  }
}
```

### 21. Where Clause on Bytes Attributes
Source: `workflows/insights/where_clause_bytes_test.py`

#### Registration with kBytes index:
```
metric_type_list {
  is_attribute: true
  metric_name: "bytes_attr"
  entity_type_name: "test_entity"
  is_index_column: true
  index_type: kBytes
}
```

#### Query with bytes where clause:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs {
        leaf {
          column: "bytes_attr"
        }
      }
      operator: 0
      rhs {
        leaf {
          value {
            bytes_value: <binary>
          }
        }
      }
    }
  }
  group_by {
    raw_columns {
      column: "bytes_attr"
    }
    raw_columns {
      column: "num_vcpus"
    }
  }
  query_name: "where_clause"
}
```

#### Query with bytes_list RHS:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "bytes_attr" } }
      operator: kContains
      rhs {
        leaf {
          value {
            bytes_list {
              value_list: <binary1>
              value_list: <binary2>
            }
          }
        }
      }
    }
  }
  group_by {
    raw_columns { column: "bytes_attr" }
  }
  query_name: "bytes_list_query"
}
```

### 22. Metadata Pseudo-Columns
Source: `workflows/insights/where_clause_metadata.py`

#### Query on metadata columns:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    raw_limit {
      limit: 100000
    }
    raw_columns {
      column: "some_attr"
    }
    raw_columns {
      column: "_master_cluster_uuid_"
    }
    raw_columns {
      column: "_cas_value_"
    }
    raw_columns {
      column: "_created_timestamp_usecs_"
    }
    raw_columns {
      column: "_modified_timestamp_usecs_"
    }
  }
  where_clause {
    lhs {
      lhs {
        comparison_expr {
          lhs { leaf { column: "_master_cluster_uuid_" } }
          operator: kEQ
          rhs { leaf { value { str_value: "uuid-here" } } }
        }
      }
      operator: kAnd
      rhs {
        lhs {
          lhs {
            comparison_expr {
              lhs { leaf { column: "_entity_id_" } }
              operator: kEQ
              rhs { leaf { value { str_value: "entity-id-here" } } }
            }
          }
          operator: kAnd
          rhs {
            comparison_expr {
              lhs { leaf { column: "_cas_value_" } }
              operator: kEQ
              rhs { leaf { value { uint64_value: 1 } } }
            }
          }
        }
        operator: kAnd
        rhs {
          lhs {
            comparison_expr {
              lhs { leaf { column: "_created_timestamp_usecs_" } }
              operator: kEQ
              rhs { leaf { value { uint64_value: 1234567890 } } }
            }
          }
          operator: kAnd
          rhs {
            comparison_expr {
              lhs { leaf { column: "_modified_timestamp_usecs_" } }
              operator: kEQ
              rhs { leaf { value { uint64_value: 1234567890 } } }
            }
          }
        }
      }
    }
  }
  query_name: "test_where_clause_metadata"
}
```

#### Group-by on metadata columns:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    raw_limit {
      limit: 100000
    }
    group_by_column: "_cas_value_"
    raw_columns {
      column: "_master_cluster_uuid_"
    }
    raw_columns {
      column: "_cas_value_"
    }
    raw_columns {
      column: "_created_timestamp_usecs_"
    }
    raw_columns {
      column: "_modified_timestamp_usecs_"
    }
  }
  query_name: "test_group_by_metadata"
}
```

#### Sort by metadata columns:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    raw_limit {
      limit: 100000
    }
    group_by_column: "_cas_value_"
    group_sort_order {
      sort_column: "_cas_value_"
      sort_order: kAscending
    }
    raw_sort_order {
      sort_column: "_cas_value_"
      sort_order: kAscending
    }
    raw_columns {
      column: "_master_cluster_uuid_"
    }
    raw_columns {
      column: "_cas_value_"
    }
    raw_columns {
      column: "_created_timestamp_usecs_"
    }
    raw_columns {
      column: "_modified_timestamp_usecs_"
    }
  }
  query_name: "test_sort_by_metadata"
}
```

### 23. Continuous Group-By (Bucketing)
Source: `workflows/insights/prism_queries.py`

```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "controller_io_bandwidth_kBps" } }
      operator: kNE
      rhs { leaf { value { } } }
    }
  }
  group_by {
    group_by_column: "controller_io_bandwidth_kBps"
    group_by_column_type: kContinuous
    num_buckets: 3
    bucket_boundary: 1000
    aggregate_columns {
      column: "controller_io_bandwidth_kBps"
      operator: kAvg
    }
    group_sort_order {
      sort_column: "controller_io_bandwidth_kBps"
      sort_order: kAscending
    }
  }
  query_name: "Filter_continous_groupby_vm_query"
}
```

### 24. Discrete Group-By with group_limit
Source: `workflows/insights/prism_queries.py`

```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "power_state"
    group_sort_order {
      sort_column: "power_state"
    }
    group_limit {
      limit: 7
      offset: 0
    }
    raw_columns {
      column: "vm_name"
    }
    raw_columns {
      column: "node_name"
    }
    raw_columns {
      column: "hypervisor_type"
    }
    raw_columns {
      column: "memory_size_bytes"
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
  query_name: "Group_discrete_groupby_vm_query"
}
```

### 25. Prism-Style Queries (Real-World Patterns)
Source: `workflows/insights/prism_queries.py`

#### Login cluster query with many columns:
```
query {
  entity_list {
    entity_type_name: "cluster"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "_arithmos_id_" } }
      operator: kNE
      rhs { leaf { value { } } }
    }
  }
  group_by {
    raw_columns { column: "hypervisor_avg_io_latency_usecs" }
    raw_columns { column: "num_cpus" }
    raw_columns { column: "storage_tier.das-sata.usage_bytes" }
    raw_columns { column: "controller_num_read_iops" }
    raw_columns { column: "memory_capacity_bytes" }
    raw_columns { column: "controller_num_iops" }
    raw_columns { column: "storage.usage_bytes" }
    raw_columns { column: "hypervisor_cpu_usage_ppm" }
    raw_columns { column: "disk_size_bytes" }
    raw_columns { column: "num_vms" }
    raw_columns { column: "storage.capacity_bytes" }
    raw_columns { column: "cluster_name" }
  }
  query_name: "Login_cluster_query"
}
```

#### VM count query (using raw_limit: 1 for count):
```
query {
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
}
```

#### VM focus query (group_by_column: " " for flat result, group_limit for pagination):
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: " "
    group_limit {
      limit: 7
      offset: 0
    }
    raw_columns { column: "vm_name" }
    raw_columns { column: "hypervisor_memory_usage_ppm" }
    raw_columns { column: "controller_num_read_iops" }
    raw_columns { column: "controller_num_write_iops" }
    raw_columns { column: "controller_io_bandwidth_kBps" }
    raw_columns { column: "controller_avg_io_latency_usecs" }
    raw_columns { column: "cluster_name" }
    raw_columns { column: "num_vcpus" }
    raw_columns { column: "power_state" }
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
}
```

#### Specific entity query (using entity_id):
```
query {
  entity_list {
    entity_type_name: "vm"
    entity_id: "specific-uuid-here"
  }
  group_by {
    raw_columns { column: "hypervisor_avg_io_latency_usecs" }
    raw_columns { column: "cluster" }
    raw_columns { column: "vm_name" }
    raw_columns { column: "power_state" }
    raw_columns { column: "num_vcpus" }
  }
  query_name: "Entity_click_vm_query"
}
```

#### kLike operator for regex-based filtering:
```
query {
  entity_list {
    entity_type_name: "vm"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "vm_name" } }
      operator: kLike
      rhs { leaf { value { str_value: ".*[s|S][d|D][f|F].*" } } }
    }
  }
  group_by {
    group_by_column: " "
    group_limit { limit: 7 offset: 0 }
    raw_columns { column: "vm_name" }
    raw_columns { column: "power_state" }
    raw_sort_order {
      sort_column: "vm_name"
      sort_order: kAscending
    }
    raw_limit { limit: 120 offset: 0 }
  }
  query_name: "Filter_where_on_vm_query"
}
```

### 26. Lookup Query with Complex Where Clause
Source: `workflows/insights/lookup_test.py`

#### Simple lookup (join on column equality):
```
query {
  query_name: "multiple_join_with_list_value"
  entity_list { entity_type_name: "type_2" }
  group_by {
    raw_columns { column: "str_list_attr" }
    raw_columns { column: "str_attr" }
    raw_columns { column: "int_list_attr" }
    raw_columns { column: "int_attr" }
    raw_sort_order {
      sort_order: kAscending
      sort_column: "str_attr"
    }
    raw_limit {
      limit: 10
    }
    lookup_query {
      entity_list { entity_type_name: "type_1" }
      where_clause {
        comparison_expr {
          lhs { leaf { column: "str_list_attr" } }
          operator: kEQ
          rhs { leaf { column: "str_list_attr" } }
        }
      }
      group_by {
        raw_columns { column: "str_attr" }
        raw_columns { column: "str_list_attr" }
        raw_columns { column: "int_list_attr" }
        raw_columns { column: "int_attr" }
        raw_sort_order {
          sort_order: kDescending
          sort_column: "str_attr"
        }
      }
    }
  }
}
```

#### Lookup with compound where clause (kEQ + kContains + kOr):
```
query {
  query_name: "multiple_join_with_list_value"
  entity_list { entity_type_name: "type_2" }
  group_by {
    raw_columns { column: "str_list_attr" }
    raw_columns { column: "str_attr" }
    raw_columns { column: "int_list_attr" }
    raw_columns { column: "int_attr" }
    raw_sort_order {
      sort_order: kDescending
      sort_column: "str_attr"
    }
    raw_limit { limit: 10 }
    lookup_query {
      entity_list { entity_type_name: "type_1" }
      where_clause {
        lhs {
          comparison_expr {
            lhs { leaf { column: "str_list_attr" } }
            operator: kEQ
            rhs { leaf { column: "str_list_attr" } }
          }
        }
        operator: kAnd
        rhs {
          lhs {
            comparison_expr {
              lhs { leaf { column: "str_list_attr" } }
              operator: kContains
              rhs { leaf { value { str_list { value_list: "Arun" } } } }
            }
          }
          operator: kOr
          rhs {
            comparison_expr {
              lhs { leaf { column: "str_attr" } }
              operator: kEQ
              rhs { leaf { value { str_value: "Arun" } } }
            }
          }
        }
      }
      group_by {
        raw_columns { column: "str_attr" }
        raw_columns { column: "str_list_attr" }
        raw_columns { column: "int_list_attr" }
        raw_columns { column: "int_attr" }
        raw_sort_order {
          sort_order: kDescending
          sort_column: "str_attr"
        }
      }
    }
  }
}
```

### 27. Group-By with group_sort_order and flags
Source: `workflows/insights/unfiltered_counts.py`

```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "dummy_immutable" } }
      operator: kEQ
      rhs { leaf { value { bool_value: true } } }
    }
  }
  group_by {
    group_by_column: "dummy_value"
    raw_columns { column: "dummy_immutable" }
    raw_columns { column: "dummy_last_updated_time_usecs" }
    raw_columns { column: "dummy_value" }
    raw_columns { column: "dummy_create_time_usecs" }
    raw_columns { column: "key" }
    raw_sort_order {
      sort_column: "dummy_immutable"
    }
    group_sort_order {
      sort_column: "dummy_value"
      sort_order: kDescending
    }
  }
  flags: 144
  query_name: "count_query"
}
```

### 28. Derived Metric Registration
Source: `workflows/insights/unfiltered_counts.py`

```
metric_type_list {
  metric_name: "derived_metric1"
  entity_type_name: "test_entity"
  is_derived_metric: true
  derived_metric_expression {
    lhs {
      leaf {
        column: "metric1"
      }
    }
    operator: kPlus
    rhs {
      leaf {
        column: "metric2"
      }
    }
  }
}
```

### 29. Registration with suppress_replication
Source: `workflows/insights/where_clause_bytes_test.py`

```
entity_type_info_list {
  entity_type_name: "test_entity"
  type_info {
    suppress_replication: true
    is_evictable: false
    track_attribute_changes: false
  }
}
```

### 30. Registration with backup_replication_control
Source: `workflows/insights/cursor_query_eid_sort.py`

```
entity_type_info_list {
  entity_type_name: "test_entity"
  type_info {
    suppress_replication: true
    backup_replication_control {
      is_backup_required: true
    }
  }
}
```

### 31. Nested Proto Registration (Serialized Proto with Compression)
Source: `workflows/insights/nested_proto.py`

#### Register base attribute with serialised proto:
```
metric_type_list {
  is_attribute: true
  bucketize_timestamps_in_tsdb: false
  metric_name: "base_attribute_query"
  entity_type_name: "FOR_TESTING_NESTED_PROTO_2"
  contains_serialised_proto: true
  persist_attribute_as_time_series: false
}
```

#### Register with compression type:
```
metric_type_list {
  is_attribute: true
  bucketize_timestamps_in_tsdb: false
  metric_name: "compressed_base_attr"
  entity_type_name: "FOR_TESTING_NESTED_PROTO_2"
  contains_serialised_proto: true
  persist_attribute_as_time_series: false
  serialised_proto_compression_type: 1
}
```

### 32. Nested Attribute Query
Source: `workflows/insights/create_and_update_nested_proto.py`

```
query {
  entity_list {
    entity_type_name: "nested_test_entity"
    entity_id: "EID_0"
  }
  group_by {
    raw_columns {
      column: "nested_entity_id"
    }
    raw_columns {
      column: "nested_entity_type_name"
    }
  }
  query_name: "Fetch_nested_proto"
}
```

### 33. Watch on Indexed and Non-Indexed Attributes (kExists)
Source: `workflows/insights/evictable_entities_watches.py`

```
lhs {
  comparison_expr {
    lhs {
      leaf {
        column: "acknowledged"
      }
    }
    operator: kExists
  }
}
operator: kAnd
rhs {
  comparison_expr {
    lhs {
      leaf {
        column: "__zprotobuf__"
      }
    }
    operator: kExists
  }
}
```

### 34. UpdateEntity with str_list and int64_list values
Source: `workflows/insights/unfiltered_counts.py`

```
entity_guid {
  entity_type_name: "test_entity"
  entity_id: "some-uuid"
}
attribute_data_arg_list {
  attribute_data {
    name: "key"
    value {
      str_list {
        value_list: "value1"
        value_list: "value2"
        value_list: "value3"
      }
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "dummy_create_time_usecs"
    value {
      int64_list {
        value_list: 5
        value_list: 15
        value_list: 25
      }
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "dummy_description"
    value {
      str_value: "Something"
    }
  }
}
attribute_data_arg_list {
  attribute_data {
    name: "dummy_immutable"
    value {
      bool_value: true
    }
  }
}
```

### 35. Multiple Metric Types Registration in Single Call
Source: `workflows/insights/unfiltered_counts.py`

```
metric_type_list {
  is_attribute: true
  metric_name: "__zprotobuf__"
  entity_type_name: "test_entity"
}
metric_type_list {
  is_attribute: true
  metric_name: "key"
  entity_type_name: "test_entity"
  is_index_column: true
  index_type: kString
}
metric_type_list {
  is_attribute: true
  metric_name: "dummy_create_time_usecs"
  entity_type_name: "test_entity"
  is_index_column: true
  index_type: kInt64
}
metric_type_list {
  is_attribute: true
  metric_name: "dummy_description"
  entity_type_name: "test_entity"
}
metric_type_list {
  is_attribute: true
  metric_name: "dummy_value"
  entity_type_name: "test_entity"
  is_index_column: true
  index_type: kString
}
metric_type_list {
  is_attribute: false
  metric_name: "metric1"
  entity_type_name: "test_entity"
}
metric_type_list {
  is_attribute: false
  metric_name: "metric2"
  entity_type_name: "test_entity"
}
```

---

## All Available Metadata Pseudo-Columns:
- `_entity_id_` - Entity ID
- `_entity_type_name_` - Entity type name
- `_arithmos_id_` - Arithmos identifier
- `_master_cluster_uuid_` - Master cluster UUID
- `_cas_value_` - CAS (Compare-And-Swap) value
- `_created_timestamp_usecs_` - Creation timestamp (microseconds)
- `_modified_timestamp_usecs_` - Last modified timestamp (microseconds)

## All Available Sort Keys:
- `kLast` - Sort by last value (default)
- `kFirst` - Sort by first value
- `kMin` - Sort by minimum value
- `kMax` - Sort by maximum value

## All Available Group-By Column Types:
- (default/not set) - Discrete grouping
- `kContinuous` - Continuous bucketing (requires `num_buckets` and `bucket_boundary`)

## All Aggregate Operators:
- `kSum` - Sum
- `kCount` - Count
- `kMin` - Minimum
- `kMax` - Maximum
- `kAvg` - Average

## All Registration Type Fields:
- `suppress_replication` - Don't replicate to PC
- `is_evictable` - Entity data can be evicted from memory
- `track_attribute_changes` - Track changes to attributes
- `backup_replication_control { is_backup_required: true }` - Enable backup

## All Metric Registration Fields:
- `is_attribute` - True for attributes, false for metrics
- `metric_name` - Name of the attribute/metric
- `entity_type_name` - Entity type this belongs to
- `is_index_column` - Whether this column is indexed
- `index_type` - Type of index (kString, kInt64, kBoolean, kBytes)
- `contains_serialised_proto` - Attribute contains serialized protobuf
- `persist_attribute_as_time_series` - Store as time series
- `serialised_proto_compression_type` - Compression type for serialized proto
- `is_derived_metric` - Whether this is a derived metric
- `derived_metric_expression` - Expression for computing derived metrics
- `bucketize_timestamps_in_tsdb` - Whether to bucketize in time-series DB

---

## Key Insights from Test Patterns:

1. **Evictable entities** require `raw_limit` for queries (cannot query all without limit).
2. **CAS entities** require `cas_value` field on create/update/delete operations.
3. **Non-CAS entities** should NOT have `cas_value` set.
4. **Cursor queries** don't support `group_by_column` or `aggregate_columns`.
5. **Lookup queries** are nested within `group_by` and allow joining across entity types.
6. **Sort on bytes/list attributes** is NOT supported.
7. **kLike operator** only works on string attributes.
8. **kContains, kIN, kAny** operators only work on list attributes.
9. **Nested attributes** use `nested_field_info` in registration with field path indices.
10. **`full_update: true`** replaces all attributes; `full_update: false` (default) is partial update.
11. **`column_namespace`** allows querying attributes in specific namespaces.
12. **`sort_column_namespace`** allows sorting by namespace-specific attributes.
13. **`raw_sort_order_list`** (plural) supports multi-column sort with independent sort directions.
14. **`sort_key`** (kFirst, kLast, kMin, kMax) controls which time-series value is used for sorting.
15. **`group_by_column: " "`** (space) creates a flat result set (no actual grouping).
16. **`group_by_column_type: kContinuous`** enables bucket-based grouping with `num_buckets` and `bucket_boundary`.
17. **`group_limit`** controls pagination at the group level, while `raw_limit` controls per-group entity pagination.
18. **`group_sort_order`** sorts groups themselves, while `raw_sort_order` sorts entities within groups.
19. **`flags: 144`** returns both unfiltered entity count and unfiltered group count.
20. **`_entity_id_`** can be used as a sort column in cursor queries for deterministic ordering.
21. **`kNot` operator** acts as negation of the child expression (unary NOT).
22. **Lookup query `where_clause`** can reference columns from the parent query using `rhs { leaf { column: "..." } }` (column reference instead of value).
23. **Derived metrics** use arithmetic expressions (`kPlus`, `kMinus`, `kMultiply`, `kDivide`) on existing metrics.
24. **`kExists` operator** checks for existence of an attribute (no RHS needed).
25. **`down_sampling_operator`** on raw_columns controls how metric values are aggregated across time (e.g., sum, avg, min, max).
26. **`suppress_ancestor_tree_traversal`** on group_by disables ancestor tree traversal for optimization.
27. **`meta_data_only: true`** on GetEntities returns only metadata (namespaces, timestamps) without attribute values.
28. **Lookup query `rhs { leaf { column: "X" } }`** (column-to-column comparison) joins on matching column values between parent and lookup entity types.

### 36. Sub-Group-By (Multi-Level/Nested Grouping)
Source: `workflows/insights/search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "alert"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "resolved" } }
        operator: kEQ
        rhs { leaf { value { bool_value: false } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "impact_type" } }
        operator: kAny
        rhs {
          leaf {
            value {
              str_list {
                value_list: "Performance"
                value_list: "Capacity"
                value_list: "Configuration"
                value_list: "Availability"
                value_list: "SystemIndicator"
              }
            }
          }
        }
      }
    }
  }
  group_by {
    group_by_column: "cluster"
    sub_group_by {
      group_by_column: "impact_type"
      sub_group_by {
        group_by_column: "severity"
        raw_columns {
          column: "_created_timestamp_usecs_"
        }
        raw_columns {
          column: "__zprotobuf__"
        }
        raw_sort_order {
          sort_column: "_created_timestamp_usecs_"
          sort_order: kAscending
        }
        raw_limit {
          limit: 1
          offset: 0
        }
      }
    }
  }
  query_name: "alert_multi_grouping"
}
```

### 37. kLatest Sort Key and flags: 4
Source: `workflows/insights/search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "cluster_name" }
    raw_columns { column: "cluster" }
    raw_columns { column: "hypervisor_cpu_usage_ppm" }
    raw_sort_order {
      sort_column: "hypervisor_cpu_usage_ppm"
      sort_order: kDescending
      sort_key: kLatest
    }
    raw_limit {
      limit: 10
      offset: 0
    }
  }
  query_name: "vm_raw_sort_with_limit"
  flags: 4
}
```

### 38. Shard-Based Queries (_shard_id_ and shard_id_list)
Source: `workflows/insights/watches_on_shards.py`

#### Query entity on specific shard:
```
query {
  entity_list {
    entity_type_name: "test_entity"
    entity_id: "some-uuid"
  }
  group_by {
    raw_limit {
      limit: 1
    }
  }
  shard_id_list: "5"
}
```

#### Watch filter on _shard_id_ pseudo-column:
```
comparison_expr {
  lhs {
    leaf {
      column: "_shard_id_"
    }
  }
  operator: kIN
  rhs {
    leaf {
      value {
        int64_list {
          value_list: 1
          value_list: 2
          value_list: 3
        }
      }
    }
  }
}
```

### 39. Watch API - Entity-Specific Watch Types
Source: `workflows/insights/watches_on_shards.py`

#### Watch for NEW entities of a type:
```python
watch_client.watch_new_entities_of_type(
    entity_type, callback,
    get_current_entities=False,
    filter_expr=bool_expr)
```

#### Watch for UPDATED entities of a type:
```python
watch_client.watch_updated_entities_of_type(
    entity_type, callback,
    get_current_entities=False,
    filter_expr=bool_expr)
```

#### Watch for DELETED entities of a type:
```python
watch_client.watch_deleted_entities_of_type(
    entity_type, callback,
    get_current_entities=False,
    filter_expr=bool_expr)
```

#### Watch for NEW specific entity:
```python
watch_client.watch_new_entity(
    entity_guid, callback,
    get_current_entity=False,
    filter_expr=bool_expr)
```

#### Watch for UPDATE on specific entity:
```python
watch_client.watch_update_entity(
    entity_guid, callback,
    get_current_entity=False,
    filter_expr=bool_expr)
```

#### Watch for DELETE on specific entity:
```python
watch_client.watch_delete_entity(
    entity_guid, callback,
    get_current_entity=False,
    filter_expr=bool_expr)
```

### 40. Tenant ID in Entity Operations
Source: `workflows/insights/cassandra_timeout.py`

#### Delete with tenant_id:
```
entity_guid {
  entity_type_name: "vm"
  entity_id: "some-uuid"
  tenant_id: "tenant-uuid"
}
```

### 41. Entity-Level suppress_replication
Source: `workflows/insights/entity_suppress_replication.py`

#### UpdateEntity with suppress_replication flag:
```
entity_guid {
  entity_type_name: "vm"
  entity_id: "some-uuid"
}
suppress_replication: true
```

### 42. Expiration Timestamp on UpdateEntity
Source: `workflows/insights/rpc_timeout.py`

```
entity_guid {
  entity_type_name: "etype"
  entity_id: "1"
}
expiration_timestamp_usecs: 86400
full_update: false
attribute_data_arg_list {
  attribute_data {
    name: "num1"
    value {
      int64_value: 10
    }
  }
}
```

### 43. Extended RegisterEntityTypes Fields
Source: `workflows/insights/rpc_timeout.py`

```
entity_type_info_list {
  entity_type_name: "etype"
  type_info {
    suppress_replication: true
    backup_replication_control {
      is_backup_required: false
    }
    replication_control_list {
      enable_replication_from: kNDFS
    }
    is_evictable: false
    track_attribute_changes: false
    enable_pulsehd_collection: false
  }
}
```

### 44. Namespace-Aware Where Clause with kOr and kNot
Source: `workflows/insights/read_write_namespace_for_alerts_usecase.py`

```
query {
  entity_list {
    entity_type_name: "alert_entity"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs {
          leaf {
            column: "is_parent"
            column_namespace: "alert_grouping_rules_np"
          }
        }
        operator: kEQ
        rhs {
          leaf {
            value {
              bool_value: false
            }
          }
        }
      }
    }
    operator: kOr
    rhs {
      lhs {
        comparison_expr {
          lhs {
            leaf {
              column: "is_parent"
              column_namespace: "alert_grouping_rules_np"
            }
          }
          operator: kExists
        }
      }
      operator: kNot
    }
  }
  group_by {
    group_by_column: "severity"
    raw_limit { offset: 0 limit: 10000 }
    raw_columns { column: "cluster_name" }
    raw_columns { column: "severity" }
    raw_columns { column: "acknowledged" }
    raw_sort_order { sort_column: "acknowledged" }
    group_sort_order {
      sort_column: "severity"
      sort_order: kDescending
    }
  }
  query_name: "alert_fetch_all"
}
```

### 45. PutMetricData with Dimension/Fact Metrics
Source: `workflows/insights/put_metric_shard_unload.py`

```
metric_data_sample_list {
  timestamp_usecs: 1234567890000000
  entity_type_name: "fact_entity"
  metric_list: "tenant"
  metric_list: "user"
  metric_list: "bucket_id"
  metric_list: "get_throughput_bytes"
  metric_list: "put_throughput_bytes"
}
```

### 46. Group-By on raw_limit: 0 (Count Only)
Source: `workflows/insights/search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "alert"
  }
  group_by {
    group_by_column: "originating_cluster_uuid"
    raw_limit {
      limit: 0
    }
  }
  query_name: "fetch_originating_cluster_uuids"
}
```

---

## All Available Query Flags:
- `flags: 2` - Return total entity count only (no raw results needed)
- `flags: 4` - Return total group count
- `flags: 16` - Return unfiltered entity count
- `flags: 144` - Return unfiltered entity count + unfiltered group count (16 + 128)

## All Available Sort Keys:
- `kLast` - Sort by last value (default)
- `kLatest` - Sort by latest value (alias for kLast in some contexts)
- `kFirst` - Sort by first value
- `kMin` - Sort by minimum value
- `kMax` - Sort by maximum value

## Additional Pseudo-Columns Found:
- `_shard_id_` - Shard ID (used in watch filters with kIN)
- `_entity_id_` - Entity ID (used in cursor sort and where clause)
- `_entity_type_name_` - Entity type name
- `_arithmos_id_` - Arithmos identifier
- `_master_cluster_uuid_` - Master cluster UUID
- `_cas_value_` - CAS (Compare-And-Swap) value
- `_created_timestamp_usecs_` - Creation timestamp (microseconds)
- `_modified_timestamp_usecs_` - Last modified timestamp (microseconds)

## Additional Entity GUID Fields:
- `entity_type_name` - Required entity type
- `entity_id` - Entity identifier
- `tenant_id` - Tenant identifier (multi-tenancy support)

## Additional UpdateEntity Fields:
- `suppress_replication` - Per-entity replication control
- `expiration_timestamp_usecs` - TTL for the entity
- `full_update` - true = replace all attrs, false = partial update
- `cas_value` - Compare-and-swap value for CAS entities

## Additional RegisterEntityTypes Fields:
- `replication_control_list { enable_replication_from: kNDFS }` - Replication source control
- `enable_pulsehd_collection` - Enable PulseHD data collection
- `suppress_ancestor_tree_traversal` - Optimize by skipping ancestor traversal

## Query-Level Fields:
- `shard_id_list` - Target specific shards for the query

### 36. Multi-Dimensional Grouping (sub_group_by)
Source: `workflows/insights/index_pseudo_suppress_replication.py`

```
# Programmatic construction (no text format):
arg.query.group_by.group_by_column = "attr_1"
arg.query.group_by.sub_group_by.group_by_column = "attr_2"
arg.query.group_by.sub_group_by.sub_group_by.group_by_column = "attr_3"
arg.query.group_by.sub_group_by.sub_group_by.raw_columns.add()
arg.query.group_by.sub_group_by.sub_group_by.raw_columns[-1].column = "attr_name"
```

Equivalent text format:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "attr_str"
    sub_group_by {
      group_by_column: "attr_int"
      sub_group_by {
        group_by_column: "attr_bool"
        raw_columns { column: "attr_str" }
        raw_columns { column: "attr_int" }
        raw_columns { column: "_created_timestamp_usecs_" }
        raw_columns { column: "_suppress_replication_" }
      }
    }
  }
  query_name: "multi_group_by_query"
}
```

### 37. UpdateEntity with Namespace
Source: `workflows/insights/read_write_namespace_for_alerts_usecase.py`

```
entity_guid {
  entity_type_name: "alert"
  entity_id: "some-uuid"
}
namespace: "alert_grouping_rules_np"
attribute_data_arg_list {
  attribute_data {
    name: "is_parent"
    value {
      bool_value: true
    }
  }
}
```

### 38. Entity Type Registration with replication_control_list
Source: `workflows/insights/update_entity_rpc_test.py`

```
entity_type_info_list {
  entity_type_name: "evictable_type"
  type_info {
    track_attribute_changes: false
    suppress_replication: false
    is_evictable: true
    replication_control_list {
      enable_replication_from: kNDFS
    }
    suppress_ancestor_tree_traversal: true
    enable_pulsehd_collection: true
  }
}
```

### 39. Index Type kUInt64
Source: `workflows/insights/update_entity_rpc_test.py`

```
metric_type_list {
  is_attribute: true
  metric_name: "uint64_attr"
  entity_type_name: "test_entity"
  persist_attribute_as_time_series: false
  is_index_column: true
  index_type: kUInt64
}
```

### 40. UpdateEntity with sync_barrier and timestamps
Source: `workflows/insights/update_entity_rpc_test.py`

```
# Programmatic construction:
arg = UpdateEntityArg()
arg.entity_guid.entity_type_name = "entity_type"
arg.entity_guid.entity_id = "some-uuid"
arg.cas_value = 0
arg.full_update = True
arg.sync_barrier = True
arg.created_timestamp_usecs = 1620000000000000
arg.timestamp_usecs = 1620000001000000
arg.suppress_replication = True
```

### 41. _suppress_replication_ Pseudo-Column
Source: `workflows/insights/index_pseudo_suppress_replication.py`

Can be used in where clauses and group-by just like other metadata pseudo-columns:
```
query {
  entity_list {
    entity_type_name: "test_entity"
  }
  group_by {
    group_by_column: "_suppress_replication_"
    raw_columns { column: "attr1" }
    raw_columns { column: "_suppress_replication_" }
  }
  query_name: "group_by_suppress_replication"
}
```

### 42. Alert Group-By with raw_limit: 0 (get all groups with no raw results)
Source: `workflows/insights/mongo/query_bm/alert_query_benchmark.py`

```
query {
  entity_list {
    entity_type_name: "alert"
  }
  group_by {
    group_by_column: "originating_cluster_uuid"
    raw_limit {
      limit: 0
    }
  }
  query_name: "prism:alert_group"
}
```

---

## All Available Metadata Pseudo-Columns (Complete):
- `_entity_id_` - Entity ID
- `_entity_type_name_` - Entity type name
- `_arithmos_id_` - Arithmos identifier
- `_master_cluster_uuid_` - Master cluster UUID
- `_cas_value_` - CAS (Compare-And-Swap) value
- `_created_timestamp_usecs_` - Creation timestamp (microseconds)
- `_modified_timestamp_usecs_` - Last modified timestamp (microseconds)
- `_suppress_replication_` - Boolean indicating if replication is suppressed

## All Available Index Types (Complete):
- `kString` - String index
- `kInt64` - 64-bit integer index
- `kBoolean` - Boolean index
- `kUInt64` - Unsigned 64-bit integer index
- `kBytes` - Bytes index

## All Available Entity Type Registration Fields (Complete):
- `suppress_replication` - Don't replicate to PC
- `is_evictable` - Entity data can be evicted from memory
- `track_attribute_changes` - Track changes to attributes
- `suppress_ancestor_tree_traversal` - Disable ancestor tree traversal
- `enable_pulsehd_collection` - Enable PulseHD collection
- `backup_replication_control { is_backup_required: true }` - Enable backup
- `replication_control_list { enable_replication_from: kNDFS }` - Replication control

## All Available UpdateEntity Fields (Complete):
- `entity_guid` - Entity type name and ID (required)
- `cas_value` - CAS value for compare-and-swap (optional)
- `full_update` - Replace all attributes if true (optional)
- `sync_barrier` - Sync barrier flag (optional)
- `namespace` - Namespace for the update (optional)
- `created_timestamp_usecs` - Explicit creation timestamp (optional)
- `timestamp_usecs` - Explicit modification timestamp (optional)
- `suppress_replication` - Suppress replication for this update (optional)
- `attribute_data_arg_list` - List of attributes to set (optional)

---

## Complete File Coverage Report

---

## 36. Multi-Level Sub-Group-By (Nested 3-Level Grouping)
**Source**: `search_benchmark/queries.py`

Real Prism benchmark query with 3-level nested grouping:
```
query {
  entity_list {
    entity_type_name: "alert"
  }
  where_clause {
    lhs {
      comparison_expr {
        lhs { leaf { column: "resolved" } }
        operator: kEQ
        rhs { leaf { value { bool_value: false } } }
      }
    }
    operator: kAnd
    rhs {
      comparison_expr {
        lhs { leaf { column: "impact_type" } }
        operator: kAny
        rhs {
          leaf {
            value {
              str_list {
                value_list: "Performance"
                value_list: "Capacity"
                value_list: "Configuration"
                value_list: "Availability"
                value_list: "SystemIndicator"
              }
            }
          }
        }
      }
    }
  }
  group_by {
    group_by_column: "cluster"
    sub_group_by {
      group_by_column: "impact_type"
      sub_group_by {
        group_by_column: "severity"
        raw_columns {
          column: "_created_timestamp_usecs_"
        }
        raw_columns {
          column: "__zprotobuf__"
        }
        raw_sort_order {
          sort_column: "_created_timestamp_usecs_"
          sort_order: kAscending
        }
        raw_limit {
          limit: 1
          offset: 0
        }
      }
    }
  }
  query_name: "alert_multi_grouping"
}
```

## 37. Prism Benchmark: Continuous Group-By with Flags
**Source**: `search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    group_by_column: "hypervisor_cpu_usage_ppm"
    group_by_column_type: kContinuous
    num_buckets: 4
    group_sort_order {
      sort_column: "hypervisor_cpu_usage_ppm"
      sort_order: kAscending
    }
  }
  query_name: "vm_continuous_fetch_cpu_usage"
  flags: 2
}
```

## 38. Raw Sort with Limit and sort_key: kLatest
**Source**: `search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "vm"
  }
  group_by {
    raw_columns { column: "vm_name" }
    raw_columns { column: "cluster_name" }
    raw_columns { column: "cluster" }
    raw_columns { column: "hypervisor_cpu_usage_ppm" }
    raw_sort_order {
      sort_column: "hypervisor_cpu_usage_ppm"
      sort_order: kDescending
      sort_key: kLatest
    }
    raw_limit {
      limit: 10
      offset: 0
    }
  }
  query_name: "vm_raw_sort_with_limit"
  flags: 4
}
```

## 39. Timestamped Metric Fetch (start_time/end_time = 0)
**Source**: `search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "vm"
  }
  start_time_usecs: 0
  end_time_usecs: 0
  group_by {
    raw_columns { column: "hypervisor_cpu_usage_ppm" }
    raw_columns { column: "hypervisor_memory_usage_ppm" }
    raw_columns { column: "num_vcpus_used_ppm" }
    raw_columns { column: "hypervisor_num_read_io" }
    raw_columns { column: "hypervisor_num_io" }
  }
  query_name: "vm_timestamped_metric_fetch"
}
```

## 40. Audit Column Fetch with Sort, Where, and Many Raw Columns
**Source**: `search_benchmark/queries.py`

```
query {
  entity_list {
    entity_type_name: "audit"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "target_entity_type" } }
      operator: kEQ
      rhs { leaf { value { str_value: "vm" } } }
    }
  }
  group_by {
    raw_columns { column: "title" }
    raw_columns { column: "user_name" }
    raw_columns { column: "target_entity_name" }
    raw_columns { column: "target_entity_type" }
    raw_columns { column: "cluster" }
    raw_columns { column: "operation_type" }
    raw_columns { column: "op_start_timestamp_usecs" }
    raw_columns { column: "param_name_list" }
    raw_columns { column: "param_value_list" }
    raw_columns { column: "target_entity_uuid" }
    raw_columns { column: "default_message" }
    raw_columns { column: "component" }
    raw_columns { column: "user" }
    raw_columns { column: "client_ip" }
    raw_columns { column: "status" }
    raw_sort_order {
      sort_column: "op_start_timestamp_usecs"
      sort_order: kDescending
    }
    raw_limit {
      limit: 1000
      offset: 0
    }
  }
  query_name: "audit_column_fetch_with_sort"
}
```

## 41. Cursor Query with Where Clause and kContains Operator
**Source**: `cursor_query_eid_sort.py`

```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "int_list_attr" } }
      operator: kContains
      rhs {
        leaf {
          value {
            int64_list {
              value_list: 1
            }
          }
        }
      }
    }
  }
  group_by {
    raw_columns { column: "_entity_id_" }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kAscending
    }
    raw_columns { column: "str_attr" }
    raw_columns { column: "int_attr" }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 2
  }
  query_name: "where_clause_kIN"
  flags: 144
}
```

## 42. Cursor Query with kNE (Not Equal) Operator
**Source**: `cursor_query_eid_sort.py`

```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "str_attr" } }
      operator: kNE
      rhs { leaf { value { str_value: "Apple_2" } } }
    }
  }
  group_by {
    raw_columns { column: "_entity_id_" }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kAscending
    }
    raw_columns { column: "str_attr" }
    raw_columns { column: "int_attr" }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 2
  }
  query_name: "where_clause_not_equal"
  flags: 144
}
```

## 43. Cursor Query Constraints (Validated by Tests)
**Source**: `cursor_query_eid_sort.py`

Key constraints discovered from tests:
- Grouping (group_by_column) is NOT supported with cursor queries: "Cursors are not supported for group-by queries"
- Aggregate columns are NOT supported with cursor queries: "Cursors are not supported for queries with aggregate columns"
- batch_size in secondary cursor queries is ignored (original batch_size from initial query is preserved)
- Cursor query has a 30-second timeout; after that: "Cursor query cache entry not found. Retry afresh."
- Secondary cursor query uses `next_cursor { ... }` from the previous response

## 44. BatchDeleteEntities Pattern
**Source**: `cursor_query_eid_sort.py`

```
entity_list {
  entity_guid {
    entity_type_name: "<entity_type>"
    entity_id: "<entity_id_1>"
  }
}
entity_list {
  entity_guid {
    entity_type_name: "<entity_type>"
    entity_id: "<entity_id_2>"
  }
}
```

## 45. PutMetricData with entity_with_metric_list (Programmatic API)
**Source**: `watches_scenarios.py`

```python
pwm_arg = PutMetricDataArg()
ewm = EntityWithMetric()
entity_guid = EntityGuid()
entity_guid.entity_type_name = "g_child"
entity_guid.entity_id = "<entity_id>"
ewm.entity_guid.CopyFrom(entity_guid)
met = MetricData()
met.name = "metric1"
tvpair = TimeValuePair()
data_value = DataValue()
tvpair.timestamp_usecs = <timestamp>
data_value.int64_value = <value>
tvpair.value.CopyFrom(data_value)
met.value_list.extend([tvpair])
ewm.metric_data_list.extend([met])
pwm_arg.entity_with_metric_list.extend([ewm])
```

## 46. GetEntities with entity_guid_list (Programmatic API)
**Source**: `watches_scenarios.py`, `idf_namespace_attribute_helper.py`

```python
g_arg = GetEntitiesArg()
uid = EntityGuid()
uid.entity_type_name = "g_child"
uid.entity_id = "<entity_id>"
g_arg.entity_guid_list.extend([uid])
ret = insights_interface.GetEntities(g_arg)
```

Text-format equivalent:
```
entity_guid_list {
  entity_type_name: "<entity_type>"
  entity_id: "<entity_id>"
}
```

## 47. UpdateEntity with full_update Flag
**Source**: `watches_scenarios.py`, `create_storage_target_in_idf.py`

`full_update: true` replaces ALL attribute data (not just the ones specified).
`full_update: false` (default) only updates the specified attributes.

```python
u_arg = UpdateEntityArg()
u_arg.entity_guid.CopyFrom(entity_guid)
u_arg.full_update = True
```

## 48. UpdateEntity with Timestamps (created_timestamp_usecs, timestamp_usecs)
**Source**: `time_shift.py`

Four cases of timestamp handling on UpdateEntityArg:
```
# Case 1: Neither timestamp set (server generates both)
entity_guid { entity_type_name: "vm" entity_id: "<id>" }

# Case 2: Only created_timestamp_usecs set
entity_guid { entity_type_name: "vm" entity_id: "<id>" }
created_timestamp_usecs: <usecs>

# Case 3: Only timestamp_usecs (modified timestamp) set
entity_guid { entity_type_name: "vm" entity_id: "<id>" }
timestamp_usecs: <usecs>

# Case 4: Both timestamps set
entity_guid { entity_type_name: "vm" entity_id: "<id>" }
created_timestamp_usecs: <usecs>
timestamp_usecs: <usecs>
```

## 49. suppress_replication on UpdateEntity and DeleteEntity
**Source**: `entity_suppress_replication.py`

UpdateEntity with suppress_replication:
```
entity_guid {
  entity_type_name: "<entity_type>"
  entity_id: "<entity_id>"
}
attribute_data_arg_list {
  attribute_data {
    name: "<attr_name>"
    value {
      str_value: "<value>"
    }
  }
}
suppress_replication: true
```

DeleteEntity with suppress_replication:
```
entity_guid {
  entity_type_name: "<entity_type>"
  entity_id: "<entity_id>"
}
suppress_replication: true
```

## 50. Registration with Namespace on Metric Types
**Source**: `register_namespace_for_alerts_usecase.py`

```
metric_type_list {
  is_attribute: true
  metric_name: "is_parent"
  entity_type_name: "<entity_type>"
  namespace: "alert_grouping_rules_np"
  is_index_column: true
  index_type: kBoolean
}
metric_type_list {
  is_attribute: true
  metric_name: "parent_uuid"
  entity_type_name: "<entity_type>"
  namespace: "alert_grouping_rules_np"
  is_index_column: true
  index_type: kString
}
```

## 51. Registration with Replication Control (kNDFS, allow_entity_deletion_on_replica, direct_purge_on_replica_delete)
**Source**: `register_namespace_for_alerts_usecase.py`, `idf_namespace_attribute_helper.py`

```
entity_type_info_list {
  entity_type_name: "<entity_type>"
  type_info {
    track_attribute_changes: false
    suppress_replication: false
    is_evictable: true
    allow_entity_deletion_on_replica: true
    direct_purge_on_replica_delete: true
    replication_control_list {
      enable_replication_from: kNDFS
    }
  }
}
```

## 52. Registration with parent_list (Entity Hierarchy)
**Source**: `watches_scenarios.py`

```python
reg_ent_type_arg = RegisterEntityTypesArg()
ent_type_info = EntityTypeInfo()
ent_type_info.entity_type_name = entity_type
type_in = TypeInfo()
type_in.parent_list.extend(["parent_entity_type"])
ent_type_info.type_info.CopyFrom(type_in)
reg_ent_type_arg.entity_type_info_list.extend([ent_type_info])
```

## 53. Union Nested Field Info
**Source**: `union_in_nested.py`

Nested field registration with union support for protobuf oneof/union types:
```
metric_type_list {
  is_attribute: true
  metric_name: "valid_union"
  entity_type_name: "<entity_type>"
  nested_field_info {
    base_attribute: "__zprotobuf__"
    nested_field_index: 3
    nested_field_index: 5
    nested_field_type: kString
    union_nested_field_info {
      nested_field_index: 1
      nested_field_type: kString
    }
    union_nested_field_info {
      nested_field_index: 2
      nested_field_type: kString
    }
  }
}
```

## 54. UpdateEntity with __protobuf__ (Serialized Proto Attribute)
**Source**: `create_storage_target_in_idf.py`

Uses `__protobuf__` (not `__zprotobuf__`) for storing serialized protobuf data:
```python
arg = UpdateEntityArg()
arg.entity_guid.entity_type_name = "storage_target"
arg.entity_guid.entity_id = "<uuid>"
arg.full_update = False
arg.cas_value = 0

attr = AttributeDataArg()
value = AttributeData()
value.name = "__protobuf__"
data_value = DataValue()
data_value.bytes_value = proto.SerializeToString()
value.value.CopyFrom(data_value)
attr.attribute_data.CopyFrom(value)
arg.attribute_data_arg_list.extend([attr])
```

## 55. GetMasterLocation RPC
**Source**: `update_new_indexed_attribute.py`

```python
arg = GetMasterLocationArg()
ret = insights_interface.GetMasterLocation(arg)
leader_ip = ret.master_handle.split(':')[0]
```

## 56. user_metadata on RegisterMetricTypes
**Source**: `update_new_indexed_attribute.py`

```
metric_type_list {
  is_attribute: true
  metric_name: "<name>"
  bucketize_timestamps_in_tsdb: false
  entity_type_name: "alert"
  user_metadata: "{\"data_type\":\"string\"}"
  persist_attribute_as_time_series: false
  nested_field_info {
    base_attribute: "__zprotobuf__"
    nested_field_index: 14
    nested_field_type: kString
  }
  is_index_column: true
  index_type: kString
}
```

## 57. Programmatic Entity Registration with CopyFrom/extend
**Source**: `register_indexed_attributes_lookup_queries.py`, `watches_scenarios.py`

```python
register_entity_type_arg = RegisterEntityTypesArg()
entity_type_info = EntityTypeInfo()
entity_type_info.entity_type_name = entity_type
type_in = TypeInfo()
type_in.is_evictable = True
type_in.suppress_replication = False
type_in.track_attribute_changes = False
entity_type_info.type_info.CopyFrom(type_in)
register_entity_type_arg.entity_type_info_list.extend([entity_type_info])
```

## 58. Watch Patterns: Delete Watch on Replica
**Source**: `replica_delete_watches.py`

Demonstrates delete watch behavior across PE/PC:
- Replica delete fires the watch
- Source delete fires the watch
- Duplicate deletes (no-op) do NOT fire the watch
- `is_deleted_on_replica` and `deleted_timestamp_usecs` in delete return

```python
watch_client.watch_delete_entity(e_guid, callback=self.callback)
```

## 59. Registration with enable_pulsehd_collection
**Source**: `rpc_timeout.py`

Complete entity type registration with all TypeInfo fields:
```
entity_type_info_list {
  entity_type_name: "etype"
  type_info {
    suppress_replication: true
    backup_replication_control {
      is_backup_required: false
    }
    replication_control_list {
      enable_replication_from: kNDFS
    }
    is_evictable: false
    track_attribute_changes: false
    enable_pulsehd_collection: false
  }
}
```

## 60. Entity Count Query (raw_limit with limit only)
**Source**: `sync_helper.py`

Minimal query to get entity count for a type using just `raw_limit`:
```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  group_by {
    raw_limit {
      limit: 1
    }
  }
}
```
Note: `offset` is optional in `raw_limit` (defaults to 0).

## 61. Last Modified Timestamp Query
**Source**: `sync_helper.py`

Query to find the most recently modified entity:
```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  group_by {
    raw_columns {
      column: "_modified_timestamp_usecs_"
    }
    raw_limit {
      limit: 1
    }
    raw_sort_order {
      sort_column: "_modified_timestamp_usecs_"
      sort_order: kDescending
    }
  }
}
```

## 62. Large Object Interface (InsightsLargeObjectsInterface)
**Source**: `large_object_helper.py`

IDF supports large object storage via S3-backed attributes:
```python
from insights_interface.insights_large_objects_interface import InsightsLargeObjectsInterface
ilo = InsightsLargeObjectsInterface(host, port)

large_object = insights_interface_pb2.LargeObject()
large_object.metric_name = "<attribute_name>"
large_object.blob = <binary_data>
# or: large_object.blob_file_path = "<file_path>"

update_arg = UpdateEntityArg()
update_arg.entity_guid.entity_type_name = "<entity_type>"
update_arg.entity_guid.entity_id = "<entity_id>"
ilo.update_entity_with_large_objects(update_arg, large_objects_list=[large_object])

# Fetch:
metadata_proto = insights_interface_pb2.LargeObjectMetaData()
metadata_proto.ParseFromString(metadata_bytes)
content = ilo.fetch_large_object(metadata_proto)

# Presigned URL:
url = ilo.fetch_presigned_url(metadata_proto, expire=300)
```

## 63. PutMetricData with metric_data_sample_list (Dimension Metrics)
**Source**: `put_metric_shard_unload.py`

Alternative PutMetricData format for dimension metrics:
```
metric_data_list {
  name: "<metric_name>"
  value_list {
    timestamp_usecs: <ts>
    value {
      int64_value: <value>
    }
  }
}
```

Also dimension-style with metric_data_sample_list:
```
metric_data_sample_list {
  timestamp_usecs: <ts>
  entity_type_name: "<entity_type>"
  metric_list: "tenant"
  metric_list: "user"
  metric_list: "bucket_id"
  metric_list: "get_throughput_bytes"
}
```
With corresponding metric_value_list entries containing str_value or int64_value.

## 64. GetMetricTypes RPC
**Source**: `reset_nested_metric.py`

Query registered metric schemas by regex:
```python
garg = GetMetricTypesArg()
garg.regex = "<metric_name>"
ret = insights.GetMetricTypes(garg)
for mt in ret.metric_type_list:
    print(mt.metric_name, mt.entity_type_name)
    print(mt.nested_field_info.base_attribute)
    print(mt.nested_field_info.nested_field_index)
```

## 65. Cursor Query with Unfiltered Entity Count (flags: 16)
**Source**: `cursor_query_eid_sort.py`

Using `flags: 16` to get `total_unfiltered_entity_count` in cursor queries:
```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  group_by {
    raw_columns { column: "_entity_id_" }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kDescending
    }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 749
  }
  query_name: "primary_cursor_query"
  flags: 16
}
```
Response includes `total_unfiltered_entity_count` field.

## 66. Cursor Query with kAny Operator on str_list
**Source**: `cursor_query_eid_sort.py`

```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "str_list_attr" } }
      operator: kAny
      rhs {
        leaf {
          value {
            str_list {
              value_list: "Apple_4"
              value_list: "Banana_3"
            }
          }
        }
      }
    }
  }
  group_by {
    raw_columns { column: "_entity_id_" }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kDescending
    }
    raw_columns { column: "str_attr" }
    raw_columns { column: "int_attr" }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 2
  }
  query_name: "where_clause_kAny"
  flags: 144
}
```

## 67. Cursor Query with kIN Operator on str_list
**Source**: `cursor_query_eid_sort.py`

```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  where_clause {
    comparison_expr {
      lhs { leaf { column: "str_list_attr" } }
      operator: kIN
      rhs {
        leaf {
          value {
            str_list {
              value_list: "Apple_1"
              value_list: "Banana_2"
            }
          }
        }
      }
    }
  }
  group_by {
    raw_columns { column: "_entity_id_" }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kDescending
    }
    raw_columns { column: "str_attr" }
    raw_columns { column: "int_attr" }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 2
  }
  query_name: "where_clause_kContains"
  flags: 144
}
```

## 68. Cursor Query with Unfiltered Group Count (flags: 144)
**Source**: `cursor_query_eid_sort.py`

Using `flags: 144` (combination of 16 + 128) to get both `total_unfiltered_entity_count` and unfiltered group counts in cursor queries:
```
query {
  entity_list {
    entity_type_name: "<entity_type>"
  }
  group_by {
    raw_columns { column: "_entity_id_" }
    raw_sort_order {
      sort_column: "_entity_id_"
      sort_order: kAscending
    }
  }
  cursor_query_info {
    is_initial_cursor_query: true
    batch_size: 749
  }
  query_name: "primary_cursor_query"
  flags: 144
}
```

## 69. BatchUpdateEntities (Programmatic API)
**Source**: `watches_on_replicated_entities.py`, `segv_repro_621030.py`

```python
batch_arg = BatchUpdateEntitiesArg()
update_arg_list = list()
for eid in eid_list:
    update_arg = UpdateEntityArg()
    update_arg.entity_guid.entity_type_name = "<entity_type>"
    update_arg.entity_guid.entity_id = eid
    update_arg.attribute_data_arg_list.add()
    update_arg.attribute_data_arg_list[0].attribute_data.name = "<attr_name>"
    update_arg.attribute_data_arg_list[0].attribute_data.value.str_value = "<value>"
    update_arg_list.append(update_arg)
batch_arg.entity_list.extend(update_arg_list)
insights.BatchUpdateEntities(batch_arg)
```

## 70. BatchDeleteEntities (Programmatic API)
**Source**: `watches_on_replicated_entities.py`

```python
arg = BatchDeleteEntitiesArg()
delete_args = list()
for eid in eid_list:
    dea = DeleteEntityArg()
    dea.entity_guid.entity_type_name = "<entity_type>"
    dea.entity_guid.entity_id = eid
    delete_args.append(dea)
arg.entity_list.extend(delete_args)
insights.BatchDeleteEntities(arg)
```

## 71. Registration with retain_attributes_on_deletion
**Source**: `segv_repro_621030.py`

```python
arg = RegisterEntityTypesArg()
arg.entity_type_info_list.add()
arg.entity_type_info_list[0].entity_type_name = "<entity_type>"
arg.entity_type_info_list[0].type_info.suppress_replication = True
arg.entity_type_info_list[0].type_info.is_evictable = False
arg.entity_type_info_list[0].type_info.retain_attributes_on_deletion = False
arg.entity_type_info_list[0].type_info.track_attribute_changes = False
arg.entity_type_info_list[0].type_info.enable_pulsehd_collection = False
```

## 72. GetEntitiesWithMetrics with Specific Entity IDs
**Source**: `segv_repro_621030.py`

Querying specific entities by adding entity_id to entity_list items:
```python
arg = GetEntitiesWithMetricsArg()
for each in entity_ids:
    arg.query.entity_list.add()
    arg.query.entity_list[-1].entity_type_name = "<entity_type>"
    arg.query.entity_list[-1].entity_id = each
arg.query.group_by.raw_columns.add()
arg.query.group_by.raw_columns[-1].column = "<attr1>"
arg.query.group_by.raw_columns.add()
arg.query.group_by.raw_columns[-1].column = "<attr2>"
insights.GetEntitiesWithMetrics(arg)
```

Text-format equivalent:
```
query {
  entity_list {
    entity_type_name: "<entity_type>"
    entity_id: "<specific_entity_id>"
  }
  group_by {
    raw_columns { column: "<attr1>" }
    raw_columns { column: "<attr2>" }
  }
}
```

## 73. Watch Updated Entities of Type (with get_current_entities flag)
**Source**: `watches_on_replicated_entities.py`

```python
watch_client.watch_new_entities_of_type(
    "<entity_type>", create_callback, get_current_entities=False)
watch_client.watch_updated_entities_of_type(
    "<entity_type>", update_callback, get_current_entities=True)
```
- `get_current_entities=True`: Returns all existing entities when registering the watch
- `get_current_entities=False`: Only fires for future events

---

## Additional Key Insights (Deep Inspection)

### Query Flags Summary
- `flags: 2` - Used with continuous group-by queries
- `flags: 4` - Used with raw sort + limit queries
- `flags: 16` - Returns `total_unfiltered_entity_count` (entity-level unfiltered count)
- `flags: 128` - Returns unfiltered group counts
- `flags: 144` - Combined 16+128: returns both unfiltered entity count and group counts

### UpdateEntityArg Fields Summary
- `entity_guid` - Required: entity type and ID
- `attribute_data_arg_list` - List of attribute updates
- `cas_value` - Compare-And-Swap value for optimistic concurrency
- `suppress_replication` - Prevent replication to PC
- `full_update` - Replace all attributes (true) vs update specified (false)
- `created_timestamp_usecs` - Override creation timestamp
- `timestamp_usecs` - Override modification timestamp
- `namespace` - Target namespace for attribute updates

### DeleteEntityArg Fields Summary
- `entity_guid` - Required: entity type and ID
- `cas_value` - CAS value for deletion
- `suppress_replication` - Prevent deletion replication

### RegisterEntityTypesArg / TypeInfo Fields Summary
- `entity_type_name` - Entity type name
- `is_evictable` - Whether entities can be evicted
- `suppress_replication` - Disable replication
- `track_attribute_changes` - Track attribute change history
- `allow_entity_deletion_on_replica` - Allow replica-side deletion
- `direct_purge_on_replica_delete` - Purge immediately on replica delete
- `parent_list` - Entity hierarchy parents
- `replication_control_list.enable_replication_from` - Replication source (kNDFS)
- `backup_replication_control.is_backup_required` - Backup requirements
- `suppress_ancestor_tree_traversal` - Performance optimization
- `enable_pulsehd_collection` - Enable/disable PulseHD metrics collection
- `retain_attributes_on_deletion` - Keep attributes after entity deletion

### RegisterMetricTypesArg Fields Summary
- `is_attribute` - true for attributes, false for time-series metrics
- `metric_name` - Name of metric/attribute
- `entity_type_name` - Parent entity type
- `namespace` - Namespace isolation
- `is_index_column` - Enable indexing
- `index_type` - kString, kInt64, kBoolean, kFloat, kDouble, kUInt64, kBytes
- `persist_attribute_as_time_series` - false for latest-value-only attributes
- `bucketize_timestamps_in_tsdb` - TSDB bucketing control
- `user_metadata` - JSON string of user-defined metadata
- `nested_field_info` - For nested protobuf fields (base_attribute, nested_field_index, nested_field_type, has_repeated_fields, union_nested_field_info)
- `contains_serialised_proto` - For serialized proto metrics
- `serialised_proto_compression_type` - Compression for serialized protos
- `derived_metric_expression` - For computed/derived metrics

### DataValue Types Summary
- `str_value` - String
- `int64_value` - 64-bit integer
- `uint64_value` - Unsigned 64-bit integer
- `float_value` - Float
- `double_value` - Double
- `bool_value` - Boolean
- `bytes_value` - Raw bytes
- `str_list.value_list` - List of strings
- `int64_list.value_list` - List of integers

### Special Attributes
- `__zprotobuf__` - Compressed serialized protobuf (most common)
- `__protobuf__` - Uncompressed serialized protobuf
- `_entity_id_` - Pseudo-column for entity ID
- `_created_timestamp_usecs_` - Pseudo-column for creation time
- `_modified_timestamp_usecs_` - Pseudo-column for modification time
- `_cas_value_` - Pseudo-column for CAS value
- `_master_cluster_uuid_` - Pseudo-column for master cluster
- `_suppress_replication_` - Pseudo-column for replication flag

### Available RPCs
- `RegisterEntityTypes` - Register entity type schemas
- `RegisterMetricTypes` - Register metric/attribute schemas
- `UpdateEntity` - Create or update entities
- `DeleteEntity` - Delete a single entity
- `BatchDeleteEntities` - Delete multiple entities
- `GetEntities` - Get entities by GUID list
- `GetEntitiesWithMetrics` - Query entities with columns, filters, grouping, sorting
- `BatchGetEntitiesWithMetrics` - Multiple queries in one call
- `PutMetricData` - Ingest time-series metric data
- `BatchUpdateEntities` - Update multiple entities
- `SpotLightSearch` - Full-text search across entities
- `GetMasterLocation` - Find the IDF master node
- `GetMetricTypes` - Query registered metric schemas
- `GetEntityTypes` - Query registered entity type schemas
- `InsightsLargeObjectsInterface.update_entity_with_large_objects` - Upload large objects
- `InsightsLargeObjectsInterface.fetch_large_object` - Download large objects
- `InsightsLargeObjectsInterface.fetch_presigned_url` - Get presigned URL for large objects

---

## Complete File Coverage Report

### Workflows/insights files with proto queries that were thoroughly inspected:
1. `all_queries.py` - Core query patterns
2. `cursor_query.py` - Cursor query patterns
3. `cursor_query_eid_sort.py` - Cursor with _entity_id_ sort, where clause cursors, BatchDeleteEntities
4. `watches_scenarios.py` - Watch patterns, PutMetricData, GetEntities, full_update
5. `composite_watches.py` - Composite watch patterns
6. `lookup_queries_test.py` - Lookup query patterns
7. `lookup_test.py` - Extended lookup with compound where clauses
8. `having_clause.py` - Having clause patterns
9. `batch_get_entities_with_metrics.py` - Batch query patterns
10. `nested_proto.py` - Nested proto registration and queries
11. `create_and_update_nested_proto.py` - Nested attribute queries
12. `where_clause_bytes_test.py` - Bytes where clause patterns
13. `where_clause_metadata.py` - Metadata pseudo-column queries
14. `nutest_namespace_queries.py` - Namespace attribute queries
15. `sort_on_multiple_columns/query_unevictable_data.py` - Multi-column sort patterns
16. `sort_on_multiple_columns/multisort_namespace_queries.py` - Namespace multi-sort
17. `unfiltered_counts.py` - Group-by with flags and derived metrics
18. `metric_sort_key/metric_sort_key.py` - Metric sort keys (kFirst, kLast, kMin, kMax)
19. `prism_queries.py` - Real-world Prism UI queries
20. `evictable_entities_watches.py` - kExists watch expressions
21. `query_rpc_test.py` - Comprehensive query parameter testing
22. `categories_helpers.py` - ABAC category queries
23. `helper_multi_sort.py` - Multi-sort helper patterns
24. `search_driver.py` - SpotLightSearch entity creation
25. `register_indexed_attributes_cursor_queries.py` - Indexed attribute registration
26. `dynamic_reg_indexed_attr.py` - Dynamic attribute registration
27. `put_metric_shard_unload.py` - PutMetricData with metric_data_sample_list
28. `register_delete_watch.py` - Delete watch registration patterns
29. `replica_delete_watches.py` - Replica delete watch behavior, PE/PC cross-site watches
30. `watch_new_entities_of_type.py` - Entity type watches, programmatic UpdateEntity with all data types
31. `register_namespace_for_alerts_usecase.py` - Namespace metric registration, replication control
32. `register_indexed_attributes_lookup_queries.py` - Programmatic entity/metric registration, lookup queries
33. `idf_namespace_attribute_helper.py` - Namespace attribute helpers, GetEntities, UpdateEntity with namespace
34. `entity_suppress_replication.py` - suppress_replication on UpdateEntity and DeleteEntity
35. `reset_nested_metric.py` - GetMetricTypes, nested_field_info reset
36. `union_in_nested.py` - union_nested_field_info registration
37. `time_shift.py` - Timestamp handling on UpdateEntityArg (created_timestamp_usecs, timestamp_usecs)
38. `update_new_indexed_attribute.py` - GetMasterLocation, user_metadata, nested indexed attributes
39. `search_benchmark/queries.py` - Full Prism benchmark queries (9 queries), multi-level sub_group_by
40. `search_benchmark/utilities.py` - DataGenerator, all data value types
41. `create_storage_target_in_idf.py` - __protobuf__ attribute, full_update, cas_value on UpdateEntity
42. `sort_multiple_raw_cols.py` - Multi-column sort helper framework
43. `large_object_helper.py` - InsightsLargeObjectsInterface usage
44. `nested_field_proto.py` - Nested field registration patterns
45. `update_entity_rpc_test.py` - Comprehensive UpdateEntity testing
46. `update_bytes_value.py` - bytes_value updates
47. `read_write_namespace_for_alerts_usecase.py` - Namespace reads/writes
48. `watches_on_shards.py` - Shard-level watch patterns
49. `index_pseudo_suppress_replication.py` - Pseudo-column indexing, sub_group_by

50. `rpc_timeout.py` - Registration with enable_pulsehd_collection, backup_replication_control
51. `sync_helper.py` - raw_limit with only limit (no offset), _modified_timestamp_usecs_ queries
52. `validate_stat_population.py` - Extensive real-world metric name lists (cluster, VM)
53. `fetch_entities_from_s3_dump.py` - LoadEntityTrailRet, S3 backup entity parsing
54. `watches_on_replicated_entities.py` - BatchUpdateEntities, BatchDeleteEntities, watch_updated_entities_of_type
55. `segv_repro_621030.py` - retain_attributes_on_deletion, BatchUpdateEntities, GetEntitiesWithMetrics with entity IDs
56. `watches_load.py` - Watch load testing patterns
57. `watch_race_test.py` - Watch race condition tests

### Testcases/insights files inspected:
1. `test_cas_entities.py`
2. `test_non_cas.py`
3. `test_groupby.py`
4. `test_comparison_operators.py`
5. `test_spotlight_entity_search.py`
6. `test_query_layer_with_aggregation.py`
7. `test_where_clause.py`
8. `test_cursor_queries.py`
9. `test_watches_scenarios.py`
10. `test_lookup.py`
11. `test_having_clause.py`
