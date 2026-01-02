# Tasks: Multi-Agent AI Observability & RCA System

**Input**: Design documents from `/specs/001-multi-agent-rca/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Not explicitly requested in specification. Implementation-focused tasks only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**POC Scope**: Full feature set including multi-alert correlation (US2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per plan.md (src/, tests/, docker/)
- [x] T002 Initialize Python project with pyproject.toml and dependencies (anthropic, fastapi, uvicorn, httpx, sqlalchemy, asyncpg, pydantic, alembic)
- [x] T003 [P] Create .env.example with required environment variables in project root
- [x] T004 [P] Configure ruff for linting and formatting in pyproject.toml
- [x] T005 [P] Create src/__init__.py and all package __init__.py files
- [x] T006 [P] Create docker/Dockerfile for Python application
- [x] T007 [P] Create docker/docker-compose.yaml with PostgreSQL, app service, and test Loki/Cortex stubs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T008 Implement configuration management in src/config.py (DATABASE_URL, LOKI_URL, CORTEX_URL, ANTHROPIC_API_KEY, CORRELATION_WINDOW_SECONDS)
- [x] T009 Create SQLAlchemy async engine and session factory in src/database.py
- [x] T010 Create base SQLAlchemy model with common fields (id, created_at, updated_at) in src/models/base.py
- [x] T011 [P] Create Pydantic base schemas for API responses in src/api/schemas.py (ErrorResponse, HealthResponse, ReadinessResponse)
- [x] T012 [P] Implement health check endpoints (/health, /health/ready) in src/api/routes.py
- [x] T013 Create FastAPI application with CORS and error handling in src/main.py
- [x] T014 Setup Alembic migrations framework in alembic/ directory
- [x] T015 Create initial database migration with common enums (AlertSeverity, AlertStatus, IncidentStatus, RCAReportStatus) in alembic/versions/

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automated Alert Triage (Priority: P1) MVP

**Goal**: Receive alerts from Alert Manager, query Loki/Cortex for context, and generate RCA reports automatically

**Independent Test**: Send POST to /webhooks/alertmanager with test alert payload → verify RCA report is created and accessible via /api/v1/reports/{id}

### Models for User Story 1

- [x] T016 [P] [US1] Create Alert SQLAlchemy model with all fields per data-model.md in src/models/alert.py
- [x] T017 [P] [US1] Create Incident SQLAlchemy model with all fields per data-model.md in src/models/incident.py
- [x] T018 [P] [US1] Create RCAReport SQLAlchemy model with all fields per data-model.md in src/models/rca_report.py
- [x] T019 [US1] Create Alembic migration for alerts, incidents, and rca_reports tables in alembic/versions/

### Schemas for User Story 1

- [x] T020 [P] [US1] Create AlertManagerWebhookPayload Pydantic schema per OpenAPI spec in src/api/schemas.py
- [x] T021 [P] [US1] Create Alert response Pydantic schema in src/api/schemas.py
- [x] T022 [P] [US1] Create Incident response Pydantic schema in src/api/schemas.py
- [x] T023 [P] [US1] Create RCAReport response Pydantic schema (including Evidence, Timeline, Remediation) in src/api/schemas.py

### External Clients for User Story 1

- [x] T024 [P] [US1] Implement LokiClient with query_range method in src/services/loki_client.py
- [x] T025 [P] [US1] Implement CortexClient with range_query method in src/services/cortex_client.py

### Agent Tools for User Story 1

- [x] T026 [P] [US1] Implement query_loki tool with JSON schema definition in src/tools/query_loki.py
- [x] T027 [P] [US1] Implement query_cortex tool with JSON schema definition in src/tools/query_cortex.py
- [x] T028 [P] [US1] Implement generate_report tool with structured output schema in src/tools/generate_report.py

### RCA Agent for User Story 1

- [x] T029 [US1] Implement RCAAgent class with tool registration and agentic loop in src/services/rca_agent.py
- [x] T030 [US1] Add system prompt for RCA analysis in src/services/rca_agent.py
- [x] T031 [US1] Implement tool execution dispatcher in src/services/rca_agent.py
- [x] T032 [US1] Add error handling and retry logic for Claude API calls in src/services/rca_agent.py

### Webhook Handler for User Story 1

- [x] T033 [US1] Implement webhook service with alert parsing and deduplication in src/services/webhook.py
- [x] T034 [US1] Implement POST /webhooks/alertmanager endpoint with async processing in src/api/routes.py
- [x] T035 [US1] Add background task to trigger RCA agent after alert storage in src/services/webhook.py

### Report Storage for User Story 1

- [x] T036 [US1] Implement alert CRUD operations in src/services/alert_service.py
- [x] T037 [US1] Implement incident CRUD operations in src/services/incident_service.py
- [x] T038 [US1] Implement RCA report CRUD operations in src/services/report_service.py
- [x] T039 [US1] Connect RCA agent output to report storage in src/services/rca_agent.py

**Checkpoint**: User Story 1 complete - can receive alerts, run RCA analysis, and store reports

---

## Phase 4: User Story 2 - Multi-Alert Correlation (Priority: P1)

**Goal**: Correlate multiple related alerts into a single incident and identify primary root cause vs symptoms

**Independent Test**: Send sequence of related alerts (disk full → OOM → health check fail) → verify all grouped as single incident with correct root cause identification

### Correlation Engine for User Story 2

- [x] T040 [US2] Implement correlation service with time-window grouping in src/services/correlation_service.py
- [x] T041 [US2] Add label-based correlation logic (service, namespace, node) in src/services/correlation_service.py
- [x] T042 [US2] Implement primary alert detection (chronological + causal analysis) in src/services/correlation_service.py
- [x] T043 [US2] Add correlation reason generation in src/services/correlation_service.py

### Webhook Integration for User Story 2

- [x] T044 [US2] Update webhook service to call correlation engine before RCA in src/services/webhook.py
- [x] T045 [US2] Implement incident creation/update logic on new alerts in src/services/webhook.py
- [x] T046 [US2] Add alert-to-incident linking in src/services/alert_service.py

### RCA Agent Updates for User Story 2

- [x] T047 [US2] Update RCA agent to accept incident (multiple alerts) as input in src/services/rca_agent.py
- [x] T048 [US2] Enhance system prompt for multi-alert analysis in src/services/rca_agent.py
- [x] T049 [US2] Add timeline generation from correlated alerts in src/services/rca_agent.py
- [x] T050 [US2] Implement causal chain analysis in report generation in src/tools/generate_report.py

### Incident Management for User Story 2

- [x] T051 [US2] Add incident status transitions (open → analyzing → resolved) in src/services/incident_service.py
- [x] T052 [US2] Implement affected_services computation from alert labels in src/services/incident_service.py
- [x] T053 [US2] Add manual correlation override endpoint POST /api/v1/incidents/{id}/correlate in src/api/routes.py

**Checkpoint**: User Story 2 complete - multi-alert correlation with causal analysis

---

## Phase 5: User Story 3 - Intelligent Log & Metric Extraction (Priority: P2)

**Goal**: Enhance data collection to query only relevant logs/metrics based on alert context

**Independent Test**: Send alert with specific labels → verify Loki/Cortex queries include matching label filters

### Implementation for User Story 3

- [x] T054 [US3] Implement label-based query builder for LogQL in src/tools/query_loki.py
- [x] T055 [US3] Implement label-based query builder for PromQL in src/tools/query_cortex.py
- [x] T056 [US3] Add service dependency detection from alert labels in src/services/rca_agent.py
- [x] T057 [US3] Implement query result sampling for high-cardinality data in src/services/loki_client.py
- [x] T058 [US3] Implement query result aggregation for metrics in src/services/cortex_client.py
- [x] T059 [US3] Add caching layer for frequently accessed queries in src/services/cache.py

**Checkpoint**: User Story 3 complete - intelligent, context-aware data extraction

---

## Phase 6: User Story 4 - Remediation Suggestions (Priority: P2)

**Goal**: Generate actionable remediation steps categorized as immediate vs long-term

**Independent Test**: Generate RCA report for known issue type (e.g., disk full) → verify remediation_steps contains specific, actionable suggestions

### Implementation for User Story 4

- [x] T060 [US4] Enhance system prompt with remediation generation guidelines in src/services/rca_agent.py
- [x] T061 [US4] Add remediation step schema validation in src/tools/generate_report.py
- [x] T062 [US4] Implement remediation categorization (immediate/long_term) in src/tools/generate_report.py
- [x] T063 [US4] Add risk assessment to remediation steps in src/tools/generate_report.py
- [x] T064 [US4] Enhance report output with structured remediation JSON in src/services/rca_agent.py

**Checkpoint**: User Story 4 complete - RCA reports include actionable remediation

---

## Phase 7: User Story 5 - RCA Report Access & History (Priority: P3)

**Goal**: Provide API access to current and historical RCA reports with filtering

**Independent Test**: Generate multiple RCA reports → verify GET /api/v1/reports returns paginated list with correct filtering

### Endpoints for User Story 5

- [x] T065 [P] [US5] Implement GET /api/v1/alerts endpoint with filtering in src/api/routes.py
- [x] T066 [P] [US5] Implement GET /api/v1/alerts/{alertId} endpoint in src/api/routes.py
- [x] T067 [P] [US5] Implement GET /api/v1/incidents endpoint with filtering in src/api/routes.py
- [x] T068 [P] [US5] Implement GET /api/v1/incidents/{incidentId} endpoint in src/api/routes.py
- [x] T069 [P] [US5] Implement GET /api/v1/reports endpoint with filtering in src/api/routes.py
- [x] T070 [P] [US5] Implement GET /api/v1/reports/{reportId} endpoint in src/api/routes.py
- [x] T071 [US5] Implement GET /api/v1/reports/{reportId}/export endpoint with JSON/Markdown formats in src/api/routes.py

### Query Filters for User Story 5

- [x] T072 [US5] Add query parameter parsing for alerts (status, severity, service, since, until) in src/api/routes.py
- [x] T073 [US5] Add query parameter parsing for incidents (status, severity, service) in src/api/routes.py
- [x] T074 [US5] Add query parameter parsing for reports (status, service, severity, min_confidence) in src/api/routes.py
- [x] T075 [US5] Implement pagination (limit, offset) for list endpoints in src/api/routes.py

### Export Functionality for User Story 5

- [x] T076 [US5] Implement Markdown report formatter in src/services/report_service.py
- [x] T077 [US5] Add content-type negotiation for export endpoint in src/api/routes.py

**Checkpoint**: User Story 5 complete - full API access to alerts, incidents, and reports

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T078 [P] Add structured logging with correlation IDs in src/main.py
- [x] T079 [P] Implement token usage tracking in RCA agent in src/services/rca_agent.py
- [x] T080 [P] Add request timing metrics to API endpoints in src/api/routes.py
- [x] T081 Update .env.example with all required configuration in project root
- [ ] T082 Add README.md with setup and usage instructions in project root
- [ ] T083 Validate docker-compose setup works end-to-end in docker/
- [ ] T084 Run quickstart.md validation scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (Phase 3): MVP - implement first
  - US2 (Phase 4): Depends on US1 (builds on alert/incident models)
  - US3 (Phase 5): Enhances US1/US2 data collection
  - US4 (Phase 6): Enhances US1/US2 remediation output
  - US5 (Phase 7): API access - can parallelize with US3/US4
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    │
    ▼
Phase 2: Foundational
    │
    ▼
Phase 3: US1 (MVP - Single Alert RCA)
    │
    ▼
Phase 4: US2 (Multi-Alert Correlation) ──────┐
    │                                         │
    ├──────────────┬──────────────┐          │
    ▼              ▼              ▼          │
Phase 5: US3   Phase 6: US4   Phase 7: US5   │
    │              │              │          │
    └──────────────┴──────────────┴──────────┘
                   │
                   ▼
            Phase 8: Polish
```

