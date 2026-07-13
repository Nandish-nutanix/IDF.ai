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

# ============================================================================
# CVM SSH PASSWORD RESOLUTION (auto-detect PC vs PE in parallel)
# ============================================================================
# PC/CVM clusters typically use "nutanix/4u"; some PE clusters use "RDMCluster.123".
# We try all candidates concurrently and cache whichever connects first, per IP.
import subprocess as _subprocess
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

try:
    import query_executor_lite as _qexec
except Exception:  # pragma: no cover - import is environment dependent
    _qexec = None

CANDIDATE_PASSWORDS = [
    p.strip() for p in os.getenv(
        "CVM_SSH_PASSWORDS",
        # legacy single-password env still honored as the first candidate
        os.getenv("CVM_SSH_PASSWORD", "nutanix/4u") + ",RDMCluster.123",
    ).split(",") if p.strip()
]
# De-dupe while preserving order
_seen_pw = set()
CANDIDATE_PASSWORDS = [p for p in CANDIDATE_PASSWORDS if not (p in _seen_pw or _seen_pw.add(p))]

_cvm_pw_cache: Dict[str, Dict] = {}  # ip -> {"password": str, "ts": float}
_CVM_PW_TTL = 600  # seconds


def _try_ssh_password(cvm_ip: str, password: str, connect_timeout: int = 8) -> Optional[str]:
    """Return `password` if it authenticates to nutanix@cvm_ip, else None."""
    try:
        r = _subprocess.run(
            [
                "sshpass", "-p", password,
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "PreferredAuthentications=password",
                "-o", "PubkeyAuthentication=no",
                "-o", "NumberOfPasswordPrompts=1",
                "-o", f"ConnectTimeout={connect_timeout}",
                f"nutanix@{cvm_ip}", "echo OK",
            ],
            capture_output=True, text=True, timeout=connect_timeout + 6,
        )
        if r.returncode == 0 and "OK" in r.stdout:
            return password
    except Exception:
        pass
    return None


def resolve_cvm_ssh(cvm_ip: str, force: bool = False) -> Optional[str]:
    """Find a working SSH password for cvm_ip by trying all candidates in parallel.

    Returns the working password (cached ~10 min per IP), or None if the host
    is unreachable / no candidate authenticates.
    """
    cvm_ip = (cvm_ip or "").strip()
    if not cvm_ip:
        return None

    cached = _cvm_pw_cache.get(cvm_ip)
    if cached and not force and (_time.time() - cached["ts"]) < _CVM_PW_TTL:
        return cached["password"]

    found: Optional[str] = None
    with ThreadPoolExecutor(max_workers=max(2, len(CANDIDATE_PASSWORDS))) as ex:
        futures = {ex.submit(_try_ssh_password, cvm_ip, pw): pw for pw in CANDIDATE_PASSWORDS}
        for fut in _as_completed(futures):
            res = fut.result()
            if res:
                found = res
                break

    if found:
        _cvm_pw_cache[cvm_ip] = {"password": found, "ts": _time.time()}
    return found


def cvm_password_for(cvm_ip: str) -> str:
    """Resolved password for cvm_ip, falling back to the first candidate if
    resolution fails (so existing flows still attempt a connection)."""
    return resolve_cvm_ssh(cvm_ip) or (CANDIDATE_PASSWORDS[0] if CANDIDATE_PASSWORDS else "nutanix/4u")


def _looks_like_ip(value: str) -> bool:
    """Basic IPv4 / hostname sanity check."""
    value = (value or "").strip()
    if not value:
        return False
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", value)
    if m:
        return all(0 <= int(o) <= 255 for o in m.groups())
    # allow hostnames too
    return bool(re.match(r"^[a-zA-Z0-9_.-]+$", value))


@app.get("/cvm/validate")
async def cvm_validate(cvm_ip: str = "", refresh: int = 0):
    """Check whether a CVM IP is reachable over SSH and which credential works.

    Used by the header to show a live reachability badge. Tries PC/PE passwords
    in parallel via resolve_cvm_ssh.
    """
    cvm_ip = (cvm_ip or "").strip()
    if not cvm_ip:
        return {"reachable": False, "error": "No IP provided."}
    if not _looks_like_ip(cvm_ip):
        return {"reachable": False, "error": f"'{cvm_ip}' is not a valid IP address."}

    pw = resolve_cvm_ssh(cvm_ip, force=bool(refresh))
    if not pw:
        return {
            "reachable": False,
            "error": f"Could not reach {cvm_ip} over SSH. Check the IP/VPN and re-enter a different IP.",
        }

    # Heuristic env label from the working credential
    cluster_type = "PE" if pw == "RDMCluster.123" else "PC/CVM"
    return {"reachable": True, "cluster_type": cluster_type, "cvm_ip": cvm_ip}

# Pydantic models (UI contract)
class QueryRequest(BaseModel):
    query: str
    schema_mode: Optional[str] = "real"  # "real" | "imaginary", same as query_cli
    generate_python: Optional[bool] = False  # Generate Python cpdb query code
    generate_go: Optional[bool] = False  # Generate Go cpdb query code
    # Optional "bring your own model" override from the Query-page Settings.
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None

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
    llm_backend: Optional[str] = None


# ============================================================================
# BACKEND-SERVER PROXY (query_cli request design)
# ============================================================================

def call_query_server(query: str, schema_mode: str = "real", generate_python: bool = False, generate_go: bool = False, llm_override: Dict = None) -> Dict:
    """
    Forward request to backend-server using query_cli design.
    POST {QUERY_SERVER_URL}/query with {"query": query, "schema_mode": schema_mode, "generate_python": generate_python, "generate_go": generate_go}.
    Returns dict with query_proto, selected_tuples, python_code (optional), go_code (optional), or error.
    """
    endpoint = f"{QUERY_SERVER_URL}/query"
    payload = {"query": query, "schema_mode": schema_mode, "generate_python": generate_python, "generate_go": generate_go}
    if llm_override and llm_override.get("api_key"):
        payload["llm_api_key"] = llm_override.get("api_key")
        payload["llm_base_url"] = llm_override.get("base_url")
        payload["llm_model"] = llm_override.get("model")
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=210,  # Increased timeout for Python code generation
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
        llm_backend=backend.get("llm_backend"),
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


