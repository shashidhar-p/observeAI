# Implementation Plan: Multi-Agent AI Observability & RCA System

**Branch**: `001-multi-agent-rca` | **Date**: 2025-12-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-multi-agent-rca/spec.md`

## Summary

Build an AI-powered observability platform that receives alerts from Alert Manager, correlates related incidents, extracts relevant logs/metrics from Loki and Cortex, and produces automated Root Cause Analysis reports with remediation suggestions. Implementation follows a phased approach: POC in Python with a single unified agent, evolving to production Go with three specialized agents.

## Technical Context

### POC Phase

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `anthropic` - Claude API client for LLM integration
- `fastapi` + `uvicorn` - Webhook receiver and API
- `httpx` - Async HTTP client for Loki/Cortex queries
- `sqlalchemy` + `asyncpg` - PostgreSQL ORM
- `pydantic` - Data validation and serialization

**Storage**: PostgreSQL 15+
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux (Docker containers)
**Project Type**: Single backend service
**Performance Goals**: RCA report generation within 2 minutes for 95% of alerts
**Constraints**:
- <2 second webhook acknowledgment
- Handle 50 concurrent incidents
- LLM cost optimization (token efficiency)
**Scale/Scope**: POC targets single-alert RCA, no correlation

### Production Phase (Future)

**Language/Version**: Go 1.21+
**Primary Dependencies**:
- `anthropics/anthropic-sdk-go` - Claude API client
- `gin-gonic/gin` - HTTP framework
- `go-redis/redis` - Message queue
- `lib/pq` or `jackc/pgx` - PostgreSQL driver
- `prometheus/client_golang` - Cortex client

**Additional Infrastructure**: Redis for inter-agent message queue

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Constitution file contains template placeholders only. No project-specific principles defined yet.

| Principle | Status | Notes |
|-----------|--------|-------|
| Constitution not configured | N/A | Template placeholders present - no violations possible |

**Recommendation**: Run `/speckit.constitution` to define project principles before production phase.

## Project Structure

### Documentation (this feature)

```text
specs/001-multi-agent-rca/
├── plan.md              # This file
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - entity schemas
├── quickstart.md        # Phase 1 output - getting started guide
├── contracts/           # Phase 1 output - API specifications
│   └── openapi.yaml     # Alert webhook & RCA API
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# POC Structure (Python) - IMPLEMENTED
src/
├── main.py              # Application entrypoint with FastAPI
├── config.py            # Configuration management (env vars)
├── models/
│   ├── __init__.py
│   ├── alert.py         # Alert entity
│   ├── incident.py      # Incident entity with correlation
│   └── rca_report.py    # RCA report entity
├── services/
│   ├── __init__.py
│   ├── webhook.py       # Alert Manager webhook handler
│   ├── loki_client.py   # Loki LogQL client
│   ├── cortex_client.py # Cortex PromQL client
│   ├── rca_agent.py     # Unified RCA agent (multi-provider)
│   ├── llm.py           # LLM provider abstraction
│   ├── incident_service.py    # Incident management
│   ├── report_service.py      # RCA report management
│   └── semantic_correlator.py # LLM-based alert correlation
├── api/
│   ├── __init__.py
│   ├── routes.py        # FastAPI routes
│   └── schemas.py       # Pydantic request/response models
└── tools/
    ├── __init__.py
    ├── query_loki.py    # Loki tool with LogQL builder
    ├── query_cortex.py  # Cortex tool with PromQL builder
    └── generate_report.py # Report generation with schemas

# React Dashboard
dashboard/
├── src/
│   ├── App.tsx          # Main application
│   ├── index.css        # Tailwind styles
│   ├── api/client.ts    # API client with SWR
│   ├── types/index.ts   # TypeScript types
│   └── pages/
│       ├── IncidentsPage.tsx   # Incident list with search, filters, status cards
│       └── IncidentDetail.tsx  # RCA report viewer with remediation
├── package.json
└── vite.config.ts       # Vite configuration with proxy

# RCA Expert Prompts
prompts/
└── network_engineer.md  # Network engineering domain expertise

# Observability Stack
prometheus/
├── prometheus.yml       # Scrape configuration
├── alertmanager.yml     # Alert routing to webhook
└── alerts/
    ├── network_alerts.yml  # Network interface alerts
    ├── host_alerts.yml     # CPU/memory/disk alerts
    └── service_alerts.yml  # Service health alerts

# Configuration
promtail-config.yml      # Log collection config
cortex-config.yml        # Cortex storage config
docker-compose.observability.yml  # Full stack

tests/
├── conftest.py          # Pytest fixtures
├── unit/
│   └── ...
└── integration/
    └── ...
```

**Structure Decision**: Single backend service with modular organization. Tools are separated from services to clearly delineate Claude agent capabilities.

## Complexity Tracking

> No constitution violations to justify - constitution not yet configured.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
