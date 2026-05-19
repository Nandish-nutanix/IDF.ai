"""
Minimal entity extraction utilities.

The LLM handles all query classification. This module only provides
entity type extraction for BM25 boosting in the vector DB retrieval layer.
"""

import re
from typing import Optional


KNOWN_ENTITY_TYPES = {
    "vm", "disk", "cluster", "node", "container", "volume_group",
    "storage_pool", "protection_domain", "consistency_group",
    "virtual_disk", "snapshot", "network", "subnet", "image",
    "task", "alert", "event", "category", "project",
    "recovery_point", "vm_recovery_point", "volume_group_recovery_point",
    "availability_zone", "remote_connection", "blueprint",
    "app", "action", "runbook", "ngt",
}

ENTITY_ALIASES = {
    "vms": "vm",
    "disks": "disk",
    "clusters": "cluster",
    "hosts": "node",
    "host": "node",
    "nodes": "node",
    "containers": "container",
    "storage_containers": "container",
    "storage containers": "container",
    "volume_groups": "volume_group",
    "volume groups": "volume_group",
    "storage_pools": "storage_pool",
    "storage pools": "storage_pool",
    "protection_domains": "protection_domain",
    "protection domains": "protection_domain",
    "consistency_groups": "consistency_group",
    "virtual_disks": "virtual_disk",
    "snapshots": "snapshot",
    "networks": "network",
    "subnets": "subnet",
    "images": "image",
    "tasks": "task",
    "alerts": "alert",
    "events": "event",
    "categories": "category",
    "projects": "project",
    "blueprints": "blueprint",
    "apps": "app",
    "actions": "action",
    "runbooks": "runbook",
}


def extract_entity_type(query: str) -> Optional[str]:
    """Extract entity type from a query string. Used for BM25 boosting."""
    query_lower = query.lower().strip()

    multi_word = sorted(ENTITY_ALIASES.keys(), key=len, reverse=True)
    for alias in multi_word:
        if alias in query_lower:
            return ENTITY_ALIASES[alias]

    for entity in KNOWN_ENTITY_TYPES:
        if entity in query_lower:
            return entity

    # Contextual extraction for unknown entity types
    contextual_patterns = [
        r'entity\s+type\s+(?:called\s+|named\s+)?["\']?([a-z][a-z0-9_-]*)["\']?',
        r'(?:about|for|of|on)\s+["\']?([a-z][a-z0-9_-]+)["\']?\s+entity',
        r'entity\s+type\s+["\']?([a-z][a-z0-9_-]+)["\']?',
    ]
    for pattern in contextual_patterns:
        match = re.search(pattern, query_lower)
        if match:
            candidate = match.group(1)
            skip_words = {'the', 'all', 'any', 'each', 'every', 'this', 'that',
                         'new', 'old', 'get', 'set', 'info', 'data', 'type'}
            if candidate not in skip_words:
                return candidate

    return None
