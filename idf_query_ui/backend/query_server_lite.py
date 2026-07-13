"""
Lightweight query server for IDF.ai hosted deployment.
Only provides the /execute endpoint for running code on the CVM via SSH.
AI features (query generation, embeddings, knowledge base) are excluded.
"""

import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from query_executor_lite import execute_query

app = FastAPI(title="IDF Query Server (Lite)", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    idf_ip: str = "127.0.0.1"
    idf_port: str = "2027"
    timeout: int = 60


class ExecuteResponse(BaseModel):
    success: bool
    output: str
    error: str
    execution_time_ms: float
    language: str


@app.get("/")
def root():
    return {"status": "ok", "mode": "lite", "message": "IDF Query Server (no AI)"}


@app.post("/execute", response_model=ExecuteResponse)
def execute_code(request: ExecuteRequest):
    """Execute code on the CVM via SSH."""
    if request.timeout > 120:
        request.timeout = 120

    result = execute_query(
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("QUERY_SERVER_PORT", "8000"))
    print(f"Starting IDF Query Server (Lite) on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