@app.get("/deploy/latest-gbn")
async def deploy_latest_gbn(branch: str = "master", repo: str = "main"):
    """
    Fetch the latest Global Build Number (GBN) from depsdb, server-side.

    Done on the backend (not the browser) to avoid CORS restrictions and to
    use the host machine's corp network/VPN routing. The depsdb path format is
    /get_dep/<repo>/<branch>/HEAD (e.g. /get_dep/main/master/HEAD).
    """
    # Sanitize to avoid path injection
    safe_branch = re.sub(r"[^A-Za-z0-9_.\-/]", "", branch).strip("/") or "master"
    safe_repo = re.sub(r"[^A-Za-z0-9_.\-]", "", repo) or "main"
    url = f"https://depsdb.canaveral-corp.us-west-2.aws/get_dep/{safe_repo}/{safe_branch}/HEAD"

    try:
        resp = requests.get(url, timeout=10, verify=False)
        if not resp.ok:
            return {"success": False, "error": f"depsdb returned HTTP {resp.status_code}", "url": url}

        raw = resp.text.strip()
        gbn = None
        githash = None

        # depsdb returns JSON: {"dep_data": "<yaml string>", ...}.
        # The authoritative GBN lives in the metadata block of that YAML.
        try:
            payload = json.loads(raw)
            dep_data = payload.get("dep_data", raw)
        except Exception:
            dep_data = raw

        # Prefer the metadata block's gbn/githash; fall back to first occurrence.
        meta_match = re.search(r"metadata:\s*([\s\S]*)$", dep_data)
        scope = meta_match.group(1) if meta_match else dep_data
        gbn_match = re.search(r"gbn:\s*'?(\d+)'?", scope)
        if gbn_match:
            gbn = gbn_match.group(1)
        githash_match = re.search(r"githash:\s*'?([0-9a-f]+)'?", scope)
        if githash_match:
            githash = githash_match.group(1)

        if not gbn:
            return {"success": False, "error": "Reached depsdb but could not parse a GBN from the response.", "url": url}

        return {"success": True, "gbn": gbn, "githash": githash, "branch": safe_branch, "repo": safe_repo, "url": url}
    except requests.exceptions.SSLError as e:
        return {"success": False, "error": f"SSL error reaching depsdb: {e}", "url": url}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot reach depsdb. Ensure you are on the corp network/VPN.", "url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}


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
        llm_override = None
        if request.llm_api_key:
            llm_override = {
                "api_key": request.llm_api_key,
                "base_url": request.llm_base_url,
                "model": request.llm_model,
            }
        backend = call_query_server(request.query, schema_mode=schema_mode, generate_python=generate_python, generate_go=generate_go, llm_override=llm_override)
        return map_query_response_to_ui(backend)
    except requests.RequestException as e:
        return QueryResponse(success=False, error=f"Query server request failed: {e}")
    except Exception as e:
        return QueryResponse(success=False, error=f"Internal error: {str(e)}")


class LLMTestRequest(BaseModel):
    llm_api_key: str
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None


@app.post("/llm/test")
async def llm_test(request: LLMTestRequest):
    """Validate a user-supplied LLM endpoint/key (proxied to the query server)."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/llm/test",
            json={
                "llm_api_key": request.llm_api_key,
                "llm_base_url": request.llm_base_url,
                "llm_model": request.llm_model,
            },
            timeout=60,
        )
        if resp.ok:
            return resp.json()
        return {"ok": False, "error": f"query server HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


def run_code_on_cvm(code: str, idf_ip: str, idf_port: str, language: str = "python", timeout: int = 65) -> Dict:
    """Run code directly on the entered CVM via SSH, auto-detecting the PC/PE
    password. This is independent of the query server, so it works for both PC
    and PE clusters wherever app.py can reach the CVM over SSH.

    Returns {success, output, error, latency_ms}.
    """
    start = _time.time()
    ip = (idf_ip or "").strip()
    if not ip or ip in ("127.0.0.1", "localhost"):
        return {"success": False, "error": "Enter a CVM IP in the header to run this against a live cluster.", "latency_ms": 0.0}

    pw = resolve_cvm_ssh(ip)
    if not pw:
        return {
            "success": False,
            "error": f"Cannot reach {ip} over SSH (tried PC and PE credentials). Check the IP / VPN and try again.",
            "latency_ms": (_time.time() - start) * 1000,
        }

    if _qexec is None:
        return {"success": False, "error": "Execution backend unavailable (query_executor_lite not importable).", "latency_ms": 0.0}

    try:
        res = _qexec.execute_query(code, language or "python", ip, str(idf_port or "2027"), timeout=timeout, password=pw)
        return {
            "success": res.success,
            "output": res.output,
            "error": res.error,
            "latency_ms": res.execution_time_ms,
        }
    except Exception as e:
        return {"success": False, "error": f"Execution error: {str(e)}", "latency_ms": (_time.time() - start) * 1000}


@app.post("/execute")
async def execute_query(request: ExecuteRequest):
    """Execute generated code against a live IDF instance (direct SSH to the CVM)."""
    return run_code_on_cvm(request.code, request.idf_ip or "", request.idf_port or "2027", request.language or "python")


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
            "BatchUpdateEntities": ("BatchUpdateEntitiesArg", "BatchUpdateEntities"),
            "BatchDeleteEntities": ("BatchDeleteEntitiesArg", "BatchDeleteEntities"),
            "BatchGetEntitiesWithMetrics": ("BatchGetEntitiesWithMetricsArg", "BatchGetEntitiesWithMetrics"),
            "GetEntityTypes": ("GetEntityTypesArg", "GetEntityTypes"),
            "GetMetricTypes": ("GetMetricTypesArg", "GetMetricTypes"),
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
            # Custom handler: supports multiple entity_type_info_list blocks
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

# Parse entity_type_info_list blocks
blocks = re.split(r'(?=entity_type_info_list\\s*{{)', proto_text)
blocks = [b.strip() for b in blocks if 'entity_type_name' in b]

for block in blocks:
    name_match = re.search(r'entity_type_name:\\s*"([^"]+)"', block)
    if not name_match:
        continue
    entity_type_name = name_match.group(1)
    metric_names = []
    for m in re.finditer(r'metric_type_list\\s*{{[^}}]*metric_name:\\s*"([^"]+)"[^}}]*entity_type_name:\\s*"' + re.escape(entity_type_name) + r'"[^}}]*}}', block, re.DOTALL):
        metric_names.append(m.group(1))
    if not metric_names:
        metric_names = [mn for mn in re.findall(r'metric_name:\\s*"([^"]+)"', block)]

    et_arg = pb2.RegisterEntityTypesArg()
    eti = et_arg.entity_type_info_list.add()
    eti.entity_type_name = entity_type_name
    eti.type_info.suppress_replication = False
    eti.type_info.track_attribute_changes = True

    try:
        ret = ifc.RegisterEntityTypes(et_arg)
        print(f"RegisterEntityTypes({{entity_type_name}}): OK")
    except Exception as e:
        err = str(e)
        if 'kDuplicate' in err:
            print(f"RegisterEntityTypes({{entity_type_name}}): Already exists (OK)")
        else:
            print(f"RegisterEntityTypes({{entity_type_name}}) Error: {{err}}")
            continue

    if metric_names:
        mt_arg = pb2.RegisterMetricTypesArg()
        for mn in metric_names:
            mt = mt_arg.metric_type_list.add()
            mt.is_attribute = True
            mt.metric_name = mn
            mt.entity_type_name = entity_type_name
        try:
            ret = ifc.RegisterMetricTypes(mt_arg)
            print(f"  RegisterMetricTypes({{entity_type_name}}): {{len(metric_names)}} attrs — {{', '.join(metric_names)}}")
        except Exception as e:
            err = str(e)
            if 'kDuplicate' in err:
                print(f"  RegisterMetricTypes({{entity_type_name}}): Already registered (OK)")
            else:
                print(f"  RegisterMetricTypes({{entity_type_name}}) Error: {{err}}")

print(f"\\nDone — registered {{len(blocks)}} entity type(s)")
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
        data = run_code_on_cvm(code, idf_ip, idf_port)
        data["latency_ms"] = (time.time() - start) * 1000
        return data

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

    data = run_code_on_cvm(code, idf_ip, idf_port)
    data["latency_ms"] = (time.time() - start) * 1000
    return data


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
    # Optional "bring your own model" override (used by Deep Search synthesis).
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None


class KBSummarizeRequest(BaseModel):
    query: str
    # Optional "bring your own model" override for summarization.
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None


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


@app.post("/kb/search-live-stats")
async def kb_search_live_stats(request: KBSearchRequest):
    """Search only live cluster stats."""
    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/search-live-stats",
            json={"query": request.query, "top_k": 12},
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
        payload = {"query": request.query}
        if request.llm_api_key:
            payload["llm_api_key"] = request.llm_api_key
            payload["llm_base_url"] = request.llm_base_url
            payload["llm_model"] = request.llm_model
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/summarize",
            json=payload,
            # Longer ceiling when a user model is set (remote/reasoning models are slower).
            timeout=260 if request.llm_api_key else 180,
        )
        if resp.ok:
            return resp.json()
        return {"answer": "", "error": resp.text}
    except Exception as e:
        return {"answer": "", "error": str(e)}


@app.post("/kb/rephrase-query")
async def kb_rephrase_query(request: KBSummarizeRequest):
    """Rewrite the user's question into a clearer, better-phrased question (for Glean)."""
    try:
        payload = {"query": request.query}
        if request.llm_api_key:
            payload["llm_api_key"] = request.llm_api_key
            payload["llm_base_url"] = request.llm_base_url
            payload["llm_model"] = request.llm_model
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/rephrase-query",
            json=payload,
            timeout=260 if request.llm_api_key else 120,
        )
        if resp.ok:
            return resp.json()
        return {"rephrased": request.query, "error": resp.text}
    except Exception as e:
        return {"rephrased": request.query, "error": str(e)}


