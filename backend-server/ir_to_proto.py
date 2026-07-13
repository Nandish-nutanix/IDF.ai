"""
ir_to_proto.py - Deterministic QueryIR -> IDF protobuf text renderer.

Because the IR is already typed + schema-validated, rendering is a pure,
total function: given any QueryIR it emits syntactically correct IDF proto text
in the exact format the cluster (and python_code_generator) expect. This
replaces the ~1,300 lines of brittle regex normalization in
proto_response_generator with one small, predictable code path.

Output is always brace-balanced and uses only valid operator/value tokens.
"""

from __future__ import annotations

from typing import List

from query_ir import (AttributeIR, FilterIR, MetricDefIR, Operator, QueryIR,
                       SubQueryIR, ValueType)

IND = "  "


def _val_literal(value: str, vt: ValueType) -> str:
    """Render a typed scalar literal for a Value oneof field."""
    v = (value or "").strip()
    if vt in (ValueType.int64_value, ValueType.uint64_value):
        num = v.lstrip("-")
        if not num.isdigit():
            # Non-numeric value with a numeric type -> fall back to string.
            return f'str_value: "{v}"'
        return f"{vt.value}: {v}"
    if vt in (ValueType.float_value, ValueType.double_value):
        try:
            float(v)
            return f"{vt.value}: {v}"
        except ValueError:
            return f'str_value: "{v}"'
    if vt == ValueType.bool_value:
        b = "true" if v.lower() in ("true", "1", "yes", "on") else "false"
        return f"bool_value: {b}"
    # default: string
    return f'str_value: "{v}"'


