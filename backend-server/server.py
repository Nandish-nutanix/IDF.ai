"""
FastAPI server for NL Query to Insights Query proto conversion.

LLM-First pipeline:
1. Check cache
2. Hybrid retrieval (vector + BM25 with RRF reranking)
3. Single LLM call (classifies intent + generates proto)
4. Code generation
"""

import hashlib
import logging
import os
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import config
import model_check
import proto_response_generator
import python_code_generator
import schema_chunker
import vectordb

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base"))
from kb_service import get_kb_service

logger = logging.getLogger(__name__)


class QueryCache:
    """Simple LRU cache for proto generation results."""

    def __init__(self, max_size: int = 200):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size

    def _key(self, query: str) -> str:
        normalized = query.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, query: str):
        key = self._key(query)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, query: str, result: dict):
        key = self._key(query)
        self._cache[key] = result
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


_query_cache = QueryCache()


class QueryRequest(BaseModel):
    query: str
    schema_mode: str = "real"
    generate_python: bool = False
    generate_go: bool = False


class QueryResponse(BaseModel):
    query_proto: str
    selected_tuples: List[Tuple[str, str]]
    python_code: Optional[str] = None
    go_code: Optional[str] = None
    query_type: Optional[str] = None
    api_method: Optional[str] = None
    used_template: bool = False
    confidence: float = 0.0
    latency_ms: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    print("=" * 60)
    print("IDF AI Query Server (LLM-First) - Starting...")
    print(f"  LLM API: {config.API_BASE_URL}")
    print(f"  Chat Model: {config.CHAT_MODEL}")
    print(f"  Embed Model: {config.EMBEDDINGS_MODEL}")
    print(f"  Schema file: {config.ENTITY_ATTRIBUTE_CONFIG_FILE}")
    print("=" * 60)

    if config.USE_FINETUNED_MODEL:
        ready, issues = model_check.verify_models()
        if not ready:
            for issue in issues:
                print(f"  WARNING: {issue}")
        else:
            print("  Fine-tuned MLX model server OK.")
    elif model_check.wait_for_ollama(max_wait_seconds=30):
        ready, issues = model_check.verify_models(auto_pull=True)
        if not ready:
            for issue in issues:
                print(f"  WARNING: {issue}")
    else:
        print("  WARNING: Ollama not reachable.")

    if config.USE_FINETUNED_MODEL:
        print("  Skipping Vector DB (fine-tuned model doesn't need RAG).")
    elif vectordb.is_vector_db_up_to_date():
        print("Vector DB exists and is up-to-date. Loading...")
        try:
            vectordb.get_vector_db()
            print("Vector DB loaded successfully.")
        except Exception as e:
            print(f"Error loading vector DB: {e}")
            vectordb.build_vector_db()
    else:
        print("Vector DB missing or stale. Building...")
        vectordb.build_vector_db()

    print("=" * 60)
    print("Server ready! Listening on http://{}:{}".format(config.SERVER_HOST, config.SERVER_PORT))
    print("=" * 60)
    yield
    print("Shutting down server...")


app = FastAPI(
    title="NL Query to Insights Query Proto",
    description="LLM-First: Convert natural language queries to IDF proto format",
    lifespan=lifespan
)


@app.get("/")
def root():
    """Health check endpoint."""
    if config.USE_FINETUNED_MODEL:
        backend_ok = model_check.check_mlx_server_health()
    else:
        backend_ok = model_check.check_ollama_health()
    return {
        "status": "ok",
        "service": "nl-query-server",
        "architecture": "llm-first-finetuned" if config.USE_FINETUNED_MODEL else "llm-first",
        "models": {
            "chat": config.CHAT_MODEL,
            "embeddings": config.EMBEDDINGS_MODEL,
        },
        "backend_healthy": backend_ok,
    }


