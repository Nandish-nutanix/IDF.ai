#
# Copyright (c) 2015 Nutanix Inc. All rights reserved.
#
# Author: amit.jambure@nutanix.com
#
# This module helps in populating Query proto object of entity-db.
#
# >>> from cpdb_query import *
# >>> print COL("component")
# leaf {
#   column: "component"
# }
# >>> print STR("acropolis")
# leaf {
#   value {
#     str_value: "acropolis"
#   }
# }
# >>> print PLUS(UINT64(10), UINT64(20))
# lhs {
#   leaf {
#     value {
#       uint64_value: 10
#     }
#   }
# }
# operator: kPlus
# rhs {
#   leaf {
#     value {
#       uint64_value: 20
#     }
#   }
# }
# >>> print EQ(COL("component"), STR("acropolis"))
# comparison_expr {
#   lhs {
#     leaf {
#       column: "component"
#     }
#   }
#   operator: kEQ
#   rhs {
#     leaf {
#       value {
#         str_value: "acropolis"
#       }
#     }
#   }
# }
# >>> print QUERY("ergon:test",
#                 FROM="task", WHERE=EQ(COL("component"), STR("acropolis")))
# entity_list {
#   entity_type_name: "task"
# }
# where_clause {
#   comparison_expr {
#     lhs {
#       leaf {
#         column: "component"
#       }
#     }
#     operator: kEQ
#     rhs {
#       leaf {
#         value {
#           str_value: "acropolis"
#         }
#       }
#     }
#   }
# }
# query_name: "ergon:test"
#
# >>> print IN(COL("component"), STR_LIST(["acropolis", "ergon", "genesis"]))
#
# >>> print  QUERY("ergon:query_example1",
#                  SELECT=["component", "sequence_id"],
#                  FROM="task",
#                  WHERE=ANY(EQ(COL("component"), STR("genesis")),
#                            EQ(COL("component"), STR("prism"))))
#
# >>> print  QUERY("ergon:query_example2",
#                  FROM="task",
#                  WHERE=ALL(EQ(COL("component"), STR("genesis")),
#                            EQ(COL("operation_type"), STR("create-vm"))))
#
# q = QUERY("ergon:query_example3",
#           SELECT=field_names,
#           FROM="task",
#           WHERE=EQ(COL("component"), STR("genesis")),
#           ORDER_BY=DESCENDING("sequence_id"),
#           LIMIT=5)
#
# q = QUERY("ergon:query_example3",
#           SELECT=field_names,
#           FROM="task",
#           WHERE=EQ(COL("component"), STR("genesis")),
#           ORDER_BY=[ASCENDING("num_cpus","namespace-1"),DESCENDING("memory")],
#           LIMIT=5)
#

# Leaving this import here cause there might clients relying on our code for
# itertool in py2.
# TODO: Remove this code when all the code is migrated to py3.
import sys
if sys.version_info[0] == 2:
  pass

import time

from insights_interface.cpdb_interface import cpdb_utils
from insights_interface.insights_interface_pb2 import *

from util.base import log
from util.base.types import NutanixUuid

# Maximum number of entities after which the thread is yielded in
# _format_result_iter()
MAX_ENTITY_NUMBER = 5000

# create time stamp in insights.
ENTITY_CREATED_TIMESTAMP_ATTR = "_created_timestamp_usecs_"

# modified time stamp in insights.
ENTITY_MODIFIED_TIMESTAMP_ATTR = "_modified_timestamp_usecs_"

# entity id attribute in insights.
ENTITY_ID_ATTR = "_entity_id_"

# entity cas value attribute in insights.
CAS_VALUE_ID_ATTR = "_cas_value_"

############# Entity types present in IDF ##############

# Entity type of alert entity
ALERT_ENTITY_TYPE = "alert"

# Entity type of cluster entity
CLUSTER_ENTITY_TYPE = "cluster"

# Entity type of event entity
EVENT_ENTITY_TYPE = "event"

# Entity type of node entity
NODE_ENTITY_TYPE = "node"

# Entity type of vm entity
VM_ENTITY_TYPE = "vm"

# Entity type of audit entity
AUDIT_ENTITY_TYPE = "audit"

########################################################