### Within Each User Story

- Models before services
- Services before endpoints
- Core implementation before enhancements
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
- T003, T004, T005, T006, T007 can all run in parallel

**Phase 2 (Foundational)**:
- T011, T012 can run in parallel after T010

**Phase 3 (US1)**:
- T016, T017, T018 can run in parallel (models)
- T020, T021, T022, T023 can run in parallel (schemas)
- T024, T025 can run in parallel (clients)
- T026, T027, T028 can run in parallel (tools)

**Phase 7 (US5)**:
- T065, T066, T067, T068, T069, T070 can all run in parallel

---

## Parallel Example: User Story 1 Models & Clients

```bash
# Launch all models together:
Task: "Create Alert SQLAlchemy model in src/models/alert.py"
Task: "Create Incident SQLAlchemy model in src/models/incident.py"
Task: "Create RCAReport SQLAlchemy model in src/models/rca_report.py"

# Launch all external clients together:
Task: "Implement LokiClient in src/services/loki_client.py"
Task: "Implement CortexClient in src/services/cortex_client.py"

# Launch all agent tools together:
Task: "Implement query_loki tool in src/tools/query_loki.py"
Task: "Implement query_cortex tool in src/tools/query_cortex.py"
Task: "Implement generate_report tool in src/tools/generate_report.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test end-to-end with sample alert
5. Deploy POC for feedback

### Full POC (All User Stories)

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Single-alert RCA works
3. Add User Story 2 → Test independently → Multi-alert correlation works
4. Add User Story 3 → Enhanced data collection
5. Add User Story 4 → Remediation suggestions
6. Add User Story 5 → Full API access
7. Each story adds value without breaking previous stories

### Deferred to Production

- **Go Migration**: Full rewrite for production scale
- **Redis Message Queue**: For multi-agent architecture
- **Three Specialized Agents**: Orchestrator, Data Collection, RCA Analysis

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US2 now included in POC with full Incident entity and correlation engine
- Avoid: vague tasks, same file conflicts, cross-story dependencies
