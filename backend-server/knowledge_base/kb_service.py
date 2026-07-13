"""
IDF Knowledge Base Service.

Provides:
- Semantic search across IDF documentation
- Document summarization via LLM
- Feature index lookups (query -> related IDF features/docs)
- Document browsing by category
"""

import json
import os
import re
from typing import Dict, List, Optional

import chromadb
import requests

KB_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(KB_DIR, "chroma_db")
HTML_DIR = os.path.join(KB_DIR, "html_docs")
RAW_DOCS_DIR = os.path.join(KB_DIR, "raw_docs")
INDEX_PATH = os.path.join(KB_DIR, "doc_index.json")

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# Chat/summarization backend is resolved from the shared server config so the KB
# uses whatever LLM is actually available (MLX Phi-4 when up, else the Ollama
# fallback). This keeps the Knowledge Base answering even when MLX is down.
try:
    import config as _server_config
    CHAT_URL = _server_config.API_BASE_URL.rstrip("/") + "/chat/completions"
    SUMMARIZE_MODEL = _server_config.CHAT_MODEL
    CHAT_API_KEY = getattr(_server_config, "API_KEY", "") or ""
    CHAT_TIMEOUT = getattr(_server_config, "LLM_TIMEOUT", 120)
except Exception:  # noqa: BLE001 - standalone import fallback
    CHAT_URL = "http://localhost:8090/v1/chat/completions"
    SUMMARIZE_MODEL = "phi4_idf_fused"
    CHAT_API_KEY = ""
    CHAT_TIMEOUT = 120

# Back-compat aliases (older code referenced these names).
MLX_CHAT_URL = CHAT_URL
PHI4_CHAT_URL = CHAT_URL


def _chat_headers():
    h = {"Content-Type": "application/json"}
    if CHAT_API_KEY and CHAT_API_KEY != "ollama":
        h["Authorization"] = f"Bearer {CHAT_API_KEY}"
    return h

# Ground truth definitions for critical IDF concepts.
# These are injected into the summarization prompt to prevent hallucination.
IDF_GROUND_TRUTH = """
## IDF Core Definitions (AUTHORITATIVE - use these exactly, do NOT invent alternatives):

- **CAS (Compare-And-Swap)**: An optimistic concurrency control mechanism in IDF. Each entity has a `cas_value` (integer version counter). On update, the client provides the current cas_value; IDF atomically checks it matches the stored value, performs the update, and increments cas_value. If the values don't match (another writer updated first), the update is rejected with a CAS conflict error. This prevents lost updates without locks. CAS does NOT stand for "Conflict-Abort-Sync" or any other expansion.

- **Entity Type**: A schema definition in IDF (like a table in a database). Must be registered via `RegisterEntityTypes` before entities of that type can be stored. Has properties like evictability, replication mode.

- **Metric Type / Attribute**: A named, typed field on an entity type (like a column). Registered via `RegisterMetricTypes` with a name, data type (kInt64, kString, kFloat64, kBoolean), and optionally `is_attribute: true`. Despite the name "metric", these are general-purpose attributes.

- **Namespace**: A partition mechanism for attributes. Different services can own different attribute namespaces on the same entity. Updates to one namespace don't affect another's CAS value. Namespaces are sub-entities whose lifecycle is tied to their parent.

- **Evictable vs Unevictable**: Entity types can be `kEvictable` (IDF can garbage-collect old entities under memory pressure) or `kNotEvictable` (permanent, never auto-deleted).

- **IDF Lattice**: A framework for Federated Entity Types that span multiple clusters. Enables global entity views using consensus (Raft-based) across Prism Central and Prism Element clusters. Uses `ProposeChange` and `ApplyChange` RPCs.

- **Watch**: A subscription mechanism. Clients register watches on entity types and get notified when entities change. Supports register, get, and unregister operations via the Watch API.

- **GEWM (GetEntitiesWithMetrics)**: The primary read/query API in IDF. Supports filtering (where_clause), sorting (order_by_column), grouping (group_by), pagination, and aggregation.

- **Secondary Index**: Attributes marked for secondary indexing can be efficiently queried in where_clause filters. Non-indexed attributes require full scans.

- **Prism Central (PC)**: Management plane that aggregates data from multiple Prism Element (PE) clusters. IDF on PC stores replicated entity views.

- **Prism Element (PE)**: Per-cluster hypervisor management. Each PE has its own IDF instance.
"""

