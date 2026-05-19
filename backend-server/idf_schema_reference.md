# IDF Schema Reference

> Companion document to [nutest_extracted_queries.md](nutest_extracted_queries.md) which contains query patterns.
> This document covers protobuf schema definitions, enums, RPCs, and the live cluster entity/attribute registry.

**Source**: `ntnxdb_client/insights/insights_interface/insights_interface.proto`
**Cluster**: `10.46.30.35` (Prism Central)
**Config files**: `cluster_schemas/entity_type_config.proto`, `entity_attribute_config.proto`, `arithmos_entity_operation.proto`

---

# Part 1: Proto Schema Reference

## 1A. RPC Service Definitions

The `InsightsRpcSvc` service defines all RPCs. Default timeout: 30,000ms. Default max retries: 0.

### Entity Management RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `RegisterEntityTypes` | `RegisterEntityTypesArg` | `RegisterEntityTypesRet` | Register new entity types or update existing ones. Changes are NOT retroactive. |
| `GetEntityTypes` | `GetEntityTypesArg` | `GetEntityTypesRet` | Get entity types. If no name specified, returns all. |
| `UpdateEntity` | `UpdateEntityArg` | `UpdateEntityRet` | Create or update a single entity. |
| `BatchUpdateEntities` | `BatchUpdateEntitiesArg` | `BatchUpdateEntitiesRet` | Create/update multiple entities. Each update atomic, no cross-batch guarantees. |
| `DeleteEntity` | `DeleteEntityArg` | `DeleteEntityRet` | Delete a single entity. Must be leaf in entity tree. |
| `BatchDeleteEntities` | `BatchDeleteEntitiesArg` | `BatchDeleteEntitiesRet` | Delete multiple entities. Each deletion independent. |
| `AttachEntity` | `AttachEntityArg` | `AttachEntityRet` | Attach entity from another cluster (entity move workflow). |
| `DetachEntity` | `DetachEntityArg` | `DetachEntityRet` | Detach entity for move to another cluster. |
| `GetEntities` | `GetEntitiesArg` | `GetEntitiesRet` | Fetch entities by GUID list. NOT for dimension-fact tables. |
| `GetEntitiesTrail` | `GetEntitiesTrailArg` | `GetEntitiesTrailRet` | Fetch entity attribute change trail in a time window. |

### Metric/Attribute Management RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `RegisterMetricTypes` | `RegisterMetricTypesArg` | `RegisterMetricTypesRet` | Register metrics/attributes for entity types. |
| `UnregisterMetricTypes` | `UnregisterMetricTypesArg` | `UnregisterMetricTypesRet` | Unregister metric types by name. |
| `GetMetricTypes` | `GetMetricTypesArg` | `GetMetricTypesRet` | Get metric types matching a substring (not full regex). |

### Query RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `GetEntitiesWithMetrics` | `GetEntitiesWithMetricsArg` | `GetEntitiesWithMetricsRet` | Query entities with columns, filters, grouping, sorting, time ranges. |
| `SpotLightSearch` | `SpotLightSearchArg` | `SpotLightSearchRet` | Full-text case-insensitive search across entity string attributes. |
| `PutMetricData` | `PutMetricDataArg` | `PutMetricDataRet` | Ingest time-series metric data and dimension-fact samples. |
| `GetMetricData` | `GetMetricDataArg` | `GetMetricDataRet` | Get raw/downsampled metric data for entities. |

### Watch RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `RegisterWatchClient` | `RegisterWatchClientArg` | `RegisterWatchClientRet` | Register a watch client session. |
| `UnregisterWatchClient` | `UnregisterWatchClientArg` | `UnregisterWatchClientRet` | Unregister client, remove all watches. |
| `RegisterWatch` | `RegisterWatchArg` | `RegisterWatchRet` | Register watches for a client. Returns current state if requested. |
| `UnregisterWatch` | `UnregisterWatchArg` | `UnregisterWatchRet` | Unregister specific watches by name/id. |
| `GetFiredWatchList` | `GetFiredWatchListArg` | `GetFiredWatchListRet` | Long-poll to get fired watches since a sequence number. |

### Cluster Management RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `GetMasterLocation` | `GetMasterLocationArg` | `GetMasterLocationRet` | Find the IDF master node handle and incarnation_id. |
| `GetNodeMapEntryProto` | `GetNodeMapEntryProtoArg` | `GetNodeMapEntryProtoRet` | Get the IDF node map (node handles + shard assignments). |
| `GetAllShardIds` | `GetAllShardIdsArg` | `GetAllShardIdsRet` | Get all available shard IDs as strings. |
| `GetInternalState` | `GetInternalStateArg` | `GetInternalStateRet` | Retrieve internal state from cluster nodes (memory, stats, version). |
| `ReplicateEntities` | `ReplicateEntitiesArg` | `ReplicateEntitiesRet` | Replicate entities from master cluster. Returns pre-replication state. |
| `SyncUpdateEntity` | `SyncUpdateEntityArg` | `SyncUpdateEntityRet` | Sync entity updates via Nusights Collector Framework. |

### Global Data / Lock RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `WriteLockGlobalData` | `WriteLockGlobalDataArg` | `WriteLockGlobalDataRet` | Acquire/renew a global write lock. Returns lock_id and ttl. |
| `WriteUnlockGlobalData` | `WriteUnlockGlobalDataArg` | `WriteUnlockGlobalDataRet` | Release a global write lock. |
| `InitGlobalDataStaging` | `InitGlobalDataStagingArg` | `InitGlobalDataStagingRet` | Initiate global data staging process. |
| `CommitGlobalDataStaging` | `CommitGlobalDataStagingArg` | `CommitGlobalDataStagingRet` | Commit global data staging. |
| `FlushGlobalData` | `FlushGlobalDataArg` | `FlushGlobalDataRet` | Flush global data from master to replica. Initiated at replica. |

### Event/Log RPCs

| RPC | Arg | Ret | Description |
|-----|-----|-----|-------------|
| `PutEvent` | `PutEventArg` | `PutEventRet` | Persist structured events (Nusights only). |
| `PutLog` | `PutLogArg` | `PutLogRet` | Persist log messages (Nusights only). |

---

## 1B. Core Message Definitions

### DataValue

Represents all supported data types. Uses `oneof ValueType` (exactly one field set).

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `str_value` | `string` | 16 | String value |
| `int64_value` | `int64` | 17 | Signed 64-bit integer |
| `bool_value` | `bool` | 18 | Boolean |
| `uint64_value` | `uint64` | 19 | Unsigned 64-bit integer |
| `float_value` | `float` | 20 | 32-bit float |
| `double_value` | `double` | 21 | 64-bit double |
| `bytes_value` | `bytes` | 22 | Raw bytes blob (cannot be used in filters/group-by) |
| `str_list` | `StrList` | 23 | `repeated string value_list` |
| `int64_list` | `Int64List` | 24 | `repeated int64 value_list` |
| `bool_list` | `BoolList` | 25 | `repeated bool value_list` |
| `uint64_list` | `UInt64List` | 26 | `repeated uint64 value_list` |
| `float_list` | `FloatList` | 27 | `repeated float value_list` |
| `double_list` | `DoubleList` | 28 | `repeated double value_list` |
| `bytes_list` | `BytesList` | 29 | `repeated bytes value_list` |
| `json_obj` | `bytes` | 30 | Marshalled JSON object stored as bytes |
| `histogram_obj` | `Histogram` | 31 | Histogram data (cumulative or count-based) |

**Histogram** sub-message:
- `bucket_upper_bounds_list` (FloatList) -- for cumulative histograms
- `bucket_keys_list` (StrList) -- for count-based histograms
- `bucket_counts_list` (repeated uint64) -- counts per bucket

### EntityGuid

Uniquely identifies an entity.

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `entity_type_name` | `string` | 1 | Required. Entity type (e.g., "vm", "node", "cluster") |
| `entity_id` | `string` | 2 | Optional. If omitted, represents all entities of the type. |
| `tenant_id` | `string` | 3 | Optional. Tenant isolation. Empty string = global tenant. Unset = any tenant. |

### UpdateEntityArg

Create or update an entity. Apps can atomically update only one namespace.

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `entity_guid` | `EntityGuid` | 1 | -- | Required. Entity identity. |
| `timestamp_usecs` | `uint64` | 2 | -- | Optional. Modified timestamp. Server sets if omitted. |
| `cas_value` | `uint64` | 3 | -- | Optional. CAS value for optimistic concurrency. Start at 0, increment by 1. |
| `created_timestamp_usecs` | `uint64` | 4 | -- | Optional. Cannot be later than modified timestamp. |
| `attribute_data_arg_list` | `repeated AttributeDataArg` | 5 | -- | Optional. Attributes to set or clear. |
| `full_update` | `bool` | 6 | `true` | Optional. true = replace ALL attributes; false = update only specified. |
| `namespace` | `string` | 7 | `"_default_"` | Optional. Target namespace for attribute updates. |
| `expiration_timestamp_usecs` | `uint64` | 8 | -- | Optional. Auto-delete entity after this time. Unset = clear previous. |
| `sync_barrier` | `bool` | 9 | `false` | Optional. Ensure all previous modifications replicated before this one. |
| `global_data_lock_id` | `string` | 10 | -- | Optional. Must match current lock for global data writes. |
| `suppress_replication` | `bool` | 11 | `false` | Optional. Prevent this entity from being replicated. |

### AttributeDataArg

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `operation` | `AttributeOperation` | 1 | `kSET` | `kSET` to set value, `kCLEAR` to clear. |
| `attribute_data` | `AttributeData` | 2 | -- | Required. Name and value of the attribute. |

### AttributeData

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `name` | `string` | 1 | Required. Attribute name. |
| `value` | `DataValue` | 2 | Optional. Set if operation is kSET. |

### DeleteEntityArg

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `entity_guid` | `EntityGuid` | 1 | -- | Required. |
| `timestamp_usecs` | `uint64` | 2 | -- | Optional. Delete timestamp. Server sets if omitted. |
| `cas_value` | `uint64` | 3 | -- | Optional. Required for CAS entities. |
| `namespace` | `string` | 4 | -- | Optional. If unset or `_default_`, deletes entire entity. Otherwise deletes only that namespace. |
| `sync_barrier` | `bool` | 5 | `false` | Optional. Sync barrier semantics. |
| `global_data_lock_id` | `string` | 6 | -- | Optional. Global data lock credential. |
| `suppress_replication` | `bool` | 7 | `false` | Optional. Suppress deletion replication. |

### BatchUpdateEntitiesArg / BatchDeleteEntitiesArg

Both contain `repeated <EntityArg> entity_list`. Each operation is atomic individually but no cross-batch atomicity. Order not guaranteed.

### RegisterEntityTypesArg

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `entity_type_info_list` | `repeated EntityTypeInfo` | 1 | Required. List of entity types to register/update. |

### EntityTypeInfo

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `entity_type_name` | `string` | 1 | Required. Must be unique, lowercase convention. |
| `type_info` | `TypeInfo` | 2 | Required. Entity type properties. |

### TypeInfo (Complete Field Reference)

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `parent_list` | `repeated string` | 1 | -- | Parent entity types. Parents must be registered first. |
| `track_attribute_changes` | `bool` | 2 | `true` | Track attribute/relationship changes over time in entity trail log. |
| `shard_strategy` | `EntityTypeShard` | 3 | -- | How entities are sharded in multi-node deployment. |
| `suppress_replication` | `bool` | 4 | `false` | Suppress DB-to-DB replication. |
| `is_dimension_fact_table` | `bool` | 5 | `false` | Entity type holds dimensions-facts table config. |
| `is_evictable` | `bool` | 6 | `false` | Entities can be evicted from in-memory cache. Cannot change after registration. |
| `replication_control_list` | `repeated ReplicationControl` | 7 | -- | Cluster configurations where replication is enabled. |
| `deleted_entity_retention_in_secs` | `uint32` | 8 | -- | TTL for deleted entities cleanup. Falls back to gflag if unset. |
| `suppress_ancestor_tree_traversal` | `bool` | 9 | `false` | Suppress walking relationship graph for ancestor attributes in queries. |
| `enable_pulsehd_collection` | `bool` | 10 | `false` | Enable PulseHD data collection for this entity type. |
| `tenant_specific` | `bool` | 11 | `false` | Entity type is tenant-specific. |
| `enable_pulsehd_condition` | `BooleanExpression` | 12 | -- | Conditional PulseHD collection based on attribute values. |
| `enable_pulsehd_metric_collection` | `bool` | 13 | `false` | Enable PulseHD metric collection (requires enable_pulsehd_collection=true). |
| `entity_loading_priority` | `int32` | 14 | `0` | Bootstrap/shard loading priority. 0 = highest. Larger = lower priority. |

### ReplicationControl

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `enable_replication_from` | `ClusterFunctions` | 1 | Source cluster type for replication. |
| `enable_replication_to` | `ClusterFunctions` | 2 | Target cluster type (federation mode). |

### EntityTypeShard

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `shard_type` | `ShardType` | 1 | `kTokenRange` | `kTokenRange` = hash-based; `kEntityType` = relationship-based. |
| `shard_entity_type_name` | `string` | 2 | -- | For kEntityType: the related entity type for sharding. Self-reference = anchor entity. |

