"""
IDF Query Generator Backend API.
Proxies UI requests to the backend-server (query_cli design: POST /query with query + schema_mode),
then maps the response to the format the UI expects.
"""

import os
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from typing import List, Dict, Optional, Tuple
import json

app = FastAPI(title="IDF Query Generator API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Backend-server URL (same as query_cli: SERVER_URL / QUERY_SERVER_URL)
QUERY_SERVER_URL = os.getenv("QUERY_SERVER_URL", os.getenv("SERVER_URL", "http://localhost:8000")).rstrip("/")

# Pydantic models (UI contract)
class QueryRequest(BaseModel):
    query: str
    schema_mode: Optional[str] = "real"  # "real" | "imaginary", same as query_cli
    generate_python: Optional[bool] = False  # Generate Python cpdb query code
    generate_go: Optional[bool] = False  # Generate Go cpdb query code

class FeedbackRequest(BaseModel):
    query: str
    generated_output: str
    corrected_output: str
    feedback_type: str  # "entity_type", "attribute", "operator", "full_query"

class QueryResponse(BaseModel):
    success: bool
    entity_type: Optional[str] = None
    intent: Optional[str] = None
    attributes: Optional[List[str]] = None
    operators: Optional[List[str]] = None
    protobuf_json: Optional[Dict] = None
    python_code: Optional[str] = None
    cpp_code: Optional[str] = None
    java_code: Optional[str] = None
    go_code: Optional[str] = None
    error: Optional[str] = None
    confidence_scores: Optional[Dict] = None
    rpc: Optional[str] = None
    query_type: Optional[str] = None
    api_method: Optional[str] = None
    used_template: bool = False
    latency_ms: float = 0.0


# ============================================================================
# BACKEND-SERVER PROXY (query_cli request design)
# ============================================================================

def call_query_server(query: str, schema_mode: str = "real", generate_python: bool = False, generate_go: bool = False) -> Dict:
    """
    Forward request to backend-server using query_cli design.
    POST {QUERY_SERVER_URL}/query with {"query": query, "schema_mode": schema_mode, "generate_python": generate_python, "generate_go": generate_go}.
    Returns dict with query_proto, selected_tuples, python_code (optional), go_code (optional), or error.
    """
    endpoint = f"{QUERY_SERVER_URL}/query"
    payload = {"query": query, "schema_mode": schema_mode, "generate_python": generate_python, "generate_go": generate_go}
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,  # Increased timeout for Python code generation
    )
    if not response.ok:
        try:
            err = response.json()
            detail = err.get("detail", err.get("error", response.text))
        except Exception:
            detail = response.text or response.reason
        return {"error": f"Query server HTTP {response.status_code}: {detail}"}
    return response.json()


def map_query_response_to_ui(backend: Dict) -> QueryResponse:
    """
    Map backend-server response (query_proto, selected_tuples, python_code) to UI QueryResponse.
    Language section includes python_code if available; cpp/java/go are left empty.
    Any "error" in backend is from the query server and is passed through unchanged.
    """
    if "error" in backend:
        return QueryResponse(success=False, error=backend["error"])

    query_proto = backend.get("query_proto") or ""
    selected_tuples: List[Tuple[str, str]] = backend.get("selected_tuples") or []
    python_code = backend.get("python_code")  # May be None if not requested
    go_code = backend.get("go_code")  # May be None if not requested

    # UI expects protobuf_json as a JSON-serialisable object; backend gives proto text
    protobuf_json: Dict = {"query_proto": query_proto}

    # Entity type from query_proto (e.g. query { entity_list { entity_type_name: "vm" } })
    entity_type: Optional[str] = None
    entity_type_matches = re.findall(r'entity_type_name\s*:\s*"([^"]+)"', query_proto or "")
    if entity_type_matches:
        entity_type = entity_type_matches[0]
    # Attributes: only those belonging to the selected entity type
    attributes: List[str] = [t[1] for t in selected_tuples if t[0] == entity_type] if entity_type else []

    query_type = backend.get("query_type")
    api_method = backend.get("api_method")
    used_template = backend.get("used_template", False)
    latency_ms = backend.get("latency_ms", 0.0)
    confidence = backend.get("confidence", 0.0)

    return QueryResponse(
        success=True,
        entity_type=entity_type,
        intent=query_type,
        attributes=attributes if attributes else None,
        operators=None,
        protobuf_json=protobuf_json,
        python_code=python_code,
        cpp_code=None,
        java_code=None,
        go_code=go_code,
        error=None,
        confidence_scores={"classification": confidence} if confidence else None,
        rpc=None,
        query_type=query_type,
        api_method=api_method,
        used_template=used_template,
        latency_ms=latency_ms,
    )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "IDF Query Generator API",
        "version": "1.0.0",
        "endpoints": {
            "/generate": "Generate IDF query from natural language",
            "/feedback": "Submit feedback for learning",
            "/health": "Health check"
        }
    }