FEATURE_INDEX = {
    "entity_type": {
        "keywords": ["entity type", "entity_type", "register entity", "entity_type_name", "RegisterEntityTypes"],
        "description": "Entity types define the schema for entities in IDF. An entity type must be registered before entities of that type can be stored.",
        "related_apis": ["RegisterEntityTypes", "GetEntityTypes"],
    },
    "namespace": {
        "keywords": ["namespace", "namespaces", "attribute namespace", "kNamespace"],
        "description": "Namespaces allow partitioning attributes so different services can own different attribute sets on the same entity.",
        "related_apis": ["GetEntitiesWithMetrics", "UpdateEntity"],
    },
    "CAS": {
        "keywords": ["cas", "cas_value", "compare and swap", "compare-and-swap", "optimistic locking"],
        "description": "Compare-And-Swap (CAS) provides optimistic concurrency control. The cas_value is incremented on each update and must match for the update to succeed.",
        "related_apis": ["UpdateEntity", "DeleteEntity"],
    },
    "watch": {
        "keywords": ["watch", "watches", "subscription", "register watch", "unregister watch", "notify"],
        "description": "Watches allow subscribing to changes on entities. When an entity changes, registered watchers are notified.",
        "related_apis": ["Watch"],
    },
    "eviction": {
        "keywords": ["evictable", "unevictable", "eviction", "kEvictable", "kNotEvictable"],
        "description": "Entities can be marked as evictable (can be garbage collected when space is needed) or unevictable (permanent).",
        "related_apis": ["RegisterEntityTypes", "UpdateEntity"],
    },
    "lattice": {
        "keywords": ["lattice", "federated", "global entity", "cross-cluster", "IDF-Lattice"],
        "description": "IDF Lattice enables federated entity types that span across multiple clusters, allowing global views of entities.",
        "related_apis": ["RegisterEntityTypes", "GetEntitiesWithMetrics", "BatchGetEntitiesWithMetrics"],
    },
    "metrics": {
        "keywords": ["metric", "metrics", "metric_type", "RegisterMetricTypes", "data_type", "kInt64", "kString"],
        "description": "Metrics define measurable/storable attributes on entities. They must be registered with a data type before use.",
        "related_apis": ["RegisterMetricTypes", "UnregisterMetricTypes", "GetMetricTypes", "PutMetricData"],
    },
    "batch_operations": {
        "keywords": ["batch", "BatchGet", "BatchUpdate", "BatchDelete", "query_list"],
        "description": "Batch operations allow performing multiple IDF operations in a single RPC call for better performance.",
        "related_apis": ["BatchGetEntitiesWithMetrics", "BatchUpdateEntities", "BatchDeleteEntities"],
    },
    "secondary_index": {
        "keywords": ["secondary index", "indexing", "indexed attribute", "searchable"],
        "description": "Secondary indexes allow efficient querying on non-primary-key attributes. Attributes must be explicitly indexed.",
        "related_apis": ["RegisterMetricTypes", "GetEntitiesWithMetrics"],
    },
    "query_filter": {
        "keywords": ["filter", "where_clause", "comparison_expr", "kEQ", "kGE", "kLE", "kGT", "kLT", "kExists"],
        "description": "Query filters allow narrowing results using comparison expressions with operators like kEQ, kGE, kLE, etc.",
        "related_apis": ["GetEntitiesWithMetrics"],
    },
    "aggregation": {
        "keywords": ["group_by", "aggregation", "sum", "avg", "count", "min", "max", "SUM", "AVG", "COUNT"],
        "description": "Aggregation functions (SUM, AVG, COUNT, MIN, MAX) can be applied to numeric attributes via group_by clauses.",
        "related_apis": ["GetEntitiesWithMetrics"],
    },
    "sorting": {
        "keywords": ["sort", "order_by", "ascending", "descending", "kAscending", "kDescending"],
        "description": "Results can be sorted by attribute values in ascending or descending order using order_by_column.",
        "related_apis": ["GetEntitiesWithMetrics"],
    },
    "pagination": {
        "keywords": ["cursor", "pagination", "limit", "offset", "cursor_id"],
        "description": "Large result sets can be paginated using cursor-based pagination for memory-efficient retrieval.",
        "related_apis": ["GetEntitiesWithMetrics"],
    },
    "replication": {
        "keywords": ["replication", "replicated", "sync", "PC-PE", "Prism Central"],
        "description": "IDF supports replication of entities between Prism Element (PE) clusters and Prism Central (PC).",
        "related_apis": ["RegisterEntityTypes", "GetEntitiesWithMetrics"],
    },
    "spotlight": {
        "keywords": ["spotlight", "full text search", "SpotLightSearch", "text search"],
        "description": "SpotLightSearch provides full-text search capabilities across entity attributes.",
        "related_apis": ["SpotLightSearch"],
    },
    "PCDR": {
        "keywords": ["PCDR", "disaster recovery", "backup", "restore", "S3"],
        "description": "PC Disaster Recovery (PCDR) enables backing up and restoring Prism Central data including IDF entities.",
        "related_apis": [],
    },
    "schema_config": {
        "keywords": ["schema", "config", "schema_config", "entity_attribute_config"],
        "description": "Schema configuration defines the registered entity types and their attributes/metrics for the IDF instance.",
        "related_apis": ["RegisterEntityTypes", "RegisterMetricTypes"],
    },
}


