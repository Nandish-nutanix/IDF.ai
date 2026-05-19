# Schema Extraction, Encoding, and Context Generation

## Overview

This document explains how the system extracts schema information, encodes it for semantic search, and generates context for the LLM to produce accurate Query proto JSON.

## 1. Schema Extraction (`schema_chunker.py`)

### Process

1. **Parse Protobuf File**: Reads `entity_attribute_config.proto.template` and extracts `metric_type_list` blocks
2. **Filter Indexed Columns**: Only processes metrics where `is_index_column: true`
3. **Extract Metadata**:
   - `entity_type_name`: Entity type (e.g., "vm", "disk", "cluster")
   - `metric_name`: Attribute/metric name (e.g., "cluster_uuid", "name")
   - `index_type`: Index type (e.g., "kString", "kInt64", "kUInt64")
   - `data_type`: Data type from user_metadata (e.g., "string", "int64")

### Chunk Text Format

For **indexed attributes**, the chunk text is:
```
Entity type: vm
Indexed attribute: cluster_uuid
Index type: string value
Data type: string
This attribute can be used in WHERE clause filters
```

For **entity summaries**, the chunk text is:
```
Entity type: vm
Available indexed attributes for filtering: cluster_uuid, name, power_state, ...
Total indexed attributes: 45
```

### Why This Format?

- **Semantic Search**: Uses natural language that captures meaning ("Entity type", "Indexed attribute")
- **LLM Context**: Provides clear structure for the LLM to understand what's available
- **Type Information**: Includes index_type and data_type to guide value formatting

## 2. Encoding (`vectordb.py` + `embeddings_client.py`)

### Process

1. **Generate Embeddings**: Calls Nutanix Enterprise AI embeddings API (`hack-embed` model)
   - Input: List of chunk texts (batch size: 100)
   - Output: Vector embeddings (float arrays)

2. **Store in Chroma DB**:
   - **Collection**: `insights_schema`
   - **Documents**: Chunk text (for retrieval)
   - **Embeddings**: Vector representations (for similarity search)
   - **Metadata**: Structured data for filtering/context
     ```python
     {
         "entity_type": "vm",
         "metric_name": "cluster_uuid",
         "is_indexed": "true",
         "index_type": "kString",
         "data_type": "string"
     }
     ```

3. **Persistence**: 
   - DB stored at `./knowledge/schema/vectordb/`
   - Hash-based change detection (rebuilds only when schema changes)

### Why Chroma?

- **File-based**: No separate server process, runs in-process
- **Persistent**: Survives server restarts
- **Metadata Support**: Can filter by entity_type, index_type, etc.
- **Lightweight**: Suitable for dev VMs

## 3. Retrieval (`vectordb.py`)

### Process

1. **Embed Query**: Convert user's natural language query to embedding vector
2. **Vector Search**: Find top-k most similar schema chunks (default: 15)
3. **Return Context**: Returns chunks with:
   - `chunk_text`: The formatted schema information
   - `metadata`: Structured metadata for filtering
   - `distance`: Similarity score (lower = more similar)

### Retrieval Strategy

- **Top-K**: Retrieves 15 most relevant chunks
- **Semantic Matching**: Uses cosine similarity on embeddings
- **Mixed Results**: May include both entity summaries and specific attributes

## 4. Context Generation (`llm_client.py`)

### System Message

Defines the task, rules, and output format:
- Task: Convert NL → Query proto JSON
- Rules: Entity selection, WHERE clause constraints, value types, operators
- Output: JSON only, no markdown

### User Message Structure

```
QUERY: <user's natural language query>

SCHEMA CONTEXT:
=== ENTITY TYPES ===
Entity type: vm
Available indexed attributes for filtering: cluster_uuid, name, power_state, ...
Total indexed attributes: 45

=== INDEXED ATTRIBUTES (for WHERE clauses) ===

Entity: vm
  - Entity type: vm
    Indexed attribute: cluster_uuid
    Index type: string value
    Data type: string
    This attribute can be used in WHERE clause filters
  - Entity type: vm
    Indexed attribute: name
    Index type: string value
    Data type: string
    This attribute can be used in WHERE clause filters
...
```

### Why This Structure?

1. **Clear Sections**: Separates entity overview from detailed attributes
2. **Grouped by Entity**: Makes it easy to see all attributes for an entity type
3. **Actionable Info**: Explicitly states "for WHERE clauses" to guide usage
4. **Complete Context**: LLM sees both high-level (summaries) and detailed (attributes) info

## 5. Data Flow

```
Schema File (protobuf)
    ↓
Schema Chunker
    ↓ (extract indexed metrics)
SchemaChunk objects
    ↓ (create chunk text)
Text chunks
    ↓ (embed via API)
Vector embeddings
    ↓ (store in Chroma)
Vector DB
    ↓ (query time: embed user query)
Retrieved chunks (top-k)
    ↓ (format for LLM)
User message with context
    ↓ (LLM call)
Query proto JSON
```

## 6. Key Design Decisions

### Chunk Text Format
- **Natural Language**: "Entity type" instead of "entity_type_name" for better semantic matching
- **Descriptive**: "Indexed attribute" clearly indicates usage
- **Type Information**: Includes both index_type and data_type for value formatting

### Context Organization
- **Hierarchical**: Entity summaries first, then detailed attributes
- **Grouped**: Attributes grouped by entity type for clarity
- **Explicit**: States purpose ("for WHERE clauses")

### Metadata Structure
- **Consistent Naming**: `entity_type` (not `entity_type_name`) for clarity
- **Filterable**: Can filter by entity_type, index_type in Chroma
- **Complete**: Includes all necessary information for validation

## 7. Improvements Made

1. **Better Chunk Text**: More descriptive, natural language format
2. **Structured Context**: Organized sections in user message
3. **Clearer Metadata**: Consistent naming (`entity_type` vs `entity_type_name`)
4. **DB Location**: Moved to `./knowledge/schema/vectordb/` for better organization
5. **Enhanced System Message**: More detailed rules and examples