@app.get("/health")
async def health():
    """Health check: backend API and query server reachability."""
    query_server_status = "unknown"
    try:
        r = requests.get(f"{QUERY_SERVER_URL}/", timeout=5)
        query_server_status = "healthy" if r.ok else "unhealthy"
    except Exception:
        query_server_status = "unreachable"
    return {
        "status": "healthy",
        "query_server": query_server_status,
        "query_server_url": QUERY_SERVER_URL,
    }


@app.post("/generate", response_model=QueryResponse)
async def generate_query(request: QueryRequest):
    """
    Generate IDF query from natural language.
    Proxies to backend-server (query_cli design): POST /query with query + schema_mode + generate_python + generate_go,
    then maps response to UI format. Python code is returned if generate_python=True, Go code if generate_go=True.
    """
    try:
        schema_mode = (request.schema_mode or "real").strip().lower()
        if schema_mode not in ("real", "imaginary"):
            schema_mode = "real"
        generate_python = request.generate_python or False
        generate_go = request.generate_go or False
        backend = call_query_server(request.query, schema_mode=schema_mode, generate_python=generate_python, generate_go=generate_go)
        return map_query_response_to_ui(backend)
    except requests.RequestException as e:
        return QueryResponse(success=False, error=f"Query server request failed: {e}")
    except Exception as e:
        return QueryResponse(success=False, error=f"Internal error: {str(e)}")

