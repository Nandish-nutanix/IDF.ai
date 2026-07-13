"""
Live IDF Stats Page Crawler & Indexer.

Connects to a CVM via SSH, discovers all available HTTP endpoints
on the insights_server (port 2027), crawls their content in a SINGLE
SSH call, and indexes them into the existing ChromaDB knowledge base.

Usage:
    python live_stats_indexer.py --cvm-ip 10.119.248.103
    python live_stats_indexer.py --cvm-ip 10.119.248.103 --password "nutanix/4u"
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import threading
from typing import Dict, List, Optional

import chromadb
import requests

KB_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(KB_DIR, "chroma_db")
LIVE_STATS_INDEX_PATH = os.path.join(KB_DIR, "live_stats_index.json")

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

IDF_PORT = 2027

KNOWN_STATS_ENDPOINTS = [
    "/",
    "/h",
    "/h/gflags",
    "/h/vars",
    "/h/pprof",
    "/h/pprof/cmdline",
    "/h/pprof/growth",
    "/h/pprof/heap",
    "/h/pprof/heapstats",
    "/h/threads",
    "/h/traces",
    "/h/res",
    "/index_map_stats",
    "/detailed_unevictable_cache_stats",
    "/entity_type_stats",
    "/cache_stats",
    "/watch_stats",
    "/rpc_stats",
    "/connection_stats",
    "/leader_stats",
    "/varz",
    "/flagz",
    "/pprof/cmdline",
    "/pprof/growth",
    "/pprof/heap",
    "/pprof/heapstats",
]

SEPARATOR = "===IDF_EP_SEP:"

# Global state for background indexing
_indexing_state = {
    "running": False,
    "progress": "",
    "error": None,
}


def ssh_exec(cvm_ip: str, command: str, password: str = "nutanix/4u",
             timeout: int = 20) -> Optional[str]:
    """Execute a command on the CVM via SSH and return stdout."""
    ssh_cmd = [
        "sshpass", "-p", password,
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
        "-o", "LogLevel=ERROR",
        f"nutanix@{cvm_ip}",
        command,
    ]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def discover_endpoints(cvm_ip: str, password: str) -> List[str]:
    """
    Discover available HTTP endpoints by hitting /h on the CVM.
    Merges with KNOWN_STATS_ENDPOINTS. No filtering - include everything.
    """
    print("  Discovering endpoints ...")
    endpoints = set(KNOWN_STATS_ENDPOINTS)

    raw = ssh_exec(cvm_ip, f"curl -s --max-time 5 'http://127.0.0.1:{IDF_PORT}/h'", password)
    if raw and len(raw.strip()) > 50:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', raw)
        for href in hrefs:
            href = href.strip()
            if href.startswith("/") and not href.startswith("//") and len(href) < 80:
                endpoints.add(href)

    endpoints.discard("")
    final = sorted(endpoints)
    print(f"  Found {len(final)} endpoints")
    return final


def strip_html(html: str) -> str:
    """Strip HTML tags and clean up whitespace."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def _is_error_page(raw_content: str, text: str) -> bool:
    """Detect HTTP error pages (404/500/etc.) and empty placeholders so they
    are never indexed as 'stats'."""
    low_raw = raw_content.lower()
    low_text = text.lower().strip()

    error_markers = [
        "404 not found",
        "not found on this server",
        "the requested url",
        "500 internal server error",
        "403 forbidden",
        "service unavailable",
        "<title>error",
        "bad request",
    ]
    for m in error_markers:
        if m in low_raw or m in low_text:
            return True

    # A page that is basically just "Not Found" with little else
    if len(low_text) < 120 and ("not found" in low_text or "error" == low_text):
        return True

    return False