__all__ = [
  "COUNT_QUERY",
  "QUERY",
  "QUERY_METRICS",

  "format_result",
  "format_result_iter",
  "format_metric_result",

  "ASCENDING",
  "DESCENDING",

  "COL",
  "STR",
  "INT64",
  "BOOL",
  "UINT64",
  "FLOAT",
  "DOUBLE",
  "BYTES",
  "EMPTY",

  "STR_LIST",
  "BYTES_LIST",
  "INT64_LIST",
  "BOOL_LIST",
  "UINT64_LIST",
  "FLOAT_LIST",
  "DOUBLE_LIST",

  "PLUS",
  "MINUS",
  "MULT",
  "DIV",
  "MOD",
  "CONCAT",

  "EQ",
  "NE",
  "LT",
  "LE",
  "GT",
  "GE",
  "LIKE",
  "CONTAINS",
  "EXISTS",
  "HAS_NO_VALUE",

  "AND",
  "OR",
  "NOT",
  "ANY",
  "ALL",
  "IN",
  "CORRELATE",
  #Checks for membership of element in the List.
  "INTERSECT",

  "SUM",
  "MAX",
  "MIN",
  "AVG",
  "LAST",
  "COUNT",
  "ANCESTOR",

  "SECONDS",
  "MINUTES",
  "HOURS",
  "DAYS",
  "WEEKS",

  "RECENT",

  "METRIC",
]

def require(exp, msg=""):
  """
  Raises:
    ValueError on failure.
  """
  if not exp:
    raise ValueError(msg)

def COUNT_QUERY(query_name, FROM=None, WHERE=None, GROUP_BY_COLUMN=None):
  """
  Prepare Query Proto for count queries.
  FROM is a required parameter.
  If WHERE clause is given then result of Query formed by this method will
  contain the number of entities passing the given filter criteria.
  If GROUP_BY_COLUMN is given then result of Query formed by this method will
  provide for each group the number of entities belonging to that particular
  group, after passing the filter criteria if provided.

  Usage:
    For querying we should use CPDB's query method.
    q = COUNT_QUERY(query_name, FROM="entity_type", ...)
    ret = cpdb.query(q)

    We can not use CPDB_IMPL.query() method because that will try to format the
    results by itself and we will not get the expected results.

  Args:
    query_name (str):
      Each query must have a name that starts with component name issuing
      the query. The component name must be registered with entity-db; otherwise
      entity-db will return error.
      e.g. "ergon:task_poll:new_tasks"

    FROM (str):
      Entity type name e.g. "task". FROM is a mandatory clause.

    WHERE (BooleanExpression): Where clause.
      See EQ, NE, LE, LT, GE, GT, LIKE, CONTAINS, AND, OR, NOT, CORRELATE, ALL, ANY,
          IN, LIKE, INTERSECT
      Wrap column names with COL().
      Wrap literals with one of STR, BOOL, INT64, UINT64, FLOAT, DOUBLE,
          BYTES, STR_LIST, BOOL_LIST, INT64_LIST, UINT64_LIST, FLOAT_LIST,
          DOUBLE_LIST.

    GROUP_BY_COLUMN (str):
      Name of column by which entities are grouped.
  """

  require(query_name)
  require(FROM)
  q = Query(entity_list=[EntityGuid(entity_type_name=FROM)])
  q.query_name = query_name
  if WHERE:
    q.where_clause.CopyFrom(WHERE)

  if GROUP_BY_COLUMN:
    q.group_by.group_by_column = GROUP_BY_COLUMN
    # As this is just a count query so setting Limit as zero.
    q.group_by.raw_limit.limit = 0
  else:
    # As this is a count query so setting the flags as kSkipGuidsForEmptyRawColumns
    # to optimise the query processing pipeline
    q.flags = q.FlagTypes.kSkipGuidsForEmptyRawColumns

  return q

