"""
Query validation: structural and real-schema validation.
"""

from typing import List, Optional, Tuple

import schema_chunker


def validate_structural(query_json: dict) -> Tuple[bool, Optional[str]]:
    """
    Perform structural validation on the query JSON.
    
    Checks:
    - entity_list is present and non-empty
    - entity_list items have entity_type_name
    - where_clause structure is valid (if present)
    - Operators are valid
    - Value types match operators
    
    Returns:
        (is_valid, error_message)
    """
    # Check entity_list
    if "entity_list" not in query_json:
        return False, "Missing required field: entity_list"
    
    entity_list = query_json["entity_list"]
    if not isinstance(entity_list, list) or len(entity_list) == 0:
        return False, "entity_list must be a non-empty list"
    
    # Check each entity
    for i, entity in enumerate(entity_list):
        if not isinstance(entity, dict):
            return False, f"entity_list[{i}] must be an object"
        if "entity_type_name" not in entity:
            return False, f"entity_list[{i}] missing required field: entity_type_name"
        entity_type = entity["entity_type_name"]
        if not isinstance(entity_type, str) or not entity_type:
            return False, f"entity_list[{i}].entity_type_name must be a non-empty string"
    
    # Validate where_clause if present
    if "where_clause" in query_json:
        where_clause = query_json["where_clause"]
        if where_clause is not None:
            valid, error = validate_where_clause(where_clause)
            if not valid:
                return False, f"Invalid where_clause: {error}"
    
    # Validate group_by if present
    if "group_by" in query_json:
        group_by = query_json["group_by"]
        if group_by is not None:
            valid, error = validate_group_by(group_by)
            if not valid:
                return False, f"Invalid group_by: {error}"
    
    return True, None


def validate_where_clause(where_clause: dict) -> Tuple[bool, Optional[str]]:
    """Validate where_clause structure."""
    # Check if it's a BooleanExpression
    if "comparison_expr" in where_clause:
        return validate_comparison_expr(where_clause["comparison_expr"])
    elif "operator" in where_clause:
        op = where_clause["operator"]
        if op in ["kAnd", "kOr", "kNot", "kCorrelate"]:
            # Recursively validate lhs and rhs
            if "lhs" in where_clause:
                valid, error = validate_where_clause(where_clause["lhs"])
                if not valid:
                    return False, f"lhs: {error}"
            if "rhs" in where_clause and op != "kNot":
                valid, error = validate_where_clause(where_clause["rhs"])
                if not valid:
                    return False, f"rhs: {error}"
            return True, None
        else:
            return False, f"Invalid boolean operator: {op}"
    else:
        return False, "where_clause must have either 'comparison_expr' or 'operator'"
    
    return True, None


def validate_comparison_expr(comp_expr: dict) -> Tuple[bool, Optional[str]]:
    """Validate a ComparisonExpression."""
    if "operator" not in comp_expr:
        return False, "comparison_expr missing 'operator'"
    
    valid_operators = ["kEQ", "kNE", "kLT", "kLE", "kGT", "kGE", "kLike", 
                       "kContains", "kIN", "kAny", "kExists"]
    op = comp_expr["operator"]
    if op not in valid_operators:
        return False, f"Invalid comparison operator: {op}"
    
    # Check lhs (required)
    if "lhs" not in comp_expr:
        return False, "comparison_expr missing 'lhs'"
    
    # Check rhs (required except for kExists)
    if op != "kExists" and "rhs" not in comp_expr:
        return False, f"comparison_expr with operator {op} missing 'rhs'"
    
    # Validate value types in rhs if present
    if "rhs" in comp_expr:
        rhs = comp_expr["rhs"]
        if isinstance(rhs, dict) and "leaf" in rhs:
            leaf = rhs["leaf"]
            if "value" in leaf:
                value = leaf["value"]
                # Basic type checking
                if not isinstance(value, dict):
                    return False, "value must be an object with a value type field"
                # Check that at least one value type is set
                value_types = ["str_value", "int64_value", "uint64_value", "bool_value",
                              "float_value", "double_value", "str_list", "int64_list", 
                              "uint64_list", "bool_list", "float_list", "double_list"]
                if not any(vt in value for vt in value_types):
                    return False, "value must have at least one value type field set"
    
    return True, None


def validate_group_by(group_by: dict) -> Tuple[bool, Optional[str]]:
    """Validate group_by structure."""
    if "group_by_column" in group_by:
        group_by_col = group_by["group_by_column"]
        if not isinstance(group_by_col, str):
            return False, "group_by_column must be a string"
    
    # Validate aggregate_columns if present
    if "aggregate_columns" in group_by:
        agg_cols = group_by["aggregate_columns"]
        if not isinstance(agg_cols, list):
            return False, "aggregate_columns must be a list"
        for i, agg_col in enumerate(agg_cols):
            if not isinstance(agg_col, dict):
                return False, f"aggregate_columns[{i}] must be an object"
            if "column" not in agg_col:
                return False, f"aggregate_columns[{i}] missing 'column'"
    
    return True, None


def validate_real_schema(query_json: dict, schema_chunks: List[schema_chunker.SchemaChunk]) -> Tuple[bool, Optional[str]]:
    """
    Validate query against real schema (check entity types and indexed columns exist).
    
    This is optional validation for "real" schema mode.
    
    Args:
        query_json: The query JSON to validate
        schema_chunks: List of schema chunks to validate against
    
    Returns:
        (is_valid, error_message)
    """
    # Build lookup maps
    entity_types = set()
    indexed_columns = {}  # entity_type -> set of metric_names
    
    for chunk in schema_chunks:
        if chunk.is_index_column:
            entity_types.add(chunk.entity_type_name)
            if chunk.entity_type_name not in indexed_columns:
                indexed_columns[chunk.entity_type_name] = set()
            indexed_columns[chunk.entity_type_name].add(chunk.metric_name)
    
    # Validate entity types
    for entity in query_json.get("entity_list", []):
        entity_type = entity.get("entity_type_name")
        if entity_type not in entity_types:
            return False, f"Entity type '{entity_type}' not found in schema"
    
    # Validate columns in where_clause (if present)
    if "where_clause" in query_json and query_json["where_clause"]:
        valid, error = validate_where_clause_columns(
            query_json["where_clause"], 
            indexed_columns
        )
        if not valid:
            return False, error
    
    return True, None


def validate_where_clause_columns(where_clause: dict, indexed_columns: dict) -> Tuple[bool, Optional[str]]:
    """Recursively validate that columns in where_clause are indexed."""
    if "comparison_expr" in where_clause:
        comp_expr = where_clause["comparison_expr"]
        # Extract column from lhs
        if "lhs" in comp_expr:
            lhs = comp_expr["lhs"]
            if isinstance(lhs, dict) and "leaf" in lhs:
                leaf = lhs["leaf"]
                if "column" in leaf:
                    column = leaf["column"]
                    # Check if this column is indexed for any entity type
                    # (We'd need entity context, but for now just check if it exists)
                    found = False
                    for entity_type, columns in indexed_columns.items():
                        if column in columns:
                            found = True
                            break
                    if not found:
                        return False, f"Column '{column}' is not an indexed column"
    
    # Recursively check nested expressions
    if "lhs" in where_clause:
        valid, error = validate_where_clause_columns(where_clause["lhs"], indexed_columns)
        if not valid:
            return False, error
    if "rhs" in where_clause:
        valid, error = validate_where_clause_columns(where_clause["rhs"], indexed_columns)
        if not valid:
            return False, error
    
    return True, None
