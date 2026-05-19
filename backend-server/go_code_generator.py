"""
Go cpdb query code generator from proto text format.
"""

import os
import re
from typing import Optional

import config
import llm_client


def _load_go_query_samples() -> str:
    """Load Go query samples from knowledge base."""
    path = "./knowledge/structure-and-rules/go_query_samples.txt"
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(os.getcwd(), path))
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


def _load_query_samples() -> str:
    """Load proto query samples for additional context."""
    path = getattr(config, "QUERY_SAMPLES_FILE", None)
    if not path:
        return ""
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(os.getcwd(), path))
    try:
        with open(path, "r") as f:
            # Read first 100 lines for context
            lines = []
            for i, line in enumerate(f):
                if i >= 100:
                    break
                lines.append(line.rstrip())
            return '\n'.join(lines)
    except OSError:
        return ""


def _load_cpdb_query_go_interface() -> str:
    """Load cpdb_query.go interface documentation."""
    path = "./knowledge/structure-and-rules/cpdb_query.go"
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(os.getcwd(), path))
    try:
        with open(path, "r") as f:
            content = f.read()
            # Extract the first ~300 lines which contain examples and function signatures
            lines = content.split('\n')[:300]
            return '\n'.join(lines)
    except OSError:
        return ""


def create_system_message() -> str:
    """Create the system message for Go code generation."""
    go_interface = _load_cpdb_query_go_interface()
    
    return f"""You are an expert at converting Insights Query proto (protobuf text format) into Go cpdb query code.

TASK:
Convert the given Query proto text format into equivalent Go code using the cpdb_query package.

CPDB_QUERY.GO INTERFACE AND USAGE EXAMPLES:
{go_interface}

CRITICAL RULES:
1. Always start with the required imports:
   ```go
   package main
   
   import(
     "flag"
     insights_interface "github.com/nutanix-core/go-cache/insights/insights_interface"
     "github.com/golang/protobuf/proto"
   )
   import "fmt"
   ```

2. Main query construction functions:
   - Query() for the main query builder
   - SetEntityList() to set entity type
   - SetQueryName() to set query name
   - SetWhereClause() for WHERE conditions
   - SetSelectRawColumns() for SELECT raw columns
   - SetGroupByColumn() for GROUP BY
   - SetLimit() for LIMIT
   - SetOrderBy() for ORDER BY

3. Comparison operators:
   - EQ(lhs, rhs) for equality (kEQ)
   - NE(lhs, rhs) for not equal (kNE)
   - LT(lhs, rhs) for less than (kLT)
   - LE(lhs, rhs) for less than or equal (kLE)
   - GT(lhs, rhs) for greater than (kGT)
   - GE(lhs, rhs) for greater than or equal (kGE)
   - IN(lhs, rhs) for membership (kIN)
   - LIKE(lhs, pattern) for pattern matching (kLike)
   - CONTAINS(lhs, rhs) for list containment (kContains)
   - EXISTS(lhs) for existence check (kExists)

4. Boolean operators:
   - AND(lhs, rhs) for logical AND
   - OR(lhs, rhs) for logical OR
   - NOT(lhs) for logical NOT
   - ALL(...) for combining multiple conditions with AND
   - ANY(...) for combining multiple conditions with OR

5. Value constructors:
   - Col(name) for column references
   - Str(value) for string values
   - Int64(value) for int64 values
   - Uint64(value) for uint64 values
   - Bool(value) for boolean values
   - Float(value) for float values
   - Double(value) for double values
   - StrList(values) for string lists
   - Int64List(values) for int64 lists

6. Arithmetic operators:
   - PLUS(lhs, rhs) for addition
   - MINUS(lhs, rhs) for subtraction
   - MULT(lhs, rhs) for multiplication
   - DIV(lhs, rhs) for division
   - MOD(lhs, rhs) for modulo

7. Aggregate functions:
   - SUM(col_name)
   - MAX(col_name)
   - MIN(col_name)
   - AVG(col_name)
   - COUNT(col_name)
   - LAST(col_name)

8. Sorting:
   - ASCENDING(col_name)
   - DESCENDING(col_name)

9. Output format:
   - Return ONLY the Go code
   - Include the main function
   - Put the query construction code inside the main function
   - Include service execution code at the end:
     ```go
     err := service.SendMsgWithTimeout("GetEntitiesWithMetrics",
                                         arg, response, nil,
                                         60)
     if err != nil {{
         fmt.Println("Failed because of error - %s\\n", err)
     }}
     fmt.Println(proto.MarshalTextString(response))
     ```
   - No markdown code blocks, just pure Go code

EXAMPLES ARE PROVIDED IN THE USER MESSAGE."""


