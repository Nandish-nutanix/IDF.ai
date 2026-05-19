#!/usr/bin/env python3
"""
CLI script for natural language query to insights Query proto.

Usage:
    python query_cli.py "give me all vms which belong to cluster 01010897549764"
    echo "query text" | python query_cli.py
    python query_cli.py --server http://localhost:8000 "query text"
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests


def read_query_from_stdin() -> str:
    """
    Read query from stdin (supports multi-line).
    
    Works with:
    - Piping: echo "query" | python query_cli.py
    - Redirection: python query_cli.py < file.txt
    - Interactive: Type query, press Enter, then Ctrl+D (Unix) or Ctrl+Z+Enter (Windows) to finish
    """
    # Check if stdin is a TTY (interactive terminal)
    if sys.stdin.isatty():
        # Interactive mode: prompt user and read until EOF
        print("Enter your query (press Ctrl+D on new line to finish, or Ctrl+C to cancel):", file=sys.stderr)
        lines = []
        try:
            for line in sys.stdin:
                lines.append(line.rstrip('\n'))
        except KeyboardInterrupt:
            print("\nCancelled.", file=sys.stderr)
            sys.exit(1)
        except EOFError:
            pass  # Ctrl+D pressed, finish reading
    else:
        # Non-interactive (piped/redirected): read all lines
        lines = []
        try:
            for line in sys.stdin:
                lines.append(line.rstrip('\n'))
        except KeyboardInterrupt:
            sys.exit(1)
    
    query = '\n'.join(lines).strip()
    if not query:
        print("Error: Query string is empty", file=sys.stderr)
        sys.exit(1)
    return query


def send_query(
    query: str,
    server_url: str,
    schema_mode: str = "real",
    generate_python: bool = False,
    generate_go: bool = False
) -> dict:
    """
    Send query to server and return response.
    
    Args:
        query: Natural language query string
        server_url: Base URL of the server (e.g., http://localhost:8000)
        schema_mode: "real" or "imaginary"
        generate_python: Whether to generate Python cpdb query code
        generate_go: Whether to generate Go cpdb query code
    
    Returns:
        Response dict with 'query_json' or 'error'
    
    Raises:
        requests.RequestException: On network errors
    """
    endpoint = f"{server_url.rstrip('/')}/query"
    payload = {
        "query": query,
        "schema_mode": schema_mode,
        "generate_python": generate_python,
        "generate_go": generate_go
    }
    
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60  # Increased timeout for Python code generation
    )
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description="Convert natural language query to insights Query proto (protobuf text format)"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language query string (if not provided, read from stdin)"
    )
    parser.add_argument(
        "--server",
        default=os.getenv("SERVER_URL", "http://localhost:8000"),
        help="Server URL (default: http://localhost:8000 or SERVER_URL env)"
    )
    parser.add_argument(
        "--schema-mode",
        choices=["real", "imaginary"],
        default="real",
        help="Schema mode: 'real' (validate against real schema) or 'imaginary' (hypothetical)"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output proto text only (suppress entity type suggestions)"
    )
    parser.add_argument(
        "--python",
        action="store_true",
        help="Generate Python cpdb query code from the proto"
    )
    parser.add_argument(
        "--go",
        action="store_true",
        help="Generate Go cpdb query code from the proto"
    )
    
    args = parser.parse_args()
    
    # Get query from argv or stdin
    if args.query:
        query = args.query
    else:
        query = read_query_from_stdin()  # This function now handles empty query check
    
    # Log that query was received
    print(f"Processing query: {query[:100]}{'...' if len(query) > 100 else ''}", file=sys.stderr)
    print("Sending to server...", file=sys.stderr)
    
    # Send to server
    try:
        response = send_query(query, args.server, args.schema_mode, args.python, args.go)
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to server at {args.server}", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: Request to server timed out", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"Error: Server returned HTTP {e.response.status_code}", file=sys.stderr)
        try:
            error_body = e.response.json()
            if "error" in error_body:
                print(f"Details: {error_body['error']}", file=sys.stderr)
        except:
            print(f"Details: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Handle response
    if "error" in response:
        print(f"Error: {response['error']}", file=sys.stderr)
        sys.exit(1)
    
    if "query_proto" not in response:
        print("Error: Invalid response format from server", file=sys.stderr)
        print(f"Response: {json.dumps(response, indent=2)}", file=sys.stderr)
        sys.exit(1)
    
    # Output query proto (text format)
    query_proto = response["query_proto"]
    
    # If Python code was requested and generated, show it
    if args.python and "python_code" in response and response["python_code"]:
        print("# Generated Python cpdb query code:", file=sys.stderr)
        print("# " + "=" * 60, file=sys.stderr)
        print(response["python_code"])
        print("\n# " + "=" * 60, file=sys.stderr)
        print("# Query proto (for reference):", file=sys.stderr)
        print("# " + "=" * 60, file=sys.stderr)
        # Print proto as comments
        for line in query_proto.split('\n'):
            print(f"# {line}", file=sys.stderr)
    # If Go code was requested and generated, show it
    elif args.go and "go_code" in response and response["go_code"]:
        print("// Generated Go cpdb query code:", file=sys.stderr)
        print("// " + "=" * 60, file=sys.stderr)
        print(response["go_code"])
        print("\n// " + "=" * 60, file=sys.stderr)
        print("// Query proto (for reference):", file=sys.stderr)
        print("// " + "=" * 60, file=sys.stderr)
        # Print proto as comments
        for line in query_proto.split('\n'):
            print(f"// {line}", file=sys.stderr)
    else:
        # Normal output: just the proto
        print(query_proto)
    
    # Optionally show selected (etype, attribute) tuples if available
    if not args.raw and not args.python and not args.go and "selected_tuples" in response and response["selected_tuples"]:
        tuples_list = response["selected_tuples"]
        sorted_tuples_list = sorted(tuples_list)
        print(f"\n# Related entity types and attributes (entity_type, attribute):", file=sys.stderr)
        for t in sorted_tuples_list:
            if len(t) == 2:
                print(f"#   ({t[0]}, {t[1]})", file=sys.stderr)


if __name__ == "__main__":
    main()