class KnowledgeBaseService:
    """Service for searching and summarizing IDF knowledge base."""

    def __init__(self):
        self._collection = None
        self._doc_index = None
        self._load()

    def _load(self):
        """Load ChromaDB collection and document index."""
        try:
            client = chromadb.PersistentClient(path=CHROMA_DIR)
            self._collection = client.get_collection("idf_knowledge_base")
            print(f"  KB: Loaded ChromaDB collection ({self._collection.count()} vectors)")
        except Exception as e:
            print(f"  KB WARNING: ChromaDB not available: {e}")
            self._collection = None

        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH) as f:
                data = json.load(f)
                self._doc_index = data
            print(f"  KB: Loaded doc index ({len(data.get('documents', []))} documents)")
        else:
            print("  KB WARNING: doc_index.json not found")
            self._doc_index = {"documents": [], "metadata": {}}

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text via Ollama."""
        try:
            resp = requests.post(
                OLLAMA_EMBED_URL,
                json={"model": EMBED_MODEL, "prompt": text[:2000], "keep_alive": "1h"},
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json()["embedding"]
        except Exception:
            pass
        return None

    def _chat_completion(self, messages: List[Dict], max_tokens: int = 500,
                         temperature: float = 0.3, llm_override: Optional[Dict] = None) -> str:
        """POST a chat/completions request and return the message content.

        When ``llm_override`` carries an api_key ("bring your own model") the
        call targets that user-supplied OpenAI-compatible endpoint; otherwise it
        uses the local default summarization backend.
        """
        use_override = bool(llm_override and llm_override.get("api_key"))
        effective_max = max_tokens
        if use_override:
            base = (llm_override.get("base_url") or "").strip().rstrip("/")
            if not base:
                base = CHAT_URL.rsplit("/chat/completions", 1)[0]
            url = base + "/chat/completions"
            model = (llm_override.get("model") or "").strip() or SUMMARIZE_MODEL
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {llm_override['api_key']}",
            }
            # Remote models (especially large reasoning models) can be slow.
            timeout = 240
            # Reasoning models spend tokens "thinking" before the final answer;
            # give them headroom so the answer isn't truncated mid-reasoning.
            effective_max = max(max_tokens + 1500, 1800)
        else:
            url = CHAT_URL
            model = SUMMARIZE_MODEL
            headers = _chat_headers()
            timeout = max(CHAT_TIMEOUT, 180)

        verify_ssl = not ("localhost" in url or "127.0.0.1" in url)
        resp = requests.post(
            url,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "max_tokens": effective_max,
                "temperature": temperature,
            },
            timeout=timeout,
            verify=verify_ssl,
        )
        resp.raise_for_status()
        message = resp.json().get("choices", [{}])[0].get("message", {}) or {}
        content = (message.get("content") or "").strip()
        # Some reasoning models (e.g. nemotron) return the chain-of-thought in a
        # separate "reasoning_content" field and the final answer in "content".
        # If content is empty (answer was short/truncated), fall back to it.
        if not content:
            content = (message.get("reasoning_content") or "").strip()
        # Strip any <think>...</think> block that leaked into the content.
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content

    def search(self, query: str, top_k: int = 8, category: Optional[str] = None) -> List[Dict]:
        """
        Semantic search across the knowledge base.
        Returns ranked list of document chunks with metadata.
        Retrieves 3x top_k candidates then deduplicates by doc to get diverse results.
        """
        if not self._collection:
            return []

        embedding = self._get_embedding(query)
        if not embedding:
            return []

        where_filter = None
        if category:
            where_filter = {"category": category}

        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k * 3, 25),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        seen_docs = set()
        if results and results["documents"]:
            distances = results["distances"][0]
            max_dist = max(abs(d) for d in distances) if distances else 1.0
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                distances,
            )):
                doc_id = meta.get("doc_id", "")
                cat = meta.get("category", "")
                # Don't dedup live stats - each chunk is independently valuable
                is_live = cat == "Live Cluster Stats"
                if not is_live and doc_id in seen_docs and len(output) >= top_k // 2:
                    continue
                seen_docs.add(doc_id)

                score = max(0.0, 1.0 - (abs(dist) / (max_dist * 1.5))) if max_dist > 0 else 0.5
                result_entry = {
                    "rank": len(output) + 1,
                    "text": doc,
                    "filename": meta.get("filename", ""),
                    "category": cat,
                    "features": json.loads(meta.get("features", "[]")),
                    "relevance_score": round(score, 4),
                    "chunk_index": meta.get("chunk_index", 0),
                    "total_chunks": meta.get("total_chunks", 1),
                    "doc_id": doc_id,
                }
                if is_live:
                    result_entry["endpoint"] = meta.get("endpoint", "")
                    result_entry["cluster_ip"] = meta.get("cluster_ip", "")
                output.append(result_entry)
                if len(output) >= top_k:
                    break

        return output

    def summarize(self, query: str, context_chunks: Optional[List[str]] = None,
                  llm_override: Optional[Dict] = None) -> str:
        """
        Summarize/answer a question about IDF using knowledge base context.
        Uses the local default model, or a user-supplied model via ``llm_override``.
        """
        if not context_chunks:
            results = self.search(query, top_k=10)
            context_chunks = [r["text"] for r in results]

        if not context_chunks:
            return "No relevant documentation found for this query."

        context = "\n\n---\n\n".join(context_chunks[:8])

        prompt = f"""You are a senior engineer on the Nutanix IDF (Insights Data Fabric) team. You have deep expertise in IDF architecture, APIs, and internals.

