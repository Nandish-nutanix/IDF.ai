//
// Copyright (c) 2017 Nutanix Inc. All rights reserved.
//
// Author: amit.jambure@nutanix.com
//

// `query` package provides utility functions to simplify construction of
// InsightsDB query protos. This package is a port of Python module
// insights_interface.cpdb_interface.cpdb_query.
//
// Examples 1:
//
//    import . "insights/insights_interface/query"  // Use "Dot import" to
//                                                  // import query package.
//
//    q, err := QUERY("test").
//        SELECT("component", "sequence_id").
//        FROM("task").
//        WHERE(ANY(EQ(COL("component"), STR("genesis")),
//                  EQ(COL("component"), STR("prism")))).
//        Proto()
//
//    if err != nil {
//        // Query is not valid. err.Error() contains reason.
//    }
//    // Use `q` to invoke GetEntitiesWithMetrics() RPC on DB.
//
// Example 2:
//
//    q, err := QUERY("test2").
//        SELECT(MAX("sequence_id")).
//        FROM("task").
//        GROUP_BY("component").
//        Proto()
//
// Example 3:
// q, err := QUERY("namespace_test").
// FROM("entity1").
// WHERE(EQ(SetColNp(COL("col1"), "namespace1"), STR("hello"))).
// SELECT("num_cpus", AttrWithNp("num_cpus", "np1")).
// Proto()

package query

import (
  "errors"
  "fmt"
  "time"
  . "insights/insights_interface"
  "github.com/golang/protobuf/proto"
)

//============================================================================

func COL(c string) *Expression {
  le := &LeafExpression{Column: proto.String(c)}
  return &Expression{Leaf: le}
}

func SetColNp(col *Expression, namespace string) *Expression {
  col.Leaf.ColumnNamespace = proto.String(namespace)
  return col
}

func exp(dv *DataValue) *Expression {
  le := &LeafExpression{Value: dv}
  return &Expression{Leaf: le}
}

func STR(v string) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_StrValue{StrValue: v}
  return exp(dv)
}

func INT64(v int64) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_Int64Value{Int64Value: v}
  return exp(dv)
}

func BOOL(v bool) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_BoolValue{BoolValue: v}
  return exp(dv)
}

func UINT64(v uint64) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_Uint64Value{Uint64Value: v}
  return exp(dv)
}

func FLOAT(v float32) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_FloatValue{FloatValue: v}
  return exp(dv)
}

func DOUBLE(v float64) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_DoubleValue{DoubleValue: v}
  return exp(dv)
}

func BYTES(v []byte) *Expression {
  dv := &DataValue{}
  dv.ValueType = &DataValue_BytesValue{BytesValue: v}
  return exp(dv)
}

func STR_LIST(v ...string) *Expression {
  dv := &DataValue{}
  lst := &DataValue_StrList{ValueList: v}
  dv.ValueType = &DataValue_StrList_{StrList: lst}
  return exp(dv)
}

func INT64_LIST(v ...int64) *Expression {
  dv := &DataValue{}
  lst := &DataValue_Int64List{ValueList: v}
  dv.ValueType = &DataValue_Int64List_{Int64List: lst}
  return exp(dv)
}

func BOOL_LIST(v ...bool) *Expression {
  dv := &DataValue{}
  lst := &DataValue_BoolList{ValueList: v}
  dv.ValueType = &DataValue_BoolList_{BoolList: lst}
  return exp(dv)
}

func UINT64_LIST(v ...uint64) *Expression {
  dv := &DataValue{}
  lst := &DataValue_UInt64List{ValueList: v}
  dv.ValueType = &DataValue_Uint64List{Uint64List: lst}
  return exp(dv)
}

func FLOAT_LIST(v ...float32) *Expression {
  dv := &DataValue{}
  lst := &DataValue_FloatList{ValueList: v}
  dv.ValueType = &DataValue_FloatList_{FloatList: lst}
  return exp(dv)
}

func DOUBLE_LIST(v ...float64) *Expression {
  dv := &DataValue{}
  lst := &DataValue_DoubleList{ValueList: v}
  dv.ValueType = &DataValue_DoubleList_{DoubleList: lst}
  return exp(dv)
}

func BYTES_LIST(v ...[]byte) *Expression {
  dv := &DataValue{}
  lst := &DataValue_BytesList{ValueList: v}
  dv.ValueType = &DataValue_BytesList_{BytesList: lst}
  return exp(dv)
}

func EMPTY() *Expression {
  return exp(&DataValue{})
}

