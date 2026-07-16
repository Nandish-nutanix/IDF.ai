"""
schema_service.py - Single source of truth for the IDF schema.

Parses the real ``entity_attribute_config.proto.template`` once (cached to disk)
into an in-memory index of entity types and their attributes, and exposes the
operations the rest of the pipeline needs:

  - which entity types / attributes actually exist (grounding + validation)
  - resolving a natural-language phrase to the most likely entity type(s)
  - snapping a hallucinated column name to the nearest REAL attribute (repair)
  - data-type aware helpers (which proto value field / value_type token to use)

Every other component (inference prompt grounding, IR validation/repair,
training-data generation, and the GRPO reward) reads its schema from HERE, which
eliminates the train/serve skew that came from the hardcoded ENTITY_SCHEMA dict.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from typing import Dict, List, Optional

import config

# ---------------------------------------------------------------------------
# Data-type helpers
# ---------------------------------------------------------------------------

# user_metadata data_type -> proto Value oneof field used in where_clause leaf values
_DATA_TYPE_TO_VALUE_FIELD = {
    "string": "str_value",
    "bytes": "bytes_value",
    "int64": "int64_value",
    "uint64": "uint64_value",
    "bool": "bool_value",
    "boolean": "bool_value",
    "float": "float_value",
    "double": "double_value",
    "string_list": "str_list",
    "bytes_list": "bytes_list",
    "int64_list": "int64_list",
    "uint64_list": "uint64_list",
    "bool_list": "bool_list",
    "float_list": "float_list",
    "double_list": "double_list",
}

# user_metadata data_type -> value_type token used in RegisterMetricTypes
_DATA_TYPE_TO_VALUE_TYPE = {
    "string": "kString",
    "bytes": "kBytes",
    "int64": "kInt64",
    "uint64": "kUInt64",
    "bool": "kBoolean",
    "boolean": "kBoolean",
    "float": "kFloat",
    "double": "kDouble",
}

# Columns that are always valid even though they are not registered metrics.
SYSTEM_COLUMNS = {
    "__protobuf__", "__zprotobuf__", "cardinality", "description",
    "immutable", "internal", "entity_id", "_created_timestamp_usecs_",
    "_last_modified_time_usecs_", "_master_cluster_uuid_",
    "_consistency_related_attributes_checksum_", "tenant_id",
}


def value_field_for_data_type(data_type: Optional[str]) -> str:
    """Return the proto Value oneof field name for a user_metadata data type."""
    if not data_type:
        return "str_value"
    return _DATA_TYPE_TO_VALUE_FIELD.get(data_type.lower(), "str_value")


def value_type_token_for_data_type(data_type: Optional[str]) -> str:
    """Return the value_type enum token (kString, kInt64, ...) for a data type."""
    if not data_type:
        return "kString"
    return _DATA_TYPE_TO_VALUE_TYPE.get(data_type.lower(), "kString")


def is_system_column(name: str) -> bool:
    """True if the column is a built-in/system column (always queryable)."""
    if not name:
        return False
    if name in SYSTEM_COLUMNS:
        return True
    # Dunder and single-underscore wrapped names are IDF-internal columns.
    if name.startswith("__") and name.endswith("__"):
        return True
    if name.startswith("_") and name.endswith("_"):
        return True
    return False


# ---------------------------------------------------------------------------
# Levenshtein (pure python, small inputs)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------------------
# Natural-language aliases -> canonical attribute / entity hints
# ---------------------------------------------------------------------------

# Common NL nouns/synonyms -> canonical entity type names.
ENTITY_ALIASES = {
    "vm": "vm", "vms": "vm", "virtual machine": "vm", "virtual machines": "vm",
    "machine": "vm", "machines": "vm", "guest": "vm", "instance": "vm",
    "node": "node", "nodes": "node", "host": "node", "hosts": "node",
    "server": "node", "servers": "node",
    "cluster": "cluster", "clusters": "cluster",
    "disk": "disk", "disks": "disk", "drive": "disk", "drives": "disk",
    "container": "container", "containers": "container", "datastore": "container",
    "alert": "alert", "alerts": "alert",
    "task": "task", "tasks": "task", "job": "task", "jobs": "task",
    "vdisk": "virtual_disk", "vdisks": "virtual_disk",
    "virtual disk": "virtual_disk", "virtual disks": "virtual_disk",
    "subnet": "virtual_network", "subnets": "virtual_network",
    "network": "virtual_network", "networks": "virtual_network",
    "image": "image", "images": "image",
    "snapshot": "snapshot", "snapshots": "snapshot",
    "category": "category", "categories": "category",
    "nic": "virtual_nic", "nics": "virtual_nic", "vnic": "virtual_nic",
    "volume group": "volume_group_config", "volume groups": "volume_group_config",
    "storage pool": "storage_pool", "storage pools": "storage_pool",
    "protection domain": "protection_domain", "protection domains": "protection_domain",
}

# NL attribute phrases -> canonical attribute name (applied per entity if it exists).
ATTRIBUTE_ALIASES = {
    "memory": "memory_size_bytes",
    "ram": "memory_size_bytes",
    "memory size": "memory_size_bytes",
    "name": "{entity}_name",        # resolved against the entity at lookup time
    "cpus": "num_vcpus",
    "cpu": "num_vcpus",
    "vcpus": "num_vcpus",
    "cores": "num_cpu_cores",
    "state": "power_state",
    "status": "power_state",
    "power": "power_state",
    "hypervisor": "hypervisor_type",
    "os": "guest_os",
    "uuid": "{entity}_uuid",
    "id": "id",
    "size": "disk_size_bytes",
    "capacity": "storage_capacity_bytes",
    "latency": "avg_io_latency_usecs",
    "iops": "num_iops",
}


class _SchemaIndex:
    """Holds the parsed schema and answers schema questions."""

    def __init__(self) -> None:
        # entity_type -> { metric_name -> {"data_type","is_attribute","is_index_column"} }
        self.entities: Dict[str, Dict[str, dict]] = {}
        self._loaded = False

    # -- parsing -----------------------------------------------------------

    def _parse_template(self, path: str) -> Dict[str, Dict[str, dict]]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        entities: Dict[str, Dict[str, dict]] = {}
        block_lines: Optional[List[str]] = None
        brace = 0
        for line in content.split("\n"):
            if "metric_type_list {" in line:
                block_lines = [line]
                brace = line.count("{") - line.count("}")
            elif block_lines is not None:
                block_lines.append(line)
                brace += line.count("{") - line.count("}")
                if brace <= 0:
                    self._ingest_block("\n".join(block_lines), entities)
                    block_lines = None
        return entities

    @staticmethod
    def _ingest_block(block: str, entities: Dict[str, Dict[str, dict]]) -> None:
        et = re.search(r'entity_type_name\s*:\s*"([^"]+)"', block)
        mn = re.search(r'metric_name\s*:\s*"([^"]+)"', block)
        if not et or not mn:
            return
        entity_type = et.group(1)
        metric_name = mn.group(1)
        is_attr = bool(re.search(r'is_attribute\s*:\s*true', block))
        is_index = bool(re.search(r'is_index_column\s*:\s*true', block))
        data_type = None
        # The value is a JSON string with escaped quotes, e.g.
        #   user_metadata: "{\"data_type\":\"int64\"}"
        # so match through escaped quotes, then unescape before reading JSON.
        um = re.search(r'user_metadata\s*:\s*"((?:[^"\\]|\\.)*)"', block)
        if um:
            raw = um.group(1).replace('\\"', '"').replace('\\\\', '\\')
            dt = re.search(r'"data_type"\s*:\s*"([^"]+)"', raw)
            if dt:
                data_type = dt.group(1)
        bucket = entities.setdefault(entity_type, {})
        # Keep the richest record if a metric appears more than once.
        existing = bucket.get(metric_name)
        if existing is None:
            bucket[metric_name] = {
                "data_type": data_type,
                "is_attribute": is_attr,
                "is_index_column": is_index,
            }
        else:
            existing["data_type"] = existing["data_type"] or data_type
            existing["is_attribute"] = existing["is_attribute"] or is_attr
            existing["is_index_column"] = existing["is_index_column"] or is_index

    # -- load + cache ------------------------------------------------------

    def load(self) -> None:
        if self._loaded:
            return
        path = config.ENTITY_ATTRIBUTE_CONFIG_FILE
        if not os.path.exists(path):
            raise FileNotFoundError(f"Schema template not found: {path}")

        with open(path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        cache_path = os.path.join(
            os.path.dirname(path), ".schema_service_cache.json"
        )

        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("hash") == file_hash and cached.get("entities"):
                    self.entities = cached["entities"]
                    self._loaded = True
                    return
            except (json.JSONDecodeError, OSError):
                pass

        self.entities = self._parse_template(path)
        self._loaded = True
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"hash": file_hash, "entities": self.entities}, f)
        except OSError:
            pass

    # -- queries -----------------------------------------------------------

    def all_entity_types(self) -> List[str]:
        self.load()
        return sorted(self.entities.keys())

    def has_entity(self, entity_type: str) -> bool:
        self.load()
        return entity_type in self.entities

    def attributes_for(self, entity_type: str) -> Dict[str, dict]:
        self.load()
        return self.entities.get(entity_type, {})

    def has_attribute(self, entity_type: str, name: str) -> bool:
        self.load()
        if is_system_column(name):
            return True
        return name in self.entities.get(entity_type, {})

    def data_type_of(self, entity_type: str, name: str) -> Optional[str]:
        self.load()
        rec = self.entities.get(entity_type, {}).get(name)
        return rec.get("data_type") if rec else None

    def indexed_attributes(self, entity_type: str) -> List[str]:
        self.load()
        return [
            n for n, r in self.entities.get(entity_type, {}).items()
            if r.get("is_index_column")
        ]

    # -- resolution / repair ----------------------------------------------

    def nearest_entity_type(self, name: str) -> Optional[str]:
        """Fuzzy-match an arbitrary string to a real entity type."""
        self.load()
        if not name:
            return None
        name_l = name.strip().lower()
        if name_l in self.entities:
            return name_l
        if name_l in ENTITY_ALIASES:
            cand = ENTITY_ALIASES[name_l]
            if cand in self.entities:
                return cand
        best, best_d = None, 999
        for et in self.entities:
            d = _levenshtein(name_l, et.lower())
            if d < best_d:
                best, best_d = et, d
        # Only accept reasonably close matches.
        if best is not None and best_d <= max(2, len(name_l) // 3):
            return best
        return None

    def resolve_entity_types(self, query: str, limit: int = 3) -> List[str]:
        """
        Rank likely entity types for a natural-language query using alias hits,
        exact token matches, and substring matches. Cheap and deterministic.
        """
        self.load()
        ql = " " + query.lower() + " "
        scores: Dict[str, float] = {}

        # Multi-word aliases first (e.g. "virtual disk").
        for phrase, et in ENTITY_ALIASES.items():
            if et not in self.entities:
                continue
            if " " in phrase:
                if phrase in ql:
                    scores[et] = scores.get(et, 0) + 3.0
            else:
                if re.search(r"\b" + re.escape(phrase) + r"\b", ql):
                    scores[et] = scores.get(et, 0) + 2.0

        # Direct entity-type name / readable-name mentions.
        for et in self.entities:
            readable = et.replace("_", " ")
            if re.search(r"\b" + re.escape(et.lower()) + r"\b", ql):
                scores[et] = scores.get(et, 0) + 3.0
            elif readable != et and readable in ql:
                scores[et] = scores.get(et, 0) + 2.5

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [et for et, _ in ranked[:limit]]

    def nearest_attribute(self, entity_type: str, name: str) -> Optional[str]:
        """
        Snap a (possibly hallucinated) column name to the nearest REAL attribute
        of the entity. Tries: exact -> alias -> substring -> Levenshtein.
        Returns None when nothing is reasonably close (caller keeps original).
        """
        self.load()
        if not name:
            return None
        if is_system_column(name):
            return name
        attrs = self.entities.get(entity_type, {})
        if not attrs:
            return None
        if name in attrs:
            return name

        name_l = name.lower()

        # Alias map (with {entity} substitution), exact then fuzzy on keys.
        alias = ATTRIBUTE_ALIASES.get(name_l)
        if not alias:
            for k in ATTRIBUTE_ALIASES:
                if " " not in k and _levenshtein(name_l, k) <= 1:
                    alias = ATTRIBUTE_ALIASES[k]
                    break
        if alias:
            cand = alias.replace("{entity}", entity_type)
            if cand in attrs:
                return cand

        # Case-insensitive exact.
        for a in attrs:
            if a.lower() == name_l:
                return a

        # Substring containment (prefer shortest containing attribute).
        contains = sorted(
            [a for a in attrs if name_l in a.lower() or a.lower() in name_l],
            key=len,
        )
        if contains:
            return contains[0]

        # Levenshtein nearest, bounded by a sensible threshold.
        best, best_d = None, 999
        for a in attrs:
            d = _levenshtein(name_l, a.lower())
            if d < best_d:
                best, best_d = a, d
        if best is not None and best_d <= max(2, len(name_l) // 2):
            return best
        return None


# Module-level singleton (thread-safe lazy init).
_index: Optional[_SchemaIndex] = None
_lock = threading.Lock()


def get_schema() -> _SchemaIndex:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                idx = _SchemaIndex()
                idx.load()
                _index = idx
    return _index


# Convenience module-level wrappers ------------------------------------------

def all_entity_types() -> List[str]:
    return get_schema().all_entity_types()


def has_entity(entity_type: str) -> bool:
    return get_schema().has_entity(entity_type)


def attributes_for(entity_type: str) -> Dict[str, dict]:
    return get_schema().attributes_for(entity_type)


def has_attribute(entity_type: str, name: str) -> bool:
    return get_schema().has_attribute(entity_type, name)


def data_type_of(entity_type: str, name: str) -> Optional[str]:
    return get_schema().data_type_of(entity_type, name)


def indexed_attributes(entity_type: str) -> List[str]:
    return get_schema().indexed_attributes(entity_type)


def nearest_entity_type(name: str) -> Optional[str]:
    return get_schema().nearest_entity_type(name)


def resolve_entity_types(query: str, limit: int = 3) -> List[str]:
    return get_schema().resolve_entity_types(query, limit=limit)


def nearest_attribute(entity_type: str, name: str) -> Optional[str]:
    return get_schema().nearest_attribute(entity_type, name)


if __name__ == "__main__":
    s = get_schema()
    ets = s.all_entity_types()
    print(f"Parsed {len(ets)} entity types.")
    for et in ["vm", "node", "cluster", "disk"]:
        if s.has_entity(et):
            attrs = s.attributes_for(et)
            idx = s.indexed_attributes(et)
            print(f"  {et}: {len(attrs)} attrs, {len(idx)} indexed")
    print("resolve('top 5 vms by memory'):", s.resolve_entity_types("top 5 vms by memory"))
    print("nearest_attribute('vm','memmory'):", s.nearest_attribute("vm", "memmory"))
    print("nearest_attribute('vm','memory'):", s.nearest_attribute("vm", "memory"))