def QUERY(query_name, SELECT=None, FROM=None, ENTITIES=None, WHERE=None,
          GROUP_BY=None, ORDER_BY=None, LIMIT=None, SKIP=None,
          SHARD_IDS=None, FLAGS=None, GROUP_BY_SUPPRESS_ANCESTOR_TRAVERSAL=None,
          LOOKUP_QUERIES=None):
  """
  Prepare Query proto.

  If both WHERE and GROUP_BY clauses are given, then WHERE is applied
  first and then GROUP_BY is applied on result of WHERE.

  Args:
    query_name (str):
      Each query must have a name that starts with component name issuing
      the query. The component name must be registered with entity-db; otherwise
      entity-db will return error.
      e.g. "ergon:task_poll:new_tasks"

    FROM (str):
      Entity type name e.g. "task". FROM is a mandatory clause.

    ENTITIES (List of EntityGuid):
      List of entities on which the query is performed.
      Only one of FROM or ENTITIES arguments must be specified.

    WHERE (BooleanExpression): Where clause.
      See EQ, NE, LE, LT, GE, GT, LIKE, CONTAINS, AND, OR, NOT, CORRELATE, ALL, ANY,
          IN, LIKE, INTERSECT
      Wrap column names with COL().
      Wrap literals with one of STR, BOOL, INT64, UINT64, FLOAT, DOUBLE,
          BYTES, STR_LIST, BOOL_LIST, INT64_LIST, UINT64_LIST, FLOAT_LIST,
          DOUBLE_LIST.

    GROUP_BY (str):
      Name of column by which entities are grouped.

    SELECT ([QueryAggregateColumn] or [str]):
      Aggregate columns e.g. [MAX("sequence_id"), AVG("latency")]) or
      raw columns e.g. ["sequence_id", "component"].
      Must not mix aggregate and raw columns.
      If aggregate columns are specified, then GROUP_BY must also be specified.

      See SUM, MIN, MAX, AVG, LAST, COUNT, ANCESTOR

    ORDER_BY (QueryOrderBy or [QueryOrderBy]):
      Specifies sort column and order.
      See ASCENDING, DESCENDING
      Should not be a list when GROUP_BY is mentioned
      [QueryOrderBy] can be used for sorting on multiple raw_columns.

    LIMIT (int):
      Limits number of entities returned by query.

    SKIP (int):
      Number of results to skip before starting to accumulate results
      to return.

    SHARD_IDS (List of str):
      List of the IDF shard IDs. They are typically provided by ShardMap module
      which balances entity loads on each node.

    FLAGS (unsigned int):
      Any number of FlagTypes bitwise or-ed together.
      FlagTypes is of type Query.FlagTypes in
      main/insights/insights_interface/insights_interface.proto

      For eg:
      enum FlagTypes {
        foo = 1;
        bar = 2;
        baz = 4;
      }
      Now FLAGS can take eight different values from 0(nothing enabled) to
      7(all enabled):
      Eg:
      FLAGS = 0(bitwise ..0000) - no flags are enabled.
      FLAGS = 3(bitwise ..0011) - flag types 1 and 2 are enabled.
      FlAGS = 6(bitwise ..0110) - flag types 2 and 4 are enabled.
      FLAGS = 7(bitwise ..0111) - all flag types 1, 2 and 4 are enabled.

    GROUP_BY_SUPPRESS_ANCESTOR_TRAVERSAL (bool):
      If GROUP_BY is an entity type, query processing pipeline creates
      ancestor relationship tree through the parent links (aka foriegn
      references) in the entity. For instance, virtual_disk has a reference to
      vm, and vm has a reference to cluster, insights will filter virtual_disk
      entities based on the cluster to which they belong. If the client wants
      insights server to make use of immediate entity-type attribute value for
      filtering instead of the ancestor relationship, it could set
      GROUP_BY_SUPPRESS_ANCESTOR_TRAVERSAL to true. Note that if the same
      column is specified in multiple leaf expressions,
      GROUP_BY_SUPPRESS_ANCESTOR_TRAVERSAL should be set for all the instances
      or none.

    LOOKUP_QUERIES (List of Query):
      Lookup queries that can be used to join entities from other entity types.
      Lookup queries can be nested (i.e. a lookup query can contain
      another lookup query).

      Sample usage:
        LOOKUP_QUERY = QUERY("lookup_query1", SELECT=["value"],
                             FROM="abac_category",
                             WHERE=IN(COL("_entity_id_"),
                                      COL("category_id_list")))

        query = QUERY("main_query", SELECT=["category_id_list"],
                      FROM="abac_entity_capability",
                      WHERE=EQ(COL("kind_id"), COL("_entity_id_")),
                      LOOKUP_QUERIES=[LOOKUP_QUERY])


  Returns:
    insights_interface_pb2.Query:
      Ready to be passed to GetEntitiesWithMetrics() RPC.

  Raises:
    ValueError:  Invalid argument specified.
  """
  require(query_name)
  require(FROM or ENTITIES,
          "One of FROM or ENTITIES clauses must be specified")
  require(not (FROM and ENTITIES),
          "Cannot specify both FROM and ENTITIES clauses together")
  require(not (GROUP_BY and LOOKUP_QUERIES),
          "Cannot specify both GROUP_BY and LOOKUP_QUERIES clauses together")

  select_raw_columns = False
  select_aggregate_columns = False
  if SELECT:
    select_raw_columns = all(isinstance(c, str) for c in SELECT)
    select_aggregate_columns = \
        all(isinstance(c, QueryAggregateColumn) for c in SELECT)
    require(select_raw_columns ^ select_aggregate_columns,
            "`select` clause must be EITHER list of str OR "
            "list of QueryAggregateColumn: %s" % SELECT)
    require(not select_aggregate_columns or GROUP_BY,
            "Group by clause is mandatory if aggregate columns"
            " are selected")
    require(not (select_raw_columns and GROUP_BY),
            "Cannot select raw columns in GROUP_BY query")

  if FROM:
    q = Query(entity_list=[EntityGuid(entity_type_name=FROM)])
  else:
    q = Query(entity_list=ENTITIES)

  q.query_name = query_name
  if WHERE:
    q.where_clause.CopyFrom(WHERE)

  if GROUP_BY:
    q.group_by.group_by_column = GROUP_BY
    if GROUP_BY_SUPPRESS_ANCESTOR_TRAVERSAL is not None:
      q.group_by.suppress_ancestor_tree_traversal = GROUP_BY_SUPPRESS_ANCESTOR_TRAVERSAL
    if select_aggregate_columns:
      q.group_by.aggregate_columns.extend(SELECT)

  if select_raw_columns:
    for column in SELECT:
      q.group_by.raw_columns.add(column=column,
                                 down_sampling_operator=MetricType.kLast)

  if ORDER_BY:
    if GROUP_BY:
      q.group_by.group_sort_order.CopyFrom(ORDER_BY)
    else:
      if isinstance(ORDER_BY, list):
        q.group_by.raw_sort_order_list.extend(ORDER_BY)
      else:
        q.group_by.raw_sort_order.CopyFrom(ORDER_BY)

  if LIMIT is not None:
    if GROUP_BY:
      q.group_by.group_limit.limit = LIMIT
    else:
      q.group_by.raw_limit.limit = LIMIT

  if SKIP is not None:
    if GROUP_BY:
      q.group_by.group_limit.offset = SKIP
    else:
      q.group_by.raw_limit.offset = SKIP

  if SHARD_IDS:
    q.shard_id_list.extend(SHARD_IDS)

  if LOOKUP_QUERIES:
    q.group_by.lookup_query.extend(LOOKUP_QUERIES)

  if FLAGS is not None:
    q.flags = FLAGS

  return q