### MetricType (Complete Field Reference)

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `is_attribute` | `bool` | 1 | `false` | true = attribute (CAS, RF3, write-through); false = stat (eventual, RF2, batched). |
| `metric_name` | `string` | 2 | -- | Required. Name of the metric. |
| `entity_type_name` | `string` | 8 | -- | Required. Parent entity type. |
| `unit` | `string` | 3 | -- | Optional. Display unit. |
| `aggregation_operator` | `Operator` | 4 | -- | Default aggregation operator across entities. |
| `down_sampling_interval_in_secs` | `uint32` | 5 | `30` | Stats only. Bucket interval for downsampling. |
| `down_sampling_operator` | `Operator` | 6 | `kLast` | Stats only. Operator for multiple values in one interval. |
| `query_down_sampling_operator` | `Operator` | 26 | -- | Stats only. Override downsampling operator for queries. |
| `bucketize_timestamps_in_tsdb` | `bool` | 7 | `true` | Stats only. false = precise timestamps in TSDB. |
| `user_metadata` | `string` | 9 | -- | JSON string of user-defined metadata (e.g., `{"data_type":"string"}`). |
| `is_derived_metric` | `bool` | 10 | `false` | Set for derived metrics. |
| `derived_metric_rollup_query` | `Query` | 11 | -- | Roll-up derived metric query (group-by on ancestor + single aggregation). |
| `derived_metric_expression` | `Expression` | 12 | -- | Per-entity derived metric arithmetic expression. |
| `raw_retention_in_weeks` | `uint32` | 13 | -- | Override raw data retention period. |
| `hourly_retention_in_weeks` | `uint32` | 14 | -- | Override hourly data retention period. |
| `is_wildcard_searchable` | `bool` | 15 | `true` | Include in SpotLightSearch and wildcard LIKE queries. |
| `persist_attribute_as_time_series` | `bool` | 16 | -- | Attributes only. Persist attribute changes as time-series data. |
| `contains_serialised_proto` | `bool` | 17 | `false` | Attribute contains serialized protobuf bytes. |
| `nested_field_info` | `NestedFieldInfo` | 18 | -- | For attributes derived from nested protobuf fields. |
| `serialised_proto_compression_type` | `CompressionType` | 19 | `kNone` | Compression for serialized proto values. |
| `namespace` | `string` | 20 | `"_default_"` | Namespace isolation. Same metric name in different namespaces = different metrics. |
| `enable_metricdata_rpc` | `bool` | 21 | `true` | Override gflag to enable MetricData RPC. |
| `is_index_column` | `bool` | 22 | `false` | Create inverted index. Attributes only. |
| `index_type` | `IndexType` | 23 | -- | Required for index columns: kInt64, kString, kUInt64, kBoolean. |
| `pii_type` | `PiiType` | 24 | `kDoesNotContainPII` | PII protection policy. |
| `pii_regex_for_value` | `string` | 25 | `".*"` | Regex for conditional PII masking/removal. |
| `parent_type_name` | `string` | 28 | -- | Alias for ancestor references. |
| `mask_type` | `MaskType` | 30 | `kDefaultMask` | Specific mask pattern (IP, email, name). |
| `ttl_calculation` | `TtlCalculation` | 27 | `kTimestampBased` | TTL calculation mode for retention. |
| `category` | `Category` | 29 | `kRealTime` | kRealTime or kAnalytics. |

### NestedFieldInfo

For attributes parsed from serialized protobuf fields.

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `base_attribute` | `string` | 1 | -- | Required. Attribute holding the serialized proto (e.g., `__zprotobuf__`). |
| `nested_field_index` | `repeated uint32` | 2 | -- | Required. Field positions from top-level proto to target field. |
| `nested_field_type` | `ValueType` | 3 | `kString` | Data type of the nested field value. |
| `has_repeated_fields` | `bool` | 4 | `false` | true if the field or any parent is repeated. Values stored as list type. |
| `union_nested_field_info` | `repeated UnionNestedFieldInfo` | 5 | -- | For protobuf oneof/union fields. Currently only supported at leaf level. |
| `nested_field_option` | `FieldOption` | 6 | `kLast` | When has_repeated_fields=false but multiple values found: kFirst or kLast. |

### UnionNestedFieldInfo

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `nested_field_index` | `repeated uint32` | 1 | -- | Continuation of path from fork point. Single index only (leaf unions). |
| `nested_field_type` | `ValueType` | 2 | `kString` | Source data type for this union branch. |

### Entity (Response Message)

Returned by UpdateEntity, DeleteEntity, GetEntities, etc.

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `entity_guid` | `EntityGuid` | 1 | Required. Identity. |
| `created_timestamp_usecs` | `uint64` | 2 | Creation time. |
| `modified_timestamp_usecs` | `uint64` | 3 | Last modification time. |
| `deleted_timestamp_usecs` | `uint64` | 4 | Deletion time (if deleted). |
| `cas_value` | `uint64` | 5 | Current CAS value (CAS entities only). |
| `attribute_data_map` | `repeated NameTimeValuePair` | 7 | Attribute names, values, and timestamps. |
| `master_cluster_uuid` | `string` | 8 | Set for replicated entities. |
| `db_modified_timestamp_usecs` | `uint64` | 9 | Server modification time (set by database). |
| `moved_to_cluster_uuid` | `string` | 10 | Target cluster UUID for detached entities. |
| `incarnation_id` | `uint64` | 11 | Incremented on entity move between clusters. |
| `entity_namespace_list` | `repeated EntityNamespace` | 12 | Auxiliary namespace data (Nusights). |
| `expiration_timestamp_usecs` | `uint64` | 13 | Auto-delete time if set. |
| `sync_barrier_info` | `repeated SyncBarrierInfo` | 14 | Per-shard sync barrier timestamps. |
| `first_synced_timestamp_usecs` | `uint64` | 15 | First replication time on replica. |
| `last_synced_timestamp_usecs` | `uint64` | 16 | Most recent replication time on replica. |
| `suppress_replication` | `bool` | 17 | Per-entity replication suppression. |

### EntityNamespace

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `namespace` | `string` | 1 | Required. Unique within entity. Cannot be `_default_`. |
| `created_timestamp_usecs` | `uint64` | 2 | Namespace creation time. |
| `modified_timestamp_usecs` | `uint64` | 3 | Last modification time. |
| `deleted_timestamp_usecs` | `uint64` | 4 | Deletion time. |
| `cas_value` | `uint64` | 5 | CAS value for namespace. |
| `attribute_data_map` | `repeated NameTimeValuePair` | 6 | Namespace-scoped attributes. |

### GetEntitiesArg

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `entity_guid_list` | `repeated EntityGuid` | 1 | -- | If empty, returns all entities. If only type set, all of that type. |
| `meta_data_only` | `bool` | 2 | `false` | Return only metadata, no attributes. |
| `timestamp_usecs` | `uint64` | 3 | -- | Return entities as-of this timestamp. |
| `include_deleted_entities` | `bool` | 4 | `false` | Include deleted entities in results. |
| `global_data_read_consistency` | `GlobalDataReadConsistency` | 6 | `kEventual` | kStrict forwards to master. |

### PutMetricDataArg

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `entity_with_metric_list` | `repeated EntityWithMetric` | 1 | -- | For regular entities (is_dimension_fact_table=false). |
| `is_replicated` | `bool` | 2 | `false` | Set for replicated entities. |
| `metric_data_sample_list` | `repeated MetricDataSample` | 3 | -- | For dimension-fact table entities. |

### EntityWithMetric

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `entity_guid` | `EntityGuid` | 1 | Required. Entity identity. |
| `metric_data_list` | `repeated MetricData` | 3 | Metric name + time-value pairs. |

### MetricData

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `name` | `string` | 1 | -- | Required. Metric name. |
| `namespace` | `string` | 3 | `"_default_"` | Namespace (Nusights). |
| `value_list` | `repeated TimeValuePair` | 2 | -- | Time-value pairs. |

### TimeValuePair

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `timestamp_usecs` | `uint64` | 1 | Required. Timestamp in microseconds. |
| `value` | `DataValue` | 2 | Required. The data value. |

### SpotLightSearchArg

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `search_term` | `string` | 1 | Case-insensitive search across string attributes. Omit = return all. |
| `entity_type_name_list` | `repeated string` | 2 | Limit search to specific entity types. |
| `scope_entity_list` | `repeated EntityGuid` | 3 | Scope to entities matching or descending from these. |
| `search_attribute_name_list` | `repeated string` | 4 | Search only specific attributes. |
| `search_attribute_namespace_list` | `repeated MetricNamespacePair` | 10 | Namespace-aware attribute search list. |
| `extra_return_attribute_list` | `repeated string` | 5 | Extra attributes to return (e.g., friendly names). |
| `extra_return_attribute_namespace_list` | `repeated MetricNamespacePair` | 11 | Namespace-aware extra return list. |
| `limit` | `QueryLimit` | 6 | Limit and offset for pagination. |
| `relevant_attribute_list` | `repeated AttributeRelevanceInfo` | 7 | Rank boosting for specific attributes (relevance_factor 1-3). |
| `relevant_ancestor_list` | `repeated EntityRelevanceInfo` | 8 | Rank boosting for specific ancestor entities. |
| `search_on_entity_type_list` | `repeated SearchOnEntityType` | 9 | Per-entity-type search configuration. |

### AttachEntityArg / DetachEntityArg

