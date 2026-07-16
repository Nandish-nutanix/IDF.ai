"""
proto_ast.py - Protobuf text-format tokenizer + recursive-descent parser.

A faithful Python port of the parser proven in the Schema Validator UI. It turns
protobuf text format into a line-numbered AST so the pipeline can REASON about
model output instead of regex-scraping it. Used to:
  - parse raw proto the model emits (fallback path) into an IR
  - locate entity types, columns, filters precisely with line numbers
  - report structural errors (unbalanced braces, missing values)

AST shape (dicts, mirroring the JS implementation):
  node            = {"fields": [field, ...]}
  field           = {"key": str, "key_line": int, "value": value}
  value(scalar)   = {"kind": "scalar", "type": "STRING|NUMBER|IDENT|BOOL", "value": str, "line": int}
  value(message)  = {"kind": "message", "fields": [field, ...], "line": int}
"""

from __future__ import annotations

import re
from typing import List, Optional

_NUM_START = re.compile(r"[0-9]")
_NUM_BODY = re.compile(r"[-+0-9.eE]")
_IDENT_START = re.compile(r"[A-Za-z_]")
_IDENT_BODY = re.compile(r"[A-Za-z0-9_.]")


def tokenize(text: str) -> List[dict]:
    tokens: List[dict] = []
    i, line, n = 0, 1, len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "#" or (c == "/" and i + 1 < n and text[i + 1] == "/"):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "{":
            tokens.append({"type": "LBRACE", "value": "{", "line": line}); i += 1; continue
        if c == "}":
            tokens.append({"type": "RBRACE", "value": "}", "line": line}); i += 1; continue
        if c == ":":
            tokens.append({"type": "COLON", "value": ":", "line": line}); i += 1; continue
        if c in ('"', "'"):
            quote = c
            j = i + 1
            s = ""
            start_line = line
            while j < n and text[j] != quote:
                if text[j] == "\\" and j + 1 < n:
                    s += text[j + 1]
                    j += 2
                    continue
                if text[j] == "\n":
                    line += 1
                s += text[j]
                j += 1
            tokens.append({"type": "STRING", "value": s, "line": start_line})
            i = j + 1 if j < n else j
            continue
        if _NUM_START.match(c) or (c == "-" and i + 1 < n and _NUM_BODY.match(text[i + 1])):
            j = i
            s = ""
            while j < n and _NUM_BODY.match(text[j]):
                s += text[j]
                j += 1
            tokens.append({"type": "NUMBER", "value": s, "line": line})
            i = j
            continue
        if _IDENT_START.match(c):
            j = i
            s = ""
            while j < n and _IDENT_BODY.match(text[j]):
                s += text[j]
                j += 1
            ttype = "BOOL" if s in ("true", "false") else "IDENT"
            tokens.append({"type": ttype, "value": s, "line": line})
            i = j
            continue
        tokens.append({"type": "UNKNOWN", "value": c, "line": line})
        i += 1
    return tokens


def parse(text: str) -> dict:
    """Parse proto text into {"fields": [...], "errors": [...]}."""
    tokens = tokenize(text)
    state = {"pos": 0}
    errors: List[dict] = []

    def expect_rbrace(open_line: int) -> None:
        t = tokens[state["pos"]] if state["pos"] < len(tokens) else None
        if t and t["type"] == "RBRACE":
            state["pos"] += 1
            return
        errors.append({
            "line": t["line"] if t else open_line,
            "msg": f'Missing closing "}}" for block opened near line {open_line}.',
        })

    def parse_body(inside_block: bool) -> List[dict]:
        fields: List[dict] = []
        while state["pos"] < len(tokens):
            t = tokens[state["pos"]]
            if t["type"] == "RBRACE":
                if inside_block:
                    return fields
                errors.append({"line": t["line"], "msg": 'Unexpected "}" with no matching open block.'})
                state["pos"] += 1
                continue
            if t["type"] != "IDENT":
                if t["type"] == "UNKNOWN":
                    errors.append({"line": t["line"], "msg": f'Unexpected character "{t["value"]}".'})
                else:
                    errors.append({"line": t["line"], "msg": f'Expected a field name but found "{t["value"]}".'})
                state["pos"] += 1
                continue
            key, key_line = t["value"], t["line"]
            state["pos"] += 1
            nxt = tokens[state["pos"]] if state["pos"] < len(tokens) else None
            if nxt and nxt["type"] == "COLON":
                state["pos"] += 1
                val = tokens[state["pos"]] if state["pos"] < len(tokens) else None
                if not val:
                    errors.append({"line": key_line, "msg": f'Missing value for "{key}".'})
                    break
                if val["type"] == "LBRACE":
                    state["pos"] += 1
                    sub = parse_body(True)
                    expect_rbrace(val["line"])
                    fields.append({"key": key, "key_line": key_line,
                                   "value": {"kind": "message", "fields": sub, "line": val["line"]}})
                elif val["type"] == "RBRACE":
                    errors.append({"line": val["line"], "msg": f'Missing value for "{key}".'})
                else:
                    state["pos"] += 1
                    fields.append({"key": key, "key_line": key_line,
                                   "value": {"kind": "scalar", "type": val["type"],
                                             "value": val["value"], "line": val["line"]}})
            elif nxt and nxt["type"] == "LBRACE":
                state["pos"] += 1
                sub = parse_body(True)
                expect_rbrace(nxt["line"])
                fields.append({"key": key, "key_line": key_line,
                               "value": {"kind": "message", "fields": sub, "line": nxt["line"]}})
            else:
                errors.append({"line": key_line, "msg": f'"{key}" is missing a value (expected ":" or "{{").'})
        return fields

    fields = parse_body(False)
    return {"fields": fields, "errors": errors}


# ---- AST accessors -------------------------------------------------------

def all_fields(node: dict, key: str) -> List[dict]:
    return [f for f in node.get("fields", []) if f["key"] == key]


def first(node: dict, key: str) -> Optional[dict]:
    for f in node.get("fields", []):
        if f["key"] == key:
            return f
    return None


def scalar(node: dict, key: str) -> Optional[dict]:
    f = first(node, key)
    if f and f["value"]["kind"] == "scalar":
        return f["value"]
    return None


def scalar_value(node: dict, key: str) -> Optional[str]:
    s = scalar(node, key)
    return s["value"] if s else None


def message(node: dict, key: str) -> Optional[dict]:
    f = first(node, key)
    if f and f["value"]["kind"] == "message":
        return f["value"]
    return None


def collect(node: dict, key: str, out: Optional[List[dict]] = None) -> List[dict]:
    """All message-valued `key` fields, any depth."""
    if out is None:
        out = []
    for f in node.get("fields", []):
        if f["key"] == key and f["value"]["kind"] == "message":
            out.append(f["value"])
        if f["value"]["kind"] == "message":
            collect(f["value"], key, out)
    return out


def collect_scalar(node: dict, key: str, out: Optional[List[dict]] = None) -> List[dict]:
    """All scalar `key` values, any depth (each {'value','line'})."""
    if out is None:
        out = []
    for f in node.get("fields", []):
        if f["key"] == key and f["value"]["kind"] == "scalar":
            out.append({"value": f["value"]["value"], "line": f["value"]["line"]})
        if f["value"]["kind"] == "message":
            collect_scalar(f["value"], key, out)
    return out


def find_first_scalar_anywhere(node: dict, key: str) -> Optional[str]:
    vals = collect_scalar(node, key)
    return vals[0]["value"] if vals else None