def format_result_iter(ret, convert_entity_id=NutanixUuid.from_hex,
                       include_timestamps=False):
  """
  Args:
    ret (insights_interface_pb2.GetEntitiesWithMetricsRet)
    convert_entity_id (callable): Method to convert entity id to CPDB key.
    include_timestamps (bool): Whether to include the last modified timestamp
        of each field. For group by queries, it includes the maximum among all
        last modified timestamp of raw_results in the group.

  Returns:
    See CpdbImpl.query_iter documentation.
  """
  if ret.total_group_count == 0:
    # Return empty iterator.
    return iter([])
  else:
    if ret.group_results_list[0].group_summaries:
      # This was a GROUP_BY query.
      return _format_group_by_result_iter(ret, include_timestamps)
    else:
      return _format_result_iter(ret, convert_entity_id, include_timestamps)

def _format_result_iter(ret, convert_entity_id, include_timestamps):
  counter = 0

  def get_metric_data_fields(metric_data_list):
    fields = []
    for metric_data in metric_data_list:
      count = len(metric_data.value_list)
      log.CHECK(count in (0, 1), "value list: %s" % metric_data.value_list)
      if count == 0:
        field_value = None
        field_timestamp = None
      else:
        field_value = cpdb_utils.get_data_value(metric_data.value_list[0].value)
        field_timestamp = metric_data.value_list[0].timestamp_usecs
      if include_timestamps:
        fields.append((field_value, field_timestamp))
      else:
        fields.append(field_value)
    return fields

  def parse_lookup_query_results(lookup_result):
    lookup_query_results_list = []
    key = convert_entity_id(
      lookup_result.entity_with_metrics.entity_guid.entity_id)
    fields = get_metric_data_fields(
      lookup_result.entity_with_metrics.metric_data_list)
    for lookup_query_result in lookup_result.lookup_query_results:
      lookup_entities = []
      child_lookup_query_results = lookup_query_result.results
      for child in child_lookup_query_results:
        child_result_ret = parse_lookup_query_results(child)
        lookup_entities.append(child_result_ret)
      lookup_query_results_list.append(lookup_entities)
    result_list = [key]
    # There should be atleast one field based on which lookup is performed.
    log.CHECK(len(fields) != 0)
    result_list.append(fields)
    for lookup_query_result in lookup_query_results_list:
      result_list.append(lookup_query_result)
    return tuple(result_list)

  if ret.group_results_list[0].lookup_query_results:
    for lookup_result in ret.group_results_list[0].lookup_query_results:
      counter += 1
      if counter == MAX_ENTITY_NUMBER:
        time.sleep(1e-9)
        counter = 0
      yield parse_lookup_query_results(lookup_result)
  else:
    for raw_result in ret.group_results_list[0].raw_results:
      counter += 1
      if counter == MAX_ENTITY_NUMBER:
        time.sleep(1e-9)
        counter = 0
      key = convert_entity_id(raw_result.entity_guid.entity_id)
      fields = get_metric_data_fields(raw_result.metric_data_list)

      if fields:
        yield key, fields
      else:
        yield key

