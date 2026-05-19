"""
Chroma vector DB setup and management with hybrid search (vector + BM25).

Key improvements over original:
- Hybrid search combining semantic vector similarity with BM25 keyword matching
- Reciprocal Rank Fusion (RRF) for merging ranked lists from both retrieval methods
- Reduced retrieval count (20 final chunks vs 70) for better LLM context precision
- Entity-aware reranking to boost chunks from detected entity types
"""

import hashlib
import json
import logging
import math
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError

import config
import embeddings_client
import schema_chunker

logger = logging.getLogger(__name__)

_bm25_index: Optional["BM25Index"] = None


class BM25Index:
    """
    Simple BM25 (Okapi BM25) index for keyword-based schema chunk retrieval.
    Operates on chunk texts stored in memory.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: List[str] = []
        self.doc_ids: List[str] = []
        self.doc_metadata: List[dict] = []
        self.tokenized_docs: List[List[str]] = []
        self.doc_lengths: List[int] = []
        self.avg_dl: float = 0.0
        self.df: Dict[str, int] = {}
        self.n_docs: int = 0

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + underscore tokenization for schema terms."""
        text = text.lower()
        tokens = re.split(r'[\s_]+', text)
        return [t for t in tokens if t]

    def build(self, docs: List[str], doc_ids: List[str], doc_metadata: List[dict]):
        """Build the BM25 index from documents."""
        self.docs = docs
        self.doc_ids = doc_ids
        self.doc_metadata = doc_metadata
        self.tokenized_docs = [self._tokenize(d) for d in docs]
        self.doc_lengths = [len(d) for d in self.tokenized_docs]
        self.n_docs = len(docs)
        self.avg_dl = sum(self.doc_lengths) / self.n_docs if self.n_docs > 0 else 1.0

        self.df = defaultdict(int)
        for tokens in self.tokenized_docs:
            seen = set()
            for token in tokens:
                if token not in seen:
                    self.df[token] += 1
                    seen.add(token)

    def search(self, query: str, top_k: int = 30) -> List[dict]:
        """
        Search for top-k matching documents using BM25 scoring.
        Returns list of dicts with chunk_text, metadata, bm25_score.
        """
        query_tokens = self._tokenize(query)
        scores = []

        for idx in range(self.n_docs):
            score = self._score_document(query_tokens, idx)
            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            results.append({
                "chunk_text": self.docs[idx],
                "metadata": self.doc_metadata[idx],
                "bm25_score": score,
                "doc_id": self.doc_ids[idx],
            })
        return results

    def _score_document(self, query_tokens: List[str], doc_idx: int) -> float:
        """Compute BM25 score for a single document."""
        doc_tokens = self.tokenized_docs[doc_idx]
        dl = self.doc_lengths[doc_idx]
        score = 0.0

        tf_map: Dict[str, int] = defaultdict(int)
        for token in doc_tokens:
            tf_map[token] += 1

        for qt in query_tokens:
            if qt not in tf_map:
                continue
            tf = tf_map[qt]
            df = self.df.get(qt, 0)
            idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (dl / self.avg_dl))
            score += idf * (numerator / denominator)

        return score


def get_schema_hash() -> str:
    """Compute hash of schema file for change detection."""
    return schema_chunker.compute_schema_hash(config.ENTITY_ATTRIBUTE_CONFIG_FILE)


def load_schema_hash() -> Optional[str]:
    """Load stored schema hash from marker file."""
    marker_file = Path(config.VECTOR_DB_MARKER_FILE)
    if not marker_file.exists():
        return None

    try:
        with open(marker_file, 'r') as f:
            data = json.load(f)
            return data.get("schema_hash")
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def save_schema_hash(schema_hash: str):
    """Save schema hash to marker file."""
    marker_file = Path(config.VECTOR_DB_MARKER_FILE)
    marker_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "schema_hash": schema_hash,
        "schema_file": config.ENTITY_ATTRIBUTE_CONFIG_FILE
    }

    with open(marker_file, 'w') as f:
        json.dump(data, f, indent=2)


