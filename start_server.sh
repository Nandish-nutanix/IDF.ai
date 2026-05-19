#!/bin/bash

# Start server script for NL Query to Insights Query Proto
# This script starts the server and optionally starts the client

set -e

# Run from project root (script directory) so venv, requirements, config paths work
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting NL Query Server...${NC}"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check if server is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}Server is already running on port 8000${NC}"
    echo -e "${YELLOW}Killing existing process...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# config.py lives at project root; backend-server imports it via PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR"

# Start the server in the background
echo -e "${GREEN}Starting server on http://localhost:8000...${NC}"
python backend-server/server.py > server.log 2>&1 &
SERVER_PID=$!

# Wait for server to be ready
echo -e "${YELLOW}Waiting for server to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        echo -e "${GREEN}Server is ready!${NC}"
        echo -e "${GREEN}Server PID: ${SERVER_PID}${NC}"
        echo -e "${GREEN}Server logs: tail -f server.log${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Server failed to start within 30 seconds${NC}"
        echo -e "${RED}Check server.log for errors${NC}"
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down server (PID: ${SERVER_PID})...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    echo -e "${GREEN}Server stopped${NC}"
}

trap cleanup EXIT INT TERM

# Check if UI should be started (query server must be up first; UI backend proxies to it)
if [ "$1" == "--with-ui" ] || [ "$1" == "-u" ]; then
    echo -e "${GREEN}Starting IDF Query UI (frontend + UI backend)...${NC}"
    echo -e "${YELLOW}Query server is on port 8000; UI backend 3001, frontend 3000${NC}"
    ( cd "$SCRIPT_DIR/idf_query_ui" && ./start.sh )
    # When start.sh exits (e.g. Ctrl+C), cleanup trap will kill SERVER_PID
elif [ "$1" == "--with-client" ] || [ "$1" == "-c" ]; then
    echo -e "${GREEN}Starting client...${NC}"
    echo -e "${YELLOW}Enter your query (Ctrl+C to exit):${NC}"
    python query_cli.py
else
    echo -e "${GREEN}Server is running in the background${NC}"
    echo -e "${YELLOW}To start the client, run:${NC}"
    echo -e "  python query_cli.py \"your query here\""
    echo -e "${YELLOW}Or run this script with:${NC}"
    echo -e "  ./start_server.sh --with-client   # CLI only"
    echo -e "  ./start_server.sh --with-ui      # Web UI (port 3000)"
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
    # Keep script running
    wait $SERVER_PID
fi