def _format_group_by_result_iter(ret, include_timestamps):
  for group_result in ret.group_results_list:
    group_by_column_value = cpdb_utils.get_data_value(
        group_result.group_by_column_value)
    aggregate_fields = []
    for summary_result in group_result.group_summaries:
      value_list = summary_result.summary_data.value_list
      count = len(value_list)
      log.CHECK(count in (0, 1))
      if count == 0:
        aggregate_value = None
        max_timestamp = None
      else:
        aggregate_value = cpdb_utils.get_data_value(value_list[0].value)
        max_timestamp = value_list[0].timestamp_usecs

      if include_timestamps:
        aggregate_fields.append((aggregate_value, max_timestamp))
      else:
        aggregate_fields.append(aggregate_value)

    yield (group_by_column_value, aggregate_fields)

def format_result(ret, convert_entity_id=NutanixUuid.from_hex,
                  include_timestamps=False):
  """
  Args:
    ret (insights_interface_pb2.GetEntitiesWithMetricsRet)
    convert_entity_id: Method to convert entity id to CPDB key.
    include_timestamps (bool): Whether to include the last modified timestamp
        of each field. For group by queries, it includes the maximum among all
        last modified timestamp of raw_results in the group.

  Returns:
    See CpdbImpl.query documentation.
  """
  return list(format_result_iter(ret, convert_entity_id, include_timestamps))

def format_metric_result(ret, convert_entity_id=NutanixUuid.from_hex):
  """
  Returns a list of records. Each record is a tuple whose first element
  is `entity_id` and second element is a list of metrics. Each metric is
  in turn a list of data-points where a data-point is a tuple of form
  (timestamp, value).

  q = QUERY_METRICS(..., SELECT=["iops", "percentage_cpu"], ...)
  ret = cpdb.query(q)
  result = format_metric_result(ret)
  for uuid, [iops, percentage_cpu] in result:
    for timestamp, value in iops:
      # process data point.
    for timestamp, value in percentage_cpu:
      # process data point.
  """
  if ret.total_group_count == 0:
    return []

  def extract_result(raw_result):
    key = convert_entity_id(raw_result.entity_guid.entity_id)
    fields = []
    for metric_data in raw_result.metric_data_list:
      value_list = [(tv.timestamp_usecs, cpdb_utils.get_data_value(tv.value))
                    for tv in metric_data.value_list]
      fields.append(value_list)

    if fields:
      return key, fields
    else:
      return key

  return [extract_result(r) for r in ret.group_results_list[0].raw_results]


def ASCENDING(col_name):
  return QueryOrderBy(sort_column=col_name)

