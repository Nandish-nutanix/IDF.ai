"""
Query executor: Execute generated IDF queries directly on CVMs via SSH.

Connects to the target CVM, activates the correct Python environment,
and runs the query code directly. Fast and simple — no intermediate proxy.
"""

import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    """Result of a query execution."""
    success: bool
    output: str
    error: str
    execution_time_ms: float
    language: str


DEFAULT_IDF_IP = "127.0.0.1"
DEFAULT_IDF_PORT = "2027"
EXECUTION_TIMEOUT_SECONDS = 60
SSH_USER = os.getenv("CVM_SSH_USER", "nutanix")
SSH_PASSWORD = os.getenv("CVM_SSH_PASSWORD", "")
DEFAULT_CVM_HOST = os.getenv("DEFAULT_CVM_HOST", "10.53.56.1")


def _get_cvm_host(idf_ip: str) -> str:
    """
    Determine which CVM to SSH into.
    If user says 127.0.0.1/localhost, use the default CVM.
    Otherwise, SSH directly to the specified IP (it IS the CVM).
    """
    if idf_ip in ("127.0.0.1", "localhost"):
        return DEFAULT_CVM_HOST
    return idf_ip


def _build_execution_code(proto: str, idf_port: str) -> str:
    """Build the Python code to execute on the CVM. Always uses 127.0.0.1 since we SSH to the CVM itself."""
    return f"""import sys
sys.path.insert(0, "/home/nutanix/bin")
import env
import gflags
gflags.FLAGS([])
from google.protobuf.text_format import Merge
from insights_interface.insights_interface_pb2 import GetEntitiesWithMetricsArg
from insights_interface.insights_interface import InsightsInterface, InsightsInterfaceError
insights_interface = InsightsInterface("127.0.0.1", "{idf_port}")
arg = GetEntitiesWithMetricsArg()
query = \'\'\'
{proto}
\'\'\'
Merge(query, arg)
try:
    ret = insights_interface.GetEntitiesWithMetrics(arg)
    print(ret)
except InsightsInterfaceError as ex:
    print("Error Message: " + ex.message)
    print(ex.ret)
"""


