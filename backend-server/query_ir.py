"""
query_ir.py - Typed intermediate representation (IR) for IDF queries.

The IR is the contract between Phi-4 and the deterministic proto renderer:

    NL query --(Phi-4, constrained)--> QueryIR (JSON) --(ir_to_proto)--> proto text

Generating a constrained JSON IR (instead of free-form proto text) means the
model can ONLY emit structurally valid choices (enum API names, enum operators,
typed value fields). Structural validity is then guaranteed by construction, and
schema validity is enforced by ir_validator before rendering.

A single flat model covers all 21 APIs via optional, API-specific fields; the
renderer reads only the fields relevant to the chosen api_method.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ApiMethod(str, Enum):
    GetEntitiesWithMetrics = "GetEntitiesWithMetrics"
    GetEntityTypes = "GetEntityTypes"
    GetMetricTypes = "GetMetricTypes"
    UpdateEntity = "UpdateEntity"
    DeleteEntity = "DeleteEntity"
    RegisterEntityTypes = "RegisterEntityTypes"
    RegisterMetricTypes = "RegisterMetricTypes"
    UnregisterMetricTypes = "UnregisterMetricTypes"
    BatchGetEntitiesWithMetrics = "BatchGetEntitiesWithMetrics"
    BatchUpdateEntities = "BatchUpdateEntities"
    BatchDeleteEntities = "BatchDeleteEntities"
    GetEntities = "GetEntities"
    GetMetricData = "GetMetricData"
    PutMetricData = "PutMetricData"
    SpotLightSearch = "SpotLightSearch"
    GetEntitiesTrail = "GetEntitiesTrail"
    AttachEntity = "AttachEntity"
    DetachEntity = "DetachEntity"
    GetMasterLocation = "GetMasterLocation"
    Watch = "Watch"
    PutEvent = "PutEvent"


class Operator(str, Enum):
    kEQ = "kEQ"
    kNE = "kNE"
    kLT = "kLT"
    kLE = "kLE"
    kGT = "kGT"
    kGE = "kGE"
    kLike = "kLike"
    kExists = "kExists"
    kIN = "kIN"


class ValueType(str, Enum):
    str_value = "str_value"
    int64_value = "int64_value"
    uint64_value = "uint64_value"
    bool_value = "bool_value"
    float_value = "float_value"
    double_value = "double_value"


class FilterIR(BaseModel):
    column: str = ""
    operator: Operator = Operator.kEQ
    value: str = ""
    value_type: ValueType = ValueType.str_value


class AttributeIR(BaseModel):
    name: str = ""
    value: str = ""
    value_type: ValueType = ValueType.str_value


class MetricDefIR(BaseModel):
    metric_name: str = ""
    value_type: str = "kString"
    is_attribute: bool = True


class SubQueryIR(BaseModel):
    entity_type: str = ""
    columns: List[str] = Field(default_factory=list)


class QueryIR(BaseModel):
    """Single flat IR covering all IDF APIs."""

    api_method: ApiMethod = ApiMethod.GetEntitiesWithMetrics

    # Read path (GetEntitiesWithMetrics / GetEntities / GetMetricData / Trail)
    entity_type: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    filters: List[FilterIR] = Field(default_factory=list)
    filter_logic: str = "and"           # "and" | "or"
    sort_column: Optional[str] = None
    sort_desc: bool = False
    limit: Optional[int] = None
    offset: Optional[int] = None

    # Single-entity ops (Update/Delete/Get/Trail/Attach/Detach)
    entity_id: Optional[str] = None
    attributes: List[AttributeIR] = Field(default_factory=list)
    cas_value: Optional[int] = None

    # Schema ops
    metrics: List[MetricDefIR] = Field(default_factory=list)   # Register/Unregister metrics
    regex: Optional[str] = None                                # GetMetricTypes filter

    # Batch
    sub_queries: List[SubQueryIR] = Field(default_factory=list)

    # Misc APIs
    search_term: Optional[str] = None       # SpotLightSearch
    event_type: Optional[str] = None        # PutEvent
    watch_name: Optional[str] = None         # Watch
    moved_to_cluster_uuid: Optional[str] = None  # DetachEntity
    incarnation_id: Optional[int] = None     # AttachEntity

    query_name: str = "auto_query"

    @staticmethod
    def json_schema_for_guided() -> dict:
        """JSON schema passed to the constrained decoder (guided_json)."""
        return QueryIR.model_json_schema()

    @classmethod
    def from_loose(cls, data: dict) -> "QueryIR":
        """
        Build a QueryIR from a loose dict (e.g. model output), tolerating
        unknown/aliased keys and missing fields. Never raises on bad input.
        """
        if not isinstance(data, dict):
            return cls()
        clean: dict = {}

        # api_method (tolerate variants)
        api = data.get("api_method") or data.get("api") or data.get("method")
        if isinstance(api, str):
            api = api.strip()
            for m in ApiMethod:
                if m.value.lower() == api.lower():
                    clean["api_method"] = m.value
                    break

        for key in ("entity_type", "filter_logic", "sort_column", "entity_id",
                    "regex", "search_term", "event_type", "watch_name",
                    "moved_to_cluster_uuid", "query_name"):
            v = data.get(key)
            if isinstance(v, (str, int)) and str(v).strip():
                clean[key] = str(v)

        for key in ("limit", "offset", "cas_value", "incarnation_id"):
            v = data.get(key)
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                clean[key] = v
            elif isinstance(v, str) and v.strip().lstrip("-").isdigit():
                clean[key] = int(v.strip())

        if isinstance(data.get("sort_desc"), bool):
            clean["sort_desc"] = data["sort_desc"]

        cols = data.get("columns")
        if isinstance(cols, list):
            clean["columns"] = [str(c) for c in cols if str(c).strip()]

        filters = data.get("filters")
        if isinstance(filters, list):
            parsed_filters = []
            for f in filters:
                if not isinstance(f, dict):
                    continue
                col = str(f.get("column", "")).strip()
                if not col:
                    continue
                op = str(f.get("operator", "kEQ")).strip()
                if op not in {o.value for o in Operator}:
                    op = "kEQ"
                vt = str(f.get("value_type", "str_value")).strip()
                if vt not in {v.value for v in ValueType}:
                    vt = "str_value"
                parsed_filters.append(FilterIR(
                    column=col, operator=Operator(op),
                    value=str(f.get("value", "")), value_type=ValueType(vt),
                ))
            clean["filters"] = parsed_filters

        attrs = data.get("attributes")
        if isinstance(attrs, list):
            parsed_attrs = []
            for a in attrs:
                if not isinstance(a, dict):
                    continue
                name = str(a.get("name", "")).strip()
                if not name:
                    continue
                vt = str(a.get("value_type", "str_value")).strip()
                if vt not in {v.value for v in ValueType}:
                    vt = "str_value"
                parsed_attrs.append(AttributeIR(
                    name=name, value=str(a.get("value", "")), value_type=ValueType(vt),
                ))
            clean["attributes"] = parsed_attrs

        metrics = data.get("metrics")
        if isinstance(metrics, list):
            parsed_metrics = []
            for m in metrics:
                if not isinstance(m, dict):
                    continue
                mn = str(m.get("metric_name", "")).strip()
                if not mn:
                    continue
                parsed_metrics.append(MetricDefIR(
                    metric_name=mn,
                    value_type=str(m.get("value_type", "kString")),
                    is_attribute=bool(m.get("is_attribute", True)),
                ))
            clean["metrics"] = parsed_metrics

        subs = data.get("sub_queries")
        if isinstance(subs, list):
            parsed_subs = []
            for sq in subs:
                if not isinstance(sq, dict):
                    continue
                et = str(sq.get("entity_type", "")).strip()
                if not et:
                    continue
                sc = sq.get("columns")
                cols2 = [str(c) for c in sc if str(c).strip()] if isinstance(sc, list) else []
                parsed_subs.append(SubQueryIR(entity_type=et, columns=cols2))
            clean["sub_queries"] = parsed_subs

        try:
            return cls(**clean)
        except Exception:
            return cls()
