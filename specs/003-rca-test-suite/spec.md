# Feature Specification: Comprehensive RCA Test Suite

**Feature Branch**: `003-rca-test-suite`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "Comprehensive Test Suite for ObserveAI Multi-Agent RCA System - covering multi-alert ingestion, multi-incident correlation, RCA agent execution, tool calling (Loki queries, Cortex queries), report generation, webhook handling, API endpoints, database operations, and edge cases like alert deduplication, incident merging, concurrent RCA execution, error handling, and retry logic"

## Clarifications

### Session 2026-01-03

- Q: What mocking approach should integration tests use for external AI APIs? → A: Use live AI API calls with test prompts (real endpoints)
- Q: What is the maximum number of concurrent RCA executions the system should support? → A: 3 concurrent executions (conservative)
- Q: What similarity threshold should semantic correlation use? → A: 70% similarity threshold (balanced)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alert Ingestion & Webhook Handling (Priority: P1)

As a DevOps engineer, I need to verify that AlertManager webhooks correctly ingest alerts into the system so that no alerts are lost and all are properly stored.

**Why this priority**: Alert ingestion is the entry point for the entire RCA system. If alerts don't arrive or are malformed, nothing else works.

**Independent Test**: Can be fully tested by sending mock AlertManager payloads to the webhook endpoint and verifying alerts appear in the database with correct attributes.

**Acceptance Scenarios**:

1. **Given** AlertManager sends a firing alert, **When** the webhook receives it, **Then** the alert is stored with status "firing" and all labels preserved
2. **Given** AlertManager sends a resolved alert, **When** the webhook receives it, **Then** the corresponding alert status is updated to "resolved"
3. **Given** AlertManager sends multiple alerts in a batch, **When** the webhook receives them, **Then** all alerts are stored individually with correct timestamps
4. **Given** AlertManager sends a duplicate alert (same fingerprint), **When** the webhook receives it, **Then** the system deduplicates and updates the existing alert
5. **Given** AlertManager sends malformed JSON, **When** the webhook receives it, **Then** the system returns 400 error and logs the issue without crashing

---

### User Story 2 - Multi-Alert Correlation into Incidents (Priority: P1)

As a DevOps engineer, I need alerts to be automatically grouped into incidents based on time proximity and label similarity so that I can address related issues together.

**Why this priority**: Correlation is fundamental to reducing alert fatigue and enabling meaningful RCA across related alerts.

**Independent Test**: Can be fully tested by ingesting multiple related alerts within a time window and verifying they are grouped into a single incident.

**Acceptance Scenarios**:

1. **Given** two alerts with matching service labels arrive within the correlation window, **When** correlation runs, **Then** both alerts belong to the same incident
2. **Given** two alerts with different service labels arrive within the correlation window, **When** correlation runs, **Then** each alert creates a separate incident
3. **Given** an alert arrives after an incident is already created for the same service, **When** within the correlation window, **Then** the alert is added to the existing incident
4. **Given** an alert arrives after the correlation window has passed, **When** for the same service, **Then** a new incident is created
5. **Given** semantic correlation is enabled, **When** alerts have semantically similar error messages, **Then** they are correlated even with slightly different labels

---

### User Story 3 - RCA Agent Execution (Priority: P1)

As a DevOps engineer, I need the AI agent to automatically analyze incidents and generate root cause analysis so that I can quickly understand what went wrong.

**Why this priority**: RCA generation is the core value proposition of the system.

**Independent Test**: Can be fully tested by triggering RCA on a test incident and verifying the agent calls appropriate tools and generates a meaningful report.

**Acceptance Scenarios**:

