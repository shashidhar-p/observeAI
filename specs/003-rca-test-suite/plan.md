# Implementation Plan: RCA Test Suite

**Branch**: `003-rca-test-suite` | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-rca-test-suite/spec.md`

## Summary

Implement a comprehensive test suite for the ObserveAI Multi-Agent RCA System covering alert ingestion, incident correlation, RCA agent execution, Loki/Cortex tool calls, report generation, API endpoints, and edge cases. Tests will use pytest with pytest-asyncio, mocking external services in unit tests and using live AI APIs in integration tests.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (asyncio), Pydantic 2.x, httpx, anthropic
**Storage**: PostgreSQL with asyncpg driver
**Testing**: pytest 8.3+, pytest-asyncio, pytest-cov, httpx (TestClient)
**Target Platform**: Linux server (containerized)
**Project Type**: Single project (backend API with tests)
**Performance Goals**: Alert ingestion <100ms, correlation <1s, API responses <500ms
**Constraints**: Max 3 concurrent RCA executions, AI API rate limits
**Scale/Scope**: 80% unit test coverage, 70% integration test coverage, all 47 acceptance scenarios automated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Test-First | ✅ PASS | This feature IS the test suite |
| Library-First | ✅ PASS | Tests organized as separate test modules |
| Integration Testing | ✅ PASS | Integration tests planned for API and services |
| Observability | ✅ PASS | Tests verify logging and error handling |
| Simplicity | ✅ PASS | Standard pytest patterns, no custom frameworks |

No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/003-rca-test-suite/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/              # Alert, Incident, RCAReport
├── services/            # AlertService, IncidentService, RCAAgent, etc.
├── api/                 # FastAPI routes and schemas
├── tools/               # Loki, Cortex query tools
└── config.py            # Settings

tests/
├── conftest.py          # Shared fixtures
├── fixtures/            # Test data (AlertManager payloads, etc.)
├── unit/
│   ├── test_alert_service.py
│   ├── test_incident_service.py
│   ├── test_correlation_service.py
│   ├── test_semantic_correlator.py
│   ├── test_rca_agent.py
│   ├── test_loki_tool.py
│   ├── test_cortex_tool.py
│   ├── test_report_service.py
│   ├── test_webhook.py
│   ├── test_schemas.py
│   └── test_tools.py
├── integration/
│   ├── test_webhook_e2e.py
│   ├── test_correlation_e2e.py
│   ├── test_rca_e2e.py
│   ├── test_api_alerts.py
│   ├── test_api_incidents.py
│   └── test_api_reports.py
└── stress/
    ├── test_concurrent_alerts.py
    └── test_concurrent_rca.py
```

**Structure Decision**: Single project structure with tests organized by type (unit/integration/stress). Tests target the existing `src/` module structure.

## Complexity Tracking

> No violations requiring justification.