//============================================================================

func aexp(lhs, rhs *Expression, op Expression_Operator) *Expression {
  return &Expression{Lhs: lhs, Rhs: rhs, Operator: op.Enum()}
}

func PLUS(lhs, rhs *Expression) *Expression {
  return aexp(lhs, rhs, Expression_kPlus)
}

func MINUS(lhs, rhs *Expression) *Expression {
  return aexp(lhs, rhs, Expression_kMinus)
}

func MULT(lhs, rhs *Expression) *Expression {
  return aexp(lhs, rhs, Expression_kMult)
}

func DIV(lhs, rhs *Expression) *Expression {
  return aexp(lhs, rhs, Expression_kDiv)
}

func MOD(lhs, rhs *Expression) *Expression {
  return aexp(lhs, rhs, Expression_kMod)
}

func CONCAT(lhs, rhs *Expression) *Expression {
  return aexp(lhs, rhs, Expression_kConcat)
}

//============================================================================

func cexp(lhs, rhs *Expression, op ComparisonExpression_Operator) *BooleanExpression {
  c := &ComparisonExpression{Lhs: lhs, Rhs: rhs, Operator: op.Enum()}
  return &BooleanExpression{ComparisonExpr: c}
}

func EQ(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kEQ)
}

func NE(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kNE)
}

func LT(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kLT)
}

func LE(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kLE)
}

func GT(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kGT)
}

func GE(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kGE)
}

// Example: LIKE(COL("component"), "acr.*")
func LIKE(lhs *Expression, rhs string) *BooleanExpression {
  return cexp(lhs, STR(rhs), ComparisonExpression_kLike)
}

// Example: EXISTS(COL ("component"))
func EXISTS(lhs *Expression) *BooleanExpression {
  return cexp(lhs, nil, ComparisonExpression_kExists)
}

// CONTAINS(COL("list_attr_name"), STR_LIST("v"))
// CONTAINS(COL("list_attr_name"), STR_LIST("v1", "v2"))
func CONTAINS(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kContains)
}

// IN(COL("uuid"), STR_LIST(u1, u2))
// IN(COL("status"), STR_LIST("kRunning", "kQueued"))
func IN(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kIN)
}

// INTERSECTS(COL("list_attr_name"), STR_LIST("v1", "v2", "v3"))
//   Evaluates to True if intersection of values in `list_attr_name` attribute
//   and ["v1", "v2", "v3"] is not empty.
func INTERSECTS(lhs, rhs *Expression) *BooleanExpression {
  return cexp(lhs, rhs, ComparisonExpression_kAny)
}

func HAS_NO_VALUE(col *Expression) *BooleanExpression {
  return EQ(col, EMPTY())
}

func ANCESTOR(ancestorEntityType, ancestorColName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(ancestorColName),
                               AncestorEntityType: proto.String(ancestorEntityType)}
}

//============================================================================

func SECONDS(s uint32) uint32 {
  return s
}

func MINUTES(m uint32) uint32 {
  return m * SECONDS(60)
}

func HOURS(h uint32) uint32 {
  return h * MINUTES(60)
}

func DAYS(d uint32)  uint32 {
  return d * HOURS(24)
}

func WEEKS(w uint32) uint32 {
  return w * DAYS(7)
}

func RECENT(IntervalInSec uint32) (uint64, uint64) {
  now := uint32(time.Now().UnixNano()/1e9)
  return uint64(now - IntervalInSec), uint64(now)
}

//============================================================================

func AND(lhs, rhs *BooleanExpression) *BooleanExpression {
  return &BooleanExpression{Lhs: lhs, Rhs: rhs, Operator: BooleanExpression_kAnd.Enum()}
}

func OR(lhs, rhs *BooleanExpression) *BooleanExpression {
  return &BooleanExpression{Lhs: lhs, Rhs: rhs, Operator: BooleanExpression_kOr.Enum()}
}

func NOT(lhs *BooleanExpression) *BooleanExpression {
  return &BooleanExpression{Lhs: lhs, Operator: BooleanExpression_kNot.Enum()}
}

func CORRELATE(lhs *BooleanExpression) *BooleanExpression {
  return &BooleanExpression{Lhs: lhs, Operator: BooleanExpression_kCorrelate.Enum()}
}

func ANY(predicates ...*BooleanExpression) *BooleanExpression {
  length := len(predicates)
  if length == 0 {
    panic("No argument specified in ANY()")
  }
  if length == 1 {
    return predicates[0]
  }
  return OR(ANY(predicates[0:length/2]...), ANY(predicates[length/2:]...))
}