- `AttachEntity`: wraps `UpdateEntityArg` + `incarnation_id` (must be greater than detached entity's).
- `DetachEntity`: wraps `DeleteEntityArg` + `moved_to_cluster_uuid`.

### GetMetricTypesArg

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `regex` | `string` | 1 | Substring match (not full regex) against metric names. Omit = return all. |

---

## 1C. Query Message Definitions

### Query

The primary query message for `GetEntitiesWithMetrics` RPC.

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `entity_list` | `repeated EntityGuid` | 1 | -- | Required. All must be same entity type. Empty entity_id = all of that type. |
| `start_time_usecs` | `uint64` | 2 | `0` | Start of time range. 0 = NOW (must pair with end_time_usecs=0 for latest). |
| `end_time_usecs` | `uint64` | 3 | `0` | End of time range (exclusive). Range: [start, end). |
| `num_intervals_for_latest_data` | `int32` | 8 | `10` | Number of sampling intervals before wallclock considered for latest data. |
| `where_clause` | `BooleanExpression` | 4 | -- | Predicates to include/exclude entities. |
| `group_by` | `QueryGroupBy` | 5 | -- | Grouping, aggregation, raw column selection, sorting, limits. |
| `query_name` | `string` | 6 | -- | Optional name for the query. |
| `from_clause` | `repeated Query` | 7 | -- | Recursive/nested queries (preprocessed metrics only, max 1). |
| `shard_id_list` | `repeated string` | 9 | -- | Restrict to specific shards (use with GetAllShardIds for fan-out). |
| `flags` | `uint64` | 10 | `0` | Bitwise OR of FlagTypes. |
| `priority` | `int64` | 11 | `0` | 0 = high (UI), 1 = low (background/capacity planning). |
| `global_data_read_consistency` | `GlobalDataReadConsistency` | 13 | `kEventual` | kStrict forwards reads to the master node. |

### QueryGroupBy

Defines grouping, aggregation columns, raw columns, and sorting within a query.

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `group_by_column` | `string` | 1 | -- | Column for grouping. If unset = raw query (no grouping). |
| `group_by_column_type` | `GroupByColumnType` | 2 | `kDiscrete` | kDiscrete = exact match; kContinuous = bucket-based. |
| `num_buckets` | `uint32` | 3 | -- | Required for kContinuous. Number of buckets for value range. |
| `bucket_boundary` | `uint32` | 4 | -- | Round bucket boundaries to this value for user-friendliness. |
| `aggregate_columns` | `repeated QueryAggregateColumn` | 5 | -- | Columns to aggregate per group. |
| `group_sort_order` | `QueryOrderBy` | 6 | -- | Sort groups by group_by_column or an aggregate column. |
| `group_limit` | `QueryLimit` | 7 | -- | Max groups to return. |
| `raw_columns` | `repeated QueryRawColumn` | 8 | -- | Columns whose raw values to return per entity. |
| `down_sampling_interval_secs` | `uint32` | 9 | -- | Downsampling interval for metric data. |
| `raw_sort_order` | `QueryOrderBy` | 10 | -- | Sort entities within each group. |
| `raw_limit` | `QueryLimit` | 11 | -- | Limit entities per group. |
| `store_ds_interval` | `MetricDataDownSamplingInterval` | 12 | -- | Override downsampling interval from store. |
| `group_by_column_namespace` | `string` | 13 | `"_default_"` | Namespace for the group-by column (Nusights). |
| `sub_group_by` | `QueryGroupBy` | 14 | -- | Multi-dimensional grouping (nested). |
| `suppress_ancestor_tree_traversal` | `bool` | 15 | `false` | Use direct attribute value instead of ancestor relationship for grouping. |
| `bucket_interval_separators` | `repeated DataValue` | 16 | -- | Custom bucket boundaries for continuous grouping (int64 values, ascending). |

### BooleanExpression

Recursive tree of logical operators and comparison expressions.

```
Grammar:
  BooleanExpression → BooleanExpression BooleanOperator BooleanExpression
                    | NOT BooleanExpression
                    | ComparisonExpression
  BooleanOperator   → AND | OR
```

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `lhs` | `BooleanExpression` | 1 | Left operand (for AND/OR). |
| `operator` | `Operator` | 2 | kAnd, kOr, or kNot. |
| `rhs` | `BooleanExpression` | 3 | Right operand (for AND/OR). |
| `comparison_expr` | `ComparisonExpression` | 4 | Leaf comparison (terminal node). |

### ComparisonExpression

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `lhs` | `Expression` | 1 | Left operand (typically a column reference). |
| `operator` | `Operator` | 2 | Comparison operator (see enum below). |
| `rhs` | `Expression` | 3 | Right operand (typically a value). |

**ComparisonExpression.Operator Enum:**

| Enum | Value | Description |
|------|-------|-------------|
| `kEQ` | 0 | Equal |
| `kNE` | 1 | Not equal |
| `kLT` | 2 | Less than |
| `kLE` | 3 | Less than or equal |
| `kGT` | 4 | Greater than |
| `kGE` | 5 | Greater than or equal |
| `kLike` | 6 | Regex match. Wildcard (no column) = search all attributes. |
| `kContains` | 7 | RHS is a subset of LHS values (LHS list contains all RHS elements). |
| `kIN` | 8 | LHS is a subset of RHS values (entity's values are within RHS set). |
| `kAny` | 9 | Intersection of LHS and RHS is non-empty. For entity types, LHS = ancestor UUIDs. |
| `kExists` | 10 | Unary: checks existence of column value (no RHS needed). |
| `kChanged` | 11 | Unary: checks attribute changed from previous value. Watches only, not queries. |

### Expression

Arithmetic expression tree for derived metrics and computed values.

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `lhs` | `Expression` | 1 | Left operand. |
| `operator` | `Operator` | 2 | kPlus, kMinus, kMult, kDiv, kMod, kConcat. |
| `rhs` | `Expression` | 3 | Right operand. |
| `leaf` | `LeafExpression` | 4 | Terminal: column reference or literal value. |

### LeafExpression

Terminal node in the expression tree.

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `column` | `string` | 1 | -- | Column/attribute name. Either column or value must be set. |
| `value` | `DataValue` | 2 | -- | Literal value. Either column or value must be set. |
| `column_namespace` | `string` | 3 | `"_default_"` | Namespace for the column (Nusights). |
| `suppress_ancestor_tree_traversal` | `bool` | 4 | `false` | Use direct attribute value for entity type columns instead of ancestor walk. |

### QueryAggregateColumn

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `column` | `string` | 1 | -- | Required. Column to aggregate. |
| `operator` | `MetricType.Operator` | 2 | -- | Aggregation operator override. |
| `down_sampling_operator` | `MetricType.Operator` | 3 | -- | Downsampling operator override. |
| `column_namespace` | `string` | 4 | `"_default_"` | Namespace (Nusights). |
| `ancestor_entity_type` | `string` | 5 | -- | For ancestor joins: return ancestor's column value as summary. |
| `ignore_missing_values` | `bool` | 6 | `false` | true = skip missing timestamps; false = fill with previous value. |

### QueryRawColumn

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `column` | `string` | 1 | -- | Required. Column whose raw values to return. |
| `down_sampling_operator` | `MetricType.Operator` | 2 | -- | Override downsampling operator. |
| `column_namespace` | `string` | 3 | `"_default_"` | Namespace (Nusights). |

### QueryOrderBy

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `sort_column` | `string` | 1 | -- | Column to sort by. |
| `sort_order` | `SortOrder` | 2 | `kAscending` | kAscending or kDescending. |
| `sort_key` | `SortKey` | 3 | `kLast` | Time-series mapping: kMax, kMin, kFirst, kLast, kLatest, kAvg. |
| `sort_column_namespace` | `string` | 4 | `"_default_"` | Namespace (Nusights). |

### QueryLimit

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `limit` | `int64` | 1 | Max results to return after sorting. |
| `offset` | `int64` | 2 | Number of results to skip (for cursor/pagination). |

### GetEntitiesWithMetricsArg

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `query` | `Query` | 1 | Required. The query plan. |
| `properties` | `QueryProperties` | 2 | Optional. Additional parameters (depth, hashed range, sampling). |

### GetEntitiesWithMetricsRet

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `group_results_list` | `repeated QueryGroupResult` | 1 | Results grouped per query definition. |
| `total_group_count` | `int64` | 2 | Total groups (may exceed returned count due to group_limit). |
| `down_sampling_params` | `repeated DownSamplingParameters` | 3 | Actual downsampling parameters used. |
| `rpc_execution_time_usecs` | `uint64` | 4 | Server-side execution time. |

### QueryGroupResult

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `group_by_column_value` | `DataValue` | 1 | Value identifying this group (discrete) or bucket lower bound (continuous). |
| `group_summaries` | `repeated SummaryResult` | 2 | Aggregate values for this group. |
| `raw_results` | `repeated EntityWithMetric` | 3 | Raw entity data. If no raw_columns, contains only GUIDs. |
| `total_entity_count` | `int64` | 4 | Total entities in group (may exceed raw_results due to raw_limit). |
| `sub_group_results` | `repeated QueryGroupResult` | 5 | Multi-dimensional sub-groups. |

### QueryProperties

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `query_depth` | `int32` | 1 | Depth for recursive queries. |
| `execute_query_as_leaf` | `bool` | 2 | Execute as leaf node (not aggregator). |
| `hashed_range` | `HashedRange` | 3 | Entity hash range for query splitting. |
| `sampling_interval_secs` | `int64` | 4 | Time window for metric aggregation. |

---

## 1D. All Enums Reference

### InsightsErrorProto.Type (41 error types)

| Enum | Value | Description |
|------|-------|-------------|
| `kNoError` | 0 | No error |
| `kUnknown` | 1 | Unknown error |
| `kCanceled` | 2 | Request canceled |
| `kTimeout` | 3 | Request timeout |
| `kTransportError` | 4 | Transport/network error |
| `kRetry` | 5 | Retry needed |
| `kInternalError` | 6 | Internal system failure |
| `kUnavailable` | 7 | DB unavailable, retry after significant wait |
| `kNonCasUpdateForCasEntity` | 8 | Non-CAS update on a CAS entity |
| `kCasUpdateForNonCasEntity` | 9 | CAS update on a non-CAS entity |
| `kIncorrectCasValue` | 10 | Wrong CAS value |
| `kIncorrectCreatedTimestamp` | 11 | Invalid created timestamp |
| `kPartial` | 12 | Partial success in batch RPC |
| `kEntityTypeNotRegistered` | 13 | Entity type not registered |
| `kParentEntityTypeNotRegistered` | 14 | Parent entity type not registered |
| `kShardEntityTypeNotRegistered` | 15 | Shard entity type not registered |
| `kMetricTypeNotRegistered` | 16 | Metric type not registered |
| `kEntityNotPresent` | 17 | Entity not present |
| `kNotFound` | 18 | Value not found in backend |
| `kAttributeMultipleDefinition` | 19 | Same attribute defined multiple times |
| `kResetWatchClient` | 20 | Watch client needs reset |
| `kAttributeInPutMetricDataRPC` | 21 | Attribute cannot be in PutMetricData |
| `kMetricInUpdateEntityRPC` | 22 | Metric cannot be in UpdateEntity |
| `kInvalidTimestamp` | 23 | Client timestamp invalid (< known max) |
| `kWatchAlreadyRegistered` | 24 | Watch already registered |
| `kEntityReadOnly` | 25 | Replicated entity is read-only |
| `kWatchClientAlreadyRegistered` | 26 | Watch client already registered |
| `kWatchNotRegistered` | 27 | Watch not currently registered |
| `kWatchClientUnexpectedState` | 28 | Watch client in unexpected state |
| `kDerivedMetricInPutMetricDataRPC` | 29 | Derived metric in PutMetricData |
| `kInvalidWatchIdForUnregistration` | 30 | Watch ID mismatch for unregister |
| `kMetricDataDroppedByRetentionPolicy` | 31 | Data dropped by retention |
| `kIncorrectIncarnationId` | 32 | Wrong incarnation ID |
| `kEntityAlreadyExists` | 33 | Entity already exists |
| `kNestedFieldDirectUpdatesNotAllowed` | 34 | Cannot directly update nested field |
| `kWatchClientNotRegistered` | 35 | Watch client not registered |
| `kTenantIdChanged` | 36 | Cannot change tenant ID |
| `kEntityUpdateOutOfOrder` | 37 | Out-of-order sync update |
| `kCurrentStateNotAllowedForEvictableEntityTypeWatch` | 38 | Current state disallowed for evictable watch |
| `kAmbiguousAncestorTree` | 39 | Ambiguous ancestor tree |
| `kFeatureDisabled` | 40 | Feature is disabled |
| `kInvalidRequest` | 1000 | Invalid request format |
| `kMultipleDefinition` | 1001 | Duplicate entry in args |
| `kNoMetricName` | 1002 | Missing metric name |
| `kNoEntityTypeName` | 1003 | Missing entity type name |
| `kAttributeIsBucketized` | 1004 | Bucketization set on attribute |
| `kInvalidMetricTypeName` | 1005 | Invalid metric type name |
| `kInvalidMetricTypeDefinition` | 1006 | Invalid metric type definition |
| `kInvalidDownSamplingInterval` | 1007 | Invalid downsampling interval |
| `kAttributeIsDownsampled` | 1008 | Downsampling set on attribute |
| `kInvalidSerialisedProto` | 1009 | Invalid serialized proto |
| `kInvalidNestedFieldInfo` | 1010 | Invalid nested field info |
| `kInvalidBaseAttribute` | 1011 | Invalid base attribute |
| `kCannotUpdateNestedFieldInfo` | 1012 | Cannot update nested field info |
| `kInvalidPutMetricData` | 1013 | Invalid PutMetricData value |
| `kCannotClearBaseAttributeSchema` | 1014 | Cannot clear base attribute schema |
| `kInvalidSerialisedProtoCompressionType` | 1015 | Invalid compression type |
| `kInvalidEvictableEntityType` | 1016 | Invalid evictable entity type |
| `kInvalidIndexColumn` | 1017 | Invalid index column definition |
| `kGetAllEvictableEntitiesUnsupported` | 1018 | Cannot get all evictable entities |
| `kDimentsionFactTableInEntityWithMetric` | 1019 | Dimension-fact in EntityWithMetric |
| `kEntityInMetricDataSample` | 1020 | Entity in MetricDataSample |
| `kMissingPrimaryKeyAttribute` | 1021 | Missing primary key in sample |
| `kPrimaryKeyIsNotAttribute` | 1022 | Primary key not an attribute |
| `kMetricTypeDoesNotMatchIndexType` | 1033 | Metric type mismatch with index |
| `kMissingIndexType` | 1034 | Index column missing index type |
| `kCannotModifyParentTypeName` | 1035 | Cannot modify parent type name on evictable |
| `kDBUpdateInProgress` | 2001 | DB update in progress, retry |
| `kCacheSyncWithDBInProgress` | 2002 | Cache sync in progress |
| `kCacheSyncWithDBFailed` | 2003 | Cache sync failed, retryable |
| `kCassandraMutateFailed` | 2004 | Cassandra mutation error |
| `kCassandraMutateEpochError` | 2005 | Cassandra epoch mismatch |
| `kCassandraReadFailed` | 2006 | Cassandra read error |

### InsightsErrorProto.SubType (70+ sub-error types)

| Enum | Value | Category | Description |
|------|-------|----------|-------------|
| `kNotSet` | 0 | -- | Not set |
| `kGetEntitiesWithMetricsArgMissingQuery` | 1000 | Query | Missing query arg |
| `kQueryMissingEntityName` | 2000 | Query | Missing entity name |
| `kQueryInvalidEntityType` | 2001 | Query | Different entity types in list |
| `kQueryDuplicateEntityId` | 2002 | Query | Duplicate entity IDs |
| `kQueryInvalidEntityWildcard` | 2003 | Query | Mixed wildcard/non-wildcard |
| `kQueryInvalidStartTime` | 2004 | Query | start_time < 0 |
| `kQueryInvalidEndTime` | 2005 | Query | end_time < start_time |
| `kQueryWhereClauseIsTooDeep` | 2006 | Query | Expression tree too deep |
| `kQueryRelationshipTreeCheckFailed` | 2007 | Query | Relationship tree integrity failure |
| `kQueryUnsupported` | 2008 | Query | Unsupported query feature |
| `kQueryInvalidShardId` | 2009 | Query | Invalid shard ID |
| `kQueryMissingEntity` | 2010 | Query | Missing entity |
| `kQueryExceedsEvictableEntityLimit` | 2011 | Query | Too many evictable entities |
| `kRegexTooLong` | 2012 | Query | Regex too long |
| `kQueryGroupByInvalidRawSort` | 3000 | GroupBy | Invalid raw sort |
| `kQueryGroupByInvalidRawLimit` | 3001 | GroupBy | Invalid raw limit |
| `kQueryGroupByMissingRawCol` | 3002 | GroupBy | Missing raw column |
| `kQueryGroupByUnsupported` | 3003 | GroupBy | Unsupported group-by |
| `kQueryGroupByInvalidAggrCol` | 3004 | GroupBy | Invalid aggregate column |
| `kQueryGroupByInvalidGroupByCol` | 3005 | GroupBy | Invalid group-by column |
| `kQueryGroupByInvalidNumBuckets` | 3006 | GroupBy | Missing num_buckets |
| `kQueryGroupByMissingAggrCol` | 3007 | GroupBy | Missing aggregate column |
| `kQueryGroupByInvalidRawCol` | 3008 | GroupBy | Invalid raw column |
| `kQueryGroupByInvalidGroupLimit` | 3009 | GroupBy | Invalid group limit |
| `kQueryGroupByInvalidBooleanExpr` | 3010 | GroupBy | Invalid boolean expression |
| `kQueryGroupByInvalidComparisionExpr` | 3011 | GroupBy | Invalid comparison expression |
| `kQueryGroupByInvalidPreprocessed` | 3012 | GroupBy | Invalid preprocessed query |
| `kQueryGroupByAggrError` | 3013 | GroupBy | Aggregation error |
| `kQueryUndefinedMetricType` | 3014 | GroupBy | Undefined metric type |
| `kQueryGroupByInvalidGroupByColType` | 3015 | GroupBy | Invalid group-by column type |
| `kQueryInvalidDownSamplingInterval` | 3016 | GroupBy | Invalid downsampling interval |
| `kQueryGroupByInvalidBucketIntervals` | 3017 | GroupBy | Invalid bucket separators |
| `kDerivedMetricNoNumericData` | 4000 | DerivedMetric | No numeric data |
| `kDerivedMetricInvalidTimeRange` | 4001 | DerivedMetric | Invalid time range |
| `kDerivedMetricNotFound` | 4002 | DerivedMetric | Not found |
| `kDerivedMetricInvalidMetricType` | 4003 | DerivedMetric | Invalid metric type |
| `kDerivedMetricInvalidExpression` | 4004 | DerivedMetric | Invalid expression |
| `kDerivedMetricInvalidRollupQuery` | 4005 | DerivedMetric | Invalid rollup query |
| `kDerivedMetricDependsOnDerivedMetric` | 4006 | DerivedMetric | Source is also derived |
| `kDerivedMetricMaxEntitiesExceeded` | 4007 | DerivedMetric | Too many entities for rollup |
| `kQueryDownsamplingInvalidInterval` | 5001 | Downsampling | Invalid interval |
| `kQueryDownsamplingConflictingOps` | 5002 | Downsampling | Multiple operators for metric |
| `kWatchClientSessionNotPresent` | 6000 | Watch | Session not registered (reset) |
| `kWatchClientSessionStale` | 6001 | Watch | Session unregistered due to inactivity |
| `kWatchClientQueuedWatchesLimit` | 6002 | Watch | Max queued watches reached |
| `kWatchClientInvalidSequenceId` | 6003 | Watch | Invalid sequence_id |
| `kMetricDataRPCDisabled` | 6004 | Watch | MetricData RPC disabled |
| `kWatchClientNestedFieldSchemaUpdated` | 6005 | Watch | Nested field schema updated |
| `kWatchClientMultipleRegistrations` | 6006 | Watch | Duplicate client registration |
| `kMetadataWatchInNonLeader` | 6007 | Watch | Metadata watch on non-leader |
| `kMetadataWatchLeaderNotFound` | 6008 | Watch | Leader not found |
| `kWatchClientShardUnloaded` | 6009 | Watch | Shard unloaded |
| `kWatchClientClusterRegistered` | 6010 | Watch | Cluster registered |
| `kWatchClientClusterUnregistered` | 6011 | Watch | Cluster unregistered |
| `kDownSamplingIntervalNotMultiple` | 7000 | MetricType | Not multiple of shard_secs |
| `kDownSamplingIntervalNotAligned` | 7001 | MetricType | Not aligned to daily boundary |
| `kMetricDataValueNotPresent` | 8000 | PutMetricData | DataValue empty |
| `kRetryPutMetricDataOverHiMem` | 8001 | PutMetricData | High memory, retry |
| `kShardInTransition` | 9000 | ScaleOut | Shard transitioning |
| `kShardMapNotInitialized` | 9001 | ScaleOut | Shard map not initialized |
| `kShardNotReady` | 9002 | ScaleOut | Shard not ready on node |
| `kCassandraOpDropped` | 10000 | Cassandra | Operation dropped |

### ComparisonExpression.Operator (12 operators)

| Enum | Value | Description |
|------|-------|-------------|
| `kEQ` | 0 | Equal |
| `kNE` | 1 | Not equal |
| `kLT` | 2 | Less than |
| `kLE` | 3 | Less than or equal |
| `kGT` | 4 | Greater than |
| `kGE` | 5 | Greater than or equal |
| `kLike` | 6 | Regex match (wildcard = search all attributes) |
| `kContains` | 7 | RHS subset of LHS |
| `kIN` | 8 | LHS subset of RHS |
| `kAny` | 9 | Intersection non-empty |
| `kExists` | 10 | Unary: value exists |
| `kChanged` | 11 | Unary: value changed (watches only) |

### BooleanExpression.Operator

| Enum | Value | Description |
|------|-------|-------------|
| `kAnd` | 0 | Logical AND |
| `kOr` | 1 | Logical OR |
| `kNot` | 2 | Logical NOT (unary, applied to LHS) |

### Expression.Operator

| Enum | Value | Description |
|------|-------|-------------|
| `kPlus` | 0 | Addition |
| `kMinus` | 1 | Subtraction |
| `kMult` | 2 | Multiplication |
| `kDiv` | 3 | Division |
| `kMod` | 4 | Modulo |
| `kConcat` | 5 | String concatenation |

### MetricType.Operator

| Enum | Value | Description |
|------|-------|-------------|
| `kSum` | 0 | Sum aggregation |
| `kMax` | 1 | Maximum value |
| `kMin` | 2 | Minimum value |
| `kAvg` | 3 | Average |
| `kLast` | 4 | Last value prevails |
| `kCount` | 5 | Count of values |

### MetricType.IndexType

| Enum | Value | Description |
|------|-------|-------------|
| `kInt64` | 0 | 64-bit signed integer index |
| `kString` | 1 | String index |
| `kUInt64` | 2 | 64-bit unsigned integer index |
| `kBoolean` | 3 | Boolean index |

### MetricType.CompressionType

| Enum | Value | Description |
|------|-------|-------------|
| `kNone` | 0 | No compression |
| `kBzip2` | 1 | Bzip2 compression |
| `kZlib` | 2 | Zlib compression |
| `kSnappy` | 3 | Snappy compression |

### MetricType.PiiType

| Enum | Value | Description |
|------|-------|-------------|
| `kDoesNotContainPII` | 0 | No PII |
| `kMaskValue` | 1 | Mask value during collection |
| `kRemoveMetric` | 2 | Remove metric during collection |
| `kMaskIfValueMatchRegex` | 3 | Mask if value matches regex (string only) |
| `kRemoveIfValueMatchRegex` | 4 | Remove if value matches regex (string only) |

### MetricType.MaskType

| Enum | Value | Description |
|------|-------|-------------|
| `kDefaultMask` | 0 | Default masking |
| `kIpAddrMask` | 1 | IP address mask (IPv4 + IPv6) |
| `kIpv4AddrMask` | 2 | IPv4 address mask |
| `kIpv6AddrMask` | 3 | IPv6 address mask |
| `kEmailMask` | 4 | Email address mask |
| `kNameMask` | 5 | Name mask |

### MetricType.TtlCalculation

| Enum | Value | Description |
|------|-------|-------------|
| `kTimestampBased` | 0 | TTL relative to data point timestamp |
| `kCurrentTimeBased` | 1 | TTL relative to current time |

### MetricType.Category

| Enum | Value | Description |
|------|-------|-------------|
| `kRealTime` | 0 | Real-time metric |
| `kAnalytics` | 1 | Analytics metric (capacity planning, VMBL) |

### Query.FlagTypes (bitwise OR)

| Enum | Value | Description |
|------|-------|-------------|
| `kReturnErrorForUndefinedColumn` | 0x1 | Don't ignore undefined columns |
| `kSkipGuidsForEmptyRawColumns` | 0x2 | Skip GUIDs when no raw columns specified |
| `kForceMultiPhaseRawColumnFetch` | 0x4 | Limit entities first, then fetch raw columns (performance) |

### QueryGroupBy.GroupByColumnType

| Enum | Value | Description |
|------|-------|-------------|
| `kDiscrete` | 0 | Exact match grouping |
| `kContinuous` | 1 | Bucket-based grouping |

### QueryOrderBy.SortOrder

| Enum | Value | Description |
|------|-------|-------------|
| `kAscending` | 0 | Ascending sort |
| `kDescending` | 1 | Descending sort |

### QueryOrderBy.SortKey

| Enum | Value | Description |
|------|-------|-------------|
| `kMax` | 0 | Maximum value in time range |
| `kMin` | 1 | Minimum value in time range |
| `kFirst` | 2 | First value in time range |
| `kLast` | 3 | Last value in time range |
| `kLatest` | 4 | Latest value (ignore time range) |
| `kAvg` | 5 | Average value (non-numeric = 0) |

### NestedFieldInfo.ValueType

| Enum | Value | Description |
|------|-------|-------------|
| `kString` | 0 | String |
| `kBoolean` | 1 | Boolean |
| `kDouble` | 2 | Double |
| `kFloat` | 3 | Float |
| `kInt64` | 4 | 64-bit signed integer |
| `kUInt64` | 5 | 64-bit unsigned integer |
| `kBytes` | 6 | Raw bytes |
| `kEnum` | 7 | Enum (stored as int64) |

### NestedFieldInfo.FieldOption

| Enum | Value | Description |
|------|-------|-------------|
| `kFirst` | 0 | Use first value when multiple present |
| `kLast` | 1 | Use last value when multiple present |

### EntityTypeShard.ShardType

| Enum | Value | Description |
|------|-------|-------------|
| `kTokenRange` | 0 | Hash-based sharding (default) |
| `kEntityType` | 1 | Relationship-based sharding (co-locate with related entities) |

### TypeInfo.ClusterFunctions (bitwise)

| Enum | Value | Description |
|------|-------|-------------|
| `kNDFS` | 0x1 | Regular PE (Prism Element) cluster |
| `kMulticluster` | 0x2 | PC (Prism Central) analytics/management |
| `kCloudDataGateway` | 0x4 | Cloud backup and DR gateway |
| `kXiVM` | 0x80 | Xi VM cluster |
| `kAGSCluster` | 0x100 | AGS cluster |
| `kIAMCluster` | 0x1000 | IAM cluster |

### GlobalDataReadConsistency

| Enum | Value | Description |
|------|-------|-------------|
| `kEventual` | 0 | Eventually consistent read (local) |
| `kStrict` | 1 | Strictly consistent read (forwarded to master) |

### Watch.WatchCategory

| Enum | Value | Description |
|------|-------|-------------|
| `kEntityWatch` | 1 | Watch on entity CRUD |
| `kMetricWatch` | 2 | Watch on metric/attribute values |
| `kEntitySchemaWatch` | 3 | Watch on entity type schema changes |

### Watch.WatchPriority

| Enum | Value | Description |
|------|-------|-------------|
| `kCritical` | 0 | Critical priority |
| `kNormal` | 1 | Normal priority |
| `kLow` | 2 | Low priority |

### EntityWatchCondition.EntityWatchType (bitset)

| Enum | Value | Description |
|------|-------|-------------|
| `kEntityCreate` | 1 | Entity creation |
| `kEntityUpdate` | 2 | Entity update |
| `kEntityDelete` | 4 | Entity deletion |

Use bitwise OR to combine: e.g., `kEntityCreate | kEntityUpdate` = 3

### EntitySchemaWatchCondition.SchemaWatchType (bitset)

| Enum | Value | Description |
|------|-------|-------------|
| `kRegisterEntityType` | 1 | New entity type creation |
| `kUpdateEntityType` | 2 | TypeInfo update |
| `kRegisterMetricType` | 4 | New metric type registration |
| `kUpdateMetricType` | 8 | Metric type update |
| `kUnregisterMetricType` | 16 | Metric type unregistration |

### WatchClientProto.ResetWatchClientOnOperations

| Enum | Value | Description |
|------|-------|-------------|
| `kNoReset` | 0 | No reset on operations |
| `kResetOnClusterRegistration` | 1 | Reset on cluster registration |
| `kResetOnClusterUnregistration` | 2 | Reset on cluster unregistration |

---

## 1E. Watch System Reference

The IDF Watch system provides real-time notifications when entities, metrics, or schema change. It uses a long-poll model with sequence numbers for reliable delivery.

### Architecture Overview

```
┌─────────────────┐    RegisterWatchClient     ┌──────────────────┐
│   Watch Client  │ ────────────────────────►   │   IDF Watch      │
│  (e.g. Prism,   │                             │   Server         │
│   Acropolis)    │    RegisterWatch            │                  │
│                 │ ────────────────────────►   │  Watches stored  │
│                 │                             │  per (client_id, │
│                 │    GetFiredWatchList        │   session_id)    │
│                 │ ◄───────────────────────   │                  │
│                 │    (long-poll, 60s)         │                  │
└─────────────────┘                             └──────────────────┘
```

### Watch Lifecycle

1. **RegisterWatchClient** -- Establish a session (client_id + session_id UUID)
2. **RegisterWatch** -- Define watches with conditions; optionally get current state
3. **GetFiredWatchList** -- Long-poll loop; returns fired watches since last sequence_num
4. **UnregisterWatch** / **UnregisterWatchClient** -- Cleanup

### WatchClientProto

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `client_id` | `string` | 1 | Required. Component identifier (e.g., "acropolis", "prism_central"). |
| `session_id` | `string` | 2 | Required. Unique session UUID. (client_id, session_id) must be globally unique. |
| `reset_watch_client_on_operations` | `int32` | 3 | Optional. Bitwise OR of ResetWatchClientOnOperations. Default: 0 (kNoReset). |

### Watch

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `watch_category` | `WatchCategory` | 1 | -- | Required. kEntityWatch, kMetricWatch, or kEntitySchemaWatch. |
| `watch_name` | `string` | 2 | -- | Required. Unique per client_id (e.g., "NewVMCreation"). |
| `watch_subject` | `WatchSubject` | 3 | -- | Required. What the watch applies to. |
| `entity_watch_condition` | `EntityWatchCondition` | 4 | -- | Set only if kEntityWatch. |
| `metric_watch_condition` | `MetricWatchCondition` | 5 | -- | Set only if kMetricWatch. |
| `entity_schema_watch_condition` | `EntitySchemaWatchCondition` | 8 | -- | Set only if kEntitySchemaWatch. |
| `watch_priority` | `WatchPriority` | 6 | `kNormal` | kCritical, kNormal, kLow. |
| `return_previous_entity_state` | `bool` | 7 | `false` | Include previous entity state in fired watch. |

### WatchSubject

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `entity_guid` | `EntityGuid` | 1 | -- | Entity identity. entity_id optional (omit = all of type). |
| `namespace` | `string` | 4 | `"_default_"` | Namespace (Nusights). |
| `metric_name` | `string` | 2 | -- | Metric/attribute name (currently attributes only). |
| `entity_type_name` | `string` | 3 | -- | For kEntitySchemaWatch: entity type to watch. |

### EntityWatchCondition

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `entity_watch_type` | `int32` | 1 | Required. Bitwise OR of EntityWatchType (kEntityCreate=1, kEntityUpdate=2, kEntityDelete=4). |
| `filter_expr` | `BooleanExpression` | 2 | Optional. Conditional filter. Only fires if entity satisfies expression. |

### MetricWatchCondition

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `metric_watch_type` | `MetricWatchType` | 1 | Required. kWatchExpression or kValueChange. |
| `watch_expression` | `WatchExpression` | 2 | New-value condition (set for kWatchExpression). |
| `change` | `WatchChange` | 3 | Change-amount condition (set for kValueChange). |

**WatchExpression:**

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `op` | `ComparisonExpression.Operator` | 1 | `kGE` | Operator for new value comparison. All except kLike supported. |
| `new_value` | `DataValue` | 3 | -- | Threshold value. |

**WatchChange:**

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `change_type` | `ChangeType` | 1 | `kAbs` | kAbs, kPos, kNeg, or kAny. |
| `percentage_change` | `double` | 2 | -- | Percentage change threshold. |
| `absolute_change` | `int64` | 3 | -- | Absolute change threshold. |

### EntitySchemaWatchCondition

| Field | Type | Tag | Default | Description |
|-------|------|-----|---------|-------------|
| `watch_type` | `uint32` | 1 | -- | Required. Bitwise OR of SchemaWatchType enums. |
| `attributes_only` | `bool` | 3 | `false` | Only consider attribute registrations/updates. |

### FiredWatch

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `watch_name` | `string` | 1 | Watch name that fired. |
| `trigger_time_usecs` | `uint64` | 2 | Server epoch time when watch fired. |
| `changed_data` | `ChangedData` | 3 | What changed. |
| `watch_id` | `uint64` | 4 | Watch ID for this watch. |
| `sequence_id` | `uint64` | 5 | Monotonically increasing sequence for ordering. |

### FiredWatch.ChangedData

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `watch_category` | `Watch.WatchCategory` | 1 | Category of the watch that fired. |
| `changed_entity_data` | `Entity` | 2 | For kEntityWatch: the entity after change. |
| `entity_watch_type` | `EntityWatchCondition.EntityWatchType` | 4 | Which operation triggered: create/update/delete. |
| `previous_entity_data` | `Entity` | 5 | Previous entity state (if return_previous_entity_state=true). |
| `changed_metric_data` | `EntityWithMetric` | 3 | For kMetricWatch: entity + changed metric data. |
| `entity_schema_change` | `EntitySchemaChange` | 6 | For kEntitySchemaWatch: schema change details. |

### EntitySchemaChange

| Field | Type | Tag | Description |
|-------|------|-----|-------------|
| `watch_type` | `SchemaWatchType` | 1 | Reason watch fired. |
| `entity_type_name` | `string` | 2 | Entity type name. |
| `entity_type_info` | `TypeInfo` | 3 | For kRegisterEntityType/kUpdateEntityType. |
| `metric_type_list` | `repeated MetricType` | 4 | For metric registration/update/unregister changes. |

### Watch RPC Flow

**RegisterWatchClientArg:**
| Field | Type | Description |
|-------|------|-------------|
| `watch_client` | `WatchClientProto` | Required. Client session to register. |

**RegisterWatchArg:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watch_client` | `WatchClientProto` | -- | Required. Client session. |
| `watch_list` | `repeated Watch` | -- | Required. Watches to register (same category). |
| `timestamp_usecs` | `uint64` | -- | Required. Client-provided creation/update time. |
| `get_current_state` | `bool` | `true` | Return current state of matching entities. |

**RegisterWatchRet.RetElem:**
| Field | Type | Description |
|-------|------|-------------|
| `watch_name` | `string` | Name of the watch. |
| `response_status` | `InsightsErrorProto` | Registration status. |
| `current_state_list` | `repeated ChangedData` | Current state snapshot. |
| `fired_watch_last_sequence_num` | `uint64` | Last consumed sequence number. |
| `watch_id` | `uint64` | Assigned watch ID. |

**GetFiredWatchListArg:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watch_client` | `WatchClientProto` | -- | Required. Client session. |
| `rpc_timeout_in_secs` | `uint32` | `60` | Long-poll timeout. |
| `fired_watch_last_sequence_num` | `uint64` | `0` | Last consumed sequence (0 for first call). |

**GetFiredWatchListRet:**
| Field | Type | Description |
|-------|------|-------------|
| `response_status` | `InsightsErrorProto` | Overall status. |
| `fired_watch_list` | `repeated FiredWatch` | Fired watches since sequence_num. |
| `rpc_execution_time_usecs` | `uint64` | Server execution time. |

### Watch Usage Examples

**Example 1: Watch for new VM creation**
```
watch_category: kEntityWatch
watch_name: "NewVMCreation"
watch_subject {
  entity_guid { entity_type_name: "vm" }
}
entity_watch_condition {
  entity_watch_type: 1  // kEntityCreate
}
```

**Example 2: Watch for entity updates and deletes with filter**
```
watch_category: kEntityWatch
watch_name: "VMPowerStateChange"
watch_subject {
  entity_guid { entity_type_name: "vm" }
}
entity_watch_condition {
  entity_watch_type: 6  // kEntityUpdate | kEntityDelete
  filter_expr {
    comparison_expr {
      lhs { leaf { column: "power_state" } }
      operator: kChanged
    }
  }
}
```

**Example 3: Metric threshold watch**
```
watch_category: kMetricWatch
watch_name: "DiskUsage30percentBump"
watch_subject {
  entity_guid { entity_type_name: "disk" }
  metric_name: "storage.usage_ppm"
}
metric_watch_condition {
  metric_watch_type: kValueChange
  change {
    change_type: kPos
    percentage_change: 30.0
  }
}
```

**Example 4: Schema watch for new entity type registration**
```
watch_category: kEntitySchemaWatch
watch_name: "NewEntityTypeRegistered"
watch_subject { }
entity_schema_watch_condition {
  watch_type: 1  // kRegisterEntityType
}
```

---

# Part 2: Live Cluster Schema Dump

**Source**: Prism Central `10.46.30.35` — `/home/nutanix/config/insights/`

## 2A. Entity Type Registry

**Total registered entity types**: 731
**Source file**: `entity_type_config.proto` (9,280 lines)

### Summary Statistics

| Category | Count |
|----------|-------|
| Total entity types | 731 |
| With parent relationships | 101 |
| Top-level (no parents) | 630 |
| kEntityType sharding | 87 |
| Evictable | 65 |
| Suppress replication | 510 |
| Tenant-specific | 69 |
| PulseHD enabled | 339 |

### Replication Sources Used

| Source | Description |
|--------|-------------|
| `kNDFS` | Regular PE (Prism Element) cluster |
| `kMulticluster` | PC (Prism Central) |
| `kMinerva` | File server (Minerva) cluster |
| `kFlowSMSP` | Flow Security Microsegmentation |
| `kXiVM` | Xi VM cluster |
| `kIAMCluster` | IAM cluster |
| `kAGSCluster` | AGS cluster |

### Key Infrastructure Entity Types (Detail)

| Entity Type | Parents | Shard Strategy | Evictable | Suppress Repl | Tenant | PulseHD | Replication From |
|-------------|---------|----------------|-----------|---------------|--------|---------|------------------|
| `cluster` | -- | kEntityType:cluster | No | Yes | No | Yes | -- |
| `node` | cluster | kEntityType:cluster | No | Yes | No | Yes | -- |
| `vm` | node, cluster, app_container_cluster | kEntityType:node | No | No | Yes | Yes | kNDFS |
| `disk` | node, cluster, storage_pool | kEntityType:node | No | Yes | No | Yes | -- |
| `container` | storage_pool, cluster | kEntityType:storage_pool | No | Yes | No | Yes | -- |
| `storage_pool` | cluster | kEntityType:cluster | No | Yes | No | Yes | -- |
| `virtual_disk` | vm, container, volume_group, cluster | kEntityType:vm | No | No | No | Yes | kNDFS |
| `virtual_nic` | vm, virtual_network, cluster | kEntityType:vm | No | No | No | Yes | kNDFS |
| `virtual_network` | cluster | kEntityType:cluster | No | No | No | Yes | kNDFS, kFlowSMSP |
| `host_nic` | cluster, node | kEntityType:node | No | No | No | Yes | kNDFS |
| `volume_group` | cluster | kEntityType:cluster | No | No | Yes | Yes | kNDFS |
| `snapshot` | cluster | kEntityType:cluster | No | Yes | No | Yes | -- |
| `protection_domain` | cluster | kEntityType:cluster | No | Yes | No | Yes | -- |
| `alert` | -- | kTokenRange (default) | **Yes** | No | No | Yes | kNDFS |
| `task` | -- | kEntityType:task | No | No | No | Yes | kNDFS |
| `image` | cluster | kEntityType:cluster | No | Yes | No | No | -- |
| `file_server` | -- | kEntityType:file_server | No | No | No | Yes | kMinerva |
| `ngt` | vm | kEntityType:vm | No | No | No | Yes | kNDFS |
| `category` | -- | kTokenRange (default) | No | Yes | Yes | Yes | -- |

### Entity Hierarchy Tree (Parent-Child Relationships)

```
cluster
├── node
│   ├── vm (also: cluster, app_container_cluster)
│   │   ├── virtual_disk (also: container, volume_group, cluster)
│   │   ├── virtual_nic (also: virtual_network, cluster)
│   │   ├── virtual_gpu (also: cluster)
│   │   ├── ngt
│   │   ├── ngt_config_change_notification_info
│   │   ├── avm → avm_data_pipeline
│   │   └── vm_snapshot (also: cluster)
│   ├── nic_team
│   ├── narsil_node_vm_capabilities
│   ├── host_nic (also: cluster)
│   ├── host_gpu (also: cluster)
│   ├── vmkernel_nic (also: cluster)
│   └── virtual_switch (also: cluster, virtual_network)
├── storage_pool
│   ├── container (also: cluster)
│   └── disk (also: node, cluster)
├── acropolis_config
├── esxi_cluster_config
├── narsil_config
├── vm_management_cluster_config
├── vmm_cluster_config
├── vmm_cluster_pair
├── virtual_network
├── volume_group
├── volume_group_config
├── volume
├── protection_domain
├── snapshot
├── pd_schedule
├── remote_site
├── replication_link
├── sync_replication
├── vlan_discovery_config
├── image
├── ip_pool
├── network_switch → network_switch_interface
├── encryption_config
├── external_storage
├── cluster_vm_capabilities
├── alert_check_schema → alert_check_schema_override (also: cluster)
└── app_container_cluster → app_container (also: vm)

file_server
├── file_server_volume_group_set → file_server_volume_group (also: nvm)
├── file_server_share (also: volume_group_set, snapshot_policy)
│   ├── file_server_share_quota
│   ├── file_server_smb_clients (also: file_server)
│   ├── file_server_notification_policy → file_server_partner_server
│   ├── dept_share_user_quota
│   ├── homes_and_nonsharded_share_user_quota
│   └── fsvm_share_level_stats (also: nvm)
├── file_server_snapshot_policy
├── file_server_network
├── file_server_protocol
├── file_server_dns_entries
├── file_server_admin_role
├── file_server_blocked_clients
├── file_server_tiering_config
├── file_server_tiering_policy
├── file_server_manual_tiering
├── file_server_native_tiering_config
├── share_dir_metadata (also: file_server_share)
├── share_self_metadata (also: file_server_share)
├── nvm (also: vm)
│   ├── nvm_network
│   └── nvm_share_stats (also: file_server_share)
├── ssr_policy
├── flr_protection_schedule
├── share_crud_op
├── volume_group_cost
└── fileserver_snapshot_metadata_info
```

### Evictable Entity Types (65 total)

Evictable entities can be unloaded from memory cache. Cannot be changed after registration.

`action_result`, `action_rule_result`, `alert`, `app_consistent_snapshot_metadata_chunk`, `atlas_port_set_address_set_map`, `atlas_security_group`, `audit`, `capacity_scenario`, `category_association`, `category_counts`, `cerebro_schedule`, `dlv_events_db`, `dlv_recommendations_chn`, `dlv_recommendations_eng`, `dlv_recommendations_jpn`, `dlv_recommendations_kor`, `dormant_spec`, `dormant_vm`, `dormant_volume_group_config`, `dormant_volume_group_entity_capability`, `entity_operation_intent`, `entity_recycle_bin`, `entity_sync_stats_source`, `entity_sync_stats_target`, `event`, `file_server_pv_dataset`, `generated_report`, `hardening_report_details`, `hermes_message`, `history`, `idempotency_entity`, `lcm_entity`, `lcm_entity_v3`, `lcm_history`, `license_enforcement_snapshot`, `licensing_product_audit`, `log_collection_request`, `nc2_node`, `notification_subscription_details`, `nucalm_action_run`, `nucalm_run_log`, `nucalm_task`, `offline_node_rebuild_progress_info`, `pc_backup_failure_log`, `pc_scheduler_snapshot`, `pc_scheduler_vm`, `recovery_plan_execution_audit`, `recovery_plan_job`, `recovery_plan_job_execution_step`, `recovery_plan_job_recovered_entity_map`, `recovery_plan_job_stats`, `recovery_plan_job_validation_status`, `report_artifact`, `security_dashboard_info`, `stig_report`, `stig_report_details`, `svcmgr_history`, `svcmgr_migration`, `svcmgr_task`, `svcmgr_taskv2`, `task_wal_information`, `vm_recovery_point`, `volume_group_recovery_point`, `vulcan_scheduled_entity`, `witness_orchestrator_audit`

### Tenant-Specific Entity Types (69 total)

Multi-tenancy enabled. Entities isolated by tenant_id.

`abac_category`, `abac_category_key`, `acropolis_ha_config`, `anduril_vm_info`, `atlas_direct_connect`, `atlas_floating_ip`, `atlas_route_table`, `atlas_routing_policy`, `atlas_subnet`, `atlas_virtual_network`, `availability_zone_physical`, `category`, `category_association`, `category_counts`, `cloud_trust`, `cluster_cpu_models`, `external_storage`, `intent_spec`, `network_security_policy`, `nucalm_budget`, `nucalm_consumption`, `nucalm_cost`, `nucalm_price_item`, `nucalm_price_item_status`, `nucalm_quota`, `project`, `project_entity`, `vm`, `volume_group`, `volume_group_config`, ... (and ~39 more)

### Complete Entity Type Name List (731 types, alphabetical)

<details>
<summary>Click to expand full list</summary>

`abac_category`, `abac_category_key`, `abac_entity_capability`, `abac_entity_permissions`, `abac_role`, `abac_user_capability`, `access_control_policy`, `access_denials_data`, `access_request_entity`, `acropolis_config`, `acropolis_ha_config`, `action_result`, `action_rule`, `action_rule_result`, `action_template`, `action_type`, `affinity_info`, `affinity_rule`, `ahv_guest_reboot_policy`, `alert`, `alert_check_schema`, `alert_check_schema_override`, `alert_grouping_rules`, `alert_metadata`, `alert_notification_policy`, `analysis_session`, `anduril_vm_info`, `anti_affinity_rule`, `aos_networking_capabilities`, `api_lock`, `app`, `app_blueprint`, `app_consistent_snapshot_metadata_chunk`, `app_container`, `app_container_cluster`, `assignment_rule`, `atlas_cidr`, `atlas_cloud_config`, `atlas_cloud_network`, `atlas_cloud_provisioning_params`, `atlas_cluster_health`, `atlas_controller_migration_config`, `atlas_direct_connect`, `atlas_direct_connect_vif`, `atlas_external_routing_domain`, `atlas_floating_ip`, `atlas_flow_gateway`, `atlas_load_balancer_session`, `atlas_load_balancer_session_listener_stats`, `atlas_load_balancer_session_target`, `atlas_load_balancer_session_targets_stats`, `atlas_map_virtual_network_external_subnet`, `atlas_migration_config`, `atlas_network_function`, `atlas_nic_profile`, `atlas_port`, `atlas_port_set`, `atlas_port_set_address_set_map`, `atlas_route_table`, `atlas_routing_policy`, `atlas_security_group`, `atlas_subnet`, `atlas_virtual_network`, `audit`, `audit_event_schema`, `autonomous_nearsync_state`, `availability_zone_physical`, `avm`, `avm_data_pipeline`, `batch_request_identifier`, `bgp_session`, `bundle_info`, `ca_certificates`, `capabilities`, `capacity_scenario`, `catalog_item`, `catalog_item_info`, `catalog_placement_policy_info`, `catalog_placement_policy_status_info`, `catalog_rate_limit_info`, `category`, `category_association`, `category_counts`, `cclm_migration_tracker`, `cell`, `cerebro_capabilities`, `cerebro_schedule`, `certificate_signing_requests`, `certificates`, `cloud_dr_config`, `cloud_file_server_hot_tier_policy`, `cloud_tenant`, `cloud_trust`, `cluster`, `cluster_ahv_config`, `cluster_cpu_models`, `cluster_data_resiliency_rebuild_progress_info`, `cluster_data_state`, `cluster_profile`, `cluster_public_key_info`, `cluster_resiliency_info`, `cluster_vm_capabilities`, `cluster_vswitch_config`, `cluster_vulnerabilities`, `clustermgmt_nc2_service`, `common_report_config`, `compute_non_migratable_vms_entity`, `config_migration_preview`, `config_migration_summary`, `config_sync_enabled_attributes`, `config_sync_queue`, `connection_interest`, `consistency_group_config`, `container`, `content_placement_policy`, `content_placement_policy_status`, `content_repository`, `convert_protection_domain_report`, `convert_protection_domain_stats`, `cpu_model_options`, `credential`, `csr_details`, `custom_form`, `cvm`, `dashboard`, `data_services_ip_mapping`, `datacenter`, `datasource`, `dcm_tenant_cache`, `dedicated_domain`, `delphi_task`, `dept_share_user_quota`, `dept_share_user_quota_enforcer`, `discovery_mapping_rule`, `discovery_result`, `discovery_version`, `disk`, `disk_group_config`, `disk_rebuild_progress_info`, `distributed_virtual_switch`, `distributed_virtual_switch_breakfix`, `dlv_config`, `dlv_events_db`, `dlv_recommendations_chn`, `dlv_recommendations_eng`, `dlv_recommendations_jpn`, `dlv_recommendations_kor`, `dlv_user_action`, `dlv_users_object`, `docker_registry`, `domain_cloud_metadata`, `domain_manager`, `domain_resiliency_info`, `dormant_spec`, `dormant_vm`, `dormant_volume_group_config`, `dormant_volume_group_entity_capability`, `dr_stats`, `enable_map`, `encryption_backup`, `encryption_config`, `entity_backup`, `entity_dr_config`, `entity_operation_intent`, `entity_recycle_bin`, `entity_site_protection_status`, `entity_snapshot`, `entity_sync_policy`, `entity_sync_rule`, `entity_sync_state`, `entity_sync_state_local`, `entity_sync_state_per_az`, `entity_sync_stats_source`, `entity_sync_stats_target`, `esxi_cluster_config`, `event`, `external_entity_config`, `external_entity_schema`, `external_entity_shareable_config`, `external_repository`, `external_storage`, `favorite`, `feature_upgrade_versions`, `federated_file_server_share`, `file_info`, `file_server`, `file_server_accord_event`, `file_server_accord_spec`, `file_server_admin_role`, `file_server_anti_virus_scan_policy`, `file_server_blocked_clients`, `file_server_dataset`, `file_server_distributed_lock`, `file_server_dns_entries`, `file_server_event`, `file_server_identity_mapping`, `file_server_job`, `file_server_manager`, `file_server_manual_tiering`, `file_server_native_tiering_config`, `file_server_network`, `file_server_notification_policy`, `file_server_partner_server`, `file_server_protocol`, `file_server_pv_dataset`, `file_server_quarantined_file`, `file_server_ransomware`, `file_server_recommendation`, `file_server_relationship_pair`, `file_server_schedule`, `file_server_schedule_execution`, `file_server_service`, `file_server_service_nvm`, `file_server_share`, `file_server_share_dir_quota`, `file_server_share_mscan_status`, `file_server_share_quota`, `file_server_share_snapshot`, `file_server_share_vg_snapshot`, `file_server_smb_clients`, `file_server_snap_cft_bucket`, `file_server_snap_cft_session`, `file_server_snapshot_policy`, `file_server_tiering_access_control`, `file_server_tiering_config`, `file_server_tiering_policy`, `file_server_tiering_recall_request`, `file_server_tiering_request`, `file_server_vg_dir_quota`, `file_server_volume_group`, `file_server_volume_group_set`, `files_migration_config`, `files_migration_plan`, `files_migration_policy`, `files_migration_source`, `files_migration_source_share`, `fileserver_snapshot_metadata_info`, `filter`, `flex_security_group`, `flow_abac_entity_capability`, `flow_kube_cluster_config`, `flow_migration_config`, `flow_smsp`, `flow_smsp_package`, `flow_smsp_to_pc_idf_sync_marker`, `flow_smsp_to_pe_idf_sync_marker`, `flow_vm_migration_info`, `flr_protection_schedule`, `fns_domain_name_server_config`, `fns_fqdn_to_ip_info`, `fsvm_share_level_stats`, `generated_report`, `global_entity_dr_state`, `global_network_controller`, `hardening_report_details`, `hardening_stats`, `health_server_checkpoint`, `hermes_message`, `history`, `homes_and_nonsharded_share_user_quota`, `host_bridge_config`, `host_gpu`, `host_nic`, `host_ovs_lockup_detection_info`, `host_pcie_device`, `host_pcie_group`, `host_swap`, `host_task_info`, `host_v2`, `http_proxy`, `http_proxy_whitelist`, `iam_identity_provider`, `iam_replication_config`, `iam_service_account`, `iam_service_account_group`, `iam_service_provider`, `iam_service_provider_role`, `iam_tenant`, `iamv2_backup_chunks`, `iamv2_backups_metadata`, `id_categorization_mapping`, `idempotency_entity`, `identity_provider`, `ignore_window`, `image`, `image_chunk_info`, `image_info`, `image_resumable_upload_status`, `infra_capabilities`, `infra_domain`, `infra_domain_pe`, `intent_spec`, `ip_pool`, `ipfix_exporter`, `iscsi_client_params`, `jump_box_entity`, `k8_cluster_entity`, `layer2_stretch`, `lazan_trm_cluster_queue_state`, `lcm_async_operation_result_v1`, `lcm_available_version`, `lcm_available_version_v3`, `lcm_bundle_v1`, `lcm_config`, `lcm_entity`, `lcm_entity_v3`, `lcm_history`, `lcm_history_upgrade_info`, `lcm_image_v1`, `lcm_metric_entity_v1`, `lcm_metric_operation_v1`, `lcm_module`, `lcm_product_meta_entity`, `lcm_status_table`, `license_addon_details`, `license_blacklist_url`, `license_cluster`, `license_configuration`, `license_details`, `license_enforcement`, `license_enforcement_snapshot`, `license_expiry_container_adv_capacity`, `license_info`, `license_metadata`, `license_metadata_mapping`, `license_prism_central`, `license_trial_details`, `licensing_allowance`, `licensing_cluster`, `licensing_consumption`, `licensing_entitlement`, `licensing_feature`, `licensing_key`, `licensing_key_association`, `licensing_key_consumption`, `licensing_metadata`, `licensing_product_audit`, `licensing_state`, `log_collection_request`, `logbay_request_proto`, `mac_address`, `magneto_persistent_state`, `maintenance_config`, `managed_machine_entity`, `managed_subnet_ip_address`, `management_server_account`, `management_server_info`, `mantle_encrypted_master_key`, `mantle_key_management_server`, `mantle_namespace_info`, `mantle_secret`, `marketplace_backup`, `marketplace_item`, `memory_model`, `metrics_data_provider`, `metrics_data_provider_eula`, `metrics_data_provider_instance`, `microseg_config`, `migrate_network_partition_record`, `migration_info`, `migration_port_reservation`, `migration_ssh_key_record`, `minerva_federation_policy`, `minerva_func_schedule`, `minerva_idf_sync_marker`, `minerva_protection_policy`, `minerva_share_conversion`, `minerva_sub_policy`, `mst`, `multicluster_config_spec`, `narsil_config`, `narsil_node_vm_capabilities`, `nc2_actor`, `nc2_cluster`, `nc2_deployment_spec`, `nc2_node`, `nc_service_version`, `nc_user_preference`, `ncc_error_codes`, `network_address_group`, `network_config`, `network_configuration`, `network_controller`, `network_controller_package`, `network_device`, `network_entity_group`, `network_flow_info`, `network_function`, `network_function_chain`, `network_function_chain2`, `network_security_policies_export`, `network_security_policy`, `network_security_rule_info`, `network_security_sync_job`, `network_segmentation`, `network_segmentation_configuration`, `network_service_group`, `network_switch`, `network_switch_interface`, `ngt`, `ngt_config_change_notification_info`, `ngt_policy`, `nic_team`, `nim_bom`, `nim_domain`, `node`, `node_config`, `node_info`, `node_lazan_stats`, `notification_subscription_details`, `nucalm_account_data`, `nucalm_action`, `nucalm_action_run`, `nucalm_app_beam_status`, `nucalm_app_blueprint`, `nucalm_app_blueprint_pulse_metrics`, `nucalm_app_failover_status`, `nucalm_app_profile_instance`, `nucalm_app_protection_policy`, `nucalm_app_protection_rule`, `nucalm_app_protection_status`, `nucalm_application`, `nucalm_application_cfg`, `nucalm_application_pulse_metrics`, `nucalm_approval_request`, `nucalm_back_filling_service_sync_status`, `nucalm_backup_restore_history`, `nucalm_budget`, `nucalm_config_runnable_spec`, `nucalm_config_spec`, `nucalm_consumption`, `nucalm_cost`, `nucalm_credential`, `nucalm_deployment`, `nucalm_deployment_cfg`, `nucalm_deployment_element`, `nucalm_endpoint`, `nucalm_environment`, `nucalm_feature`, `nucalm_global_variable`, `nucalm_job`, `nucalm_library_task`, `nucalm_library_variable`, `nucalm_license`, `nucalm_lifecycle`, `nucalm_loadbalancer`, `nucalm_loadbalancer_cfg`, `nucalm_network_group`, `nucalm_nutanix_snapshot_info`, `nucalm_package`, `nucalm_package_cfg`, `nucalm_package_element`, `nucalm_platform_instance_element`, `nucalm_policy`, `nucalm_policy_rule`, `nucalm_price_item`, `nucalm_price_item_status`, `nucalm_provider`, `nucalm_published_service`, `nucalm_published_service_cfg`, `nucalm_quota`, `nucalm_recovery_plan_job_sync_status`, `nucalm_replication_connection`, `nucalm_resource_type`, `nucalm_run_log`, `nucalm_runbook`, `nucalm_secret`, `nucalm_service`, `nucalm_service_cfg`, `nucalm_service_element`, `nucalm_service_upgrade_history`, `nucalm_service_version`, `nucalm_snapshot_group`, `nucalm_stats`, `nucalm_substrate`, `nucalm_substrate_cfg`, `nucalm_substrate_element`, `nucalm_sync_status`, `nucalm_task`, `nucalm_tunnel`, `nucalm_user_file`, `nucalm_variable`, `nucalm_vcenter_snapshot_info`, `nucalm_worker_state`, `nutanix_resource_group`, `nutanix_vulnerability_db`, `nvm`, `nvm_dept_share_user_quota`, `nvm_icap_stats`, `nvm_network`, `nvm_share_stats`, `nvmf_client_params`, `oauth_client`, `oauth_grant`, `oauth_token`, `objectstore`, `objectstore_datalens`, `objectstore_federation`, `objectstore_licensing`, `objectstore_multicluster`, `objectstore_packages`, `offline_node_rebuild_progress_info`, `ova_file_info`, `ova_info`, `ovs_config`, `parcel_info`, `password_manager_stats`, `pc_backup_config`, `pc_backup_failure_log`, `pc_backup_idf_sync_marker`, `pc_backup_metadata`, `pc_backup_restore_config`, `pc_backup_specs`, `pc_idf_sync_marker`, `pc_license_details`, `pc_licenses_sync`, `pc_object_store_backup_sync_marker`, `pc_objects_lite_service`, `pc_pe_unregistration_stats`, `pc_restore_dummy_idf_sync_marker`, `pc_restore_idf_sync_marker`, `pc_restore_points`, `pc_restore_service_version_metadata`, `pc_scheduler_snapshot`, `pc_scheduler_vm`, `pc_seed_data`, `pc_vm_group_graph`, `pc_zk_data`, `pcdr_syncrep_metadata`, `pd_schedule`, `pe_idf_sync_marker`, `pe_license_details`, `pe_vcenter_cluster_map`, `pe_vm_group_graph`, `pending_vm`, `permission`, `physical_gpu_profile`, `polaris_sync_object`, `policy_schema`, `port_set`, `portfolio_product`, `primary_approval_policy_details`, `prism_app`, `prism_central_data_protection_stats`, `prism_central_scaleout_stats`, `prism_ssl_certs_info`, `project`, `project_entity`, `protection_domain`, `protection_domain_config`, `protection_policy_consistency_group`, `protection_rule`, `pulse`, `qos_profile`, `qos_profile_association`, `rack`, `ratelimit_config`, `receiver_host`, `receiver_host_data_pipeline`, `reclaim_licensing_key`, `recovery_config_store`, `recovery_config_store_item`, `recovery_plan`, `recovery_plan_cluster_license_info`, `recovery_plan_entity_state_mapping`, `recovery_plan_execution_audit`, `recovery_plan_info_stats`, `recovery_plan_job`, `recovery_plan_job_execution_step`, `recovery_plan_job_recovered_entity_map`, `recovery_plan_job_stats`, `recovery_plan_job_validation_status`, `recovery_plan_network_mapping`, `recovery_plan_recovery_setting`, `recovery_plan_stage`, `recovery_plan_stats`, `recovery_point`, `recovery_point_replication_stat`, `recycle_bin_policy`, `registrations`, `remote_connection`, `remote_file_server`, `remote_magneto_capabilities`, `remote_site`, `remote_syslog_configuration`, `remote_syslog_module`, `remote_syslog_server`, `remote_syslog_server_v2`, `remove_vmdisks`, `replica_placement_policy`, `replicated_mantle_secret`, `replication_bandwidth_policy`, `replication_entity_map`, `replication_link`, `replication_policy_metadata`, `replication_target_info`, `report_artifact`, `report_config`, `report_template`, `report_view`, `repository_item`, `request_identifier`, `resource_consumption`, `resource_store`, `restore_workflow_stats`, `role`, `route`, `runway_blackout_period`, `scheduler_cluster_capabilities`, `scheduler_node_capabilities`, `scheduler_node_info`, `scheduler_node_pool_record`, `scheduler_segment_assignment_logical_timestamp`, `scheduler_segment_assignment_record`, `secret`, `secret_directory`, `secret_store_metadata`, `secured_protection_policy_list`, `security_dashboard_config`, `security_dashboard_info`, `security_group`, `security_profile_info`, `service_network_segmentation_info`, `session_key`, `share_crud_op`, `share_dir_metadata`, `share_self_metadata`, `smart_alert_metadata`, `snapshot`, `snapshot_metadata`, `snmp_transport`, `snmp_trap`, `snmp_user`, `source_target_map`, `span_session`, `span_session_stats`, `ssh_user_entity`, `ssr_policy`, `stale_entities_checkpoint`, `stig_report`, `stig_report_details`, `stig_rule`, `stig_stats`, `storage_policy`, `storage_policy_compliance`, `storage_pool`, `storage_summary`, `storage_target`, `storage_vdisk`, `streaming_policy`, `svcmgr_app`, `svcmgr_app_protection_policy`, `svcmgr_bundle_mapping`, `svcmgr_bundle_uploads`, `svcmgr_history`, `svcmgr_migration`, `svcmgr_task`, `svcmgr_taskv2`, `sync_replication`, `tag`, `task`, `task_wal_information`, `trigger_template`, `trigger_type`, `trimurti_server_version`, `tsc_data`, `underlay_subnet`, `unutilized_disk`, `user_account_password_info`, `user_group`, `uuid_mapping`, `vdi_sync_metadata`, `vg_storage_policy_compliance`, `virtual_disk`, `virtual_gpu`, `virtual_gpu_profile`, `virtual_network`, `virtual_nic`, `virtual_switch`, `vlan_discovery_config`, `vm`, `vm_affinity_compliance`, `vm_anti_affinity_compliance`, `vm_anti_affinity_policy`, `vm_cluster_map`, `vm_conversion`, `vm_group`, `vm_guest_customization_profile`, `vm_host_affinity_policy`, `vm_host_affinity_policy_compliance`, `vm_host_rule_node_list`, `vm_management_cluster_config`, `vm_migration`, `vm_profiles`, `vm_recovery_point`, `vm_snapshot`, `vm_startup_policy`, `vm_startup_policy_compliance`, `vm_template_info`, `vm_uptime_metrics`, `vmkernel_nic`, `vmm_cluster_config`, `vmm_cluster_pair`, `vmm_remote_cluster_info`, `volume`, `volume_group`, `volume_group_config`, `volume_group_cost`, `volume_group_entity_capability`, `volume_group_recovery_point`, `vpn_connection`, `vpn_gateway`, `vulcan_scheduled_entity`, `vulnerability_stats`, `wal_ha_host_record`, `wal_vm_decoupled_record`, `webhook`, `widget`, `witness_orchestrator_audit`, `witness_orchestrator_db`, `witness_relationship_db`, `wsvm_resource_stats_db`, `xat_table`, `xfit_policy`, `xi_tenant`, `xi_vm_idf_sync_marker`, `xstream__datadog`, `xstream__metric_metadata`, `xstream__others`, `xstream__service_metadata`, `xstream__telegraf`

</details>

---

## 2B. Attribute/Metric Registry

**Total metric type registrations**: 10,573 across 720 entity types
**Source file**: `entity_attribute_config.proto` (104,182 lines)

### Registry Summary by Key Entity Types

| Entity Type | Attributes | Stats (Time-Series) | Total |
|-------------|-----------|---------------------|-------|
| `cluster` | 77 | 354 | 431 |
| `vm` | 180 | 217 | 397 |
| `node` | 83 | 253 | 336 |
| `container` | 48 | 242 | 290 |
| `virtual_disk` | 44 | 178 | 222 |
| `file_server` | 88 | 77 | 165 |
| `storage_pool` | 7 | 140 | 147 |
| `disk` | 46 | 85 | 131 |
| `virtual_network` | 42 | 68 | 110 |
| `host_nic` | 50 | 43 | 93 |
| `volume_group` | 21 | 68 | 89 |
| `image` | 8 | 68 | 76 |
| `virtual_nic` | 34 | 42 | 76 |
| `alert` | 52 | 0 | 52 |
| `task` | 51 | 0 | 51 |
| `ngt` | 23 | 0 | 23 |

### vm (180 attributes, 217 stats)

**Key Attributes:**
| Attribute | Index | Notes |
|-----------|-------|-------|
| `cluster` | kString | Parent cluster UUID |
| `node` | kString | Host node UUID |
| `is_cvm` | kInt64 | 1 if Controller VM |
| `platform_type` | kString | Hypervisor platform |
| `virtual_nic_uuids` | kString | Attached NIC UUIDs |
| `vm_name` | -- | Display name |
| `power_state` | -- | on/off/suspended |
| `num_vcpus` | -- | Virtual CPUs |
| `memory_size_bytes` | -- | RAM allocation |
| `hypervisor_type` | -- | AHV/ESXi/Hyper-V |
| `ip_addresses` | -- | Guest IP addresses |
| `protection_type` | -- | DR protection type |

**All Attributes (180):**
`__protobuf__`, `__zprotobuf__`, `_arithmos_id_`, `apc_cpu_model_name`, `apc_cpu_model_uuid`, `apc_enabled`, `app_container_cluster_uuid`, `app_container_host_flags`, `app_container_host_image_version`, `app_container_host_uuid`, `auto_stop_action`, `availability_zone`, `backup_policy`, `bios_uuid`, `boot.uefi_firmware`, `boot_device_config`, `boot_device_order`, `capacity_bytes`, `category_host_affinity_list`, `cbr_not_capable_reason`, `cluster`, `cluster_name`, `config_nutanix_nfs_file_path`, `configured_gpu_list`, `consistency_group`, `consistency_group_name`, `container_ids`, `container_uuids`, `controller.storage_tier.cloud.configured_pinned_bytes`, `controller.storage_tier.das-sata.configured_pinned_bytes`, `controller.storage_tier.ssd.configured_pinned_bytes`, `controller.total_pinned_vdisks`, `cpu_architecture`, `cpu_hotplug_enabled`, `cpu_reservation_hz`, `created_by`, `disable_branding`, `disable_update_white_list`, `display_address`, `empty_cdrom_device_uuid_list`, `empty_cdrom_disk_addresses`, `enable_cpu_passthrough`, `flash_mode_enabled`, `frodo_enabled`, `generation_uuid`, `gpu_console`, `gpu_type`, `gpus_in_use`, `guest_driver_version`, `guest_os_id`, `guest_os_name`, `ha_priority`, `hardware_clock_timezone`, `hardware_virtualization`, `has_virtual_disk_chains`, `host`, `hydration_remaining_bytes`, `hydration_status`, `hypervisor_fetch_timestamp_usecs`, `hypervisor_specific_id`, `hypervisor_type`, `id`, `image_id`, `instance_id`, `instance_name`, `instance_type`, `ip_addresses`, `is_acropolis_vm`, `is_agent_vm`, `is_cbr_capable`, `is_control_domain`, `is_cvm`, `is_esx_vm_with_encrypted_disk`, `is_live_migratable`, `is_virtual_disk_uuid_reporting_enabled`, `launch_time`, `legacy_host_affinity_list`, `logical_timestamp`, `machine_type`, `management_server_account`, `memory_overcommit`, `memory_reserved_bytes`, `memory_size_bytes`, `minimum_memory_bytes`, `minimum_memory_mb`, `network_security_rule_id_list`, `ngt.cluster_version`, `ngt.communication_active`, `ngt.communication_over_serial_port_active`, `ngt.communication_type`, `ngt.dns_name`, `ngt.enabled`, `ngt.enabled_applications`, `ngt.esx_drivers_installed`, `ngt.flr_enabled`, `ngt.guest_os`, `ngt.guest_os_build_number`, `ngt.guest_os_version`, `ngt.installed_version`, `ngt.is_deleted`, `ngt.iscsi_iqn`, `ngt.iso_mounted`, `ngt.kvm_drivers_installed`, `ngt.last_bootup_time`, `ngt.metrics_enabled`, `ngt.multipathing_enabled_for_devices`, `ngt.network_interfaces`, `ngt.virtio_version`, `ngt.vm_vss_enabled`, `ngt_enable_script_exec`, `ngt_fail_on_script_failure`, `node`, `node_id`, `node_ipv4_address`, `node_name`, `num_cores_per_socket`, `num_network_adapters`, `num_threads_per_core`, `num_vcpus`, `num_vnuma_nodes`, `nutanix_iscsi_based_virtual_disk_uuids`, `nutanix_iscsi_based_virtual_disks`, `nutanix_nfs_based_virtual_disk_uuids`, `nutanix_nfs_based_virtual_disks`, `originated_by_uhura_vcenter`, `platform_type`, `port_sets`, `possible_flash_mode_pinned_virtual_disk_list`, `power_on_memory_bytes`, `power_on_memory_mb`, `power_state`, `power_state_mechanism`, `private_dns_name`, `private_ip_address`, `protection_domain`, `protection_domain_name`, `protection_rule_uuid`, `protection_rule_version`, `protection_type`, `provisioned_iops`, `public_dns_name`, `public_ip_address`, `qos_policy`, `reboot_required`, `region`, `removed_from_host_uuid`, `root_device_type`, `scsi_controller_enabled`, `secure_boot`, `serial_port_device_uuids`, `serial_port_types`, `serial_port_urls`, `serial_ports`, `service_id`, `source_vm_uuid`, `storage_cluster_uuid`, `system_storage_policy_uuid_list`, `tag_list`, `throttled_iops`, `tools_installer_mounted`, `tools_running_status`, `tools_version_status`, `uefi_boot`, `uefi_nvram_disk_uuid`, `vcpu_hard_pin`, `vga_console_enabled`, `virtual_disk_uuids_disabled_for_flash_mode`, `virtual_gpu_uuids`, `virtual_hardware_version`, `virtual_nic_ids`, `virtual_nic_uuids`, `vm_annotation`, `vm_name`, `vm_profile_uuid`, `vm_snapshot`, `vm_state`, `vm_to_vm_affinity_uuids`, `vm_type`, `volume_group`, `vtpm_disk_uuid`

**Sample Stats (217 total):** `avg_io_latency_usecs`, `avg_read_io_latency_usecs`, `avg_write_io_latency_usecs`, `controller_avg_io_latency_usecs`, `controller_io_bandwidth_kBps`, `controller_num_io`, `controller_num_iops`, `controller_num_read_io`, `controller_num_write_io`, `hypervisor_cpu_usage_ppm`, `hypervisor_memory_usage_ppm`, `hypervisor.cpu_ready_time_ppm`, `memory_usage_ppm`, `capacity.is_dead_vm`, `capacity.is_vm_underutilized`, ...

### node (83 attributes, 253 stats)

**Key Attributes:**
| Attribute | Index | Notes |
|-----------|-------|-------|
| `cluster` | kString | Parent cluster UUID |
| `node_name` | -- | Display name |
| `hypervisor_type` | -- | AHV/ESXi |
| `num_cpu_cores` | -- | Physical CPU cores |
| `memory_size_bytes` | -- | Total physical RAM |
| `service_vm_ipv4_address` | -- | CVM IP address |
| `host_type` | -- | Host hardware type |
| `node_status` | -- | Online/offline/maintenance |
| `ipv4_addresses` | -- | Management IPs |
| `boot_time_usecs` | -- | Last boot timestamp |

**All Attributes (83):**
`_arithmos_id_`, `_cluster_uuid_`, `_cluster_version_`, `block_model`, `block_model_name`, `block_serial`, `bmc_ip`, `bmc_passkey`, `bmc_username`, `boot_time_usecs`, `capacity.minimal_compute_node`, `capacity.model_cpu_ghz_list`, `capacity.model_hdd_gb_list`, `capacity.model_ram_gb_list`, `capacity.model_ssd_gb_list`, `check.1021.unresolved_alerts.2`, `cluster`, `cluster_id`, `cluster_name`, `controller.cpu_count`, `cpu.capacity_hz`, `cpu_frequency_hz`, `cpu_model`, `default_vhd_container_id`, `default_vhd_container_uuid`, `default_vhd_location`, `default_vm_container_id`, `default_vm_container_uuid`, `default_vm_location`, `disk_size_bytes`, `failover_cluster_fqdn`, `failover_cluster_node_status`, `flux_state`, `frodo_enabled`, `gpu_driver_version`, `host_gpu_list`, `host_maintenance_state`, `host_nic_ids`, `host_overhead_bytes`, `host_provides_usage_metrics`, `host_type`, `host_version`, `hypervisor_full_name`, `hypervisor_swap_used_bytes`, `hypervisor_type`, `id`, `ipv4_addresses`, `is_compute_only`, `kernel_nic_ids`, `max_supported_virtual_hardware_version`, `memory_size_bytes`, `model_cpu_ghz_list`, `model_hdd_gb_list`, `model_ram_gb_list`, `model_ssd_gb_list`, `node_name`, `node_status`, `node_uuid`, `num_cpu_cores`, `num_cpu_sockets`, `num_cpu_threads`, `num_external_client_sessions`, `num_hbas`, `num_nics`, `num_numa_nodes`, `num_vms`, `physical_capacity_bytes`, `reboot_pending`, `service_vm_ipv4_address`, `storage_tier.cloud.physical_capacity_bytes`, `storage_tier.das-sata.physical_capacity_bytes`, `storage_tier.ssd-mem-nvme.physical_capacity_bytes`, `storage_tier.ssd.physical_capacity_bytes`, `unmounted_disks_serial`, `xi.installation_time_in_usec`, `xi.management_ip`, `xi.management_mac`, `xi.node_class`, `xi.node_position`, `xi.node_serial`, `xi.rack_id`, `xi.u_height`, `xi.u_position`

### cluster (77 attributes, 354 stats)

**Key Attributes:**
| Attribute | Index | Notes |
|-----------|-------|-------|
| `_cluster_uuid_` | kString | Cluster UUID (indexed) |
| `cluster_name` | -- | Display name |
| `cluster_type` | -- | PE vs PC |
| `hypervisor_types` | -- | List of hypervisors |
| `num_nodes` | -- | Node count |
| `version` | -- | AOS version |
| `external_ip_address` | -- | Cluster VIP |
| `timezone` | -- | Configured timezone |

### alert (52 attributes, 0 stats)

All attributes, heavily indexed for query performance.

**Key Indexed Attributes:**
| Attribute | Index Type | Notes |
|-----------|-----------|-------|
| `_entity_id_` | kString | Alert UUID |
| `_created_timestamp_usecs_` | kUInt64 | Creation time |
| `_modified_timestamp_usecs_` | kUInt64 | Last modified |
| `_master_cluster_uuid_` | kString | Source cluster |
| `_tenant_id_` | kString | Tenant isolation |
| `acknowledged` | kBoolean | Ack status |
| `alert_origin` | kInt64 | Origin type |
| `alert_status` | kInt64 | Status code |
| `alert_type` | kInt64 | Type code |
| `auto_resolved` | kBoolean | Auto-resolved flag |
| `cassandra_id` | kString | Internal ID |
| `classification` | kString | Alert classification |
| `cluster_name` | kString | Source cluster name |
| `display_title` | kString | Title text |
| `impact_type` | kString | Impact category |
| `originating_cluster_uuid` | kString | Origin cluster UUID |
| `resolved` | kBoolean | Resolved flag |
| `service_name` | kString | Service name |
| `severity` | kString | Critical/Warning/Info |
| `severity_int` | kInt64 | Numeric severity |
| `source_entity_name` | kString | Source entity name |
| `source_entity_type` | kString | Source entity type |
| `source_entity_uuid` | kString | Source entity UUID |
| `type_id` | kString | Alert type ID |

**Namespace attributes:** `is_parent` [kBoolean, ns:alert_grouping_rules_np], `parent_uuid` [kString, ns:alert_grouping_rules_np]

### task (51 attributes, 0 stats)

**Key Indexed Attributes:**
| Attribute | Index Type | Notes |
|-----------|-----------|-------|
| `cluster_uuid` | kString | Associated cluster |
| `complete_time_usecs` | kUInt64 | Completion time |
| `component` | kString | Service component |
| `create_time_usecs` | kUInt64 | Creation time |
| `internal_task` | kBoolean | Internal vs user-visible |
| `is_legacy_progress_monitor_task` | kBoolean | Legacy PM task |
| `last_updated_time_usecs` | kUInt64 | Last update |
| `parent_task_uuid` | kString | Parent task |
| `project_uuid` | kString | Project scope |
| `status` | kString | QUEUED/RUNNING/SUCCEEDED/FAILED |
| `ui_hidden_task` | kBoolean | Hidden from UI |

**Namespace attribute:** `root_task_uuid` [ns:root_task_information]

### disk (46 attributes, 85 stats)

**Key Attributes:** `_arithmos_id_`, `cluster`, `cluster_name`, `disk_hardware_config`, `disk_size_bytes`, `disk_status`, `disk_uuid`, `host_name`, `id`, `location`, `model`, `mount_path`, `node`, `node_ipv4_address`, `online`, `serial_number`, `storage_pool`, `storage_tier_name`, `vendor`

### container (48 attributes, 242 stats)

**Key Attributes:** `_arithmos_id_`, `advertised_capacity_bytes`, `cluster`, `cluster_name`, `compression_type`, `container_name`, `erasure_code`, `id`, `max_capacity_bytes`, `on_disk_dedup`, `replication_factor`, `storage_pool`

### virtual_disk (44 attributes, 178 stats)

**Key Attributes:** `_arithmos_id_`, `attach_vm_id`, `attach_volume_group_id`, `capacity_bytes`, `cluster`, `container`, `disk_address`, `flash_mode_enabled`, `id`, `nutanix_nfs_file_path`, `storage_container_uuid`, `vdisk_uuid`, `vm`

### Pseudo Attributes (System-Generated)

These are internal/pseudo attributes prefixed with `_` that are available on all/most entity types:

| Pseudo Attribute | Description |
|-----------------|-------------|
| `_entity_id_` | Entity UUID (same as entity_guid.entity_id) |
| `_entity_type_` | Entity type name |
| `_arithmos_id_` | Internal Arithmos identifier (PE-synced entities) |
| `_cluster_uuid_` | Cluster UUID (node-level) |
| `_cluster_version_` | Cluster AOS version |
| `_created_timestamp_usecs_` | Entity creation time |
| `_modified_timestamp_usecs_` | Last modification time |
| `_last_synced_timestamp_usecs_` | Last replication sync time |
| `_master_cluster_uuid_` | Master cluster for replicated entities |
| `_tenant_id_` | Tenant identifier |

### Serialized Proto Attributes

Special attributes that contain serialized protobuf data:

| Attribute | Entity Types | Description |
|-----------|-------------|-------------|
| `__protobuf__` | vm, virtual_disk, task, ... | Serialized proto (uncompressed) |
| `__zprotobuf__` | vm, alert, virtual_nic, host_nic, ngt, ... | Compressed serialized proto (zlib/snappy) |
| `__heavy_zprotobuf__` | task | Large compressed proto (detailed task data) |

These attributes are the source for NestedFieldInfo-based derived attributes (parsed at query time).

---

## 2C. Arithmos Entity Operations

**Source file**: `arithmos_entity_operation.proto` (1,038 lines)

This file defines how entities synced from Arithmos (PE's internal metrics/data service) are transformed before being stored in Insights (IDF) on PC. Each entity type has an `entity_operations_list` block defining:
- **Arithmos name → Insights name** mapping
- **Entity ID derivation** (which attribute becomes entity_id)
- **Attribute operations** (rename, delete, convert, copy)
- **Version-specific overrides** for backward compatibility

### Operation Types

| Operation | Description |
|-----------|-------------|
| `kRename` | Rename an Arithmos attribute to a different Insights name (e.g., `cluster_uuid` → `cluster`) |
| `kDelete` | Remove an attribute (not needed in Insights) |
| `kEntityId` | Specify which attribute(s) derive the entity_id (precedence list) |
| `kConvertToMetric` | Convert an Arithmos attribute to a time-series metric in Insights |
| `kConvertToList` | Convert a scalar attribute to a list-type attribute |
| `kCopy` | Copy an attribute to a new name (keep original) |
| `kCopyToMetric` | Copy an attribute value as a time-series metric (preserves original as attribute) |

### Entity Operation Mappings

| Arithmos Entity | Insights Entity | Entity ID Source | Golang Method | Suppress Updates |
|----------------|-----------------|-----------------|---------------|-----------------|
| `kInvalidEntity` | `invalid_entity` | -- | -- | No |
| `kDisk` | `disk` | `disk_uuid` | `GetDisk` | No |
| `kVDisk` | `vdisk` | -- | `GetVdisk` | No |
| `kContainer` | `container` | `container_uuid` | `GetContainer` | No |
| `kStoragePool` | `storage_pool` | `storage_pool_uuid` | `GetStoragePool` | No |
| `kNode` | `node` | `node_uuid` | `GetNode` | No |
| `kCluster` | `cluster` | `cluster_uuid` | `GetCluster` | No |
| `kRemoteSite` | `remote_site` | `id` | `GetRemoteSite` | No |
| `kProtectionDomain` | `protection_domain` | `id` | `GetProtectionDomain` | No |
| `kSnapshot` | `snapshot` | `snapshot_uuid` | `GetSnapshot` | **Yes** |
| `kReplicationLink` | `replication_link` | `id` | `GetReplicationLink` | No |
| `kNetworkSwitchInterface` | `network_switch_interface` | `network_switch_interface_uuid`, `id` | -- | **Yes** |
| `kNetworkSwitch` | `network_switch` | `network_switch_uuid`, `id` | -- | **Yes** |
| `kVMKernelNic` | `vmkernel_nic` | `vmkernel_nic_uuid`, `id` | -- | No |
| `kHostNic` | `host_nic` | `host_nic_uuid`, `id` | -- | **Yes** |
| `kHostGpu` | `host_gpu` | `host_gpu_uuid` | -- | **Yes** |
| `kSyncReplication` | `sync_replication` | `id` | `GetSyncReplication` | No |
| `kVirtualNetwork` | `virtual_network` | `id` | -- | **Yes** |
| `kVolumeGroup` | `volume_group_config` | `volume_group_uuid` | `GetVolumeGroup` | **Yes** |
| `kImage` | `image` | `id` | -- | **Yes** |
| `kFileServer` | `file_server` | `id` | -- | No |
| `kFileServerShare` | `share` | `id` | -- | No |
| `kAppContainer` | `app_container` | `app_container_uuid` | -- | **Yes** |
| `kVM` | `vm` | `vm_uuid` | `GetVm` | **Yes** |
| `kVirtualDisk` | `virtual_disk` | `virtual_disk_uuid` | `GetVirtualDisk` | **Yes** |
| `kVirtualNic` | `virtual_nic` | `virtual_nic_uuid` | -- | **Yes** |
| `kVmSnapshot` | `vm_snapshot` | `vm_snapshot_uuid` | -- | **Yes** |
| `kVirtualGpu` | `virtual_gpu` | `virtual_gpu_uuid` | -- | **Yes** |
| `kDRVDisk` | `dr_vdisk` | `id` | -- | No |
| `kProtectionDomainSchedule` | `pd_schedule` | `id` | `GetPdSchedule` | No |
| `kEntityBackup` | `entity_backup` | `uuid` | -- | **Yes** |
| `kRecoveryPointReplicationStat` | `recovery_point_replication_stat` | `uuid` | -- | Version-dependent |
| `kReplicationTargetInfo` | `replication_target_info` | `uuid` | -- | **Yes** |
| `kUnutilizedDisk` | `unutilized_disk` | `disk_uuid` | -- | No |
| `kEntitySiteProtectionStatus` | `entity_site_protection_status` | `entity_site_protection_status_id` | -- | No |

### Detailed Attribute Operations per Entity

#### kDisk → disk

| Operation | Arithmos Attribute | Insights Attribute |
|-----------|-------------------|-------------------|
| kRename | `node_uuid` | `node` |
| kRename | `storage_pool_uuid` | `storage_pool` |
| kRename | `cluster_uuid` | `cluster` |
| kEntityId | `disk_uuid` | (entity_id) |
| kConvertToMetric | `storage.usage_ppm` | (time-series) |

#### kContainer → container

| Operation | Arithmos Attribute | Insights Attribute |
|-----------|-------------------|-------------------|
| kRename | `cluster_uuid` | `cluster` |
| kRename | `storage_pool_uuid` | `storage_pool` |
| kEntityId | `container_uuid` | (entity_id) |
| kDelete | `id` | -- |
| kConvertToList | `sequential_io_tier_preference` | (list) |
| kConvertToList | `ilm_down_migrate_time_secs` | (list) |
| kConvertToList | `random_io_tier_preference` | (list) |
| kConvertToList | `remote_names` | (list) |
| kConvertToList | `remote_container_names` | (list) |
| kConvertToList | `vstore_name_list` | (list) |

#### kNode → node

| Operation | Arithmos Attribute | Insights Attribute |
|-----------|-------------------|-------------------|
| kEntityId | `node_uuid` | (entity_id) |
| kRename | `cluster_uuid` | `cluster` |
| kDelete | `id` | -- |
| kDelete | `last_published_timestamp_usecs` | -- |
| kConvertToList | `ipv4_addresses`, `host_gpu_list`, `host_nic_ids`, `kernel_nic_ids`, `unmounted_disks_serial` | (lists) |
| kConvertToMetric | `hypervisor_memory_balloon_reclaim_target_bytes`, `hypervisor_num_transmit_packets_dropped`, `hypervisor_swap_in_rate_kBps`, `hypervisor_num_receive_packets_dropped`, `hypervisor_memory_balloon_reclaimed_bytes`, `hypervisor_swap_out_rate_kBps` | (time-series) |
| kCopyToMetric | `memory_size_bytes` | `memory_size_bytes_metric` |

#### kCluster → cluster

| Operation | Arithmos Attribute | Insights Attribute |
|-----------|-------------------|-------------------|
| kEntityId | `cluster_uuid` | (entity_id) |
| kDelete | `id` | -- |
| kConvertToList | `network_segmentation_events`, `name_server_ip_list`, `ntp_server_ip_list` | (lists) |
| kCopyToMetric | `memory_capacity_bytes` | `memory_capacity_bytes_metric` |

#### kVM → vm (default / current version)

| Operation | Arithmos Attribute | Insights Attribute |
|-----------|-------------------|-------------------|
| kEntityId | `vm_uuid` | (entity_id) |
| kRename | `node_uuid` | `node` |
| kConvertToMetric | `hypervisor_memory_balloon_reclaim_target_bytes`, `hypervisor_num_transmit_packets_dropped`, `num_vcpus_used_ppm`, `hypervisor_total_cpu_usage_time_since_boot_usecs`, `memory_usage_bytes`, `hypervisor_memory_balloon_reclaimed_bytes`, `hypervisor_swap_in_rate_kBps`, `hypervisor_swap_out_rate_kBps`, `hypervisor_num_receive_packets_dropped` | (time-series) |
| kCopyToMetric | `capacity_bytes` | `capacity_bytes_metric` |

#### kVirtualDisk → virtual_disk (default / current version)

| Operation | Arithmos Attribute | Insights Attribute |
|-----------|-------------------|-------------------|
| kEntityId | `virtual_disk_uuid` | (entity_id) |
| kRename | `vm_uuid` | `vm` |
| kConvertToMetric | `hypervisor_total_read_io_size_since_boot_kbytes`, `hypervisor_total_io_size_since_boot_kbytes`, `hypervisor_num_read_io_since_boot`, `hypervisor_num_io_since_boot`, `hypervisor_total_read_io_time_since_boot_usecs`, `hypervisor_total_io_time_since_boot_usecs` | (time-series) |
| kDelete | `controller.num_queued_io`, `controller.num_queued_read_io` | -- |

### Version-Specific Overrides

The config supports version-specific entity operation definitions using regex patterns:

| Version Pattern | Entity | Key Differences |
|----------------|--------|-----------------|
| `4\.5(\.[0-9]+)*` | kVM | Uses `id` for entity_id (not `vm_uuid`); renames `host_uuid`→`node`, `vm_id`→`hypervisor_specific_id`; adds `cluster_uuid`→`cluster` rename; converts many list attributes |
| `4.*`, `5\.0(\.[0-9]+)*` | kVM | Uses `vm_uuid` for entity_id; adds conditional `kCopy` of `hypervisor_memory_usage_ppm`→`memory_usage_ppm` only for kVMware/kHyperv hypervisors |
| `4\.5(\.[0-9]+)*` | kVirtualDisk | Uses `id` for entity_id; renames `cluster_uuid`→`cluster`, `container_uuid`→`container`; copies `attach_vm_id`→`vm` |
| `4\.5(\.[0-9]+)*` | kVirtualNic | Uses `id` for entity_id; renames `cluster_uuid`→`cluster`, `vm_id`→`hypervisor_specific_id`, `vm_uuid`→`vm` |
| `[4-6]\.[0-9]`, `7\.[0-5]` | kRecoveryPointReplicationStat | No suppress_entity_updates (Iris and below) |
| Default | kRecoveryPointReplicationStat | suppress_entity_updates=true (Janus 7.6+) |

### Conditional Operations

The `kCopy` operation supports `perform_op_on_condition` with a `BooleanExpression` filter. Example from kVM (version 4.*/5.0.*):

```
attribute_list {
  op_on_attribute: kCopy
  arithmos_attribute_name: "hypervisor_memory_usage_ppm"
  insights_attribute_name: "memory_usage_ppm"
  perform_op_on_condition {
    lhs {
      comparison_expr {
        lhs { leaf { column: "hypervisor_type" } }
        operator: kEQ
        rhs { leaf { value { str_value: "kVMware" } } }
      }
    }
    operator: kOr
    rhs {
      comparison_expr {
        lhs { leaf { column: "hypervisor_type" } }
        operator: kEQ
        rhs { leaf { value { str_value: "kHyperv" } } }
      }
    }
  }
}
```

This copies `hypervisor_memory_usage_ppm` to `memory_usage_ppm` only when `hypervisor_type` is "kVMware" or "kHyperv".