1. **Given** an incident with firing alerts, **When** RCA is triggered, **Then** the agent queries relevant logs and metrics
2. **Given** the agent needs log data, **When** it calls the Loki query tool, **Then** it receives structured log results
3. **Given** the agent needs metrics data, **When** it calls the Cortex query tool, **Then** it receives time-series metric results
4. **Given** the agent completes analysis, **When** it generates a report, **Then** the report contains summary, root cause, affected services, and remediation steps
5. **Given** an incident with multiple correlated alerts, **When** RCA runs, **Then** the analysis considers all alerts in the incident

---

### User Story 4 - Loki Log Query Tool (Priority: P2)

As the RCA agent, I need to query Loki for relevant logs so that I can analyze error patterns and stack traces.

**Why this priority**: Log analysis is essential for root cause determination but depends on the agent being functional first.

**Independent Test**: Can be fully tested by calling the Loki tool with various LogQL queries and verifying correct results are returned.

**Acceptance Scenarios**:

1. **Given** a valid LogQL query, **When** the tool executes, **Then** matching log entries are returned with timestamps and labels
2. **Given** a time range filter, **When** the tool executes, **Then** only logs within that range are returned
3. **Given** a service label filter, **When** the tool executes, **Then** only logs from that service are returned
4. **Given** Loki is unavailable, **When** the tool executes, **Then** a graceful error is returned without crashing the agent
5. **Given** the query returns too many results, **When** limits are applied, **Then** results are truncated with indication of more available

---

### User Story 5 - Cortex Metrics Query Tool (Priority: P2)

As the RCA agent, I need to query Cortex for relevant metrics so that I can identify performance anomalies and resource issues.

**Why this priority**: Metrics analysis complements log analysis for comprehensive RCA.

**Independent Test**: Can be fully tested by calling the Cortex tool with PromQL queries and verifying time-series data is returned.

**Acceptance Scenarios**:

1. **Given** a valid PromQL query, **When** the tool executes, **Then** time-series data is returned with values and timestamps
2. **Given** a time range, **When** the tool executes, **Then** only data within that range is returned
3. **Given** a query for CPU/memory metrics, **When** the tool executes, **Then** resource utilization data is returned
4. **Given** Cortex is unavailable, **When** the tool executes, **Then** a graceful error is returned
5. **Given** the query matches no data, **When** the tool executes, **Then** an empty result is returned with appropriate message

---

### User Story 6 - Report Generation & Storage (Priority: P2)

As a DevOps engineer, I need RCA reports to be stored and retrievable so that I can review past analyses and share with team members.

**Why this priority**: Reports are the output of RCA and must be accessible for the system to provide value.

**Independent Test**: Can be fully tested by generating a report, storing it, and retrieving it via API.

**Acceptance Scenarios**:

1. **Given** RCA completes, **When** the report is generated, **Then** it is stored with incident reference and timestamp
2. **Given** a stored report, **When** retrieved by ID, **Then** the full report content is returned
3. **Given** multiple reports exist, **When** listing reports, **Then** they are returned with pagination and filtering options
4. **Given** a report export request, **When** format is JSON, **Then** the report is returned as structured JSON
5. **Given** a report export request, **When** format is Markdown, **Then** the report is returned as formatted Markdown

---

### User Story 7 - API Endpoints (Priority: P2)

As a DevOps engineer, I need REST API endpoints to query alerts, incidents, and reports so that I can integrate with other tools and dashboards.

**Why this priority**: APIs enable integration and programmatic access to the system.

**Independent Test**: Can be fully tested by calling each API endpoint and verifying correct responses.

**Acceptance Scenarios**:

1. **Given** alerts exist in the database, **When** GET /api/v1/alerts is called, **Then** alerts are returned with pagination
2. **Given** a specific alert ID, **When** GET /api/v1/alerts/{id} is called, **Then** the alert details are returned
3. **Given** incidents exist, **When** GET /api/v1/incidents is called, **Then** incidents are returned with their alert counts
4. **Given** a specific incident ID, **When** GET /api/v1/incidents/{id} is called, **Then** the incident with all alerts is returned
5. **Given** reports exist, **When** GET /api/v1/reports is called, **Then** reports are returned with metadata
6. **Given** filter parameters, **When** applied to list endpoints, **Then** only matching items are returned