func ALL(predicates ...*BooleanExpression) *BooleanExpression {
  length := len(predicates)
  if length == 0 {
    panic("No argument specified in ALL()")
  }
  if length == 1 {
    return predicates[0]
  }
  return AND(ALL(predicates[0:length/2]...), ALL(predicates[length/2:]...))
}

//============================================================================

func SUM(colName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(colName),
    Operator: MetricType_kSum.Enum()}
}

func MAX(colName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(colName),
    Operator: MetricType_kMax.Enum()}
}

func MIN(colName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(colName),
    Operator: MetricType_kMin.Enum()}
}

func AVG(colName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(colName),
    Operator: MetricType_kAvg.Enum()}
}

func LAST(colName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(colName),
    Operator: MetricType_kLast.Enum()}
}

func COUNT(colName string) *QueryAggregateColumn {
  return &QueryAggregateColumn{Column: proto.String(colName),
    Operator: MetricType_kCount.Enum()}
}

func SetAggrColNp(queryAggregateColumn *QueryAggregateColumn,
  namespace string) *QueryAggregateColumn {
  queryAggregateColumn.ColumnNamespace = proto.String(namespace)
  return queryAggregateColumn
}

//============================================================================

func ASCENDING(colName string) *QueryOrderBy {
  return &QueryOrderBy{SortColumn: proto.String(colName)}
}

func DESCENDING(colName string) *QueryOrderBy {
  return &QueryOrderBy{
    SortColumn: proto.String(colName),
    SortOrder:  QueryOrderBy_kDescending.Enum()}
}

func SetOrderByNp(orderBy *QueryOrderBy, namespace string) *QueryOrderBy {
  orderBy.SortColumnNamespace = proto.String(namespace)
  return orderBy
}

//============================================================================

var op_map = map[string]*MetricType_Operator {
  "SUM": MetricType_kSum.Enum(),
  "MAX": MetricType_kMax.Enum(),
  "MIN": MetricType_kMin.Enum(),
  "AVG": MetricType_kAvg.Enum(),
  "LAST": MetricType_kLast.Enum(),
  "COUNT": MetricType_kCount.Enum()}

func METRIC(colName string, op string) *QueryRawColumn {
  return &QueryRawColumn{Column: proto.String(colName),
                         DownSamplingOperator: op_map[op]}
}

func AttrWithNp(colName, namespace string) *QueryRawColumn {
  return &QueryRawColumn{Column: proto.String(colName),
                         ColumnNamespace: proto.String(namespace)}
}

type QueryBuilder struct {
  queryName        string
  rawColumns       []*QueryRawColumn
  aggregateColumns []*QueryAggregateColumn
  entityList       []*EntityGuid
  where            *BooleanExpression
  groupByColName   string
  orderByList      []*QueryOrderBy
  limit            int64
  skip             int64
  shardIds         []string
  flags            uint64
  samplingInterval uint32
  spanStart        uint64
  spanEnd          uint64
  lookupQueries    []*Query

  isGroupByQuery   bool
  isCountQuery     bool
}

// Currently if a groupBy clause is specified in QueryBuilder, LIMIT and OFFSET
// values are set to 'group_limit'. 'raw_limit' values will have to be set
// manually.
func QUERY(name string) *QueryBuilder {
  return &QueryBuilder{queryName: name, limit: -1, skip: -1}
}

func COUNT_QUERY(name string) *QueryBuilder {
  return &QueryBuilder{queryName: name, limit: 0, isCountQuery: true}
}

// All arguments of `SELECT()` must be of type either `string`,
// *QueryAggregateColumn or *QueryRawColumn.
func (self *QueryBuilder) SELECT(cols ...interface{}) *QueryBuilder {
  for i, c := range cols {
    switch col := c.(type) {
    case string:
      rawCol := &QueryRawColumn{
        Column:               proto.String(col),
        DownSamplingOperator: MetricType_kLast.Enum(),
      }
      self.rawColumns = append(self.rawColumns, rawCol)

    case *QueryAggregateColumn:
      self.aggregateColumns = append(self.aggregateColumns, col)

    case *QueryRawColumn:
      self.rawColumns = append(self.rawColumns, col)

    default:
      panic(fmt.Sprintf("Argument %d of SELECT() has incorrect type %T", i+1, col))
    }
  }
  return self
}

func (self *QueryBuilder) FROM(entityTypeName string) *QueryBuilder {
  eguid := &EntityGuid{EntityTypeName: proto.String(entityTypeName)}
  self.entityList = []*EntityGuid{eguid}
  return self
}