CRITICAL RULES:
- ONLY answer based on the documentation context below and the ground truth definitions. If the context doesn't contain enough information, say "This information is not available in the current documentation."
- NEVER invent information, make up field names, fabricate API behaviors, or guess at implementation details.
- Use the GROUND TRUTH DEFINITIONS below as the authoritative source for IDF terminology. NEVER invent your own definitions or expansions for acronyms.
- Be definitive and authoritative. Do NOT use uncertain language like "appears to be", "seems to", "suggests that", "might be".
- Use markdown formatting: headers (##), bullet points, **bold** for key terms, `code` for technical terms.
- Structure your answer clearly with sections if needed.
- Keep the answer focused, technical, and accurate.
- Cite which document the information comes from when possible (look for [Category | Filename] prefixes in context chunks).

{IDF_GROUND_TRUTH}

DOCUMENTATION CONTEXT (from indexed internal documents):
{context[:5000]}

QUESTION: {query}

Answer (use markdown, be definitive, cite sources when possible, NEVER invent information not in context):"""

        # Local default model, or a user-supplied model when llm_override is set.
        try:
            system_msg = """You are a technical writer for the Nutanix IDF team. Your job is to REPHRASE the provided documentation into clear, well-written, easy-to-read language. Do NOT add analysis, opinions, or any facts that are not present in the documentation. Do NOT invent field names, APIs, or behaviors. Keep it faithful to the source, only improve the wording, structure, and readability. Use light markdown (short paragraphs, bullet points, **bold** for key terms)."""
            user_msg = f"""Documentation:
{context[:6000]}

Rephrase the documentation above into clear, well-written language relevant to: "{query}"

Rephrased version (faithful to the source, just better worded):"""
            answer = self._chat_completion(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=500,
                temperature=0.3,
                llm_override=llm_override,
            )
            if answer and len(answer) > 20:
                return answer
            print(f"  [Summarize] LLM returned short/empty: {answer[:100]}")
        except requests.exceptions.Timeout:
            print("  [Summarize] LLM timed out")
            return "Summarization timed out. Please retry."
        except Exception as e:
            print(f"  [Summarize] LLM error: {e}")
            return f"Summarization failed: {e}"

        return "Summarization service unavailable (LLM backend not reachable)."

    def rephrase_query(self, query: str, llm_override: Optional[Dict] = None) -> str:
        """Rewrite the user's question into a single, clearer, better-phrased question.

        Used to produce a clean query the user can copy and search on Glean.
        Returns just the reworded question (falls back to the original on error).
        """
        query = (query or "").strip()
        if not query:
            return ""
        try:
            system_msg = (
                "You rewrite short technical questions about Nutanix IDF (Insights Data "
                "Fabric) into a single, clear, well-phrased question. Return ONLY the "
                "rewritten question on one line, with no preamble, quotes, bullet points, "
                "or explanation. Keep it concise, specific, and search-friendly."
            )
            user_msg = f"Rewrite this into one clear, well-phrased question:\n\n{query}"
            out = self._chat_completion(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=80,
                temperature=0.3,
                llm_override=llm_override,
            )
            out = (out or "").strip()
            # Keep only the first non-empty line and strip wrapping quotes.
            for line in out.splitlines():
                line = line.strip().strip('"').strip("'").strip()
                if line:
                    return line
            return query
        except Exception as e:
            print(f"  [Rephrase] error: {e}")
            return query

    def get_related_features(self, query: str, api_method: Optional[str] = None) -> List[Dict]:
        """
        Given a query or API method, return related IDF features with documentation links.
        Used by the 'Related Features' button in the UI.
        """
        query_lower = query.lower()
        matched_features = []

        for feature_name, feature_data in FEATURE_INDEX.items():
            score = 0.0

            for kw in feature_data["keywords"]:
                if kw.lower() in query_lower:
                    score += 1.0

            if api_method and api_method in feature_data.get("related_apis", []):
                score += 2.0

            if score > 0:
                # Find related documents
                related_docs = self._find_docs_for_feature(feature_name)
                matched_features.append({
                    "feature": feature_name,
                    "description": feature_data["description"],
                    "related_apis": feature_data["related_apis"],
                    "relevance_score": score,
                    "related_docs": related_docs[:3],
                })

        matched_features.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matched_features[:5]

    def _find_docs_for_feature(self, feature_name: str) -> List[Dict]:
        """Find documents related to a specific feature."""
        if not self._doc_index:
            return []

        feature_data = FEATURE_INDEX.get(feature_name, {})
        keywords = feature_data.get("keywords", [])

        relevant_docs = []
        for doc in self._doc_index.get("documents", []):
            doc_features = doc.get("features", [])
            filename_lower = doc["filename"].lower()

            match_score = 0
            for kw in keywords:
                if kw.lower() in filename_lower:
                    match_score += 3
                for df in doc_features:
                    if kw.lower() in df.lower():
                        match_score += 1

            if match_score > 0:
                relevant_docs.append({
                    "filename": doc["filename"],
                    "category": doc["category"],
                    "match_score": match_score,
                })

        relevant_docs.sort(key=lambda x: x["match_score"], reverse=True)
        return relevant_docs

    def get_all_documents(self, category: Optional[str] = None) -> List[Dict]:
        """List all indexed documents, optionally filtered by category."""
        if not self._doc_index:
            return []

        docs = self._doc_index.get("documents", [])
        if category:
            docs = [d for d in docs if d["category"] == category]

        return [
            {
                "id": d["id"],
                "filename": d["filename"],
                "category": d["category"],
                "features": d["features"],
                "num_chunks": d["num_chunks"],
            }
            for d in docs
        ]

    def get_categories(self) -> List[Dict]:
        """Get all document categories with counts."""
        if not self._doc_index:
            return []

        category_counts = {}
        for doc in self._doc_index.get("documents", []):
            cat = doc["category"]
            if cat not in category_counts:
                category_counts[cat] = 0
            category_counts[cat] += 1

        return [
            {"name": cat, "doc_count": count}
            for cat, count in sorted(category_counts.items())
        ]

    def get_document_content(self, doc_id: str) -> Optional[Dict]:
        """Get full content of a specific document, preferring rich HTML."""
        if not self._doc_index:
            return None

        meta = self._doc_index.get("metadata", {}).get(doc_id)
        if not meta:
            return None

        doc_info = None
        for d in self._doc_index.get("documents", []):
            if d["id"] == doc_id:
                doc_info = d
                break

        if not doc_info:
            return None

        # Try to serve rich HTML (preserves formatting, images, tables)
        html_path = os.path.join(HTML_DIR, f"{doc_id}.html")
        content = ""
        content_type = "text"
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            content_type = "html"
        else:
            content = "\n\n".join(meta.get("chunks", []))

        return {
            "id": doc_id,
            "filename": doc_info["filename"],
            "category": doc_info["category"],
            "features": doc_info["features"],
            "content": content,
            "content_type": content_type,
            "num_chunks": len(meta.get("chunks", [])),
        }


    # ========================================================================
    # DEEP SEARCH — Multi-stage retrieval + synthesis pipeline
    # Uses ONLY: Microsoft Phi-4 (MLX) + nomic-embed-text (Ollama)
    # ========================================================================

    def _phi4_chat(self, messages: List[Dict], max_tokens: int = 600, temperature: float = 0.3,
                   llm_override: Optional[Dict] = None) -> str:
        """Call the summarization LLM (local default, or a user-supplied model)."""
        try:
            return self._chat_completion(
                messages, max_tokens=max_tokens, temperature=temperature,
                llm_override=llm_override,
            )
        except requests.exceptions.Timeout:
            print("  [DeepSearch] LLM call timed out")
        except Exception as e:
            print(f"  [DeepSearch] LLM call failed: {e}")
        return ""

    def _multi_embed_search(self, queries: List[str], top_k_per_query: int = 12) -> List[Dict]:
        """Run multiple embedding queries and merge results with cross-query boosting."""
        all_results = {}
        query_appearances = {}

        for q_idx, query in enumerate(queries):
            embedding = self._get_embedding(query)
            if not embedding or not self._collection:
                continue

            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=top_k_per_query,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results["documents"] or not results["documents"][0]:
                continue

            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                chunk_key = meta.get("doc_id", "") + "_" + str(meta.get("chunk_index", i))
                rank_score = 1.0 / (60 + i + 1)

                if chunk_key in all_results:
                    all_results[chunk_key]["rrf_score"] += rank_score
                    query_appearances[chunk_key] += 1
                else:
                    all_results[chunk_key] = {
                        "text": doc,
                        "metadata": meta,
                        "distance": dist,
                        "rrf_score": rank_score,
                    }
                    query_appearances[chunk_key] = 1

        for key in all_results:
            if query_appearances[key] > 1:
                all_results[key]["rrf_score"] *= (1 + 0.3 * query_appearances[key])

        ranked = sorted(all_results.values(), key=lambda x: x["rrf_score"], reverse=True)
        return ranked

    def deep_search(self, query: str, llm_override: Optional[Dict] = None) -> Dict:
        """
        Deep Search: 5-stage pipeline for comprehensive, accurate answers.

        Stage 1: Query Expansion (Phi-4 generates 2 sub-queries)
        Stage 2: Multi-Pass Retrieval (nomic-embed across sub-queries)
        Stage 3: Deduplicate & Re-rank (RRF + cross-query boost)
        Stage 4: Relevance Filter (Phi-4 scores chunks)
        Stage 5: Synthesis (Phi-4 generates comprehensive answer)
        """
        stages = []

        # ---- STAGE 1: Query Expansion ----
        stages.append({"stage": 1, "name": "Query Expansion", "status": "running"})

        expansion_prompt = [
            {"role": "system", "content": "You are an IDF (Insights Data Fabric) expert. Given a user question, generate 2 alternative search queries that approach the topic from different angles. Return ONLY the queries, one per line, no numbering."},
            {"role": "user", "content": f"Question: {query}\n\nGenerate 2 alternative search queries:"}
        ]
        expansion_result = self._phi4_chat(expansion_prompt, max_tokens=100, temperature=0.5, llm_override=llm_override)
        sub_queries = [q.strip().strip('"').strip("'") for q in expansion_result.split('\n') if q.strip() and len(q.strip()) > 10]
        if not sub_queries:
            sub_queries = [query]
        sub_queries = [query] + sub_queries[:2]

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(sub_queries)} search angles"

        # ---- STAGE 2: Multi-Pass Retrieval ----
        stages.append({"stage": 2, "name": "Multi-Pass Retrieval", "status": "running"})

        all_chunks = self._multi_embed_search(sub_queries, top_k_per_query=8)

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(all_chunks)} candidate chunks from {len(sub_queries)} queries"

        # ---- STAGE 3: Deduplicate & Re-rank ----
        stages.append({"stage": 3, "name": "Deduplicate & Re-rank", "status": "running"})

        seen_texts = set()
        deduped = []
        for chunk in all_chunks:
            text_hash = chunk["text"][:200]
            if text_hash not in seen_texts:
                seen_texts.add(text_hash)
                deduped.append(chunk)
        top_candidates = deduped[:15]

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(top_candidates)} unique chunks after dedup (from {len(all_chunks)})"

        # ---- STAGE 4: Relevance Filter ----
        stages.append({"stage": 4, "name": "Relevance Filter", "status": "running"})

        chunk_summaries = ""
        for i, chunk in enumerate(top_candidates[:15]):
            snippet = chunk["text"][:250].replace('\n', ' ')
            chunk_summaries += f"[{i+1}] {snippet}\n\n"

        filter_prompt = [
            {"role": "system", "content": "You are evaluating document relevance. Given a question and numbered document snippets, return ONLY the numbers of snippets that are DIRECTLY relevant to answering the question. Return numbers separated by commas, nothing else."},
            {"role": "user", "content": f"Question: {query}\n\nDocuments:\n{chunk_summaries}\n\nRelevant document numbers (comma-separated):"}
        ]
        filter_result = self._phi4_chat(filter_prompt, max_tokens=50, temperature=0.1, llm_override=llm_override)

        relevant_indices = set()
        for token in re.findall(r'\d+', filter_result):
            idx = int(token) - 1
            if 0 <= idx < len(top_candidates[:15]):
                relevant_indices.add(idx)

        if not relevant_indices:
            relevant_indices = set(range(min(8, len(top_candidates))))

        filtered_chunks = [top_candidates[i] for i in sorted(relevant_indices)]

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(filtered_chunks)} relevant chunks (filtered from {min(15, len(top_candidates))})"

        # ---- STAGE 5: Synthesis ----
        stages.append({"stage": 5, "name": "Comprehensive Synthesis", "status": "running"})

        context_parts = []
        sources = []
        for chunk in filtered_chunks[:12]:
            context_parts.append(chunk["text"])
            fname = chunk["metadata"].get("filename", "unknown")
            cat = chunk["metadata"].get("category", "")
            if fname not in [s["filename"] for s in sources]:
                sources.append({"filename": fname, "category": cat})

        context = "\n\n---\n\n".join(context_parts)

        synthesis_prompt = [
            {"role": "system", "content": f"""You are a senior Nutanix IDF (Insights Data Fabric) engineer providing a thorough technical answer.

RULES:
- ONLY use information from the provided documentation context. NEVER invent details.
- Structure your answer with: ## Summary (2-3 sentence overview), ## Details (thorough explanation with sub-sections), ## Key Takeaways (bullet points)
- Use markdown: headers, bold for key terms, code blocks for technical terms, bullet points
- Cite source documents using [Source: filename] notation
- If information is insufficient, explicitly state what is missing
- Be definitive — no hedging language

{IDF_GROUND_TRUTH}"""},
            {"role": "user", "content": f"DOCUMENTATION CONTEXT:\n{context[:7000]}\n\nQUESTION: {query}\n\nProvide a comprehensive, well-structured answer:"}
        ]
        synthesis_result = self._phi4_chat(synthesis_prompt, max_tokens=1000, temperature=0.2, llm_override=llm_override)

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"Answer synthesized from {len(filtered_chunks)} sources"

        return {
            "answer": synthesis_result,
            "sources": sources[:10],
            "sub_queries": sub_queries,
            "stages": stages,
            "chunks_searched": len(all_chunks),
            "chunks_used": len(filtered_chunks),
            "query": query,
        }


# Singleton instance
_kb_service: Optional[KnowledgeBaseService] = None


def get_kb_service() -> KnowledgeBaseService:
    """Get or create the KB service singleton."""
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service