@app.post("/kb/deep-search")
async def kb_deep_search(request: KBSearchRequest):
    """Deep Search: multi-stage pipeline for comprehensive answers."""
    try:
        payload = {"query": request.query}
        if request.llm_api_key:
            payload["llm_api_key"] = request.llm_api_key
            payload["llm_base_url"] = request.llm_base_url
            payload["llm_model"] = request.llm_model
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/deep-search",
            json=payload,
            # Deep Search runs several LLM calls; give remote models more headroom.
            timeout=600 if request.llm_api_key else 300,
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


class LiveStatsIndexRequest(BaseModel):
    cvm_ip: str
    password: Optional[str] = None
    port: int = 2027


@app.post("/kb/index-live-stats")
async def kb_index_live_stats(request: LiveStatsIndexRequest):
    """Trigger live stats crawl in background. Returns immediately.

    Auto-detects the PC/PE SSH password for the entered CVM so PE clusters work
    without the caller hardcoding a credential.
    """
    cvm_ip = (request.cvm_ip or "").strip()
    if not cvm_ip:
        return {"success": False, "error": "No CVM IP provided."}

    password = request.password or resolve_cvm_ssh(cvm_ip)
    if not password:
        return {"success": False, "error": f"Cannot reach {cvm_ip} over SSH (tried PC and PE credentials). Check the IP / VPN."}

    try:
        resp = requests.post(
            f"{QUERY_SERVER_URL}/kb/index-live-stats",
            json={"cvm_ip": cvm_ip, "password": password, "port": request.port},
            timeout=10,
        )
        if resp.ok:
            return resp.json()
        return {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/kb/live-stats-status")
async def kb_live_stats_status():
    """Check if live stats have been indexed."""
    try:
        resp = requests.get(f"{QUERY_SERVER_URL}/kb/live-stats-status", timeout=5)
        if resp.ok:
            return resp.json()
        return {"indexed": False}
    except Exception:
        return {"indexed": False}


import json as _json_mod
_kb_index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doc_index.json")
_kb_cache = {"docs": None}

def _load_kb_index():
    if _kb_cache["docs"] is None:
        try:
            with open(_kb_index_path, "r") as f:
                data = _json_mod.load(f)
            _kb_cache["docs"] = data.get("documents", [])
        except Exception:
            _kb_cache["docs"] = []
    return _kb_cache["docs"]


@app.get("/kb/documents")
async def kb_documents(category: Optional[str] = None):
    """List all knowledge base documents."""
    docs = _load_kb_index()
    if category:
        docs = [d for d in docs if d.get("category") == category]
    return {"documents": docs}


@app.get("/kb/categories")
async def kb_categories():
    """Get knowledge base categories with document counts."""
    docs = _load_kb_index()
    cat_counts = {}
    for doc in docs:
        cat = doc.get("category", "Uncategorized")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    categories = [{"name": name, "doc_count": count} for name, count in sorted(cat_counts.items())]
    return {"categories": categories}


@app.get("/kb/documents/{doc_id}")
async def kb_get_document(doc_id: str):
    """Get full content of a specific document."""
    _load_kb_index()
    docs = _kb_cache["docs"]
    doc_info = None
    for doc in docs:
        if doc.get("id") == doc_id:
            doc_info = doc
            break
    if not doc_info:
        return {"error": "Document not found"}

    # Load full index to get metadata with chunks
    with open(_kb_index_path, "r") as f:
        full_index = _json_mod.load(f)
    meta = full_index.get("metadata", {}).get(doc_id, {})

    # Try HTML first (richer formatting)
    html_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html_docs")
    html_path = os.path.join(html_dir, f"{doc_id}.html")
    content = ""
    content_type = "text"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        content_type = "html"
    else:
        chunks = meta.get("chunks", [])
        content = "\n\n".join(chunks)

    return {
        "id": doc_id,
        "filename": doc_info.get("filename", ""),
        "category": doc_info.get("category", ""),
        "features": doc_info.get("features", []),
        "content": content,
        "content_type": content_type,
        "num_chunks": len(meta.get("chunks", [])),
    }


@app.get("/kb/documents/{doc_id}/download")
async def kb_download_document(doc_id: str):
    """Download the original document file."""
    from starlette.responses import FileResponse
    docs = _load_kb_index()
    for doc in docs:
        if doc.get("id") == doc_id:
            filepath = doc.get("filepath", "")
            if os.path.exists(filepath):
                return FileResponse(filepath, filename=doc.get("filename", "document"))
            return {"error": "File not found on disk"}
    return {"error": "Document not found"}


import time as _time_module
# Schema cache is keyed by CVM IP so different clusters never share results.
_schema_cache_by_ip: Dict[str, Dict] = {}

@app.get("/schema/explorer")
async def schema_explorer(refresh: int = 0, cvm_ip: str = ""):
    """Fetch all entity types + attributes from the live cluster via InsightsInterface RPCs.

    IP-driven: SSHes into the entered CVM and runs InsightsInterface against the
    local insights_server (127.0.0.1:2027). No default/template schema is returned
    when no IP is supplied.
    """
    cvm_ip = (cvm_ip or "").strip()
    if not cvm_ip:
        return {"entity_types": [], "needs_ip": True,
                "error": "Enter a CVM IP in the header to load this cluster's schema."}

    # Per-IP cache (short TTL)
    cached = _schema_cache_by_ip.get(cvm_ip)
    if not refresh and cached and (_time_module.time() - cached["ts"]) < 60:
        return cached["data"]

    cvm_password = resolve_cvm_ssh(cvm_ip)
    if not cvm_password:
        return {"entity_types": [], "error": f"Could not reach {cvm_ip} over SSH. Check the IP/VPN and try again."}

    idf_port = os.getenv("IDF_PORT", "2027")

    code = f"""import sys, os, json
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib64/python3.9/site-packages')
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib/python3.9/site-packages')
os.environ['GLOG_minloglevel'] = '3'
import logging
logging.disable(logging.CRITICAL)
import gflags
gflags.FLAGS([])
from insights_interface.insights_interface import InsightsInterface
from insights_interface import insights_interface_pb2 as pb2

ifc = InsightsInterface(ip='127.0.0.1', port={idf_port})

et_arg = pb2.GetEntityTypesArg()
et_ret = ifc.GetEntityTypes(et_arg)

result = []
for eti in et_ret.entity_type_list:
    name = eti.entity_type_name
    ti = eti.type_info if eti.HasField('type_info') else None

    attrs = []
    attr_count = 0
    metric_count = 0
    indexed_count = 0
    time_series_count = 0
    for mt in eti.metric_type_list:
        if mt.is_attribute:
            attr_count += 1
        else:
            metric_count += 1
        if mt.is_index_column:
            indexed_count += 1
        if mt.persist_attribute_as_time_series:
            time_series_count += 1
        idx_type_map = {{0: 'int64', 1: 'string', 2: 'uint64', 3: 'boolean', 4: 'bytes'}}
        vtype = ''
        if mt.is_index_column:
            vtype = idx_type_map.get(int(mt.index_type), '')
        elif mt.user_metadata:
            try:
                import json as _j
                _meta = _j.loads(mt.user_metadata)
                vtype = _meta.get('data_type', '')
            except:
                pass
        try:
            _large_obj = mt.is_large_object_attribute
        except:
            _large_obj = False
        attrs.append({{
            'name': mt.metric_name,
            'is_attribute': mt.is_attribute,
            'indexed': mt.is_index_column,
            'namespace': mt.namespace if mt.namespace and mt.namespace != '_default_' else '',
            'can_have_list': mt.can_have_list_values,
            'wildcard_searchable': mt.is_wildcard_searchable,
            'time_series': mt.persist_attribute_as_time_series,
            'is_large_object': _large_obj,
            'value_type': vtype,
            'unit': mt.unit if mt.unit else '',
            'ds_interval': mt.down_sampling_interval_in_secs if not mt.is_attribute else 0,
        }})

    shard_info = None
    if ti and ti.HasField('shard_strategy'):
        ss = ti.shard_strategy
        shard_type_map = {{0: 'None', 1: 'EntityType', 2: 'HashBased'}}
        shard_info = {{
            'type': shard_type_map.get(int(ss.shard_type), str(ss.shard_type)),
            'entity_type': ss.shard_entity_type_name if ss.shard_entity_type_name else ''
        }}

    entry = {{
        'name': name,
        'evictable': ti.is_evictable if ti else False,
        'suppress_replication': ti.suppress_replication if ti else False,
        'track_attribute_changes': ti.track_attribute_changes if ti else False,
        'is_dimension_fact': ti.is_dimension_fact_table if ti else False,
        'parent_list': list(ti.parent_list) if ti else [],
        'namespace_list': list(ti.namespace_list) if ti else [],
        'shard_strategy': shard_info,
        'deleted_entity_retention_secs': ti.deleted_entity_retention_in_secs if ti else 0,
        'attr_count': attr_count,
        'metric_count': metric_count,
        'indexed_count': indexed_count,
        'time_series_count': time_series_count,
        'total_fields': len(eti.metric_type_list),
        'attributes': attrs
    }}
    result.append(entry)

result.sort(key=lambda x: x['name'])
print(json.dumps({{'entity_types': result}}))
"""

    try:
        import subprocess

        # Write the schema script to the CVM via stdin (no escaping issues),
        # then run it locally on the CVM against 127.0.0.1:2027.
        write_cmd = [
            "sshpass", "-p", cvm_password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "PreferredAuthentications=password",
            "-o", "PubkeyAuthentication=no",
            "-o", "ConnectTimeout=15",
            f"nutanix@{cvm_ip}",
            "cat > /tmp/_idf_schema_explorer.py",
        ]
        subprocess.run(write_cmd, input=code, capture_output=True, text=True, timeout=20)

        exec_cmd = (
            f"sshpass -p '{cvm_password}' ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password "
            f"-o PubkeyAuthentication=no -o ConnectTimeout=15 "
            f"nutanix@{cvm_ip} 'python3 /tmp/_idf_schema_explorer.py' 2>/dev/null"
        )
        result = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True, timeout=90)
        output = (result.stdout or "").strip()

        if not output:
            err = (result.stderr or "").strip()[-400:]
            return {"entity_types": [], "error": f"No schema returned from {cvm_ip}. {err or 'Check SSH connectivity / that insights_server is running.'}"}

        # Be robust to any stray stdout lines: take the JSON object line.
        json_text = output
        if not output.lstrip().startswith("{"):
            for line in reversed(output.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    json_text = line
                    break
        try:
            schema_result = json.loads(json_text)
            _schema_cache_by_ip[cvm_ip] = {"data": schema_result, "ts": _time_module.time()}
            return schema_result
        except json.JSONDecodeError:
            return {"entity_types": [], "error": f"Could not parse schema output from {cvm_ip}: {output[:500]}"}

    except subprocess.TimeoutExpired:
        return {"entity_types": [], "error": f"Schema fetch timed out talking to {cvm_ip}."}
    except Exception as e:
        return {"entity_types": [], "error": str(e)}


# Entity-count cache is keyed by CVM IP so counts never leak across clusters.
_entity_counts_cache_by_ip: Dict[str, Dict] = {}

@app.get("/schema/entity-count")
async def schema_entity_count(entity_types: str = "", cvm_ip: str = ""):
    """Get entity counts for specified entity types (comma-separated) from the
    entered cluster. IP-driven so counts reflect the cluster in the header."""
    if not entity_types:
        return {"counts": {}}

    cvm_ip = (cvm_ip or "").strip()
    if not cvm_ip or cvm_ip in ("127.0.0.1", "localhost"):
        return {"counts": {}, "error": "Enter a CVM IP in the header to fetch entity counts."}

    type_list = [t.strip() for t in entity_types.split(",") if t.strip()][:20]

    # Per-IP cache
    now = _time_module.time()
    cache = _entity_counts_cache_by_ip.setdefault(cvm_ip, {"data": {}, "ts": 0})
    results = {}
    to_fetch = []
    for t in type_list:
        if t in cache["data"] and (now - cache["ts"]) < 120:
            results[t] = cache["data"][t]
        else:
            to_fetch.append(t)

    if not to_fetch:
        return {"counts": results}

    idf_port = os.getenv("IDF_PORT", "2027")

    types_str = repr(to_fetch)
    code = f"""# GetEntityTypesArg - direct execution marker
import sys, os, json, re
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib64/python3.9/site-packages')
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib/python3.9/site-packages')
os.environ['GLOG_minloglevel'] = '3'
import logging
logging.disable(logging.CRITICAL)
import gflags
gflags.FLAGS([])
from insights_interface.insights_interface import InsightsInterface
from insights_interface import insights_interface_pb2 as pb2
from google.protobuf import text_format

ifc = InsightsInterface(ip='127.0.0.1', port={idf_port})
counts = {{}}
for etype in {types_str}:
    try:
        proto_text = 'query {{ entity_list {{ entity_type_name: \"' + etype + '\" }} query_name: \"count_' + etype + '\" }}'
        arg = pb2.GetEntitiesWithMetricsArg()
        text_format.Merge(proto_text, arg)
        ret = ifc.GetEntitiesWithMetrics(arg)
        if ret.group_results_list:
            counts[etype] = ret.group_results_list[0].total_entity_count
        else:
            counts[etype] = 0
    except Exception as e:
        counts[etype] = -1
print(json.dumps(counts))
"""

    try:
        data = run_code_on_cvm(code, cvm_ip, idf_port, timeout=30)
        if data.get("success") and data.get("output"):
            try:
                fetched = json.loads(data["output"].strip())
                cache["data"].update(fetched)
                cache["ts"] = now
                results.update(fetched)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    return {"counts": results}


_field_docs_cache = {"data": None, "ts": 0}

@app.get("/schema/field-docs")
async def schema_field_docs():
    """Parse proto comments from UBVM insights_interface.proto to build field documentation."""
    import subprocess

    if _field_docs_cache["data"] and (_time_module.time() - _field_docs_cache["ts"]) < 3600:
        return _field_docs_cache["data"]

    ubvm_host = "nandish-chokshi.r8.ubvm.nutanix.com"

    try:
        cmd = f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 nandish.chokshi@{ubvm_host} "python3 /tmp/parse_proto_docs.py" 2>/dev/null'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            raw_lines = result.stdout.strip().split('\n')
            json_line = raw_lines[-1]
            docs_data = json.loads(json_line)
            _field_docs_cache["data"] = docs_data
            _field_docs_cache["ts"] = _time_module.time()
            return docs_data
        return {"type_info_fields": {}, "metric_type_fields": {}, "enums": {}, "error": result.stderr[:200] if result.stderr else "No output"}
    except Exception as e:
        return {"type_info_fields": {}, "metric_type_fields": {}, "enums": {}, "error": str(e)}


_gflags_cache = {"data": None, "ts": 0, "ip": ""}

@app.get("/gflags/live")
async def gflags_live(refresh: int = 0, cvm_ip: str = ""):
    """Fetch live gflag values from CVM and descriptions from UBVM source.
    cvm_ip: The CVM IP to fetch gflags from (passed from frontend header input).
    """
    import subprocess

    if not cvm_ip:
        return {"gflags": [], "total": 0, "source": "none", "error": "No CVM IP provided. Enter your cluster CVM IP in the header."}

    cache_valid = (
        not refresh
        and _gflags_cache["data"]
        and _gflags_cache["ip"] == cvm_ip
        and (_time_module.time() - _gflags_cache["ts"]) < 300
    )
    if cache_valid:
        return _gflags_cache["data"]

    cvm_password = cvm_password_for(cvm_ip)
    ubvm_host = "nandish-chokshi.r8.ubvm.nutanix.com"
    insights_src = "/home/nandish.chokshi/src/main/views/attr_timestamp/ntnxdb/ntnxdb_server/insights"

    gflags_result = []

    # Step 1: Fetch live gflag values from CVM via SSH
    try:
        cmd_live = f"sshpass -p '{cvm_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 nutanix@{cvm_ip} \"curl -s 'http://0:2027/h/gflags'\" 2>/dev/null"
        live_output = subprocess.run(cmd_live, shell=True, capture_output=True, text=True, timeout=30)
        live_text = live_output.stdout
        # Strip HTML tags if present (CVM returns HTML page with <pre> content)
        live_text = re.sub(r'<[^>]+>', '', live_text)

        live_flags = {}
        for line in live_text.split('\n'):
            line = line.strip()
            if line.startswith('--'):
                match = re.match(r'^--([a-zA-Z0-9_]+)=(.*)$', line)
                if match:
                    name = match.group(1)
                    rest = match.group(2)
                    default_match = re.match(r'^(.*?)\s*\(default\s+(.*?)\)$', rest)
                    if default_match:
                        value = default_match.group(1).strip()
                        default = default_match.group(2).strip()
                    else:
                        value = rest.strip()
                        default = value
                    live_flags[name] = {"value": value, "default": default}
    except Exception as e:
        live_flags = {}

    # Step 2: Fetch gflag descriptions from UBVM C++ source via pre-deployed script
    try:
        cmd_ubvm = f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 nandish.chokshi@{ubvm_host} "python3 /tmp/extract_gflags.py" 2>/dev/null'
        ubvm_output = subprocess.run(cmd_ubvm, shell=True, capture_output=True, text=True, timeout=60)
        if ubvm_output.returncode == 0 and ubvm_output.stdout.strip():
            try:
                raw_lines = ubvm_output.stdout.strip().split('\n')
                json_line = raw_lines[-1] if raw_lines else ''
                desc_list = json.loads(json_line)
                desc_map = {d["name"]: d for d in desc_list}
            except (json.JSONDecodeError, IndexError):
                desc_map = {}
        else:
            desc_map = {}
    except Exception:
        desc_map = {}

    # Step 3: Merge live values with descriptions — include ALL live gflags from cluster
    all_names = set(list(live_flags.keys()) + list(desc_map.keys()))

    for name in sorted(all_names):
        if name not in live_flags and name not in desc_map:
            continue

        entry = {"name": name}
        if name in live_flags:
            entry["value"] = live_flags[name]["value"]
            entry["default"] = live_flags[name]["default"]
        else:
            entry["value"] = ""
            entry["default"] = ""

        if name in desc_map:
            entry["type"] = desc_map[name]["type"]
            entry["description"] = desc_map[name]["description"]
        else:
            val = entry.get("value", "")
            if val in ("true", "false"):
                entry["type"] = "bool"
            elif val.lstrip('-').isdigit():
                entry["type"] = "int32"
            else:
                entry["type"] = "string"
            entry["description"] = ""

        # Categorize based on prefix and content
        if name.startswith("insights_") or name.startswith("watch_client_insights"):
            entry["category"] = "Insights Core"
        elif name.startswith("chakr_"):
            entry["category"] = "ChakrDB"
        elif name.startswith("odin_"):
            entry["category"] = "Odin"
        elif name.startswith("cassandra_"):
            entry["category"] = "Cassandra"
        elif name.startswith("watch_"):
            entry["category"] = "Watch"
        elif name.startswith("metadata_"):
            entry["category"] = "Metadata Service"
        elif name.startswith("zookeeper_"):
            entry["category"] = "Zookeeper"
        elif "nusights" in name or "pulse" in name:
            entry["category"] = "Nusights"
        elif "query" in name or "filter" in name:
            entry["category"] = "Query"
        elif "retention" in name or "ttl" in name or "expir" in name:
            entry["category"] = "Retention"
        elif "experimental" in name:
            entry["category"] = "Experimental"
        elif "throttl" in name or "rate_limit" in name:
            entry["category"] = "Throttling"
        elif "shard" in name or "lattice" in name:
            entry["category"] = "Sharding"
        elif "replicat" in name or "sync" in name:
            entry["category"] = "Replication"
        elif "schema" in name or "entity_type" in name or "metric_type" in name:
            entry["category"] = "Schema"
        elif "cache" in name or "rss" in name or "memory" in name:
            entry["category"] = "Cache"
        elif "store" in name or "mongo" in name:
            entry["category"] = "Store"
        elif "rpc" in name or "http" in name or "port" in name:
            entry["category"] = "Networking"
        elif "log" in name or "trace" in name or "debug" in name:
            entry["category"] = "Logging"
        else:
            entry["category"] = "Other"

        gflags_result.append(entry)

    result = {"gflags": gflags_result, "total": len(gflags_result), "source": "live", "cluster_ip": cvm_ip}
    _gflags_cache["data"] = result
    _gflags_cache["ts"] = _time_module.time()
    _gflags_cache["ip"] = cvm_ip
    return result


class GflagSetRequest(BaseModel):
    cvm_ip: str
    flag_name: str
    value: str


@app.post("/gflags/set")
async def gflags_set(request: GflagSetRequest):
    """Set a gflag value on the live CVM cluster via its HTTP interface."""
    import subprocess

    cvm_ip = request.cvm_ip.strip()
    flag_name = request.flag_name.strip()
    new_value = request.value.strip()

    if not cvm_ip:
        return {"success": False, "error": "No CVM IP provided."}
    if not flag_name:
        return {"success": False, "error": "No flag name provided."}
    if not re.match(r'^[a-zA-Z0-9_]+$', flag_name):
        return {"success": False, "error": "Invalid flag name. Only alphanumeric and underscores allowed."}

    cvm_password = cvm_password_for(cvm_ip)

    try:
        cmd = (
            f"sshpass -p '{cvm_password}' ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 "
            f"nutanix@{cvm_ip} "
            f"\"curl -s 'http://0:2027/h/gflags?{flag_name}={new_value}'\""
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()

        # Strip HTML tags and clean up
        output_clean = re.sub(r'<[^>]+>', '', output).strip()
        # Remove the "Command line flags" title text that comes from the HTML page
        output_clean = re.sub(r'^Command line flags\s*', '', output_clean).strip()

        if "Modified gflag" in output_clean:
            # Parse old value from response like "Modified gflag --flag from OLD to NEW"
            mod_match = re.search(r'Modified gflag --\S+ from (.+?) to (.+)', output_clean)
            old_value = mod_match.group(1).strip() if mod_match else ""
            confirmed_value = mod_match.group(2).strip() if mod_match else new_value

            # Invalidate cache so next fetch shows updated value
            _gflags_cache["ts"] = 0

            return {
                "success": True,
                "message": output_clean,
                "flag_name": flag_name,
                "old_value": old_value,
                "new_value": confirmed_value,
            }
        elif "Failed to modify" in output_clean:
            fail_msg = re.sub(r'^.*?(Failed to modify)', r'\1', output_clean).strip()
            return {"success": False, "error": fail_msg}
        elif not output_clean:
            return {"success": False, "error": f"No response from CVM at {cvm_ip}. Check if the IP is correct and IDF is running on port 2027."}
        else:
            return {"success": False, "error": f"Unexpected response: {output_clean[:200]}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"SSH to {cvm_ip} timed out."}
    except Exception as e:
        return {"success": False, "error": str(e)}


class BenchmarkRequest(BaseModel):
    cvm_ip: str
    command: str  # 'rss', 'index_map_stats', 'unevictable_cache_stats', 'init_time'


@app.post("/benchmark/stats")
async def benchmark_stats(request: BenchmarkRequest):
    """Execute memory benchmarking commands on the CVM and return parsed stats."""
    import subprocess

    cvm_ip = request.cvm_ip.strip()
    if not cvm_ip:
        return {"success": False, "error": "No CVM IP provided."}

    cvm_password = cvm_password_for(cvm_ip)

    commands_map = {
        "rss": "curl -s --max-time 15 'http://127.0.0.1:2027/'",
        "index_map_stats": "curl -s --max-time 15 'http://127.0.0.1:2027/index_map_stats'",
        "unevictable_cache_stats": "curl -s --max-time 15 'http://127.0.0.1:2027/detailed_unevictable_cache_stats'",
        "init_time": "curl -s --max-time 15 'http://127.0.0.1:2027/'",
        "all_stats": "curl -s --max-time 15 'http://127.0.0.1:2027/'",
    }

    cmd_to_run = commands_map.get(request.command)
    if not cmd_to_run:
        return {"success": False, "error": f"Unknown benchmark command: {request.command}"}

    try:
        # Use list-based subprocess to avoid shell escaping issues
        ssh_base = [
            "sshpass", "-p", cvm_password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15",
            f"nutanix@{cvm_ip}"
        ]

        # Run primary command (curl)
        result = subprocess.run(ssh_base + [cmd_to_run], capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()

        # For RSS, also get it from /proc as fallback (more reliable than parsing HTML)
        if request.command in ("rss", "all_stats"):
            proc_cmd = (
                "PID=$(ps aux | grep '/home/nutanix/bin/insights_server --insights' "
                "| grep -v grep | grep -v bash | grep -v logpipe | sort -k6 -rn "
                "| head -1 | awk '{print $2}') && "
                "cat /proc/$PID/status 2>/dev/null | grep VmRSS | awk '{print $2}'"
            )
            proc_result = subprocess.run(ssh_base + [proc_cmd], capture_output=True, text=True, timeout=15)
            if proc_result.stdout.strip():
                output += "\n___PROC_RSS___\n" + proc_result.stdout.strip()

        if not output and result.returncode != 0:
            return {"success": False, "error": f"SSH failed (exit {result.returncode}). Check CVM IP and connectivity."}

        import re
        parsed = {}
        flags = re.IGNORECASE | re.DOTALL

        if request.command in ("rss", "all_stats", "init_time"):
            # Try multiple RSS patterns (IDF page format varies across versions)
            rss_match = re.search(r'Resident Size\(MB\)</td>\s*<td[^>]*>\s*(\d+)', output, flags)
            if not rss_match:
                rss_match = re.search(r'IDF RSS.*?(\d+)\s*MB', output, flags)
            if rss_match:
                parsed["rss_mb"] = int(rss_match.group(1))

            # Fallback: get RSS from /proc (KB -> MB)
            if "___PROC_RSS___" in output:
                proc_part = output.split("___PROC_RSS___")[1].strip()
                proc_rss_match = re.search(r'(\d+)', proc_part)
                if proc_rss_match:
                    rss_from_proc = int(proc_rss_match.group(1)) // 1024
                    if rss_from_proc > 0:
                        parsed["rss_mb"] = rss_from_proc

            cluster_match = re.search(r'Cluster Type</td>\s*<td[^>]*>\s*([^<]+)', output, flags)
            if cluster_match:
                parsed["cluster_type"] = cluster_match.group(1).strip()

            leader_match = re.search(r'Is Leader Node</td>\s*<td[^>]*>\s*([^<]+)', output, flags)
            if leader_match:
                parsed["is_leader"] = leader_match.group(1).strip()

            build_match = re.search(r'Build Version</td>\s*<td[^>]*>\s*([^<]+)', output, flags)
            if build_match:
                parsed["build_version"] = build_match.group(1).strip()[:80]

            pid_match = re.search(r'Process ID</td>\s*<td[^>]*>\s*(\d+)', output, flags)
            if pid_match:
                parsed["pid"] = int(pid_match.group(1))

            init_match = re.search(r'Init Time</td>\s*<td[^>]*>\s*([^<]+)', output, flags)
            if init_match:
                parsed["init_time"] = init_match.group(1).strip()

            uptime_match = re.search(r'Uptime</td>\s*<td[^>]*>\s*([^<]+)', output, flags)
            if uptime_match:
                parsed["uptime"] = uptime_match.group(1).strip()

            unev_match = re.search(r'Unevictable Cache.*?(\d+)', output, flags)
            if unev_match:
                parsed["unevictable_cache_size"] = int(unev_match.group(1))

        return {"success": True, "output": output[:5000], "parsed": parsed, "command": request.command}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out on {cvm_ip}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


class BenchmarkPopulateRequest(BaseModel):
    cvm_ip: str
    entity_type: str
    attribute_name: str
    max_entities: int = 1000
    unique_values: int = 100
    value_type: str = "kString"
    is_evictable: bool = True


@app.post("/benchmark/populate")
async def benchmark_populate(request: BenchmarkPopulateRequest):
    """Register entity type + metric, then populate dummy entities at scale."""
    import subprocess

    cvm_ip = request.cvm_ip.strip()
    if not cvm_ip:
        return {"success": False, "error": "No CVM IP provided."}

    cvm_password = cvm_password_for(cvm_ip)
    et = request.entity_type
    attr = request.attribute_name
    count = min(request.max_entities, 50000)
    uniq = request.unique_values
    evictable_str = "True" if request.is_evictable else "False"

    # Map value_type string to index_type enum int
    # index_type field: kInt64=0, kString=1, kUInt64=2, kBoolean=3, kBytes=4
    vtype_map = {"kInt64": 0, "kString": 1, "kUInt64": 2, "kBoolean": 3, "kBytes": 4}
    idx_type_int = vtype_map.get(request.value_type, 1)

    # IMPORTANT: Always use is_evictable=False for benchmarking.
    # Reason: IDF does not allow setting is_index_column=True via RPC for evictable types.
    # Unevictable also gives us worst-case memory measurement (all entities in RAM).
    script = f'''import sys, os, time, subprocess as sp
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib64/python3.9/site-packages')
sys.path.insert(0, '/home/nutanix/.venvs/bin/lib/python3.9/site-packages')
os.environ['GLOG_minloglevel'] = '3'
import gflags
gflags.FLAGS([])

# Pre-check: ensure IDF is actually responding on port 2027
for attempt in range(6):
    try:
        check = sp.run("curl -s --max-time 5 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:2027/",
                       shell=True, capture_output=True, text=True, timeout=8)
        code = check.stdout.strip().replace("'", "")
        if code == "200":
            break
    except:
        pass
    if attempt < 5:
        print(f"IDF not ready (attempt {{attempt+1}}/6), waiting 10s...", flush=True)
        time.sleep(10)
else:
    print("REGISTER_ETYPE:FAIL:IDF not responding on port 2027 after 60s wait")
    sys.exit(1)

from insights_interface.insights_interface import InsightsInterface
from insights_interface import insights_interface_pb2 as pb2

idf = InsightsInterface("127.0.0.1", 2027)

# Step 1: Register entity type as UNEVICTABLE (required for is_index_column via RPC)
try:
    reg_arg = pb2.RegisterEntityTypesArg()
    ei = reg_arg.entity_type_info_list.add()
    ei.entity_type_name = "{et}"
    ei.type_info.is_evictable = False
    ei.type_info.suppress_replication = True
    ei.type_info.shard_strategy.shard_type = 1  # kEntityType
    ei.type_info.shard_strategy.shard_entity_type_name = "cluster"
    ei.type_info.parent_list.append("cluster")
    idf.RegisterEntityTypes(reg_arg)
    print("REGISTER_ETYPE:OK (unevictable for benchmark)")
except Exception as e:
    if "kAlreadyExists" in str(e) or "already" in str(e).lower():
        print("REGISTER_ETYPE:ALREADY_EXISTS")
    else:
        print(f"REGISTER_ETYPE:FAIL:{{e}}")
        sys.exit(1)

# Step 2: Register metric/attribute WITH is_index_column
try:
    mt_arg = pb2.RegisterMetricTypesArg()
    mt = mt_arg.metric_type_list.add()
    mt.entity_type_name = "{et}"
    mt.metric_name = "{attr}"
    mt.is_attribute = True
    mt.index_type = {idx_type_int}
    mt.is_index_column = True
    idf.RegisterMetricTypes(mt_arg)
    print("REGISTER_METRIC:OK (with is_index_column)")
except Exception as e:
    if "kAlreadyExists" in str(e) or "already" in str(e).lower():
        print("REGISTER_METRIC:ALREADY_EXISTS")
    elif "kInvalidIndexColumn" in str(e):
        print("REGISTER_METRIC:INDEX_ALREADY_SET")
    else:
        print(f"REGISTER_METRIC:FAIL:{{e}}")
        sys.exit(1)

# Step 3: Populate entities in batches
unique_pool = ["val_" + str(i) for i in range({uniq})]
BATCH = 100
total = {count}
created = 0
errors = 0

for batch_start in range(0, total, BATCH):
    batch_end = min(batch_start + BATCH, total)
    arg = pb2.BatchUpdateEntitiesArg()
    for i in range(batch_start, batch_end):
        ent = arg.entity_list.add()
        ent.entity_guid.entity_type_name = "{et}"
        ent.entity_guid.entity_id = "bench_" + str(i)
        ad = ent.attribute_data_arg_list.add()
        ad.attribute_data.name = "{attr}"
        val = unique_pool[i % len(unique_pool)]
        ad.attribute_data.value.str_value = val
    try:
        idf.BatchUpdateEntities(arg)
        created += (batch_end - batch_start)
    except Exception as e:
        errors += 1
        if errors > 5:
            print(f"TOO_MANY_ERRORS:{{errors}}")
            break

print(f"DONE:created={{created}},errors={{errors}},entity_type={et},attribute={attr}")
'''

    try:
        import base64

        # Write script to CVM via stdin pipe (most reliable - no escaping issues)
        write_cmd = [
            "sshpass", "-p", cvm_password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15",
            f"nutanix@{cvm_ip}",
            "cat > /tmp/_idf_bench_populate.py"
        ]
        wr = subprocess.run(write_cmd, input=script, capture_output=True, text=True, timeout=15)

        # Execute the script
        exec_cmd = (
            f"sshpass -p '{cvm_password}' ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 "
            f"nutanix@{cvm_ip} 'python3 /tmp/_idf_bench_populate.py' 2>/dev/null"
        )
        result = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True, timeout=180)
        output = result.stdout.strip()

        if "DONE:" in output:
            return {"success": True, "output": output, "entities_created": count}
        elif "TOO_MANY_ERRORS" in output:
            return {"success": False, "error": f"Too many batch errors. Output: {output}"}
        else:
            err = result.stderr.strip()[-500:] if result.stderr else output[-500:]
            return {"success": False, "error": f"Script failed: {err or output or 'No output. Check SSH connectivity.'}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Entity population timed out (>180s). Try reducing max_entities."}
    except Exception as e:
        return {"success": False, "error": str(e)}


class BenchmarkApplyIndexRequest(BaseModel):
    cvm_ip: str
    entity_type: str
    attribute_name: str
    is_evictable: bool = True
    value_type: str = "kString"


@app.post("/benchmark/apply-index")
async def benchmark_apply_index(request: BenchmarkApplyIndexRequest):
    """Apply index to an attribute and restart IDF. Returns when IDF is back up."""
    import subprocess

    cvm_ip = request.cvm_ip.strip()
    if not cvm_ip:
        return {"success": False, "error": "No CVM IP provided."}

    cvm_password = cvm_password_for(cvm_ip)
    et = request.entity_type
    attr = request.attribute_name

    # index_type enum: kInt64=0, kString=1, kUInt64=2, kBoolean=3, kBytes=4
    vtype_map = {"kInt64": 0, "kString": 1, "kUInt64": 2, "kBoolean": 3, "kBytes": 4}
    idx_type_int = vtype_map.get(request.value_type, 1)
    evictable_str = "True" if request.is_evictable else "False"

    # The populate step already registers the metric WITH is_index_column=True.
    # This step kills all insights_server instances and starts a fresh one with full flags.
    script = f'''import sys, os, time, subprocess as sp

print("INDEX_APPLIED:OK (already registered in populate step)", flush=True)

# Kill ALL existing insights_server processes to avoid port conflicts
print("RESTARTING_IDF...", flush=True)
sp.run("pkill -9 -f 'insights_server.*insights'", shell=True, capture_output=True, text=True, timeout=10)
time.sleep(3)

# Verify all killed
check = sp.run("pgrep -f 'insights_server.*insights' | wc -l",
               shell=True, capture_output=True, text=True, timeout=5)
remaining = check.stdout.strip()
if remaining != "0":
    sp.run("pkill -9 -f insights_server", shell=True, capture_output=True, text=True, timeout=10)
    time.sleep(2)
print(f"KILLED_ALL: remaining={{remaining}}", flush=True)

# Wait for port 2027 to be free
for i in range(10):
    port_check = sp.run("ss -tlnp | grep ':2027 '", shell=True, capture_output=True, text=True, timeout=5)
    if not port_check.stdout.strip():
        break
    time.sleep(1)

# Start insights_server with full production flags
IDF_CMD = ("/home/nutanix/bin/insights_server "
    "--insights_auto_register=true "
    "--log_dir=/home/nutanix/data/logs --v=0 "
    "--insights_cluster_function=2 "
    "--insights_nusights_pulse_enable=true "
    "--insights_skip_metric_data_caching=true "
    "--insights_max_outstanding_low_memory_rpc_ops=32 "
    "--insights_max_outstanding_high_memory_rpc_ops=4 "
    "--insights_max_outstanding_replication_local_rpc_ops=4 "
    "--insights_max_outstanding_replication_remote_rpc_ops=4 "
    "--insights_obj_spinrwlock_pool_size=65000 "
    "--insights_xi_ct_rss_share_mb=3584 "
    "--insights_experimental_enable_scaleout=true "
    "--insights_load_registered_cluster_entities=true "
    "--insights_enforce_rss_limits_by_share_mb=true "
    "--insights_rss_share_mb=5500 "
    "--insights_cache_num_shards=17 "
    "--insights_rss_low_watermark_pct=80 "
    "--insights_uploader_port=2029 "
    "--insights_replication_state_cassandra_flush_frequency_secs=150 "
    "--insights_persist_unregistered_entities_during_restore=true "
    "--insights_load_entities_from_cassandra_on_new_etype_registration=true "
    "--insights_publish_disk_usage_to_nusights=true "
    "--util_net_enable_serial_md5_implementation=true "
    "--undefok=insights_cluster_function,insights_num_threads_vcpu_factor,"
    "insights_nusights_pulse_enable,insights_xi_ct_rss_share_mb,"
    "insights_skip_metric_data_caching,insights_publish_disk_usage_to_nusights,"
    "util_net_enable_serial_md5_implementation")

sp.run(f"nohup {{IDF_CMD}} > /tmp/_idf_restart.log 2>&1 &",
       shell=True, capture_output=True, text=True, timeout=10, executable="/bin/bash")
print("MANUAL_START:INITIATED", flush=True)

# Wait for IDF to come back up (check port 2027 listening + HTTP 200)
print("WAITING_FOR_IDF...", flush=True)
for attempt in range(40):
    time.sleep(5)
    try:
        check = sp.run("curl -s --max-time 5 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:2027/",
                       shell=True, capture_output=True, text=True, timeout=8)
        code = check.stdout.strip().replace("'", "")
        if code == "200":
            print(f"IDF_UP:OK (attempt {{attempt+1}})")
            break
    except:
        pass
else:
    print("IDF_UP:TIMEOUT")
'''

    try:
        # Write script to CVM via stdin pipe (most reliable)
        write_cmd = [
            "sshpass", "-p", cvm_password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15",
            f"nutanix@{cvm_ip}",
            "cat > /tmp/_idf_bench_index.py"
        ]
        subprocess.run(write_cmd, input=script, capture_output=True, text=True, timeout=15)

        exec_cmd = (
            f"sshpass -p '{cvm_password}' ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 "
            f"nutanix@{cvm_ip} 'python3 /tmp/_idf_bench_index.py' 2>/dev/null"
        )
        result = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True, timeout=240)
        output = result.stdout.strip()

        if "IDF_UP:OK" in output:
            return {"success": True, "output": output, "status": "Index applied and IDF restarted successfully"}
        elif "IDF_UP:TIMEOUT" in output:
            return {"success": False, "error": "IDF did not come back up within 150s after restart.", "output": output}
        elif "INDEX_APPLIED:FAIL" in output:
            return {"success": False, "error": f"Failed to apply index: {output}"}
        else:
            err = result.stderr.strip()[-500:] if result.stderr else ""
            return {"success": False, "error": f"Unexpected output: {output[-500:]} {err}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Operation timed out (>240s). IDF may still be restarting."}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    _port = int(os.getenv("UI_BACKEND_PORT", "3001"))
    print("Starting IDF Query Generator Backend...")
    print(f"Backend API: http://0.0.0.0:{_port}")
    print(f"Query server: {QUERY_SERVER_URL}")
    uvicorn.run(app, host="0.0.0.0", port=_port)
