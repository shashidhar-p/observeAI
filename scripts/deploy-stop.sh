#!/bin/bash
# =============================================================================
# Stop observeAI stack
# Stops all infrastructure and application containers
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the workspace root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$WORKSPACE_ROOT"

echo -e "${YELLOW}Stopping observeAI stack...${NC}"

# Stop application processes and containers
echo -e "${GREEN}[1/3] Stopping application...${NC}"
# Kill processes if running
if [ -f /tmp/observeai-backend.pid ]; then
    kill $(cat /tmp/observeai-backend.pid) 2>/dev/null || true
    rm /tmp/observeai-backend.pid
fi
if [ -f /tmp/observeai-dashboard.pid ]; then
    kill $(cat /tmp/observeai-dashboard.pid) 2>/dev/null || true
    rm /tmp/observeai-dashboard.pid
fi
# Also stop any uvicorn or vite processes
pkill -f "uvicorn src.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
# Stop containers if any
docker stop observeai-backend observeai-dashboard 2>/dev/null || true
docker rm observeai-backend observeai-dashboard 2>/dev/null || true

# Stop observability stack
echo -e "${GREEN}[2/3] Stopping observability stack...${NC}"
docker-compose -f docker-compose.observability.yml down 2>/dev/null || true

# Stop database
echo -e "${GREEN}[3/3] Stopping database...${NC}"
docker-compose -f docker/docker-compose.yaml down 2>/dev/null || true

echo ""
echo -e "${GREEN}All services stopped.${NC}"
echo ""
echo -e "To remove all data volumes, run:"
echo -e "  ${YELLOW}docker-compose -f docker-compose.observability.yml down -v${NC}"
echo -e "  ${YELLOW}docker-compose -f docker/docker-compose.yaml down -v${NC}"
