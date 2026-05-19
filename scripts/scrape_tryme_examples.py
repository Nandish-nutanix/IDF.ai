"""
Scrape query examples from the IDF Try Me Editor (http://10.53.56.1:5002/try-me-editor).

Fetches Python and Go code examples for query-related categories and saves them
to the knowledge base for use as few-shot examples in the RAG pipeline.

Usage:
    python scripts/scrape_tryme_examples.py

Output:
    knowledge/examples/tryme_python_examples.txt
    knowledge/examples/tryme_go_examples.txt
"""

import os
import re
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

BASE_URL = "http://10.53.56.1:5002"

QUERY_CATEGORIES = [
    ("Queries - Where Clause", [
        "Contains", "Not", "In", "GreaterThanEqual", "LessThan",
        "Like: Match with multiple substrings", "Like: Match by substring",
        "Equal", "Like: Match by start of string", "Exists",
        "Nested Where Clause", "Any",
        "Like: Match by start and end of string", "NotEqual",
        "LessThanEqual", "GreaterThan",
    ]),
    ("Queries", [
        "Group Limit", "Raw limit Queries", "Group By",
        "Downsampling", "Group Sort", "Entity Specific Query",
        "Time Range Queries", "Lookup Query",
        "Aggregate Columns", "Continuous Grouping", "Raw Sort",
        "Entity Count", "Having Clause Group By",
        "Multi Dimensional Grouping", "Ancestor Join Query",
        "Fetching Raw Columns", "Shard Ids",
        "Grouping With Bucket Interval Separators",
    ]),
    ("Namespaces", [
        "Where Clause Query", "Group By Query",
        "Fetch Raw Columns Query", "Aggregation Query",
        "Group Sort Query", "Lookup Query",
    ]),
]


def build_url(category: str, example: str, lang: str) -> str:
    """Build the URL for a specific example."""
    cat_encoded = urllib.parse.quote(category)
    example_encoded = urllib.parse.quote(example)
    return f"{BASE_URL}/RPCS/{cat_encoded}/{example_encoded}/{lang}"


def build_url_go(category: str, example: str) -> str:
    """Build URL for Go examples (uses underscores in category names)."""
    cat_go = category.replace(" ", "_")
    cat_encoded = urllib.parse.quote(cat_go)
    example_encoded = urllib.parse.quote(example)
    return f"{BASE_URL}/RPCS/{cat_encoded}/{example_encoded}/go"


def fetch_page(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch a page and return its HTML content."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def extract_code_from_html(html: str) -> Optional[str]:
    """
    Extract the Python/Go code from the Try Me Editor HTML page.
    The code is rendered server-side inside the editor div.
    """
    code_start_patterns = [
        r"import env",
        r"package main",
        r"from insights_interface",
        r"from google\.protobuf",
    ]

    for pattern in code_start_patterns:
        match = re.search(pattern, html)
        if match:
            start = match.start()
            snippet = html[start:]
            end_markers = ["</div>", "</pre>", "</textarea>", "<script"]
            end_pos = len(snippet)
            for marker in end_markers:
                idx = snippet.find(marker)
                if idx > 0 and idx < end_pos:
                    end_pos = idx

            code = snippet[:end_pos]
            code = re.sub(r"<[^>]+>", "", code)
            code = code.replace("&lt;", "<").replace("&gt;", ">")
            code = code.replace("&amp;", "&").replace("&quot;", '"')
            code = code.replace("&#39;", "'").replace("&#x27;", "'")
            code = code.strip()
            if code:
                return code

    return None


def scrape_all_examples() -> Tuple[List[Dict], List[Dict]]:
    """Scrape all query examples in Python and Go."""
    python_examples = []
    go_examples = []

    for category, examples in QUERY_CATEGORIES:
        print(f"\n[{category}]")
        for example_name in examples:
            # Python
            py_url = build_url(category, example_name, "py")
            html = fetch_page(py_url)
            if html:
                code = extract_code_from_html(html)
                if code and len(code) > 50:
                    python_examples.append({
                        "category": category,
                        "name": example_name,
                        "code": code,
                    })
                    print(f"  [PY] {example_name} ({len(code)} chars)")
                else:
                    print(f"  [PY] {example_name} - no code found")
            time.sleep(0.2)

            # Go
            go_url = build_url_go(category, example_name)
            html = fetch_page(go_url)
            if html:
                code = extract_code_from_html(html)
                if code and len(code) > 50:
                    go_examples.append({
                        "category": category,
                        "name": example_name,
                        "code": code,
                    })
                    print(f"  [GO] {example_name} ({len(code)} chars)")
                else:
                    print(f"  [GO] {example_name} - no code found")
            time.sleep(0.2)

    return python_examples, go_examples


def save_examples(examples: List[Dict], output_path: str):
    """Save examples to a formatted text file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        f.write(f"# Auto-scraped from IDF Try Me Editor ({BASE_URL}/try-me-editor)\n")
        f.write(f"# Total examples: {len(examples)}\n")
        f.write("#" + "=" * 78 + "\n\n")

        for ex in examples:
            f.write(f"# Category: {ex['category']}\n")
            f.write(f"# Example: {ex['name']}\n")
            f.write("#" + "-" * 78 + "\n")
            f.write(ex["code"])
            f.write("\n\n" + "#" + "=" * 78 + "\n\n")

    print(f"\nSaved {len(examples)} examples to {output_path}")


def main():
    print("=" * 60)
    print("IDF Try Me Editor Example Scraper")
    print(f"Source: {BASE_URL}/try-me-editor")
    print("=" * 60)

    python_examples, go_examples = scrape_all_examples()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_output = os.path.join(project_root, "knowledge", "examples", "tryme_python_examples.txt")
    go_output = os.path.join(project_root, "knowledge", "examples", "tryme_go_examples.txt")

    save_examples(python_examples, py_output)
    save_examples(go_examples, go_output)

    print(f"\nDone! Python: {len(python_examples)}, Go: {len(go_examples)} examples scraped.")


if __name__ == "__main__":
    main()