def is_vector_db_up_to_date() -> bool:
    """Check if vector DB exists and is up-to-date with current schema."""
    db_path = Path(config.VECTOR_DB_PATH)
    if not db_path.exists():
        return False

    stored_hash = load_schema_hash()
    if stored_hash is None:
        return False

    current_hash = get_schema_hash()
    return stored_hash == current_hash


def build_vector_db():
    """
    Build or rebuild the vector DB from schema chunks and initialize the BM25 index.
    """
    global _bm25_index

    print("Loading schema chunks...")
    chunks = schema_chunker.load_schema_chunks()
    print(f"Found {len(chunks)} schema chunks")

    db_path = Path(config.VECTOR_DB_PATH)
    db_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        client.delete_collection(config.VECTOR_DB_COLLECTION_NAME)
    except (ValueError, NotFoundError):
        pass

    collection = client.create_collection(
        name=config.VECTOR_DB_COLLECTION_NAME,
        metadata={"description": "Insights schema chunks for NL query"}
    )

    chunk_texts = [chunk.chunk_text for chunk in chunks]
    chunk_ids = [chunk.chunk_id for chunk in chunks]

    batch_size = 100
    all_embeddings = []

    print("Getting embeddings from API...")
    for i in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[i:i + batch_size]
        print(f"  Processing batch {i // batch_size + 1}/{(len(chunk_texts) + batch_size - 1) // batch_size}")
        batch_embeddings = embeddings_client.get_embeddings(batch)
        all_embeddings.extend(batch_embeddings)

    metadatas = []
    for chunk in chunks:
        metadata = {
            "entity_type": chunk.entity_type_name,
            "attribute": chunk.metric_name,
        }
        if chunk.data_type:
            metadata["data_type"] = chunk.data_type
        metadatas.append(metadata)

    print("Storing in vector DB...")
    collection.add(
        ids=chunk_ids,
        embeddings=all_embeddings,
        documents=chunk_texts,
        metadatas=metadatas
    )

    # Build BM25 index in memory
    print("Building BM25 keyword index...")
    _bm25_index = BM25Index()
    _bm25_index.build(chunk_texts, chunk_ids, metadatas)
    print(f"BM25 index built with {len(chunk_texts)} documents")

    schema_hash = get_schema_hash()
    save_schema_hash(schema_hash)
    print(f"Vector DB built successfully. Schema hash: {schema_hash[:16]}...")


def _ensure_bm25_index():
    """Ensure BM25 index is loaded. Build from vector DB if needed."""
    global _bm25_index
    if _bm25_index is not None:
        return

    db_path = Path(config.VECTOR_DB_PATH)
    if not db_path.exists():
        return

    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection(config.VECTOR_DB_COLLECTION_NAME)
    except (ValueError, NotFoundError):
        return

    all_data = collection.get(include=["documents", "metadatas"])
    if not all_data or not all_data["ids"]:
        return

    _bm25_index = BM25Index()
    _bm25_index.build(
        docs=all_data["documents"],
        doc_ids=all_data["ids"],
        doc_metadata=all_data["metadatas"]
    )
    print(f"[BM25] Index loaded with {len(all_data['ids'])} documents")


def get_vector_db() -> chromadb.Collection:
    """Get or initialize the vector DB collection."""
    db_path = Path(config.VECTOR_DB_PATH)
    if not db_path.exists():
        raise RuntimeError(
            f"Vector DB not found at {config.VECTOR_DB_PATH}. "
            "Please build it first by calling build_vector_db()."
        )

    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection(config.VECTOR_DB_COLLECTION_NAME)
    except ValueError:
        raise RuntimeError(
            f"Collection '{config.VECTOR_DB_COLLECTION_NAME}' not found. "
            "Please rebuild the vector DB."
        )

    _ensure_bm25_index()
    return collection


