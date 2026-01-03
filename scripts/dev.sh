#!/bin/bash
# =============================================================================
# Development server launcher for observeAI
# Starts both backend (uvicorn) and dashboard (vite) dev servers
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting observeAI development servers...${NC}"

# Get the workspace root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to workspace root
cd "$WORKSPACE_ROOT"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down development servers...${NC}"
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend server
echo -e "${GREEN}Starting backend server on http://localhost:8000${NC}"
PYTHONPATH=. uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start dashboard server
echo -e "${GREEN}Starting dashboard server on http://localhost:3001${NC}"
cd dashboard && npm run dev &
DASHBOARD_PID=$!

cd "$WORKSPACE_ROOT"

echo -e "\n${GREEN}Development servers running:${NC}"
echo -e "  Backend:   http://localhost:8000"
echo -e "  Dashboard: http://localhost:3001"
echo -e "\n${YELLOW}Press Ctrl+C to stop all servers${NC}"

# Wait for any process to exit
wait