@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback to the query server (if it exposes /feedback)."""
    try:
        # Parse JSON strings to dictionaries
        generated_query_dict = {}
        corrected_query_dict = {}
        
        try:
            # Try to parse generated_output as JSON
            if request.generated_output:
                generated_query_dict = json.loads(request.generated_output) if isinstance(request.generated_output, str) else request.generated_output
        except json.JSONDecodeError:
            print(f"[Backend] Warning: Could not parse generated_output as JSON")
            generated_query_dict = {"raw": request.generated_output}
        
        try:
            # Try to parse corrected_output as JSON
            if request.corrected_output:
                corrected_query_dict = json.loads(request.corrected_output) if isinstance(request.corrected_output, str) else request.corrected_output
        except json.JSONDecodeError:
            print(f"[Backend] Warning: Could not parse corrected_output as JSON")
            corrected_query_dict = {"raw": request.corrected_output}
        
        # Call query server feedback endpoint if available (payload shape depends on server)
        response = requests.post(
            f"{QUERY_SERVER_URL}/feedback",
            json={
                "natural_language_query": request.query,
                "generated_query": generated_query_dict,
                "suggested_rpc": os.getenv("FEEDBACK_SUGGESTED_RPC", "GetEntitiesWithMetrics"),
                "feedback_type": "correction",
                "corrected_query": corrected_query_dict,
                "error_message": "User provided correction",
                "notes": f"Feedback type: {request.feedback_type}"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[Backend] Feedback recorded successfully: {result}")
            return {
                "success": True,
                "message": "Feedback recorded successfully."
            }
        else:
            error_detail = response.text
            print(f"[Backend] Feedback failed: {error_detail}")
            return {
                "success": False,
                "error": f"Query server returned status {response.status_code}: {error_detail}"
            }
        
    except Exception as e:
        print(f"[Backend] Feedback exception: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to record feedback: {str(e)}"
        }

class ExecuteRequest(BaseModel):
    code: str
    language: Optional[str] = "python"
    idf_ip: Optional[str] = "127.0.0.1"
    idf_port: Optional[str] = "2027"


@app.post("/execute")
async def execute_query(request: ExecuteRequest):
    """Execute generated code against a live IDF instance (proxied to query server)."""
    try:
        endpoint = f"{QUERY_SERVER_URL}/execute"
        payload = {
            "code": request.code,
            "language": request.language or "python",
            "idf_ip": request.idf_ip or "127.0.0.1",
            "idf_port": request.idf_port or "2027",
        }
        response = requests.post(endpoint, json=payload, timeout=65)
        if response.ok:
            return response.json()
        return {"success": False, "error": f"Execution failed: {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"Execution request failed: {str(e)}"}


class WorkflowExecuteRequest(BaseModel):
    query_proto: str
    api_method: str = "GetEntitiesWithMetrics"
    idf_ip: Optional[str] = ""
    idf_port: Optional[str] = "2027"


@app.post("/execute-proto")
async def execute_proto_workflow(request: WorkflowExecuteRequest):
    """Execute a raw proto query from the workflow playground via idf_cli.py on the CVM."""
    import time
    start = time.time()
    idf_ip = request.idf_ip or "127.0.0.1"
    idf_port = request.idf_port or "2027"
    api = request.api_method

    api_to_rpc_name = {
        "GetEntitiesWithMetrics": "get-entities-with-metrics",
        "UpdateEntity": "update-entity",
        "DeleteEntity": "delete-entity",
        "GetEntities": "get-entities",
        "AttachEntity": "attach-entity",
        "DetachEntity": "detach-entity",
    }
    rpc_name = api_to_rpc_name.get(api)

    proto_text = request.query_proto

    # For RPCs not supported by idf_cli.py, use InsightsInterface Python client
    if not rpc_name:
        # Build Python code that uses InsightsInterface on the CVM
        # proto_text is passed as a variable and parsed with text_format.Merge
        rpc_to_arg_class = {
            "RegisterWatchClient": ("RegisterWatchClientArg", "RegisterWatchClient"),
            "RegisterWatch": ("RegisterWatchArg", "RegisterWatch"),
            "GetFiredWatchList": ("GetFiredWatchListArg", "GetFiredWatchList"),
            "UnregisterWatchClient": ("UnregisterWatchClientArg", "UnregisterWatchClient"),
            "UnregisterWatch": ("UnregisterWatchArg", "UnregisterWatch"),
            "RegisterEntityType": ("_custom_register_entity_", "_custom_"),
            "SyncUpdateEntity": ("SyncUpdateEntityArg", "SyncUpdateEntity"),
        }

        rpc_info = rpc_to_arg_class.get(api)
        if not rpc_info:
            elapsed = (time.time() - start) * 1000
            return {
                "success": False,
                "error": f"Unsupported RPC: {api}",
                "latency_ms": elapsed,
            }

        arg_class, method_name = rpc_info
        # Use base64 encoding to safely pass proto_text to the remote script
        import base64
        proto_b64 = base64.b64encode(proto_text.encode()).decode()

        if arg_class == "_custom_register_entity_":
            # Custom handler: parse proto to extract entity_type_name, type_info, and metric_type_list
            # Then call RegisterEntityTypes and RegisterMetricTypes separately
            code = f"""import sys, os, base64, re
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib64/python3.9/site-packages')
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib/python3.9/site-packages')
os.environ['GLOG_minloglevel'] = '3'
import logging
logging.disable(logging.CRITICAL)
from insights_interface.insights_interface import InsightsInterface
from insights_interface import insights_interface_pb2 as pb2
from google.protobuf import text_format

proto_text = base64.b64decode('{proto_b64}').decode()
ifc = InsightsInterface(ip='127.0.0.1', port={idf_port})

# Extract entity_type_name from proto
name_match = re.search(r'entity_type_name:\\s*"([^"]+)"', proto_text)
entity_type_name = name_match.group(1) if name_match else "unknown"

# Extract metric names from metric_type_list blocks
metric_names = re.findall(r'metric_name:\\s*"([^"]+)"', proto_text)

# Build RegisterEntityTypes arg (just entity type + type_info)
et_arg = pb2.RegisterEntityTypesArg()
eti = et_arg.entity_type_info_list.add()
eti.entity_type_name = entity_type_name
eti.type_info.suppress_replication = 'suppress_replication: true' not in proto_text
eti.type_info.track_attribute_changes = True

