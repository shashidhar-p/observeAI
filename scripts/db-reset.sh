#!/bin/bash
# =============================================================================
# Reset database - drop all tables and run migrations fresh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Handle both direct execution and bazel run
if [ -n "$BUILD_WORKSPACE_DIRECTORY" ]; then
    WORKSPACE_ROOT="$BUILD_WORKSPACE_DIRECTORY"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"
fi

cd "$WORKSPACE_ROOT"

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Database Reset${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Check if PostgreSQL is running
POSTGRES_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres|observeai.*postgres' | head -1)

if [ -z "$POSTGRES_CONTAINER" ]; then
    echo -e "${RED}PostgreSQL container not running!${NC}"
    echo -e "Start it with: docker-compose -f docker-compose.observability.yml up -d"
    exit 1
fi

echo -e "${GREEN}[1/3] Dropping all tables...${NC}"
docker exec "$POSTGRES_CONTAINER" psql -U rca -d rca_db -c "
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO rca;
GRANT ALL ON SCHEMA public TO public;
" 2>/dev/null || echo -e "${YELLOW}      (tables may not exist yet)${NC}"

echo -e "${GREEN}[2/3] Running migrations...${NC}"
PYTHONPATH=. alembic upgrade head

echo -e "${GREEN}[3/3] Verifying tables...${NC}"
docker exec "$POSTGRES_CONTAINER" psql -U rca -d rca_db -c "\dt" 2>/dev/null

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Database Reset Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Tables created. Ready for testing."
echo ""
