"""
Knowledge store: Multi-source knowledge management for the RAG pipeline.

Manages three collections:
1. Schema collection (existing) - entity/attribute definitions
2. Examples collection - query examples from Try Me Editor
3. Documentation collection - IDF articles and docs (placeholder for Google Drive integration)

The examples collection is particularly important for improving code generation
quality by providing real, working examples as few-shot context.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import config


def load_tryme_examples(lang: str = "py") -> List[Dict[str, str]]:
    """
    Load scraped Try Me Editor examples for a given language.
    
    Args:
        lang: "py" for Python, "go" for Go
    
    Returns:
        List of dicts with keys: category, name, code, proto_text
    """
    if lang == "py":
        filename = "tryme_python_examples.txt"
    elif lang == "go":
        filename = "tryme_go_examples.txt"
    else:
        return []

    examples_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "knowledge", "examples")
    filepath = os.path.join(examples_dir, filename)

    if not os.path.exists(filepath):
        return []

    with open(filepath, "r") as f:
        content = f.read()

    examples = []
    blocks = content.split("#" + "=" * 78)

    for block in blocks:
        block = block.strip()
        if not block or block.startswith("# Auto-scraped"):
            continue

        category_match = re.search(r"# Category:\s*(.+)", block)
        name_match = re.search(r"# Example:\s*(.+)", block)

        if not category_match or not name_match:
            continue

        category = category_match.group(1).strip()
        name = name_match.group(1).strip()

        header_end = block.find("#" + "-" * 78)
        if header_end >= 0:
            code = block[header_end + 80:].strip()
        else:
            code = block

        proto_text = extract_proto_from_example(code)

        examples.append({
            "category": category,
            "name": name,
            "code": code,
            "proto_text": proto_text,
        })

    return examples


def extract_proto_from_example(code: str) -> str:
    """Extract the proto text from an example code block (between triple quotes)."""
    match = re.search(r"query\s*=\s*'''(.*?)'''", code, re.DOTALL)
    if match:
        return match.group(1).strip()

    match = re.search(r'query\s*=\s*"""(.*?)"""', code, re.DOTALL)
    if match:
        return match.group(1).strip()

    return ""


def get_examples_for_query_type(query_type: str, lang: str = "py") -> List[Dict[str, str]]:
    """
    Get relevant examples for a specific query type.
    
    Maps query classifier types to Try Me Editor categories.
    """
    all_examples = load_tryme_examples(lang)

    type_to_categories = {
        "filter_equality": ["Queries - Where Clause"],
        "filter_comparison": ["Queries - Where Clause"],
        "filter_contains": ["Queries - Where Clause"],
        "filter_like": ["Queries - Where Clause"],
        "group_by": ["Queries"],
        "aggregation": ["Queries"],
        "count": ["Queries"],
        "sort_limit": ["Queries"],
        "simple_fetch_all": ["Queries"],
        "fetch_with_columns": ["Queries"],
        "complex": ["Queries - Where Clause", "Queries", "Namespaces"],
    }

    type_to_names = {
        "filter_equality": ["Equal", "NotEqual"],
        "filter_comparison": ["GreaterThan", "GreaterThanEqual", "LessThan", "LessThanEqual"],
        "filter_contains": ["Contains", "In"],
        "filter_like": ["Like: Match by substring", "Like: Match with multiple substrings",
                       "Like: Match by start of string", "Like: Match by start and end of string"],
        "group_by": ["Group By", "Group Sort", "Fetching Raw Columns"],
        "aggregation": ["Aggregate Columns", "Aggregation Query"],
        "count": ["Entity Count"],
        "sort_limit": ["Raw Sort", "Raw limit Queries", "Group Limit"],
        "simple_fetch_all": ["Fetching Raw Columns", "Entity Specific Query"],
        "fetch_with_columns": ["Fetching Raw Columns", "Raw Sort"],
    }

    target_categories = type_to_categories.get(query_type, ["Queries"])
    target_names = type_to_names.get(query_type, [])

    filtered = []
    for ex in all_examples:
        if ex["category"] in target_categories:
            if target_names:
                if ex["name"] in target_names:
                    filtered.insert(0, ex)
                else:
                    filtered.append(ex)
            else:
                filtered.append(ex)

    return filtered[:5]


def get_proto_examples_for_type(query_type: str) -> str:
    """
    Get proto text examples formatted for inclusion in LLM context.
    Returns the proto portions from the most relevant Try Me Editor examples.
    """
    examples = get_examples_for_query_type(query_type, lang="py")

    if not examples:
        return ""

    parts = []
    for ex in examples[:3]:
        if ex["proto_text"]:
            parts.append(f"# {ex['category']} / {ex['name']}")
            parts.append(ex["proto_text"])
            parts.append("")

    return "\n".join(parts)


def get_documentation_context(query: str) -> str:
    """
    Placeholder for Google Drive documentation retrieval.
    Will be implemented when the Google Drive knowledge base is connected.
    
    For now, returns empty string. In production, this would:
    1. Search the documentation vector store for relevant articles
    2. Return the most relevant document chunks
    3. Include IDF design docs, API references, and best practices
    """
    return ""