def _load_tryme_go_examples() -> str:
    """Load relevant scraped Go examples from Try Me Editor."""
    try:
        import knowledge_store
        examples = knowledge_store.load_tryme_examples("go")
        if not examples:
            return ""
        relevant = [ex for ex in examples if ex.get("category") in ("Queries_-_Where_Clause", "Queries", "Queries - Where Clause")]
        parts = []
        for ex in relevant[:5]:
            parts.append(f"// {ex['category']} / {ex['name']}")
            parts.append(ex["code"])
            parts.append("")
        return "\n".join(parts)
    except Exception:
        return ""


def create_user_message(query_proto: str, natural_language_query: str) -> str:
    """
    Create the user message for Go code generation with proto and examples.
    Includes scraped Try Me Editor examples for real-world reference.
    """
    go_samples = _load_go_query_samples()
    proto_samples = _load_query_samples()
    tryme_examples = _load_tryme_go_examples()
    
    user_message = f"""GO CPDB QUERY API EXAMPLES:
{go_samples}

REAL-WORLD IDF GO EXAMPLES (from Try Me Editor):
{tryme_examples}

PROTO QUERY EXAMPLES (for context):
{proto_samples}

NATURAL LANGUAGE QUERY:
{natural_language_query}

QUERY PROTO TO CONVERT:
{query_proto}

Generate the Go code for this proto. Follow the real-world examples pattern using insights_interface and GetEntitiesWithMetrics RPC."""
    
    return user_message


def extract_go_code(response_text: str) -> Optional[str]:
    """
    Extract Go code from LLM response, handling markdown code blocks if present.
    
    Args:
        response_text: Raw response from LLM
    
    Returns:
        Go code string, or None if extraction fails
    """
    # Try to find Go code in markdown code blocks
    go_match = re.search(r'```go\s*(.*?)\s*```', response_text, re.DOTALL)
    if go_match:
        return go_match.group(1).strip()
    
    # Try generic code block
    code_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
    if code_match:
        code = code_match.group(1).strip()
        # Check if it looks like Go code
        if 'package main' in code or 'import' in code or 'func main()' in code:
            return code
    
    # No code block: check if response itself looks like Go code
    cleaned = response_text.strip()
    if 'package main' in cleaned or 'import' in cleaned or 'func main()' in cleaned:
        return cleaned
    
    return None


def generate_go_code(query_proto: str, natural_language_query: str = "") -> str:
    """
    Generate Go cpdb query code from proto text format.
    
    Args:
        query_proto: Query proto in protobuf text format
        natural_language_query: Original natural language query (for context)
    
    Returns:
        Go code string
    
    Raises:
        requests.RequestException: On API errors
        ValueError: If code extraction fails
    """
    system_msg = create_system_message()
    user_msg = create_user_message(query_proto, natural_language_query)
    
    print("[Go Code Generator] Calling LLM...")
    
    # Call LLM via llm_client
    content = llm_client.call_llm(system_msg, user_msg)
    
    print("[Go Code Generator] Generated code successfully")
    
    # Extract Go code from response
    go_code = extract_go_code(content)
    
    if go_code is None:
        raise ValueError(f"Failed to extract valid Go code from LLM response: {content[:200]}")
    
    return go_code

