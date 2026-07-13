#!/bin/bash
# Restart IDF.ai services on the UMSVM: backend API (3001) + no-cache frontend (3000).
# The query server (8000) is left untouched.
set -u
BASE=/home/nandish.chokshi/idf-ai

# --- Backend API (app.py) on 3001 ---
pkill -f "python3 app.py" 2>/dev/null || true
sleep 1
cd "$BASE/backend"
nohup python3 app.py > /tmp/app_3001.log 2>&1 &
echo "started app.py (pid $!)"

# --- Frontend on 3000 with no-cache server ---
pkill -f "http.server 3000" 2>/dev/null || true
pkill -f "serve_nocache.py 3000" 2>/dev/null || true
sleep 1
cd "$BASE/frontend"
nohup python3 serve_nocache.py 3000 > /tmp/frontend_3000.log 2>&1 &
echo "started serve_nocache.py 3000 (pid $!)"

sleep 4
echo "=== listening ports ==="
(ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -E ":3000|:3001|:8000" || true
echo "=== app.py log ==="
tail -6 /tmp/app_3001.log 2>/dev/null || true
echo "=== frontend log ==="
tail -4 /tmp/frontend_3000.log 2>/dev/null || true