def DESCENDING(col_name):
  return QueryOrderBy(sort_column=col_name,
                      sort_order=QueryOrderBy.kDescending)

def COL(col_name, suppress_ancestor_tree_traversal_flag = None):
  if suppress_ancestor_tree_traversal_flag is not None:
    return Expression(leaf=LeafExpression(
                           column=col_name, suppress_ancestor_tree_traversal=
                           suppress_ancestor_tree_traversal_flag))
  else:
    return Expression(leaf=LeafExpression(column=col_name))

def STR(v):
  return Expression(leaf=LeafExpression(value=DataValue(str_value=v)))

def INT64(v):
  return Expression(leaf=LeafExpression(value=DataValue(int64_value=v)))

def BOOL(v):
  return Expression(leaf=LeafExpression(value=DataValue(bool_value=v)))

def UINT64(v):
  return Expression(leaf=LeafExpression(value=DataValue(uint64_value=v)))

def FLOAT(v):
  return Expression(leaf=LeafExpression(value=DataValue(float_value=v)))

def DOUBLE(v):
  return Expression(leaf=LeafExpression(value=DataValue(double_value=v)))

def BYTES(v):
  return Expression(leaf=LeafExpression(value=DataValue(bytes_value=v)))

def EMPTY():
  return Expression(leaf=LeafExpression(value=DataValue()))