def crawl_all(cvm_ip: str, password: str) -> List[Dict]:
    """
    Crawl ALL endpoints in a SINGLE SSH call.
    Builds a bash for-loop that runs on the CVM, fetching all URLs locally.
    This reduces latency from N*4s to just 1 SSH connection + local curls.
    """
    endpoints = discover_endpoints(cvm_ip, password)

    print(f"\n  Crawling {len(endpoints)} endpoints via single SSH call ...")
    _indexing_state["progress"] = f"Crawling {len(endpoints)} endpoints..."

    # Build a bash script that curls all endpoints with delimiters
    curl_cmds = []
    for ep in endpoints:
        # Use a unique separator with the endpoint path embedded
        curl_cmds.append(
            f'echo "{SEPARATOR}{ep}==="; curl -s --max-time 8 "http://127.0.0.1:{IDF_PORT}{ep}" 2>/dev/null'
        )
    batch_script = " ; ".join(curl_cmds)

    # Single SSH call - timeout = 10s connection + 8s per endpoint (generous)
    total_timeout = 15 + (len(endpoints) * 9)
    raw_output = ssh_exec(cvm_ip, batch_script, password, timeout=total_timeout)

    if not raw_output:
        print("  ERROR: Single SSH batch call failed.")
        return []

    print(f"  Received {len(raw_output)} bytes from CVM. Parsing...")

    # Parse the delimited output
    pages = []
    parts = raw_output.split(SEPARATOR)

    for part in parts[1:]:  # first part is empty
        # Each part starts with "endpoint_path===\ncontent..."
        sep_end = part.find("===")
        if sep_end == -1:
            continue
        ep_name = part[:sep_end].strip()
        content = part[sep_end + 3:].strip()  # skip "==="

        if not content or len(content) < 20:
            continue

        text = strip_html(content)
        if len(text) < 30:
            continue

        # Skip dead/error endpoints (404, 500, etc.) so they never pollute the KB
        if _is_error_page(content, text):
            print(f"    {ep_name:40s} -> SKIPPED (error/empty page)")
            continue

        pages.append({
            "endpoint": ep_name,
            "url": f"http://<CVM_IP>:{IDF_PORT}{ep_name}",
            "raw_length": len(content),
            "text": text,
            "is_html": "<html" in content.lower() or "<table" in content.lower(),
            "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    print(f"  Crawled {len(pages)} pages with content (from {len(endpoints)} endpoints)")
    for p in pages:
        print(f"    {p['endpoint']:40s} -> {len(p['text']):6d} chars")

    return pages


def chunk_stats_page(page: Dict, chunk_size: int = 1200) -> List[Dict]:
    """Chunk a stats page into embeddable pieces."""
    text = page["text"]
    endpoint = page["endpoint"]
    context_prefix = f"[IDF Live Stats | Endpoint: {endpoint}]\n"

    if len(text) <= chunk_size:
        return [{"text": context_prefix + text, "chunk_index": 0}]

    chunks = []
    sections = text.split("\n\n")
    current = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(current) + len(section) + 2 <= chunk_size:
            current += ("\n\n" + section) if current else section
        else:
            if current:
                chunks.append(context_prefix + current)
            if len(section) <= chunk_size:
                current = section
            else:
                lines = section.split("\n")
                current = ""
                for line in lines:
                    if len(current) + len(line) + 1 <= chunk_size:
                        current += ("\n" + line) if current else line
                    else:
                        if current:
                            chunks.append(context_prefix + current)
                        current = line

    if current and len(current) > 30:
        chunks.append(context_prefix + current)

    return [{"text": c, "chunk_index": i} for i, c in enumerate(chunks)]


def get_embeddings_batch(texts: List[str], batch_size: int = 64) -> List[Optional[List[float]]]:
    """Get embeddings in batch via Ollama /api/embed (much faster than one-by-one)."""
    BATCH_EMBED_URL = "http://localhost:11434/api/embed"
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = [t[:2000] for t in texts[i:i + batch_size]]
        try:
            resp = requests.post(
                BATCH_EMBED_URL,
                json={"model": EMBED_MODEL, "input": batch},
                timeout=120,
            )
            if resp.status_code == 200:
                embeddings = resp.json().get("embeddings", [])
                all_embeddings.extend(embeddings)
            else:
                all_embeddings.extend([None] * len(batch))
        except Exception:
            all_embeddings.extend([None] * len(batch))

    return all_embeddings


def index_into_chromadb(pages: List[Dict], cvm_ip: str):
    """Index crawled stats pages into ChromaDB using batch embeddings."""
    print(f"\n  Indexing into ChromaDB at {CHROMA_DIR} ...")
    _indexing_state["progress"] = "Preparing chunks..."

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        collection = client.get_collection("idf_knowledge_base")
        print(f"    Existing collection: {collection.count()} vectors")
    except Exception:
        collection = client.create_collection(
            name="idf_knowledge_base",
            metadata={"description": "IDF knowledge base with live stats"}
        )
        print("    Created new collection")

    try:
        existing = collection.get(where={"category": "Live Cluster Stats"})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            print(f"    Removed {len(existing['ids'])} old live stats vectors")
    except Exception:
        pass

    # Prepare all chunks first
    all_ids = []
    all_texts = []
    all_metadatas = []

    for page in pages:
        chunks = chunk_stats_page(page)
        endpoint = page["endpoint"]
        doc_id = hashlib.md5(endpoint.encode()).hexdigest()[:12]

        for chunk in chunks:
            chunk_id = f"live_{doc_id}_c{chunk['chunk_index']}"
            all_ids.append(chunk_id)
            all_texts.append(chunk["text"])
            all_metadatas.append({
                "doc_id": f"live_{doc_id}",
                "filename": f"stats{endpoint.replace('/', '_')}",
                "category": "Live Cluster Stats",
                "features": json.dumps(["stats", "live", endpoint.strip("/").replace("/", "_")]),
                "chunk_index": chunk["chunk_index"],
                "total_chunks": len(chunks),
                "endpoint": endpoint,
                "cluster_ip": cvm_ip,
            })

    if not all_texts:
        print("    No chunks to embed.")
        return

    # Batch embed all at once
    print(f"    Embedding {len(all_texts)} chunks in batches of 64...")
    _indexing_state["progress"] = f"Embedding {len(all_texts)} chunks..."
    all_embeddings = get_embeddings_batch(all_texts)

    # Filter out any failed embeddings
    valid_ids = []
    valid_texts = []
    valid_embeddings = []
    valid_metadatas = []
    for i, emb in enumerate(all_embeddings):
        if emb is not None:
            valid_ids.append(all_ids[i])
            valid_texts.append(all_texts[i])
            valid_embeddings.append(emb)
            valid_metadatas.append(all_metadatas[i])

    if not valid_ids:
        print("    No valid embeddings generated.")
        return

    print(f"    Got {len(valid_ids)} embeddings. Inserting into ChromaDB...")
    _indexing_state["progress"] = f"Inserting {len(valid_ids)} vectors..."

    BATCH_SIZE = 100
    total = len(valid_ids)
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        collection.add(
            ids=valid_ids[batch_start:batch_end],
            documents=valid_texts[batch_start:batch_end],
            embeddings=valid_embeddings[batch_start:batch_end],
            metadatas=valid_metadatas[batch_start:batch_end],
        )
        pct = batch_end * 100 // total
        _indexing_state["progress"] = f"Indexing: {pct}% ({batch_end}/{total})"
        print(f"    [{pct:3d}%] Indexed {batch_end}/{total} chunks")

    print(f"\n  Done! Added {total} live stats vectors to ChromaDB")
    print(f"  Collection now has {collection.count()} total vectors")


def save_live_index(pages: List[Dict], cvm_ip: str):
    """Save a JSON index of crawled pages for reference."""
    index = {
        "cluster_ip": cvm_ip,
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_pages": len(pages),
        "status": "complete",
        "pages": [
            {
                "endpoint": p["endpoint"],
                "url": p["url"],
                "text_length": len(p["text"]),
                "is_html": p["is_html"],
            }
            for p in pages
        ],
    }
    with open(LIVE_STATS_INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)
    print(f"  Saved live stats index: {LIVE_STATS_INDEX_PATH}")


def run(cvm_ip: str, password: str = "nutanix/4u"):
    """Main entry point: crawl + index. Returns True on success."""
    _indexing_state["running"] = True
    _indexing_state["error"] = None
    _indexing_state["progress"] = "Starting..."

    print("=" * 60)
    print("  IDF Live Stats Crawler & Indexer (Single-SSH)")
    print("=" * 60)
    print(f"  Target CVM: {cvm_ip}:{IDF_PORT}")
    print(f"  ChromaDB:   {CHROMA_DIR}")
    print()

    try:
        # Verify connectivity
        _indexing_state["progress"] = "Verifying SSH connection..."
        test = ssh_exec(cvm_ip, "echo OK", password)
        if not test or "OK" not in test:
            _indexing_state["error"] = f"Could not reach {cvm_ip} (check VPN/network). Showing previously indexed data."
            _indexing_state["running"] = False
            _indexing_state["progress"] = ""
            print(f"  ERROR: Cannot SSH to {cvm_ip}. Check network/VPN.")
            return False

        print("  SSH connection verified.\n")

        # Crawl (single SSH call)
        pages = crawl_all(cvm_ip, password)
        if not pages:
            _indexing_state["error"] = "No pages crawled (is insights_server running?). Showing previously indexed data."
            _indexing_state["running"] = False
            _indexing_state["progress"] = ""
            print("  No pages crawled. Is insights_server running?")
            return False

        # Save index
        save_live_index(pages, cvm_ip)

        # Index into ChromaDB
        index_into_chromadb(pages, cvm_ip)

        # Reset KB service singleton so searches pick up new vectors
        try:
            import kb_service as _kbs
            _kbs._kb_service = None
            print("  KB service reset - searches will now include live stats")
        except Exception:
            pass

        _indexing_state["running"] = False
        _indexing_state["progress"] = "Complete"
        print("\n" + "=" * 60)
        print("  Live stats KB ready!")
        print("=" * 60)
        return True

    except Exception as e:
        _indexing_state["error"] = str(e)
        _indexing_state["running"] = False
        _indexing_state["progress"] = ""
        print(f"  ERROR: {e}")
        return False


def run_background(cvm_ip: str, password: str = "nutanix/4u"):
    """Run the indexer in a background thread. Non-blocking."""
    if _indexing_state["running"]:
        return
    t = threading.Thread(target=run, args=(cvm_ip, password), daemon=True)
    t.start()


def get_status() -> Dict:
    """Get current indexing status (for polling from API)."""
    if os.path.exists(LIVE_STATS_INDEX_PATH):
        try:
            with open(LIVE_STATS_INDEX_PATH) as f:
                data = json.load(f)
            return {
                "indexed": True,
                "running": _indexing_state["running"],
                "progress": _indexing_state["progress"],
                "error": _indexing_state["error"],
                "cluster_ip": data.get("cluster_ip"),
                "crawled_at": data.get("crawled_at"),
                "total_pages": data.get("total_pages", 0),
            }
        except Exception:
            pass

    return {
        "indexed": False,
        "running": _indexing_state["running"],
        "progress": _indexing_state["progress"],
        "error": _indexing_state["error"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl IDF stats pages and index into KB")
    parser.add_argument("--cvm-ip", required=True, help="CVM IP address")
    parser.add_argument("--password", default="nutanix/4u", help="SSH password")
    parser.add_argument("--port", type=int, default=2027, help="IDF port (default 2027)")
    args = parser.parse_args()

    IDF_PORT = args.port
    run(args.cvm_ip, args.password)
