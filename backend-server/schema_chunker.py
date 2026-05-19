"""
Schema chunking module: Parse protobuf schema files and create enriched chunks for vector DB.

Improvements over original:
- Richer chunk text that includes data type info for better semantic matching
- Entity summary chunks that list all attributes for each entity type
- Better handling of edge cases in parsing
"""

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import config


@dataclass
class SchemaChunk:
    """Represents a schema chunk for vector DB."""
    entity_type_name: str
    metric_name: str
    is_index_column: bool
    index_type: Optional[str]
    data_type: Optional[str]
    chunk_text: str
    chunk_id: str


def parse_user_metadata(user_metadata: str) -> Optional[str]:
    """Extract data_type from user_metadata JSON string."""
    if not user_metadata:
        return None
    try:
        metadata = json.loads(user_metadata)
        return metadata.get("data_type")
    except (json.JSONDecodeError, AttributeError):
        return None


def parse_metric_block(block_text: str) -> Optional[Dict]:
    """
    Parse a single metric_type_list block from protobuf text format.
    Returns dict with extracted fields, or None if not an indexed column.
    """
    entity_type_match = re.search(r'entity_type_name\s*:\s*"([^"]+)"', block_text)
    metric_name_match = re.search(r'metric_name\s*:\s*"([^"]+)"', block_text)
    is_attribute_match = re.search(r'is_attribute\s*:\s*(true|false)', block_text)
    is_index_column_match = re.search(r'is_index_column\s*:\s*(true|false)', block_text)
    index_type_match = re.search(r'index_type\s*:\s*(\w+)', block_text)
    user_metadata_match = re.search(r'user_metadata\s*:\s*"([^"]+)"', block_text)

    if not entity_type_match or not metric_name_match:
        return None

    is_index_column = is_index_column_match and is_index_column_match.group(1) == "true"
    if not is_index_column:
        return None

    entity_type_name = entity_type_match.group(1)
    metric_name = metric_name_match.group(1)
    is_attribute = is_attribute_match and is_attribute_match.group(1) == "true"
    index_type = index_type_match.group(1) if index_type_match else None
    user_metadata = user_metadata_match.group(1) if user_metadata_match else None
    data_type = parse_user_metadata(user_metadata) if user_metadata else None

    return {
        "entity_type_name": entity_type_name,
        "metric_name": metric_name,
        "is_attribute": is_attribute,
        "is_index_column": True,
        "index_type": index_type,
        "data_type": data_type,
    }


def create_chunk_text(entity_type: str, metric_name: str, data_type: Optional[str] = None,
                     index_type: Optional[str] = None) -> str:
    """
    Create enriched text representation of a schema chunk for embedding.

    Format: "<entity_type> attribute <metric_name> type <data_type>"
    The extra context helps the embedding model understand the semantics better
    than just "entity_type metric_name".
    """
    parts = [entity_type, "attribute", metric_name]

    if data_type:
        parts.append(f"type {data_type}")
    elif index_type:
        type_map = {
            "kString": "string",
            "kInt64": "integer",
            "kUInt64": "unsigned integer",
            "kDouble": "number",
            "kFloat": "number",
            "kBoolean": "boolean",
            "kBool": "boolean",
        }
        mapped = type_map.get(index_type, index_type.lower().replace("k", ""))
        parts.append(f"type {mapped}")

    readable_name = metric_name.replace("_", " ")
    if readable_name != metric_name:
        parts.append(f"({readable_name})")

    return " ".join(parts)


def create_entity_summary_text(entity_type: str, attributes: List[Dict]) -> str:
    """
    Create entity summary text listing all attributes.
    This helps when the user asks broad questions like "what attributes does VM have?"
    """
    attr_names = [a["metric_name"] for a in attributes[:30]]
    attr_str = ", ".join(attr_names)
    return f"entity {entity_type} has attributes: {attr_str}"


def parse_schema_file(file_path: str) -> List[SchemaChunk]:
    """
    Parse the entity_attribute_config protobuf file and extract indexed metrics.
    Returns list of SchemaChunk objects.
    """
    chunks = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = []
    current_block = None
    brace_count = 0

    for line in content.split('\n'):
        if 'metric_type_list {' in line:
            current_block = [line]
            brace_count = line.count('{') - line.count('}')
        elif current_block is not None:
            current_block.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                blocks.append('\n'.join(current_block))
                current_block = None

    for block in blocks:
        parsed = parse_metric_block(block)
        if parsed:
            chunk_text = create_chunk_text(
                parsed["entity_type_name"],
                parsed["metric_name"],
                data_type=parsed.get("data_type"),
                index_type=parsed.get("index_type"),
            )
            chunk_id = f"entity:{parsed['entity_type_name']}:metric:{parsed['metric_name']}"

            chunk = SchemaChunk(
                entity_type_name=parsed["entity_type_name"],
                metric_name=parsed["metric_name"],
                is_index_column=True,
                index_type=parsed.get("index_type"),
                data_type=parsed.get("data_type"),
                chunk_text=chunk_text,
                chunk_id=chunk_id
            )
            chunks.append(chunk)

    return chunks


def create_entity_summary_chunks(attribute_chunks: List[SchemaChunk]) -> List[SchemaChunk]:
    """
    Create entity summary chunks that list all attributes for each entity type.
    These help with broad queries about entity types.
    """
    entity_attrs: Dict[str, List[Dict]] = defaultdict(list)
    for chunk in attribute_chunks:
        entity_attrs[chunk.entity_type_name].append({
            "metric_name": chunk.metric_name,
            "data_type": chunk.data_type,
        })

    summary_chunks = []
    for entity_type, attrs in entity_attrs.items():
        summary_text = create_entity_summary_text(entity_type, attrs)
        chunk_id = f"entity_summary:{entity_type}"

        summary_chunk = SchemaChunk(
            entity_type_name=entity_type,
            metric_name="_entity_summary_",
            is_index_column=False,
            index_type=None,
            data_type=None,
            chunk_text=summary_text,
            chunk_id=chunk_id
        )
        summary_chunks.append(summary_chunk)

    return summary_chunks


def compute_schema_hash(file_path: str) -> str:
    """Compute SHA256 hash of schema file for change detection."""
    with open(file_path, 'rb') as f:
        content = f.read()
    return hashlib.sha256(content).hexdigest()


def load_schema_chunks() -> List[SchemaChunk]:
    """
    Load schema chunks from the schema file.
    Returns both attribute-level chunks and entity summary chunks.
    """
    schema_file = Path(config.ENTITY_ATTRIBUTE_CONFIG_FILE)
    if not schema_file.exists():
        raise FileNotFoundError(
            f"Schema file not found: {config.ENTITY_ATTRIBUTE_CONFIG_FILE}"
        )

    attribute_chunks = parse_schema_file(str(schema_file))
    summary_chunks = create_entity_summary_chunks(attribute_chunks)

    all_chunks = attribute_chunks + summary_chunks
    print(f"  Loaded {len(attribute_chunks)} attribute chunks + {len(summary_chunks)} entity summaries")
    return all_chunks