def _reciprocal_rank_fusion(
    vector_results: List[dict],
    bm25_results: List[dict],
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
    k: int = 60
) -> List[dict]:
    """
    Merge vector and BM25 results using Reciprocal Rank Fusion (RRF).
    
    RRF score for a document d = sum_over_rankings(1 / (k + rank(d)))
    weighted by the source weight.
    """
    doc_scores: Dict[str, float] = defaultdict(float)
    doc_data: Dict[str, dict] = {}

    for rank, result in enumerate(vector_results):
        doc_id = result.get("doc_id", result.get("metadata", {}).get("attribute", "") + ":" + result.get("metadata", {}).get("entity_type", ""))
        rrf_score = vector_weight * (1.0 / (k + rank + 1))
        doc_scores[doc_id] += rrf_score
        if doc_id not in doc_data:
            doc_data[doc_id] = result

    for rank, result in enumerate(bm25_results):
        doc_id = result.get("doc_id", result.get("metadata", {}).get("attribute", "") + ":" + result.get("metadata", {}).get("entity_type", ""))
        rrf_score = bm25_weight * (1.0 / (k + rank + 1))
        doc_scores[doc_id] += rrf_score
        if doc_id not in doc_data:
            doc_data[doc_id] = result

    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

    merged = []
    for doc_id, score in sorted_docs:
        result = doc_data[doc_id].copy()
        result["hybrid_score"] = score
        merged.append(result)

    return merged


def _entity_aware_rerank(
    results: List[dict],
    query: str,
    boost_factor: float = 1.5
) -> List[dict]:
    """
    Rerank results by boosting chunks that belong to detected entity types
    mentioned in the query.
    """
    from query_classifier import extract_entity_type, ENTITY_ALIASES

    detected_entity = extract_entity_type(query)
    if not detected_entity:
        return results

    for result in results:
        entity_type = result.get("metadata", {}).get("entity_type", "")
        if entity_type == detected_entity:
            result["hybrid_score"] = result.get("hybrid_score", 0.0) * boost_factor

    results.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
    return results


def retrieve_schema_chunks(query_text: str, top_k: int = None) -> List[dict]:
    """
    Retrieve top-k most relevant schema chunks using hybrid search.
    
    Pipeline:
    1. Vector search (semantic similarity) -> TOP_K_VECTOR candidates
    2. BM25 search (keyword matching) -> TOP_K_BM25 candidates
    3. Reciprocal Rank Fusion to merge both lists
    4. Entity-aware reranking to boost relevant entity types
    5. Return top TOP_K_RETRIEVAL chunks
    """
    if top_k is None:
        top_k = config.TOP_K_RETRIEVAL

    t_start = time.perf_counter()

    # Step 1: Vector search
    t_embed_start = time.perf_counter()
    query_embedding = embeddings_client.get_embeddings([query_text])[0]
    t_embed_ms = (time.perf_counter() - t_embed_start) * 1000
    logger.info("embedding_api_ms=%.2f", t_embed_ms)

    collection = get_vector_db()
    vector_top_k = getattr(config, 'TOP_K_VECTOR', 30)
    vector_results_raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=vector_top_k
    )

    vector_results = []
    if vector_results_raw["ids"] and len(vector_results_raw["ids"][0]) > 0:
        for i in range(len(vector_results_raw["ids"][0])):
            chunk = {
                "chunk_text": vector_results_raw["documents"][0][i],
                "metadata": vector_results_raw["metadatas"][0][i],
                "distance": vector_results_raw["distances"][0][i] if "distances" in vector_results_raw else None,
                "doc_id": vector_results_raw["ids"][0][i],
            }
            vector_results.append(chunk)

    # Step 2: BM25 search
    _ensure_bm25_index()
    bm25_results = []
    if _bm25_index is not None:
        bm25_top_k = getattr(config, 'TOP_K_BM25', 30)
        bm25_results = _bm25_index.search(query_text, top_k=bm25_top_k)

    # Step 3: Reciprocal Rank Fusion
    vector_weight = getattr(config, 'RERANK_WEIGHT_VECTOR', 0.6)
    bm25_weight = getattr(config, 'RERANK_WEIGHT_BM25', 0.4)
    merged = _reciprocal_rank_fusion(
        vector_results, bm25_results,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight
    )

    # Step 4: Entity-aware reranking
    reranked = _entity_aware_rerank(merged, query_text)

    # Step 5: Return top_k results
    final_results = reranked[:top_k]

    t_total_ms = (time.perf_counter() - t_start) * 1000
    logger.info("hybrid_retrieval_ms=%.2f vector=%d bm25=%d merged=%d final=%d",
                t_total_ms, len(vector_results), len(bm25_results), len(merged), len(final_results))

    return final_results