func (self *QueryBuilder) FROM_ENTITIES(entityList []*EntityGuid) *QueryBuilder {
  self.entityList = entityList
  return self
}

func (self *QueryBuilder) WHERE(predicate *BooleanExpression) *QueryBuilder {
  self.where = predicate
  return self
}

func (self *QueryBuilder) GROUP_BY(colName string) *QueryBuilder {
  self.groupByColName = colName
  self.isGroupByQuery = true
  return self
}

func (self *QueryBuilder) ORDER_BY(orderBy *QueryOrderBy) *QueryBuilder {
  self.orderByList = []*QueryOrderBy{orderBy}
  return self
}

func (self *QueryBuilder) ORDER_BY_LIST(orderByList []*QueryOrderBy) *QueryBuilder {
  self.orderByList = orderByList
  return self
}

func (self *QueryBuilder) LIMIT(limit int64) *QueryBuilder {
  self.limit = limit
  return self
}

func (self *QueryBuilder) SKIP(skip int64) *QueryBuilder {
  self.skip = skip
  return self
}

func (self *QueryBuilder) SHARD_IDS(shardIds []string) *QueryBuilder {
  self.shardIds = shardIds
  return self
}

func (self *QueryBuilder) FLAGS(flags uint64) *QueryBuilder {
  self.flags = flags
  return self
}

func (self *QueryBuilder) SAMPLING_INTERVAL(samplingInterval uint32) *QueryBuilder {
  self.samplingInterval = samplingInterval
  return self
}

func (self *QueryBuilder) SPAN(spanStart uint64, spanEnd uint64) *QueryBuilder {
  self.spanStart = spanStart
  self.spanEnd   = spanEnd
  return self
}

func (self *QueryBuilder) LOOKUP_QUERIES(lookupQueries []*Query) *QueryBuilder {
  self.lookupQueries = lookupQueries
  return self
}

func (self *QueryBuilder) validate() error {
  if self.queryName == "" {
    return errors.New("Query name not specified")
  }
  return nil
}

func (self *QueryBuilder) Proto() (*Query, error) {
  if err := self.validate(); err != nil {
    return nil, err
  }

  q := &Query{}
  q.GroupBy = &QueryGroupBy{}

  q.QueryName = proto.String(self.queryName)

  // SELECT
  q.GroupBy.AggregateColumns = self.aggregateColumns
  q.GroupBy.RawColumns = self.rawColumns

  // FROM
  q.EntityList = self.entityList

  // WHERE
  q.WhereClause = self.where

  // GROUP_BY
  if self.isGroupByQuery {
    q.GroupBy.GroupByColumn = proto.String(self.groupByColName)
  }

  // ORDER_BY
  if self.isGroupByQuery && len(self.orderByList) > 0 {
    if (len(self.orderByList) > 1) {
      err := errors.New("Order by has to be a single value in group by query.")
      return nil, err
    }
    q.GroupBy.GroupSortOrder = self.orderByList[0]
  } else {
    if len(self.orderByList) == 1 {
      q.GroupBy.RawSortOrder = self.orderByList[0]
    } else if len(self.orderByList) > 1 {
      q.GroupBy.RawSortOrderList = self.orderByList
    }
  }

  // LIMIT, SKIP
  if self.limit != -1 || self.skip != -1 {
    ql := &QueryLimit{}
    if self.limit != -1 {
      ql.Limit = proto.Int64(self.limit)
    }
    if self.skip != -1 {
      ql.Offset = proto.Int64(self.skip)
    }
    if self.isGroupByQuery {
      if self.isCountQuery {
        q.GroupBy.RawLimit = ql
      } else {
        q.GroupBy.GroupLimit = ql
      }
    } else {
      q.GroupBy.RawLimit = ql
    }
  }

  // SAMPLING_INTERVAL
  if self.samplingInterval != 0 {
    q.GroupBy.DownSamplingIntervalSecs = proto.Uint32(self.samplingInterval)
  }

  // SPAN
  q.StartTimeUsecs = proto.Uint64(self.spanStart*1e6)
  q.EndTimeUsecs   = proto.Uint64(self.spanEnd*1e6)

  // SHARD_IDS
  q.ShardIdList = self.shardIds

  // FLAGS
  q.Flags = proto.Uint64(self.flags)

  // LOOKUP_QUERY
  q.GroupBy.LookupQuery = self.lookupQueries

  return q, nil
}