---

### User Story 8 - Concurrent RCA Execution (Priority: P3)

As a DevOps engineer, I need the system to handle multiple simultaneous RCA executions so that incidents are analyzed promptly even during outage storms.

**Why this priority**: Concurrency is important for real-world usage but is an optimization on top of basic functionality.

**Independent Test**: Can be fully tested by triggering RCA on multiple incidents simultaneously and verifying all complete without interference.

**Acceptance Scenarios**:

1. **Given** two incidents trigger RCA simultaneously, **When** both execute, **Then** both complete with separate reports
2. **Given** many incidents during an outage, **When** RCA queue fills, **Then** incidents are processed in priority order
3. **Given** concurrent RCA executions, **When** accessing shared resources, **Then** no data corruption or race conditions occur
4. **Given** agent rate limits are approached, **When** RCA is queued, **Then** execution is throttled gracefully

---

### User Story 9 - Error Handling & Retry Logic (Priority: P3)

As a DevOps engineer, I need the system to gracefully handle errors and retry transient failures so that temporary issues don't cause permanent data loss.

**Why this priority**: Robustness is critical for production but builds on top of happy-path functionality.

**Independent Test**: Can be fully tested by simulating failures at various points and verifying recovery behavior.

**Acceptance Scenarios**:

1. **Given** database connection fails temporarily, **When** operation is retried, **Then** it succeeds after reconnection
2. **Given** Loki/Cortex times out, **When** agent tool call fails, **Then** agent continues with partial data and notes the gap
3. **Given** AI API returns rate limit error, **When** RCA is running, **Then** execution pauses and retries with backoff
4. **Given** webhook receives invalid data, **When** processing fails, **Then** error is logged and 4xx response returned
5. **Given** critical failure during RCA, **When** agent cannot recover, **Then** incident is marked for manual review

---

### User Story 10 - Database Operations (Priority: P3)

As a system administrator, I need database operations to be reliable and efficient so that the system performs well under load.

**Why this priority**: Database reliability is foundational but is typically handled by the ORM and tested indirectly through other tests.

**Independent Test**: Can be fully tested by performing CRUD operations and verifying data integrity.

**Acceptance Scenarios**:

1. **Given** an alert is created, **When** queried immediately, **Then** it is retrievable with all fields
2. **Given** an incident is updated, **When** alerts are added, **Then** the relationship is persisted correctly
3. **Given** a report is stored, **When** the incident is deleted, **Then** cascade behavior is applied correctly
4. **Given** concurrent writes to same incident, **When** updates conflict, **Then** optimistic locking prevents data loss
5. **Given** large query results, **When** pagination is used, **Then** memory usage remains bounded

---

### Edge Cases

- What happens when AlertManager sends alerts with missing required fields?
- How does the system handle extremely long alert labels or annotation values?
- What happens when two incidents should be merged after initial creation?
- How does semantic correlation handle non-English error messages?
- What happens when Loki returns logs in unexpected format?
- How does the system handle clock skew between AlertManager and the server?
- What happens when RCA is triggered on an incident that's already being analyzed?
- How does the system handle alerts with future timestamps?
- What happens when the AI model returns malformed JSON in tool calls?
- How does the system recover from a crash mid-RCA execution?

## Requirements *(mandatory)*

### Functional Requirements

**Alert Ingestion**
- **FR-001**: System MUST accept AlertManager webhook payloads conforming to the standard AlertManager format
- **FR-002**: System MUST deduplicate alerts based on fingerprint to prevent duplicate entries
- **FR-003**: System MUST preserve all alert labels and annotations during ingestion
- **FR-004**: System MUST update alert status when resolved notifications arrive
- **FR-005**: System MUST handle batch alerts (multiple alerts in single payload)

