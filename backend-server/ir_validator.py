"""
ir_validator.py - Schema-aware validation + repair for QueryIR, and a
raw-proto -> IR extractor for the fallback path.

The validator does three jobs against the REAL schema (schema_service):
  1. Validate: does the entity type exist? Is every referenced column a real
     attribute (or a system column)? Are value types sane for the column?
  2. Repair: snap unknown entity types / columns to the nearest real one,
     coerce value types to match the column's declared data type. Every fix is
     recorded so the caller can compute a confidence level.
  3. Report: structured errors/warnings/fixes + a quality verdict
     ("exact" | "repaired" | "low").

`proto_to_ir` parses arbitrary IDF proto text (via proto_ast) into a QueryIR so
the pipeline can recover a structured query even when the model emitted free
proto instead of constrained JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import proto_ast
import schema_service
from query_ir import (ApiMethod, AttributeIR, FilterIR, Operator, QueryIR,
                      ValueType)

# Value type that matches a schema data_type.
_DATA_TYPE_TO_VALUE_ENUM = {
    "string": ValueType.str_value,
    "bytes": ValueType.str_value,
    "int64": ValueType.int64_value,
    "uint64": ValueType.uint64_value,
    "bool": ValueType.bool_value,
    "boolean": ValueType.bool_value,
    "float": ValueType.float_value,
    "double": ValueType.double_value,
}

# APIs that operate on a concrete entity TYPE whose columns we can validate.
_COLUMN_VALIDATED_APIS = {
    ApiMethod.GetEntitiesWithMetrics,
    ApiMethod.BatchGetEntitiesWithMetrics,
    ApiMethod.GetMetricData,
}


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)

    @property
    def quality(self) -> str:
        if self.errors:
            return "low"
        if self.fixes:
            return "repaired"
        return "exact"

    @property
    def confidence(self) -> float:
        if self.errors:
            return 0.4
        if self.fixes:
            return 0.8
        return 1.0


def _coerce_value_type(entity_type: str, column: str, current: ValueType) -> Optional[ValueType]:
    """Return the value type matching the column's schema data type, if different."""
    dt = schema_service.data_type_of(entity_type, column)
    if not dt:
        return None
    target = _DATA_TYPE_TO_VALUE_ENUM.get(dt.lower())
    if target and target != current:
        return target
    return None


def validate_and_repair(ir: QueryIR) -> ValidationReport:
    """Validate the IR against the real schema and repair it in place."""
    report = ValidationReport()

    # --- entity type ---
    et = ir.entity_type
    if et and not schema_service.has_entity(et):
        snapped = schema_service.nearest_entity_type(et)
        if snapped and snapped != et:
            report.fixes.append(f'entity type "{et}" -> "{snapped}"')
            ir.entity_type = snapped
            et = snapped
        else:
            report.warnings.append(f'entity type "{et}" not found in schema')

    api = ir.api_method
    if api not in _COLUMN_VALIDATED_APIS or not et:
        # Nothing more we can schema-check for this API.
        return report

    if not schema_service.has_entity(et):
        return report

    # --- filter columns + value types ---
    for f in ir.filters:
        if not f.column:
            continue
        if not schema_service.has_attribute(et, f.column):
            snapped = schema_service.nearest_attribute(et, f.column)
            if snapped and snapped != f.column:
                report.fixes.append(f'filter column "{f.column}" -> "{snapped}"')
                f.column = snapped
            else:
                report.warnings.append(f'filter column "{f.column}" is not a known attribute of {et}')
        # coerce value type to match schema
        if f.operator != Operator.kExists:
            coerced = _coerce_value_type(et, f.column, f.value_type)
            if coerced:
                report.fixes.append(f'filter "{f.column}" value type {f.value_type.value} -> {coerced.value}')
                f.value_type = coerced

    # --- select columns ---
    repaired_cols = []
    for c in ir.columns:
        if not c:
            continue
        if schema_service.has_attribute(et, c):
            repaired_cols.append(c)
            continue
        snapped = schema_service.nearest_attribute(et, c)
        if snapped and snapped != c:
            report.fixes.append(f'column "{c}" -> "{snapped}"')
            repaired_cols.append(snapped)
        else:
            report.warnings.append(f'column "{c}" is not a known attribute of {et}')
            repaired_cols.append(c)  # keep; cluster may still resolve internal cols
    ir.columns = list(dict.fromkeys(repaired_cols))

    # --- sort column ---
    if ir.sort_column and not schema_service.has_attribute(et, ir.sort_column):
        snapped = schema_service.nearest_attribute(et, ir.sort_column)
        if snapped and snapped != ir.sort_column:
            report.fixes.append(f'sort column "{ir.sort_column}" -> "{snapped}"')
            ir.sort_column = snapped
        else:
            report.warnings.append(f'sort column "{ir.sort_column}" is not a known attribute of {et}')

    return report