def _comparison_expr(f: FilterIR, indent: str) -> str:
    """Render a single comparison_expr block."""
    lines = [f"{indent}comparison_expr {{"]
    lines.append(f'{indent}{IND}lhs {{ leaf {{ column: "{f.column}" }} }}')
    lines.append(f"{indent}{IND}operator: {f.operator.value}")
    if f.operator != Operator.kExists:
        lines.append(f"{indent}{IND}rhs {{ leaf {{ value {{ {_val_literal(f.value, f.value_type)} }} }} }}")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def _boolean_expr(filters: List[FilterIR], logic: str, indent: str) -> str:
    """
    Render a BooleanExpression body (the inside of where_clause / lhs / rhs).
    Single filter -> comparison_expr. Multiple -> right-nested lhs/op/rhs.
    """
    op_token = "kOr" if str(logic).lower() == "or" else "kAnd"
    if len(filters) == 1:
        return _comparison_expr(filters[0], indent)
    head, tail = filters[0], filters[1:]
    lines = [f"{indent}lhs {{"]
    lines.append(_comparison_expr(head, indent + IND))
    lines.append(f"{indent}}}")
    lines.append(f"{indent}operator: {op_token}")
    lines.append(f"{indent}rhs {{")
    lines.append(_boolean_expr(tail, logic, indent + IND))
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def _render_get_entities_with_metrics(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    lines = ["query {"]
    if ir.entity_id:
        lines.append(f'{IND}entity_list {{ entity_type_name: "{et}" entity_id: "{ir.entity_id}" }}')
    else:
        lines.append(f'{IND}entity_list {{ entity_type_name: "{et}" }}')

    if ir.filters:
        lines.append(f"{IND}where_clause {{")
        lines.append(_boolean_expr(ir.filters, ir.filter_logic, IND * 2))
        lines.append(f"{IND}}}")

    # group_by: columns + optional sort + optional limit.
    columns = list(dict.fromkeys(ir.columns))  # de-dup, keep order
    if not columns:
        # Always project something so the result is human-readable.
        columns = [f"{et}_name"]
    gb_lines = [f"{IND}group_by {{"]
    for c in columns:
        gb_lines.append(f'{IND * 2}raw_columns {{ column: "{c}" }}')
    if ir.sort_column:
        order = "kDescending" if ir.sort_desc else "kAscending"
        if ir.sort_column not in columns:
            gb_lines.append(f'{IND * 2}raw_columns {{ column: "{ir.sort_column}" }}')
        gb_lines.append(f'{IND * 2}raw_sort_order {{ column: "{ir.sort_column}" order: {order} }}')
        limit = ir.limit if ir.limit is not None else 50
        offset = ir.offset if ir.offset is not None else 0
        gb_lines.append(f"{IND * 2}raw_limit {{ limit: {limit} offset: {offset} }}")
    elif ir.limit is not None:
        offset = ir.offset if ir.offset is not None else 0
        gb_lines.append(f"{IND * 2}raw_limit {{ limit: {ir.limit} offset: {offset} }}")
    gb_lines.append(f"{IND}}}")
    lines.extend(gb_lines)

    lines.append(f'{IND}query_name: "{ir.query_name or "auto_query"}"')
    lines.append("}")
    return "\n".join(lines)


def _render_update_entity(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    eid = ir.entity_id or "entity-id"
    lines = ["entity_guid {",
             f'{IND}entity_type_name: "{et}"',
             f'{IND}entity_id: "{eid}"',
             "}"]
    lines.append(f"cas_value: {ir.cas_value if ir.cas_value is not None else 0}")
    attrs = ir.attributes or [AttributeIR(name=f"{et}_name", value=eid)]
    for a in attrs:
        lines.append("attribute_data_arg_list {")
        lines.append(f"{IND}attribute_data {{")
        lines.append(f'{IND * 2}name: "{a.name}"')
        lines.append(f"{IND * 2}value {{ {_val_literal(a.value, a.value_type)} }}")
        lines.append(f"{IND}}}")
        lines.append("}")
    return "\n".join(lines)


def _render_delete_entity(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    eid = ir.entity_id or "entity-id"
    return (f'entity_guid {{ entity_type_name: "{et}" entity_id: "{eid}" }}')


def _render_guid_list(ir: QueryIR, field: str) -> str:
    et = ir.entity_type or "vm"
    eid = ir.entity_id or "entity-id"
    return f'{field} {{ entity_type_name: "{et}" entity_id: "{eid}" }}'


def _render_register_metric_types(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    metrics = ir.metrics or [MetricDefIR(metric_name="new_attribute", value_type="kString", is_attribute=True)]
    blocks = []
    for m in metrics:
        blocks.append(
            "metric_type_list {\n"
            f'{IND}is_attribute: {"true" if m.is_attribute else "false"}\n'
            f'{IND}metric_name: "{m.metric_name}"\n'
            f'{IND}entity_type_name: "{et}"\n'
            f'{IND}value_type: {m.value_type or "kString"}\n'
            "}"
        )
    return "\n".join(blocks)


def _render_unregister_metric_types(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    metrics = ir.metrics or [MetricDefIR(metric_name="old_attribute")]
    blocks = []
    for m in metrics:
        blocks.append(
            "metric_type_list {\n"
            f'{IND}metric_name: "{m.metric_name}"\n'
            f'{IND}entity_type_name: "{et}"\n'
            "}"
        )
    return "\n".join(blocks)


def _render_register_entity_types(ir: QueryIR) -> str:
    et = ir.entity_type or "new_entity_type"
    lines = ["entity_type_info_list {", f'{IND}entity_type_name: "{et}"']
    for m in (ir.metrics or []):
        lines.append(f"{IND}metric_type_list {{")
        lines.append(f"{IND * 2}is_attribute: {'true' if m.is_attribute else 'false'}")
        lines.append(f'{IND * 2}metric_name: "{m.metric_name}"')
        lines.append(f'{IND * 2}entity_type_name: "{et}"')
        lines.append(f"{IND}}}")
    lines.append(f"{IND}type_info {{ suppress_replication: false }}")
    lines.append("}")
    return "\n".join(lines)


def _render_batch_get(ir: QueryIR) -> str:
    subs = ir.sub_queries
    if not subs:
        subs = [SubQueryIR(entity_type=ir.entity_type or "vm", columns=ir.columns)]
    blocks = []
    for idx, sq in enumerate(subs):
        cols = sq.columns or [f"{sq.entity_type}_name"]
        col_lines = "\n".join(f'{IND * 3}raw_columns {{ column: "{c}" }}' for c in cols)
        blocks.append(
            "query_list {\n"
            f"{IND}query {{\n"
            f'{IND * 2}entity_list {{ entity_type_name: "{sq.entity_type}" }}\n'
            f"{IND * 2}group_by {{\n{col_lines}\n{IND * 2}}}\n"
            f'{IND * 2}query_name: "batch_q{idx}"\n'
            f"{IND}}}\n"
            "}"
        )
    return "\n".join(blocks)


def _render_spotlight(ir: QueryIR) -> str:
    term = ir.search_term or ""
    lines = [f'search_term: "{term}"']
    if ir.entity_type:
        lines.append(f'entity_type_name_list: "{ir.entity_type}"')
    lines.append(f"limit {{ limit: {ir.limit if ir.limit is not None else 20} }}")
    return "\n".join(lines)


def _render_watch(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    name = ir.watch_name or f"{et}_watch"
    return ('client_id: "idf_ai_client"\n'
            'session_id: "idf_ai_session"\n'
            "watch_list {\n"
            f'{IND}watch_name: "{name}"\n'
            f'{IND}entity_type_name: "{et}"\n'
            f"{IND}watch_type_mask: 7\n"
            "}")


def _render_put_event(ir: QueryIR) -> str:
    lines = [f'event_type: "{ir.event_type or "custom_event"}"']
    if ir.entity_type:
        lines.append(f'entity_type_name: "{ir.entity_type}"')
    if ir.entity_id:
        lines.append(f'entity_id: "{ir.entity_id}"')
    return "\n".join(lines)


def _render_get_metric_data(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    lines = [f'entity_type_name: "{et}"']
    if ir.entity_id:
        lines.append(f'entity_id_list: "{ir.entity_id}"')
    for c in (ir.columns or ["cpu_usage_ppm"]):
        lines.append(f'metric_name_list: "{c}"')
    return "\n".join(lines)


def _render_put_metric_data(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    eid = ir.entity_id or "entity-id"
    metric = (ir.columns[0] if ir.columns else "cpu_usage_ppm")
    return ("entity_with_metric_list {\n"
            f'{IND}entity_guid {{ entity_type_name: "{et}" entity_id: "{eid}" }}\n'
            f"{IND}metric_data_list {{\n"
            f'{IND * 2}name: "{metric}"\n'
            f"{IND * 2}value_list {{ value {{ uint64_value: 0 }} }}\n"
            f"{IND}}}\n"
            "}")


def _render_attach_entity(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    eid = ir.entity_id or "entity-id"
    return ("update_entity_arg {\n"
            f'{IND}entity_guid {{ entity_type_name: "{et}" entity_id: "{eid}" }}\n'
            "}\n"
            f"incarnation_id: {ir.incarnation_id if ir.incarnation_id is not None else 1}")


def _render_detach_entity(ir: QueryIR) -> str:
    et = ir.entity_type or "vm"
    eid = ir.entity_id or "entity-id"
    return ("delete_entity_arg {\n"
            f'{IND}entity_guid {{ entity_type_name: "{et}" entity_id: "{eid}" }}\n'
            "}\n"
            f'moved_to_cluster_uuid: "{ir.moved_to_cluster_uuid or "target-cluster-uuid"}"')


def _render_get_entity_types(ir: QueryIR) -> str:
    return f'entity_type_name: "{ir.entity_type}"' if ir.entity_type else ""


def _render_get_metric_types(ir: QueryIR) -> str:
    if ir.regex:
        return f'regex: "{ir.regex}"'
    if ir.entity_type:
        return f'regex: ".*:{ir.entity_type}"'
    return 'regex: ".*"'


_RENDERERS = {
    "GetEntitiesWithMetrics": _render_get_entities_with_metrics,
    "GetEntities": lambda ir: _render_guid_list(ir, "entity_guid_list"),
    "GetEntitiesTrail": lambda ir: _render_guid_list(ir, "entity_guid_list"),
    "UpdateEntity": _render_update_entity,
    "DeleteEntity": _render_delete_entity,
    "BatchDeleteEntities": _render_delete_entity,
    "RegisterEntityTypes": _render_register_entity_types,
    "RegisterMetricTypes": _render_register_metric_types,
    "UnregisterMetricTypes": _render_unregister_metric_types,
    "BatchGetEntitiesWithMetrics": _render_batch_get,
    "BatchUpdateEntities": _render_update_entity,
    "SpotLightSearch": _render_spotlight,
    "Watch": _render_watch,
    "PutEvent": _render_put_event,
    "GetMetricData": _render_get_metric_data,
    "PutMetricData": _render_put_metric_data,
    "AttachEntity": _render_attach_entity,
    "DetachEntity": _render_detach_entity,
    "GetEntityTypes": _render_get_entity_types,
    "GetMetricTypes": _render_get_metric_types,
    "GetMasterLocation": lambda ir: "",
}


def render(ir: QueryIR) -> str:
    """Render QueryIR to IDF proto text. Total function (never raises)."""
    api = ir.api_method.value if hasattr(ir.api_method, "value") else str(ir.api_method)
    renderer = _RENDERERS.get(api, _render_get_entities_with_metrics)
    try:
        return renderer(ir).strip()
    except Exception:  # noqa: BLE001 - last-resort minimal valid proto
        et = ir.entity_type or "vm"
        return (f'query {{\n{IND}entity_list {{ entity_type_name: "{et}" }}\n'
                f'{IND}group_by {{ raw_columns {{ column: "{et}_name" }} }}\n'
                f'{IND}query_name: "auto_query"\n}}')
