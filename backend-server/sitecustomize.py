"""Auto-loaded by Python at startup (when this directory is on sys.path).

On hosts whose system sqlite3 is older than what ChromaDB requires (e.g. RHEL 9
with Python 3.9), transparently swap in the newer `pysqlite3` build. This is a
no-op on machines where pysqlite3 is not installed (e.g. macOS/MLX dev boxes),
so it is safe to ship everywhere.
"""
try:  # pragma: no cover - environment dependent
    import sys
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:
    pass