# ---------------------------------------------------------------------------
# Raw proto text -> QueryIR (fallback / self-correct recovery)
# ---------------------------------------------------------------------------

_VALUE_FIELDS = {
    "str_value": ValueType.str_value,
    "int64_value": ValueType.int64_value,
    "uint64_value": ValueType.uint64_value,
    "bool_value": ValueType.bool_value,
    "float_value": ValueType.float_value,
    "double_value": ValueType.double_value,
}


def _extract_filters(node: dict) -> List[FilterIR]:
    """Pull comparison_expr blocks (any depth) into FilterIR list."""
    filters: List[FilterIR] = []
    for cmp_node in proto_ast.collect(node, "comparison_expr"):
        # column from lhs.leaf.column
        col = proto_ast.find_first_scalar_anywhere(cmp_node, "column")
        op = proto_ast.find_first_scalar_anywhere(cmp_node, "operator") or "kEQ"
        if op not in {o.value for o in Operator}:
            op = "kEQ"
        # value: look for any known value field under rhs
        value, vt = "", ValueType.str_value
        for vf, enum_vt in _VALUE_FIELDS.items():
            v = proto_ast.find_first_scalar_anywhere(cmp_node, vf)
            if v is not None:
                value, vt = v, enum_vt
                break
        if col:
            filters.append(FilterIR(column=col, operator=Operator(op), value=value, value_type=vt))
    return filters


def proto_to_ir(proto_text: str, api_method: str) -> QueryIR:
    """Best-effort parse of raw IDF proto text into a QueryIR."""
    ast = proto_ast.parse(proto_text or "")
    api = api_method if api_method in {m.value for m in ApiMethod} else "GetEntitiesWithMetrics"
    ir = QueryIR(api_method=ApiMethod(api))

    ir.entity_type = proto_ast.find_first_scalar_anywhere(ast, "entity_type_name")
    eid = proto_ast.find_first_scalar_anywhere(ast, "entity_id")
    if eid:
        ir.entity_id = eid

    if api in ("GetEntitiesWithMetrics", "BatchGetEntitiesWithMetrics"):
        # columns from raw_columns { column: X }
        cols = []
        for rc in proto_ast.collect(ast, "raw_columns"):
            c = proto_ast.scalar_value(rc, "column")
            if c:
                cols.append(c)
        ir.columns = list(dict.fromkeys(cols))
        ir.filters = _extract_filters(ast)
        # sort
        for so in proto_ast.collect(ast, "raw_sort_order"):
            sc = proto_ast.scalar_value(so, "column")
            order = proto_ast.scalar_value(so, "order")
            if sc:
                ir.sort_column = sc
                ir.sort_desc = (order == "kDescending")
                break
        # limit
        for rl in proto_ast.collect(ast, "raw_limit"):
            lim = proto_ast.scalar_value(rl, "limit")
            off = proto_ast.scalar_value(rl, "offset")
            if lim is not None and str(lim).lstrip("-").isdigit():
                ir.limit = int(lim)
            if off is not None and str(off).lstrip("-").isdigit():
                ir.offset = int(off)
            break
    elif api in ("UpdateEntity", "BatchUpdateEntities"):
        attrs = []
        for ad in proto_ast.collect(ast, "attribute_data"):
            name = proto_ast.scalar_value(ad, "name")
            if not name:
                continue
            value, vt = "", ValueType.str_value
            for vf, enum_vt in _VALUE_FIELDS.items():
                v = proto_ast.find_first_scalar_anywhere(ad, vf)
                if v is not None:
                    value, vt = v, enum_vt
                    break
            attrs.append(AttributeIR(name=name, value=value, value_type=vt))
        ir.attributes = attrs
        cas = proto_ast.find_first_scalar_anywhere(ast, "cas_value")
        if cas is not None and str(cas).lstrip("-").isdigit():
            ir.cas_value = int(cas)
    elif api == "SpotLightSearch":
        ir.search_term = proto_ast.find_first_scalar_anywhere(ast, "search_term")
    elif api == "PutEvent":
        ir.event_type = proto_ast.find_first_scalar_anywhere(ast, "event_type")
    elif api == "GetMetricTypes":
        ir.regex = proto_ast.find_first_scalar_anywhere(ast, "regex")

    return ir
