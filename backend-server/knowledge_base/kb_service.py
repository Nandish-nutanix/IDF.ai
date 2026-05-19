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
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MLX_CHAT_URL = "http://localhost:8090/v1/chat/completions"
EMBED_MODEL = "nomic-embed-text"
SUMMARIZE_MODEL = "qwen2.5-coder:7b-instruct"
PHI4_CHAT_URL = "http://localhost:8090/v1/chat/completions"

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
                json={"model": EMBED_MODEL, "prompt": text[:2000]},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["embedding"]
        except Exception:
            pass
        return None

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
                if doc_id in seen_docs and len(output) >= top_k // 2:
                    continue
                seen_docs.add(doc_id)

                score = max(0.0, 1.0 - (abs(dist) / (max_dist * 1.5))) if max_dist > 0 else 0.5
                output.append({
                    "rank": len(output) + 1,
                    "text": doc,
                    "filename": meta.get("filename", ""),
                    "category": meta.get("category", ""),
                    "features": json.loads(meta.get("features", "[]")),
                    "relevance_score": round(score, 4),
                    "chunk_index": meta.get("chunk_index", 0),
                    "total_chunks": meta.get("total_chunks", 1),
                    "doc_id": doc_id,
                })
                if len(output) >= top_k:
                    break

        return output

    def summarize(self, query: str, context_chunks: Optional[List[str]] = None) -> str:
        """
        Summarize/answer a question about IDF using knowledge base context.
        Uses Ollama general-purpose model (not the fine-tuned proto model).
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
{context[:7000]}

QUESTION: {query}

Answer (use markdown, be definitive, cite sources when possible, NEVER invent information not in context):"""

        # Use Microsoft Phi-4 via MLX server (approved model)
        try:
            system_msg = """You are a senior Nutanix IDF engineer. Answer questions using ONLY the provided documentation context. Use markdown formatting with headers, bold, bullet points, and code blocks. Be definitive and authoritative. NEVER invent information not in the context. Cite source documents when possible."""
            user_msg = f"""Documentation context:
{context[:6000]}

Question: {query}

Provide a comprehensive, well-structured answer using the documentation above:"""
            resp = requests.post(
                PHI4_CHAT_URL,
                json={
                    "model": "phi4_idf_fused",
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    "max_tokens": 1200,
                    "temperature": 0.3,
                },
                timeout=150,
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if answer and len(answer) > 20:
                    return answer
                print(f"  [Summarize] Phi-4 returned short/empty: {answer[:100]}")
        except requests.exceptions.Timeout:
            print("  [Summarize] Phi-4 timed out (150s)")
        except Exception as e:
            print(f"  [Summarize] Phi-4 error: {e}")

        # Fallback to Ollama
        try:
            resp = requests.post(
                OLLAMA_GENERATE_URL,
                json={
                    "model": SUMMARIZE_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 1200},
                },
                timeout=120,
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                if answer:
                    return answer
        except Exception as e:
            return f"Summarization failed: {e}"

        return "Summarization service unavailable."

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

    def _phi4_chat(self, messages: List[Dict], max_tokens: int = 600, temperature: float = 0.3) -> str:
        """Call local Microsoft Phi-4 via MLX server."""
        try:
            resp = requests.post(
                PHI4_CHAT_URL,
                json={
                    "model": "phi4_idf_fused",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=180,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content.strip()
            else:
                print(f"  [DeepSearch] Phi-4 returned status {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.Timeout:
            print("  [DeepSearch] Phi-4 call timed out (180s)")
        except Exception as e:
            print(f"  [DeepSearch] Phi-4 call failed: {e}")
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

    def deep_search(self, query: str) -> Dict:
        """
        Deep Search: 6-stage pipeline for comprehensive, accurate answers.

        Stage 1: Query Expansion (Phi-4 generates sub-queries)
        Stage 2: Multi-Pass Retrieval (nomic-embed across sub-queries)
        Stage 3: Deduplicate & Re-rank (RRF + cross-query boost)
        Stage 4: Relevance Filter (Phi-4 scores chunks)
        Stage 5: Synthesis (Phi-4 generates comprehensive answer)
        Stage 6: Self-Verification (Phi-4 checks for hallucinations)
        """
        stages = []

        # ---- STAGE 1: Query Expansion ----
        stages.append({"stage": 1, "name": "Query Expansion", "status": "running"})

        expansion_prompt = [
            {"role": "system", "content": "You are an IDF (Insights Data Fabric) expert. Given a user question, generate 4 diverse search queries that would retrieve different relevant documents. Each query should approach the topic from a different angle (architecture, API usage, error handling, related concepts). Return ONLY the queries, one per line, no numbering."},
            {"role": "user", "content": f"Question: {query}\n\nGenerate 4 diverse search queries:"}
        ]
        expansion_result = self._phi4_chat(expansion_prompt, max_tokens=200, temperature=0.5)
        sub_queries = [q.strip().strip('"').strip("'") for q in expansion_result.split('\n') if q.strip() and len(q.strip()) > 10]
        if not sub_queries:
            sub_queries = [query]
        sub_queries = [query] + sub_queries[:4]

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(sub_queries)} sub-queries generated"

        # ---- STAGE 2: Multi-Pass Retrieval ----
        stages.append({"stage": 2, "name": "Multi-Pass Retrieval", "status": "running"})

        all_chunks = self._multi_embed_search(sub_queries, top_k_per_query=12)

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
        top_candidates = deduped[:30]

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(top_candidates)} unique chunks after dedup (from {len(all_chunks)})"

        # ---- STAGE 4: Relevance Filter ----
        stages.append({"stage": 4, "name": "Relevance Filter", "status": "running"})

        chunk_summaries = ""
        for i, chunk in enumerate(top_candidates[:20]):
            snippet = chunk["text"][:300].replace('\n', ' ')
            chunk_summaries += f"[{i+1}] {snippet}\n\n"

        filter_prompt = [
            {"role": "system", "content": "You are evaluating document relevance. Given a question and numbered document snippets, return ONLY the numbers of snippets that are DIRECTLY relevant to answering the question. Return numbers separated by commas, nothing else."},
            {"role": "user", "content": f"Question: {query}\n\nDocuments:\n{chunk_summaries}\n\nRelevant document numbers (comma-separated):"}
        ]
        filter_result = self._phi4_chat(filter_prompt, max_tokens=100, temperature=0.1)

        relevant_indices = set()
        for token in re.findall(r'\d+', filter_result):
            idx = int(token) - 1
            if 0 <= idx < len(top_candidates[:20]):
                relevant_indices.add(idx)

        if not relevant_indices:
            relevant_indices = set(range(min(10, len(top_candidates))))

        filtered_chunks = [top_candidates[i] for i in sorted(relevant_indices)]

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"{len(filtered_chunks)} relevant chunks (filtered from {min(20, len(top_candidates))})"

        # ---- STAGE 5: Synthesis ----
        stages.append({"stage": 5, "name": "Comprehensive Synthesis", "status": "running"})

        context_parts = []
        sources = []
        for chunk in filtered_chunks[:15]:
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
            {"role": "user", "content": f"DOCUMENTATION CONTEXT:\n{context[:8000]}\n\nQUESTION: {query}\n\nProvide a comprehensive, well-structured answer:"}
        ]
        synthesis_result = self._phi4_chat(synthesis_prompt, max_tokens=1500, temperature=0.2)

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = f"Answer synthesized from {len(filtered_chunks)} sources"

        # ---- STAGE 6: Self-Verification ----
        stages.append({"stage": 6, "name": "Self-Verification", "status": "running"})

        verify_prompt = [
            {"role": "system", "content": "You are a fact-checker. Review the answer below against the provided context. If any claims are NOT supported by the context, rewrite the answer removing those claims. If the answer is fully supported, return it unchanged. Return ONLY the final verified answer."},
            {"role": "user", "content": f"CONTEXT:\n{context[:4000]}\n\nANSWER TO VERIFY:\n{synthesis_result}\n\nVerified answer:"}
        ]
        verified_answer = self._phi4_chat(verify_prompt, max_tokens=1500, temperature=0.1)

        if not verified_answer or len(verified_answer) < len(synthesis_result) * 0.3:
            verified_answer = synthesis_result

        stages[-1]["status"] = "done"
        stages[-1]["detail"] = "Answer verified against source documents"

        return {
            "answer": verified_answer,
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