def STR_LIST(v):
  dv = DataValue(str_list=DataValue.StrList(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def BYTES_LIST(v):
  dv = DataValue(bytes_list=DataValue.BytesList(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def INT64_LIST(v):
  dv = DataValue(int64_list=DataValue.Int64List(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def BOOL_LIST(v):
  dv = DataValue(bool_list=DataValue.BoolList(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def UINT64_LIST(v):
  dv = DataValue(uint64_list=DataValue.UInt64List(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def FLOAT_LIST(v):
  dv = DataValue(float_list=DataValue.FloatList(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def DOUBLE_LIST(v):
  dv = DataValue(double_list=DataValue.DoubleList(value_list=v))
  return Expression(leaf=LeafExpression(value=dv))

def PLUS(lhs, rhs):
  return Expression(lhs=lhs, rhs=rhs, operator=Expression.kPlus)

def MINUS(lhs, rhs):
  return Expression(lhs=lhs, rhs=rhs, operator=Expression.kMinus)

def MULT(lhs, rhs):
  return Expression(lhs=lhs, rhs=rhs, operator=Expression.kMult)

def DIV(lhs, rhs):
  return Expression(lhs=lhs, rhs=rhs, operator=Expression.kDiv)

def MOD(lhs, rhs):
  return Expression(lhs=lhs, rhs=rhs, operator=Expression.kMod)

def CONCAT(lhs, rhs):
  return Expression(lhs=lhs, rhs=rhs, operator=Expression.kConcat)


def EQ(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=rhs,
                                           operator=ComparisonExpression.kEQ))

def NE(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=rhs,
                                           operator=ComparisonExpression.kNE))

def LT(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=rhs,
                                           operator=ComparisonExpression.kLT))

def LE(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=rhs,
                                           operator=ComparisonExpression.kLE))

def GT(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=rhs,
                                           operator=ComparisonExpression.kGT))

def GE(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=rhs,
                                           operator=ComparisonExpression.kGE))

def LIKE(lhs, pattern):
  """
  Example: LIKE(COL("component"), "acr.*")
  """
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs, rhs=STR(pattern),
                                           operator=ComparisonExpression.kLike))

def EXISTS(lhs):
  """
  Example: EXISTS(COL("component"))
  """
  return BooleanExpression(
      comparison_expr=ComparisonExpression(lhs=lhs,
                                           operator=ComparisonExpression.kExists))

def CONTAINS(lhs, rhs):
  """
  Example:
    CONTAINS(COL("list_attr_name"), STR_LIST(["v"]))
    CONTAINS(COL("list_attr_name"), STR_LIST(["v1", "v2"]))
  """
  return BooleanExpression(
      comparison_expr=ComparisonExpression(
          lhs=lhs, rhs=rhs, operator=ComparisonExpression.kContains))

# >>> QUERY("qname", SELECT=["uuid"], FROM="task",
#           WHERE=HAS_NO_VALUE(COL("component")))
def HAS_NO_VALUE(col):
  return EQ(col, EMPTY())

def IN(lhs, rhs):
  """
  Example:
    IN(COL("uuid"), STR_LIST([u1, u2]))
    IN(COL("status"), STR_LIST(["kRunning", "kQueued"]))
  """
  return BooleanExpression(
      comparison_expr=ComparisonExpression(
          lhs=lhs, rhs=rhs, operator=ComparisonExpression.kIN))

def AND(lhs, rhs):
  return BooleanExpression(lhs=lhs, rhs=rhs,
                           operator=BooleanExpression.kAnd)

def OR(lhs, rhs):
  return BooleanExpression(lhs=lhs, rhs=rhs,
                           operator=BooleanExpression.kOr)

def NOT(lhs):
  return BooleanExpression(lhs=lhs, operator=BooleanExpression.kNot)

def CORRELATE(lhs):
  return BooleanExpression(lhs=lhs, operator=BooleanExpression.kCorrelate)

def ANY(*predicates):
  require(predicates)
  length = len(predicates)
  if length == 1:
    return predicates[0]
  return OR(ANY(*predicates[:length//2]), ANY(*predicates[length//2:]))

def ALL(*predicates):
  """
  Example Usage:
    QUERY("qname", SELECT=["uuid"], FROM="task",
          WHERE=ALL(EQ(COL("component"), STR("genesis")),
                    EQ(COL("operation_type"), STR("create-vm"))))
  """
  require(predicates)
  length = len(predicates)
  if length == 1:
    return predicates[0]
  return AND(ALL(*predicates[:length//2]), ALL(*predicates[length//2:]))

def SUM(col_name):
  return QueryAggregateColumn(column=col_name, operator=MetricType.kSum)

def MAX(col_name):
  return QueryAggregateColumn(column=col_name, operator=MetricType.kMax)

def MIN(col_name):
  return QueryAggregateColumn(column=col_name, operator=MetricType.kMin)

def AVG(col_name):
  return QueryAggregateColumn(column=col_name, operator=MetricType.kAvg)

def LAST(col_name):
  return QueryAggregateColumn(column=col_name, operator=MetricType.kLast)

def COUNT(col_name):
  return QueryAggregateColumn(column=col_name, operator=MetricType.kCount)

def INTERSECT(lhs, rhs):
  return BooleanExpression(
      comparison_expr=ComparisonExpression(
          lhs=lhs, rhs=rhs, operator=ComparisonExpression.kAny))

def ANCESTOR(ancestor_entity_type, ancestor_col_name):
  """
  Use: Used only if joins are requested on an ancestor entity type. The
    ancestor_entity_type can only be the 'group_by_column' attribute.
  Response: The query response will contain the values of the column
    specified by 'ancestor_col_name' for the given ancestor entity
    type in summary results.
  """
  return QueryAggregateColumn(
    column=ancestor_col_name, ancestor_entity_type=ancestor_entity_type)

def SECONDS(s):
  return s

def MINUTES(m):
  return m * SECONDS(60)

def HOURS(h):
  return h * MINUTES(60)

def DAYS(d):
  return d * HOURS(24)

def WEEKS(w):
  return w * DAYS(7)

def RECENT(interval_in_sec):
  now = int(time.time())
  return (now - interval_in_sec, now)


op_map = {
  "SUM": MetricType.kSum,
  "MAX": MetricType.kMax,
  "MIN": MetricType.kMin,
  "AVG": MetricType.kAvg,
  "LAST": MetricType.kLast,
  "COUNT": MetricType.kCount,
}
def METRIC(col, op=None):
  log.CHECK(op in op_map)
  return QueryRawColumn(column=col,
                        down_sampling_operator=op_map[op])


#  >>> print QUERY_METRICS("vm-iops", \
#  ... SELECT=[METRIC("iops", "SUM"), METRIC("percentage_cpu", "AVG")], \
#  ... FROM="vm",\
#  ... SAMPLING_INTERVAL=MINUTES(1), SPAN=RECENT(HOURS(12)))
#  entity_list {
#    entity_type_name: "vm"
#  }
#  start_time_usecs: 1483381479000000
#  end_time_usecs: 1483424679000000
#  group_by {
#    raw_columns {
#      column: "iops"
#      down_sampling_operator: kSum
#    }
#    raw_columns {
#      column: "percentage_cpu"
#      down_sampling_operator: kAvg
#    }
#    down_sampling_interval_secs: 60
#  }
#  query_name: "vm-iops"
def QUERY_METRICS(query_name, SELECT=None, FROM=None, ENTITIES=None, WHERE=None,
                  ORDER_BY=None, LIMIT=None, SKIP=None,
                  SAMPLING_INTERVAL=None, SPAN=None):
  """
  Prepare Query proto to query metrics.

  Args:
    query_name (str):
      Each query must have a name that starts with component name issuing
      the query. The component name must be registered with entity-db; otherwise
      entity-db will return error.
      e.g. "ergon:task_poll:new_tasks"

    FROM (str):
      Entity type name e.g. "task". FROM is a mandatory clause.

    ENTITIES (List of EntityGuid):
      List of entities on which the query is performed.
      Only one of FROM or ENTITIES arguments must be specified.

    WHERE (BooleanExpression): Where clause.
      See EQ, NE, LE, LT, GE, GT, LIKE, CONTAINS, AND, OR, NOT, CORRELATE, ALL, ANY,
          IN, LIKE, EXISTS
      Wrap column names with COL().
      Wrap literals with one of STR, BOOL, INT64, UINT64, FLOAT, DOUBLE,
          BYTES, STR_LIST, BOOL_LIST, INT64_LIST, UINT64_LIST, FLOAT_LIST,
          DOUBLE_LIST.

    SELECT ([str, QueryRawColumn]):
      Metric name as str in which case default down sampling operator will be
      used. Else an instance of QueryRawColumn. See `METRIC()`.

    ORDER_BY (QueryOrderBy or [QueryOrderBy]):
      Specifies sort column, sort order and sort key.
      See ASCENDING, DESCENDING
      Should not be a list when GROUP_BY is mentioned
      [QueryOrderBy] can be used for sorting on multiple raw_columns.

    LIMIT (int):
      Limits number of entities returned by query.

    SKIP (int):
      Number of results to skip before starting to accumulate results
      to return.

    SAMPLING_INTERVAL (int):
      Down sampling interval in seconds. There will be 0 or 1 value per
      interval. See SECONDS, MINUTES, HOURS, DAYS, WEEKS.

    SPAN (int, int):
      Tuple specifying start-time and end-time in seconds. Only those
      data points which fall in this interval are returned.
      If end-time is `NOW`, then you can use `RECENT` with SECONDS,
      MINUTES, HOURS, DAYS and WEEKS to specify this value e.g.
      RECENT(HOURS(12)).

  Returns:
    insights_interface_pb2.Query:
      Ready to be passed to GetEntitiesWithMetrics() RPC.

  Raises:
    ValueError:  Invalid argument specified.
  """
  require(query_name)
  require(FROM or ENTITIES,
          "One of FROM or ENTITIES clauses must be specified")
  require(not (FROM and ENTITIES),
          "Cannot specify both FROM and ENTITIES clauses together")

  q = Query(query_name=query_name)

  if FROM:
    entity_list = [EntityGuid(entity_type_name=FROM)]
  else:
    entity_list = ENTITIES
  q.entity_list.extend(entity_list)

  if SPAN:
    q.start_time_usecs = SPAN[0] * 10**6
    q.end_time_usecs = SPAN[1] * 10**6

  if SAMPLING_INTERVAL:
    q.group_by.down_sampling_interval_secs = SAMPLING_INTERVAL

  if WHERE:
    q.where_clause.CopyFrom(WHERE)

  for column in SELECT:
    require(isinstance(column, (str, QueryRawColumn)),
            "Each column in SELECT clause must be either a str or a "
            "QueryRawColumn: %r" % column)
    if isinstance(column, QueryRawColumn):
      q.group_by.raw_columns.extend([column])
    else:
      q.group_by.raw_columns.add(column=column)

  if ORDER_BY is not None:
    if isinstance(ORDER_BY, list):
      q.group_by.raw_sort_order_list.extend(ORDER_BY)
    else:
      q.group_by.raw_sort_order.CopyFrom(ORDER_BY)

  if LIMIT is not None:
    q.group_by.raw_limit.limit = LIMIT

  if SKIP is not None:
    q.group_by.raw_limit.offset = SKIP

  return q
