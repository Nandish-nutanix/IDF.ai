#!/bin/bash

# IDF Query Generator - Startup Script

echo "🚀 Starting IDF Query Generator..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Free UI ports if already in use (e.g. from a previous run)
if lsof -Pi :3001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 3001 in use; freeing it...${NC}"
    lsof -ti:3001 | xargs kill -9 2>/dev/null || true
    sleep 1
fi
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 3000 in use; freeing it...${NC}"
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Check if query server (backend-server) is running on port 8000
echo "📡 Checking query server..."
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Query server is running on port 8000${NC}"
else
    echo -e "${RED}❌ Query server is not running on port 8000!${NC}"
    echo "Start it from the project root first:"
    echo "  ./start_server.sh"
    exit 1
fi

# Check Python dependencies
echo ""
echo "📦 Checking Python dependencies..."
if python3 -c "import fastapi, uvicorn, numpy, requests" 2>/dev/null; then
    echo -e "${GREEN}✅ All dependencies installed${NC}"
else
    echo -e "${RED}❌ Missing dependencies!${NC}"
    echo "Installing dependencies..."
    cd backend
    pip3 install -r requirements.txt
    cd ..
fi

# Cleanup UI processes on exit (Ctrl+C or script end)
cleanup_ui() {
    echo -e "\n${YELLOW}Shutting down UI...${NC}"
    [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}UI stopped${NC}"
}
trap cleanup_ui EXIT INT TERM

# Start backend API
echo ""
echo "🔧 Starting Backend API..."
cd backend
python3 app.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 3

# Check if backend is running
if curl -s http://localhost:3001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend API is running on port 3001${NC}"
else
    echo -e "${RED}❌ Backend failed to start!${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start frontend
echo ""
echo "🌐 Starting Frontend..."
cd frontend
python3 -m http.server 3000 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 2

# Verify frontend is actually up
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ | grep -q 200; then
    echo -e "${RED}❌ Frontend failed to start on port 3000 (address may still be in use)${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✅ Frontend is running on port 3000${NC}"

echo ""
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}🎉 IDF Query Generator is ready!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Frontend UI:    http://localhost:3000"
echo "🔧 Backend API:    http://localhost:3001"
echo "📡 Query server:   http://localhost:8000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Try these example queries:"
echo "   • Get all VMs"
echo "   • Count all hosts"
echo "   • Get VMs where cpu_usage greater than 80"
echo "   • Fetch all clusters with vm_name"
echo ""
echo "🛑 To stop all services, press Ctrl+C or run: ./stop.sh"
echo ""

# Open browser (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🌐 Opening browser..."
    sleep 2
    open http://localhost:3000
fi

# Keep script running
wait
