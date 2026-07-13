#!/bin/bash
# Start the full IDF.AI stack locally with a resilient LLM backend.
#
# Brings up:
#   - Query server (backend-server)      : auto-picks 8000, else 8055
#   - UI backend (idf_query_ui/backend)  : 3001  -> proxies to the query server
#   - Frontend (idf_query_ui/frontend)   : 5050  (3000 is often used by other apps)
#
# LLM backend is auto-selected (config.py): MLX Phi-4 on :8090 if reachable,
# otherwise the local Ollama code model (qwen2.5-coder). Embeddings always use
# Ollama's nomic-embed-text. Ollama must be running (`ollama serve`).

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3)"

pick_port() {  # echo first free port from the args
  for p in "$@"; do
    if ! lsof -Pi :"$p" -sTCP:LISTEN -t >/dev/null 2>&1; then echo "$p"; return; fi
  done
  echo "$1"
}

QPORT="$(pick_port 8000 8055 8056)"
UIPORT=3001
FEPORT=5050

echo "==> Ollama check"
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "   WARNING: Ollama not reachable on :11434. Start it with 'ollama serve'."
fi

echo "==> Query server on :$QPORT"
lsof -ti:"$QPORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
( cd "$ROOT/backend-server" && IDF_SERVER_PORT="$QPORT" nohup "$PY" -u server.py > /tmp/idf_qserver.log 2>&1 & )

echo "==> UI backend on :$UIPORT"
lsof -ti:"$UIPORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
( cd "$ROOT/idf_query_ui/backend" && QUERY_SERVER_URL="http://localhost:$QPORT" UI_BACKEND_PORT="$UIPORT" \
    nohup "$PY" -u app.py > /tmp/idf_uiback.log 2>&1 & )

echo "==> Frontend on :$FEPORT"
lsof -ti:"$FEPORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
( cd "$ROOT/idf_query_ui/frontend" && nohup "$PY" -u serve_nocache.py "$FEPORT" > /tmp/idf_frontend.log 2>&1 & )

echo "==> Waiting for services..."
for i in $(seq 1 40); do
  up=0
  curl -s "http://localhost:$QPORT/" >/dev/null 2>&1 && up=$((up+1))
  curl -s "http://localhost:$UIPORT/health" >/dev/null 2>&1 && up=$((up+1))
  curl -s "http://localhost:$FEPORT/" >/dev/null 2>&1 && up=$((up+1))
  [ "$up" -eq 3 ] && break
  sleep 1
done

echo ""
echo "IDF.AI is up:"
echo "  Frontend    : http://localhost:$FEPORT"
echo "  UI backend  : http://localhost:$UIPORT   (QUERY_SERVER_URL=http://localhost:$QPORT)"
echo "  Query server: http://localhost:$QPORT"
echo ""
echo "Logs: /tmp/idf_qserver.log  /tmp/idf_uiback.log  /tmp/idf_frontend.log"