try:
    ret = ifc.RegisterEntityTypes(et_arg)
    print(f"RegisterEntityTypes: OK ({{ret.rpc_execution_time_usecs}}us)")
except Exception as e:
    err = str(e)
    if 'kDuplicate' in err:
        print(f"RegisterEntityTypes: Entity type already exists (OK)")
    else:
        print(f"RegisterEntityTypes Error: {{err}}")
        sys.exit(1)

# Register metrics/attributes
if metric_names:
    mt_arg = pb2.RegisterMetricTypesArg()
    for mn in metric_names:
        mt = mt_arg.metric_type_list.add()
        mt.is_attribute = True
        mt.metric_name = mn
        mt.entity_type_name = entity_type_name
    try:
        ret = ifc.RegisterMetricTypes(mt_arg)
        print(f"RegisterMetricTypes: OK — registered {{len(metric_names)}} attributes: {{', '.join(metric_names)}}")
    except Exception as e:
        err = str(e)
        if 'kDuplicate' in err:
            print(f"RegisterMetricTypes: Attributes already registered (OK)")
        else:
            print(f"RegisterMetricTypes Error: {{err}}")

print(f"\\nEntity type '{{entity_type_name}}' ready with suppress_replication=False")
"""
        else:
            code = f"""import sys, os, base64
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib64/python3.9/site-packages')
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib/python3.9/site-packages')
os.environ['GLOG_minloglevel'] = '3'
import logging
logging.disable(logging.CRITICAL)
from insights_interface.insights_interface import InsightsInterface
from insights_interface import insights_interface_pb2 as pb2
from google.protobuf import text_format

proto_text = base64.b64decode('{proto_b64}').decode()
ifc = InsightsInterface(ip='127.0.0.1', port={idf_port})
arg = pb2.{arg_class}()
try:
    text_format.Merge(proto_text, arg)
except Exception as parse_err:
    print(f"Proto parse error: {{parse_err}}")
    sys.exit(1)
try:
    ret = ifc.{method_name}(arg)
    output = str(ret)
    if output.strip():
        print(output)
    else:
        print("{method_name} completed successfully.")
except Exception as e:
    err_msg = str(e)
    print(f"RPC Error: {{err_msg}}")
"""
        try:
            endpoint = f"{QUERY_SERVER_URL}/execute"
            payload = {
                "code": code,
                "language": "python",
                "idf_ip": idf_ip,
                "idf_port": idf_port,
            }
            response = requests.post(endpoint, json=payload, timeout=65)
            elapsed = (time.time() - start) * 1000
            if response.ok:
                data = response.json()
                data["latency_ms"] = elapsed
                return data
            return {"success": False, "error": f"Execution failed: {response.text}", "latency_ms": elapsed}
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return {"success": False, "error": str(e), "latency_ms": elapsed}

    # Use idf_cli.py execute-from-file which is available on all CVMs
    # Include UpdateEntityArg marker so query_executor treats this as direct execution
    code = f"""# Direct execution via idf_cli.py (UpdateEntityArg marker for executor)
import subprocess, tempfile, os
proto_text = '''{proto_text}'''
with tempfile.NamedTemporaryFile(mode='w', suffix='.proto', delete=False) as f:
    f.write(proto_text)
    proto_file = f.name
