#!/bin/bash

# IDF Query Generator - Stop Script

echo "🛑 Stopping IDF Query Generator..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Stop backend (port 3001)
echo "Stopping Backend API (port 3001)..."
lsof -ti:3001 | xargs kill -9 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backend stopped${NC}"
else
    echo "ℹ️  Backend was not running"
fi

# Stop frontend (port 3000)
echo "Stopping Frontend (port 3000)..."
lsof -ti:3000 | xargs kill -9 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend stopped${NC}"
else
    echo "ℹ️  Frontend was not running"
fi

echo ""
echo -e "${GREEN}✅ All services stopped${NC}"
echo ""
echo "💡 To start again, run: ./start.sh"
