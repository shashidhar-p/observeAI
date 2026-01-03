#!/bin/bash
# =============================================================================
# Deploy observeAI stack
# Starts infrastructure services and application containers
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the workspace root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$WORKSPACE_ROOT"

# Parse arguments
SKIP_BUILD=false
DETACH=true
OBSERVABILITY=true

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --no-build       Skip building container images"
    echo "  --no-detach      Run in foreground (show logs)"
    echo "  --no-observability  Skip observability stack (Prometheus, Grafana, etc.)"
    echo "  --help           Show this help message"
}

for arg in "$@"; do
    case $arg in
        --no-build)
            SKIP_BUILD=true
            shift
            ;;
        --no-detach)
            DETACH=false
            shift
            ;;
        --no-observability)
            OBSERVABILITY=false
            shift
            ;;
        --help)
            print_usage
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  observeAI Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Build container images
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${GREEN}[1/5] Building container images...${NC}"
    # Check if we're already running from bazel run (parent bazel exists)
    if [ -n "$BUILD_WORKSPACE_DIRECTORY" ]; then
        echo -e "${YELLOW}      Running from bazel run - images should already be built${NC}"
        cd "$BUILD_WORKSPACE_DIRECTORY"
    else
        /tmp/bazel build //containers:backend_image //containers:dashboard_image --config=stamp
    fi
    echo -e "${GREEN}      Container images ready${NC}"
else
    echo -e "${YELLOW}[1/5] Skipping container build (--no-build)${NC}"
fi

# Step 2: Start observability stack
if [ "$OBSERVABILITY" = true ]; then
    echo -e "${GREEN}[2/5] Starting observability stack...${NC}"
    docker-compose -f docker-compose.observability.yml up -d
    echo -e "${GREEN}      Observability stack started${NC}"
else
    echo -e "${YELLOW}[2/5] Skipping observability stack (--no-observability)${NC}"
fi

# Step 3: Start database
echo -e "${GREEN}[3/5] Starting PostgreSQL database...${NC}"

# Check if postgres is already running (from any source)
if docker ps --format '{{.Names}}' | grep -q postgres; then
    echo -e "${YELLOW}      PostgreSQL already running${NC}"
else
    docker-compose -f docker/docker-compose.yaml up -d postgres
    echo -e "${GREEN}      PostgreSQL started${NC}"
fi

# Wait for PostgreSQL to be ready
echo -e "${YELLOW}      Waiting for PostgreSQL to be ready...${NC}"
POSTGRES_CONTAINER=$(docker ps --format '{{.Names}}' | grep postgres | head -1)
for i in {1..30}; do
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U rca -d rca_db > /dev/null 2>&1; then
        echo -e "${GREEN}      PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}      PostgreSQL failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Step 4: Run database migrations
echo -e "${GREEN}[4/5] Running database migrations...${NC}"
PYTHONPATH=. alembic upgrade head
echo -e "${GREEN}      Migrations complete${NC}"

# Step 5: Start application
echo -e "${GREEN}[5/5] Starting application...${NC}"

# Use docker-compose for app (includes pip dependencies)
# Stop any existing app containers
docker stop observeai-backend observeai-dashboard 2>/dev/null || true
docker rm observeai-backend observeai-dashboard 2>/dev/null || true

# Start backend via uvicorn directly (pip deps already installed locally)
if [ -n "$BUILD_WORKSPACE_DIRECTORY" ]; then
    cd "$BUILD_WORKSPACE_DIRECTORY"
fi

# Start backend in background
echo -e "${GREEN}      Starting backend server...${NC}"
nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/observeai-backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/observeai-backend.pid

# Start dashboard dev server in background
echo -e "${GREEN}      Starting dashboard server...${NC}"
cd dashboard
nohup npm run dev -- --port 3001 --host > /tmp/observeai-dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo $DASHBOARD_PID > /tmp/observeai-dashboard.pid
cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Services running:"
echo -e "  ${BLUE}Backend API:${NC}     http://localhost:8000"
echo -e "  ${BLUE}Dashboard:${NC}       http://localhost:3001"
echo -e "  ${BLUE}API Docs:${NC}        http://localhost:8000/docs"
if [ "$OBSERVABILITY" = true ]; then
    echo ""
    echo -e "Observability:"
    echo -e "  ${BLUE}Prometheus:${NC}      http://localhost:9090"
    echo -e "  ${BLUE}Alertmanager:${NC}   http://localhost:9093"
    echo -e "  ${BLUE}Grafana:${NC}        http://localhost:3000 (admin/admin)"
    echo -e "  ${BLUE}Loki:${NC}           http://localhost:3100"
    echo -e "  ${BLUE}Cortex:${NC}         http://localhost:9009"
fi
echo ""
echo -e "Commands:"
echo -e "  ${YELLOW}View logs:${NC}       docker logs -f observeai-backend"
echo -e "  ${YELLOW}Stop all:${NC}        bazel run //:deploy-stop"
echo ""