try:
    result = subprocess.run(
        ['/usr/local/nutanix/bin/idf_cli.py', '--advanced', '--port', '{idf_port}',
         'execute-from-file', '{rpc_name}', proto_file],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(result.stderr or result.stdout)
finally:
    os.unlink(proto_file)
"""

    try:
        endpoint = f"{QUERY_SERVER_URL}/execute"
        payload = {
            "code": code,
            "language": "python",
            "idf_ip": idf_ip,
            "idf_port": idf_port,
        }
        response = requests.post(endpoint, json=payload, timeout=65)
        elapsed = (time.time() - start) * 1000
        if response.ok:
            data = response.json()
            data["latency_ms"] = elapsed
            return data
        return {"success": False, "error": f"Execution failed: {response.text}", "latency_ms": elapsed}
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "error": f"Execution request failed: {str(e)}", "latency_ms": elapsed}


@app.get("/entity-types")
async def get_entity_types():
    """Get all entity types from the schema via query server."""
    try:
        response = requests.get(f"{QUERY_SERVER_URL}/schema/entities", timeout=10)
        if response.ok:
            return response.json()
    except Exception:
        pass
    return {"entity_types": [], "total": 0}


# ============================================================================
# KNOWLEDGE BASE PROXY ENDPOINTS
# ============================================================================

class KBSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    category: Optional[str] = None


class KBSummarizeRequest(BaseModel):
    query: str


class KBRelatedFeaturesRequest(BaseModel):
    query: str
    api_method: Optional[str] = None


@app.post("/kb/search")
async def kb_search(request: KBSearchRequest):
    """Search the IDF knowledge base."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/search",
            json={"query": request.query, "top_k": request.top_k or 5, "category": request.category},
            timeout=30,
        )
        if resp.ok:
            return resp.json()
        return {"results": [], "error": resp.text}
    except Exception as e:
        return {"results": [], "error": str(e)}


@app.post("/kb/summarize")
async def kb_summarize(request: KBSummarizeRequest):
    """Summarize/answer a question about IDF."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/summarize",
            json={"query": request.query},
            timeout=90,
        )
        if resp.ok:
            return resp.json()
        return {"answer": "", "error": resp.text}
    except Exception as e:
        return {"answer": "", "error": str(e)}


@app.post("/kb/deep-search")
async def kb_deep_search(request: KBSearchRequest):
    """Deep Search: multi-stage pipeline for comprehensive answers."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/deep-search",
            json={"query": request.query},
            timeout=180,
        )
        if resp.ok:
            return resp.json()
        return {"answer": "", "error": resp.text}
    except Exception as e:
        return {"answer": "", "error": str(e)}


@app.post("/kb/related-features")
async def kb_related_features(request: KBRelatedFeaturesRequest):
    """Get related IDF features for a query."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/related-features",
            json={"query": request.query, "api_method": request.api_method},
            timeout=15,
        )
        if resp.ok:
            return resp.json()
        return {"features": [], "error": resp.text}
    except Exception as e:
        return {"features": [], "error": str(e)}


@app.get("/kb/documents")
async def kb_documents(category: Optional[str] = None):
    """List all knowledge base documents."""
    try:
        params = {}
        if category:
            params["category"] = category
        resp = requests.get(f"{QUERY_SERVER_URL}/kb/documents", params=params, timeout=10)
        if resp.ok:
            return resp.json()
        return {"documents": [], "error": resp.text}
    except Exception as e:
        return {"documents": [], "error": str(e)}


@app.get("/kb/categories")
async def kb_categories():
    """Get knowledge base categories."""
    try:
        resp = requests.get(f"{QUERY_SERVER_URL}/kb/categories", timeout=10)
        if resp.ok:
            return resp.json()
        return {"categories": []}
    except Exception as e:
        return {"categories": [], "error": str(e)}


@app.get("/kb/documents/{doc_id}")
async def kb_get_document(doc_id: str):
    """Get full content of a specific document."""
    try:
        resp = requests.get(f"{QUERY_SERVER_URL}/kb/documents/{doc_id}", timeout=30)
        if resp.ok:
            return resp.json()
        return {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}


@app.get("/kb/documents/{doc_id}/download")
async def kb_download_document(doc_id: str):
    """Download the original document file."""
    from starlette.responses import StreamingResponse
    import io
    try:
        resp = requests.get(f"{QUERY_SERVER_URL}/kb/documents/{doc_id}/download", timeout=30, stream=True)
        if resp.ok:
            content_disp = resp.headers.get("content-disposition", "")
            return StreamingResponse(
                io.BytesIO(resp.content),
                media_type="application/octet-stream",
                headers={"Content-Disposition": content_disp} if content_disp else {}
            )
        return {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    _port = int(os.getenv("UI_BACKEND_PORT", "3001"))
    print("Starting IDF Query Generator Backend...")
    print(f"Backend API: http://0.0.0.0:{_port}")
    print(f"Query server: {QUERY_SERVER_URL}")
    uvicorn.run(app, host="0.0.0.0", port=_port)