@app.post("/query", response_model=QueryResponse)
def process_query(request: QueryRequest):
    """
    Process a natural language query and return Query proto.

    LLM-First pipeline:
    1. Check cache
    2. Retrieve schema context (hybrid search)
    3. Single LLM call (classify + generate proto)
    4. Generate Python code if requested
    """
    try:
        t0 = time.perf_counter()
        logger.info("request query=%r", request.query[:200])

        # Step 1: Check cache
        cached = _query_cache.get(request.query)
        if cached and not request.generate_python:
            cached_response = dict(cached)
            cached_response["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            return QueryResponse(**cached_response)

        # Step 2: Retrieve schema context (skip for fine-tuned model)
        schema_chunks = []
        selected_tuples: List[Tuple[str, str]] = []

        if not config.USE_FINETUNED_MODEL:
            schema_chunks = vectordb.retrieve_schema_chunks(request.query)
            if not schema_chunks:
                raise HTTPException(status_code=500, detail="No schema chunks retrieved.")

            seen = set()
            for chunk in schema_chunks:
                metadata = chunk.get('metadata', {})
                entity_type = metadata.get('entity_type', '')
                attribute = metadata.get('attribute', metadata.get('metric_name', ''))
                if entity_type and attribute:
                    pair = (entity_type, attribute)
                    if pair not in seen:
                        seen.add(pair)
                        selected_tuples.append(pair)

        # Step 3: Single LLM call - classify intent + generate proto
        try:
            query_proto, result_entity_types, api_method = proto_response_generator.generate_proto(
                query=request.query,
                schema_chunks=schema_chunks,
            )
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Proto generation error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

        # Step 4: Generate Python code if requested
        python_code = None
        if request.generate_python:
            try:
                python_code = python_code_generator.generate_python_code(
                    query_proto=query_proto,
                    natural_language_query=request.query,
                    api_method=api_method,
                )
            except Exception as e:
                logger.warning("Code generation failed: %s", str(e))
                python_code = f"# Code generation failed: {str(e)}"

        t_total_ms = (time.perf_counter() - t0) * 1000
        logger.info("total_ms=%.2f api=%s", t_total_ms, api_method)

        # Cache result
        _query_cache.put(request.query, {
            "query_proto": query_proto,
            "selected_tuples": selected_tuples,
            "python_code": None,
            "go_code": None,
            "query_type": api_method,
            "api_method": api_method,
            "used_template": False,
            "confidence": 1.0,
            "latency_ms": 0.0,
        })

        return QueryResponse(
            query_proto=query_proto,
            selected_tuples=selected_tuples,
            python_code=python_code,
            go_code=None,
            query_type=api_method,
            api_method=api_method,
            used_template=False,
            confidence=1.0,
            latency_ms=round(t_total_ms, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    idf_ip: str = "127.0.0.1"
    idf_port: str = "2027"
    timeout: int = 30


class ExecuteResponse(BaseModel):
    success: bool
    output: str
    error: str
    execution_time_ms: float
    language: str


@app.post("/execute", response_model=ExecuteResponse)
def execute_code(request: ExecuteRequest):
    """Execute generated query code against a live IDF instance."""
    import query_executor

    if request.timeout > 60:
        raise HTTPException(status_code=400, detail="Timeout cannot exceed 60 seconds")

    result = query_executor.execute_query(
        code=request.code,
        language=request.language,
        idf_ip=request.idf_ip,
        idf_port=request.idf_port,
        timeout=request.timeout,
    )

    return ExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        execution_time_ms=result.execution_time_ms,
        language=result.language,
    )


@app.get("/schema/entities")
def list_entity_types():
    """List all entity types in the schema."""
    try:
        chunks = schema_chunker.load_schema_chunks()
        entity_types = sorted(set(
            c.entity_type_name for c in chunks
            if c.metric_name != "_entity_summary_"
        ))
        return {"entity_types": entity_types, "total": len(entity_types)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/entities/{entity_type}/attributes")
def list_entity_attributes(entity_type: str):
    """List all indexed attributes for a given entity type."""
    try:
        chunks = schema_chunker.load_schema_chunks()
        attributes = [
            {"name": c.metric_name, "data_type": c.data_type}
            for c in chunks
            if c.entity_type_name == entity_type and c.metric_name != "_entity_summary_"
        ]
        if not attributes:
            raise HTTPException(status_code=404, detail=f"Entity type '{entity_type}' not found")
        return {"entity_type": entity_type, "attributes": attributes, "total": len(attributes)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    category: Optional[str] = None


class KBSummarizeRequest(BaseModel):
    query: str


class KBRelatedFeaturesRequest(BaseModel):
    query: str
    api_method: Optional[str] = None


@app.post("/kb/search")
def kb_search(request: KBSearchRequest):
    """Search the IDF knowledge base."""
    kb = get_kb_service()
    results = kb.search(request.query, top_k=request.top_k, category=request.category)
    return {"results": results, "total": len(results), "query": request.query}


@app.post("/kb/summarize")
def kb_summarize(request: KBSummarizeRequest):
    """Summarize/answer a question about IDF using the knowledge base."""
    kb = get_kb_service()
    answer = kb.summarize(request.query)
    return {"answer": answer, "query": request.query}


@app.post("/kb/deep-search")
def kb_deep_search(request: KBSearchRequest):
    """Deep Search: multi-stage retrieval + synthesis using Phi-4 + nomic-embed."""
    kb = get_kb_service()
    result = kb.deep_search(request.query)
    return result


@app.post("/kb/related-features")
def kb_related_features(request: KBRelatedFeaturesRequest):
    """Get related IDF features for a query (used by 'Related Features' button)."""
    kb = get_kb_service()
    features = kb.get_related_features(request.query, request.api_method)
    return {"features": features, "query": request.query}


@app.get("/kb/documents")
def kb_list_documents(category: Optional[str] = None):
    """List all documents in the knowledge base."""
    kb = get_kb_service()
    docs = kb.get_all_documents(category=category)
    return {"documents": docs, "total": len(docs)}


@app.get("/kb/categories")
def kb_categories():
    """Get knowledge base categories."""
    kb = get_kb_service()
    categories = kb.get_categories()
    return {"categories": categories}


@app.get("/kb/documents/{doc_id}")
def kb_get_document(doc_id: str):
    """Get full content of a specific document."""
    kb = get_kb_service()
    doc = kb.get_document_content(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/kb/documents/{doc_id}/download")
def kb_download_document(doc_id: str):
    """Download the original document file."""
    from fastapi.responses import FileResponse
    kb = get_kb_service()
    doc = kb.get_document_content(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    filename = doc["filename"]
    raw_docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base", "raw_docs")

    for root, dirs, files in os.walk(raw_docs_dir):
        if filename in files:
            filepath = os.path.join(root, filename)
            return FileResponse(filepath, filename=filename, media_type="application/octet-stream")

    raise HTTPException(status_code=404, detail="Original file not found")


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT)