def _extract_proto(code: str) -> Optional[str]:
    """Extract the proto text from generated code."""
    match = re.search(r"query\s*=\s*'''(.*?)'''", code, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'query\s*=\s*"""(.*?)"""', code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _is_direct_execution_code(code: str) -> bool:
    """Check if this is non-read code that should be executed directly."""
    indicators = [
        "InsightsWatchClient",
        "composite_watch_on_entities_of_type",
        "watch_new_entities_of_type",
        "UpdateEntityArg",
        "DeleteEntityArg",
        "RegisterMetricTypesArg",
        "RegisterEntityTypesArg",
        "UnregisterMetricTypesArg",
        "BatchGetEntitiesWithMetricsArg",
        "BatchUpdateEntitiesArg",
        "BatchDeleteEntitiesArg",
        "GetEntitiesArg",
        "GetEntityTypesArg",
        "GetMetricTypesArg",
        "GetMetricDataArg",
        "PutMetricDataArg",
        "SpotLightSearchArg",
        "GetEntitiesTrailArg",
        "AttachEntityArg",
        "DetachEntityArg",
        "GetMasterLocationArg",
        "PutEventArg",
        "RegisterWatchClientArg",
        "RegisterWatchArg",
        "GetFiredWatchListArg",
        "UnregisterWatchClientArg",
        "UnregisterWatchArg",
        "SyncUpdateEntityArg",
    ]
    return any(ind in code for ind in indicators)


def _prepare_direct_code(code: str, idf_ip: str, idf_port: str) -> str:
    """Prepare non-read code for direct SSH execution with proper path setup."""
    lines = code.split('\n')
    prepared = []
    has_path_insert = False
    for line in lines:
        if line.startswith('# Query:'):
            continue
        if 'sys.path.insert' in line:
            has_path_insert = True
        prepared.append(line)

    result = "import sys\nsys.path.insert(0, '/home/nutanix/cluster/bin')\n" if not has_path_insert else ""
    result += '\n'.join(prepared)

    # Replace IP/port with actual target (127.0.0.1 since we SSH to the CVM)
    result = re.sub(r'InsightsInterface\([^)]+\)', f'InsightsInterface("127.0.0.1", "{idf_port}")', result)
    result = re.sub(r'InsightsWatchClient\("([^"]+)",\s*error_callback,\s*"[^"]+",\s*"[^"]+"',
                    f'InsightsWatchClient("\\1", error_callback, "127.0.0.1", "{idf_port}"', result)

    # For watch queries, reduce sleep time for execution (don't wait 30s)
    result = re.sub(r'WATCH_DURATION_SECS\s*=\s*\d+', 'WATCH_DURATION_SECS = 5', result)
    result = result.replace('time.sleep(WATCH_DURATION_SECS)', 'time.sleep(5)')
    result = result.replace('time.sleep(30)', 'time.sleep(5)')

    return result


def execute_python_query(
    code: str,
    idf_ip: str = DEFAULT_IDF_IP,
    idf_port: str = DEFAULT_IDF_PORT,
    timeout: int = EXECUTION_TIMEOUT_SECONDS,
) -> ExecutionResult:
    """Execute a Python IDF query directly on the CVM via SSH."""
    t_start = time.perf_counter()

    # For non-read operations (watch, update, delete, register), execute directly
    if _is_direct_execution_code(code):
        cvm_host = _get_cvm_host(idf_ip)
        exec_code = _prepare_direct_code(code, idf_ip, idf_port)
    else:
        proto = _extract_proto(code)
        if not proto:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            return ExecutionResult(
                success=False,
                output="",
                error="Could not extract query proto from the generated code.",
                execution_time_ms=elapsed_ms,
                language="python",
            )

        cvm_host = _get_cvm_host(idf_ip)
        exec_code = _build_execution_code(proto, idf_port)

    try:
        ssh_cmd = [
            "sshpass", "-p", SSH_PASSWORD,
            "ssh",
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            "-o", "LogLevel=ERROR",
            f"{SSH_USER}@{cvm_host}",
            "source /home/nutanix/.venvs/bin/bin/activate && python -"
        ]

        result = subprocess.run(
            ssh_cmd,
            input=exec_code,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Filter SSH noise from stderr
        stderr_lines = [
            l for l in stderr.split('\n')
            if l.strip() and not any(skip in l for skip in [
                'WARNING', 'vulnerable', 'upgraded', 'openssh',
                'Prism Central', 'Kernel', '\\S', '\\r', '\\m'
            ])
        ]
        stderr_clean = '\n'.join(stderr_lines).strip()

        if result.returncode == 0 and stdout:
            return ExecutionResult(
                success=True,
                output=stdout,
                error="",
                execution_time_ms=elapsed_ms,
                language="python",
            )
        elif result.returncode == 0:
            return ExecutionResult(
                success=True,
                output="(Query executed successfully — no results returned)",
                error="",
                execution_time_ms=elapsed_ms,
                language="python",
            )
        else:
            error_msg = stderr_clean or stdout or f"Command exited with code {result.returncode}"
            return ExecutionResult(
                success=False,
                output=stdout,
                error=error_msg,
                execution_time_ms=elapsed_ms,
                language="python",
            )

    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        return ExecutionResult(
            success=False,
            output="",
            error=f"Execution timed out after {timeout} seconds",
            execution_time_ms=elapsed_ms,
            language="python",
        )
    except FileNotFoundError:
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        return ExecutionResult(
            success=False,
            output="",
            error="'sshpass' not installed. Run: brew install hudochenkov/sshpass/sshpass",
            execution_time_ms=elapsed_ms,
            language="python",
        )
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        return ExecutionResult(
            success=False,
            output="",
            error=f"Execution error: {str(e)}",
            execution_time_ms=elapsed_ms,
            language="python",
        )


def execute_go_query(
    code: str,
    idf_ip: str = DEFAULT_IDF_IP,
    idf_port: str = DEFAULT_IDF_PORT,
    timeout: int = EXECUTION_TIMEOUT_SECONDS,
) -> ExecutionResult:
    """Go execution not yet supported for direct SSH execution."""
    return ExecutionResult(
        success=False,
        output="",
        error="Direct Go execution is not yet supported. Use the Python tab to run queries.",
        execution_time_ms=0.0,
        language="go",
    )


def execute_query(
    code: str,
    language: str,
    idf_ip: str = DEFAULT_IDF_IP,
    idf_port: str = DEFAULT_IDF_PORT,
    timeout: int = EXECUTION_TIMEOUT_SECONDS,
) -> ExecutionResult:
    """Execute a query directly on the target CVM via SSH."""
    if language in ("python", "py"):
        return execute_python_query(code, idf_ip, idf_port, timeout)
    elif language in ("go", "golang"):
        return execute_go_query(code, idf_ip, idf_port, timeout)
    else:
        return ExecutionResult(
            success=False,
            output="",
            error=f"Unsupported language: {language}. Use 'python' or 'go'.",
            execution_time_ms=0.0,
            language=language,
        )