**Correlation**
- **FR-006**: System MUST correlate alerts into incidents based on configurable time window (default 5 minutes)
- **FR-007**: System MUST correlate alerts with matching service/namespace labels into same incident
- **FR-008**: System MUST support semantic correlation based on error message similarity (70% threshold)
- **FR-009**: System MUST allow manual correlation of alerts into existing incidents

**RCA Agent**
- **FR-010**: System MUST automatically trigger RCA when new incidents are created
- **FR-011**: System MUST provide Loki query tool for log analysis during RCA
- **FR-012**: System MUST provide Cortex query tool for metrics analysis during RCA
- **FR-013**: System MUST generate structured RCA reports with summary, root cause, and remediation
- **FR-014**: System MUST support configurable RCA expert context/prompts

**Reports**
- **FR-015**: System MUST store RCA reports linked to their source incidents
- **FR-016**: System MUST support report export in JSON and Markdown formats
- **FR-017**: System MUST include confidence scores and evidence in reports

**API**
- **FR-018**: System MUST provide REST API for querying alerts with filtering and pagination
- **FR-019**: System MUST provide REST API for querying incidents with filtering and pagination
- **FR-020**: System MUST provide REST API for querying and exporting reports
- **FR-021**: System MUST provide health check endpoints for monitoring

**Error Handling**
- **FR-022**: System MUST retry transient failures with exponential backoff
- **FR-023**: System MUST log all errors with sufficient context for debugging
- **FR-024**: System MUST gracefully degrade when external services are unavailable
- **FR-025**: System MUST return appropriate HTTP status codes for different error types

**Concurrency**
- **FR-026**: System MUST handle concurrent alert ingestion without data loss
- **FR-027**: System MUST handle up to 3 concurrent RCA executions without interference
- **FR-028**: System MUST implement rate limiting for AI API calls

### Key Entities

- **Alert**: Individual alert from AlertManager with labels, annotations, status, timestamps, and fingerprint
- **Incident**: Group of correlated alerts representing a single issue, with status and lifecycle timestamps
- **RCAReport**: Analysis output containing summary, root cause determination, affected services, evidence, and remediation steps
- **CorrelationRule**: Configuration for how alerts are grouped, including time window and label matching rules

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Test Coverage**
- **SC-001**: Unit test coverage reaches at least 80% for all service modules
- **SC-002**: Integration test coverage reaches at least 70% for API endpoints
- **SC-003**: All user story acceptance scenarios have corresponding automated tests
- **SC-004**: All edge cases have corresponding test cases with expected behavior documented

**Reliability**
- **SC-005**: Alert ingestion succeeds for 99.9% of valid payloads under normal operation
- **SC-006**: No data loss occurs during concurrent operations (verified by stress tests)
- **SC-007**: System recovers gracefully from external service failures within 30 seconds

**Performance**
- **SC-008**: Alert ingestion completes in under 100ms for single alerts
- **SC-009**: Correlation runs complete in under 1 second for incidents with up to 50 alerts
- **SC-010**: API list endpoints return results in under 500ms for up to 1000 items

**Quality**
- **SC-011**: All tests pass in CI/CD pipeline before merge
- **SC-012**: No flaky tests (tests that fail intermittently without code changes)
- **SC-013**: Test execution completes in under 5 minutes for the full suite

## Assumptions

- AlertManager webhook format follows the standard Prometheus AlertManager specification
- Loki and Cortex APIs follow their documented query interfaces
- The AI model (Claude/Gemini) is available with standard rate limits
- PostgreSQL is used as the primary database with asyncpg driver
- Tests will use mocking for external services (Loki, Cortex) in unit tests; AI APIs are mocked only in unit tests
- Integration tests use live AI API calls with test prompts for realistic RCA validation
- Integration tests use containerized versions of Loki, Cortex, and database dependencies
- The correlation window default of 5 minutes is appropriate for most use cases
- Test data fixtures will be created to represent realistic alert patterns
