# Feature Specification: Multi-Agent AI Observability & RCA System

**Feature Branch**: `001-multi-agent-rca`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Multi-agent AI system for reactive observability and automated Root Cause Analysis (RCA) integrating with Loki, Node Exporter, and Alert Manager"

## Overview

An intelligent observability platform that automatically analyzes infrastructure alerts, correlates related incidents, extracts relevant telemetry data, and produces actionable Root Cause Analysis reports with remediation recommendations.

## Phased Implementation

### Phase 1: POC (Proof of Concept) - COMPLETED

**Goal**: Validate core RCA capability with minimal complexity

| Aspect | POC Approach |
|--------|--------------|
| **Language** | Python 3.11+ |
| **Agent Architecture** | Single unified agent with multiple tools |
| **LLM Integration** | Multi-provider: Claude, Gemini, Ollama (local) |
| **Deployment** | Docker Compose |
| **Storage** | PostgreSQL |
| **Scope** | Multi-alert correlation + RCA with semantic analysis |

**POC Deliverables** (All Completed):
- Webhook receiver for Alert Manager
- Single RCA agent with Loki and Cortex query tools
- Multi-provider LLM support (Claude, Gemini, Ollama)
- LLM-based semantic alert correlation
- Full monitoring stack (Prometheus, Alertmanager, Node Exporter)
- Custom alert rules (network, host, service alerts)
- Real-time React dashboard
- Detailed remediation with shell commands
- Promtail for real system log collection
- RCA report generation with confidence scoring

### Phase 2: Production

**Goal**: Scale to production workloads with full feature set

| Aspect | Production Approach |
|--------|---------------------|
| **Language** | Go |
| **Agent Architecture** | Three specialized agents (Orchestrator, Data Collection, RCA) |
| **LLM Integration** | Claude API with native tool use |
| **Communication** | Message queue (Redis) for inter-agent coordination |
| **Deployment** | Docker → Kubernetes |
| **Storage** | PostgreSQL |
| **Scope** | Full multi-alert correlation and RCA |

**Production Deliverables**:
- High-throughput alert ingestion
- Multi-alert correlation
- Distributed agent architecture
- Full API with history and search
- Operator feedback loop

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Alert Triage (Priority: P1)

As an SRE engineer, when an alert fires from Alert Manager, I want the system to automatically analyze the alert, gather relevant context, and produce an initial RCA report so that I can quickly understand the issue without manually querying multiple systems.

**Why this priority**: This is the core value proposition - reducing mean-time-to-resolution (MTTR) by automating the initial investigation phase that typically consumes 30-60% of incident response time.

**Independent Test**: Can be fully tested by triggering a test alert via Alert Manager webhook and verifying an RCA report is generated within the expected timeframe.

**Acceptance Scenarios**:

1. **Given** Alert Manager is configured with a webhook to the system, **When** a critical alert fires (e.g., high CPU on server-01), **Then** the system receives the alert within 5 seconds and begins processing.

2. **Given** an alert has been received, **When** the Orchestrator Agent analyzes it, **Then** it correctly identifies the alert type, affected resources, and severity level.

3. **Given** alert context has been established, **When** the Data Collection Agent queries Loki and the metrics backend, **Then** it retrieves logs and metrics from a configurable time window (default: 15 minutes before alert to current time).

4. **Given** telemetry data has been collected, **When** the RCA Agent analyzes it, **Then** it produces a report containing: probable root cause, confidence score (0-100%), supporting evidence, and remediation steps.

---

### User Story 2 - Multi-Alert Correlation (Priority: P1)

As an SRE engineer, when multiple related alerts fire in succession (e.g., disk full, then service crash, then health check failure), I want the system to correlate these as a single incident and identify the primary root cause versus secondary symptoms.

**Why this priority**: Alert storms during outages are common and create cognitive overload. Correlating alerts into coherent incidents is essential for effective RCA.

**Independent Test**: Can be tested by triggering a sequence of related alerts and verifying they are grouped into a single incident with correct root cause identification.

**Acceptance Scenarios**:

1. **Given** the system has received alert A (disk usage > 90%), **When** alerts B (service OOMKilled) and C (health check failed) arrive within a correlation window, **Then** all three are grouped as a single incident.

2. **Given** correlated alerts exist, **When** the Orchestrator Agent analyzes them, **Then** it identifies the chronologically first or causally primary alert (disk full) as the root cause and others as symptoms.

3. **Given** a correlated incident, **When** the RCA report is generated, **Then** it presents a timeline showing the cascade of events and their causal relationships.

---

### User Story 3 - Intelligent Log & Metric Extraction (Priority: P2)

As an SRE engineer, I want the system to intelligently determine which logs and metrics are relevant to an alert based on context (affected service, labels, historical patterns) rather than pulling everything.

**Why this priority**: Efficient data extraction reduces noise in RCA reports and minimizes load on telemetry backends.

**Independent Test**: Can be tested by sending alerts with specific labels and verifying the system queries only relevant log streams and metric series.

**Acceptance Scenarios**:

1. **Given** an alert with labels `{service="payment-api", pod="payment-api-xyz"}`, **When** the Data Collection Agent runs, **Then** it queries Loki for logs matching those labels plus related infrastructure (node, namespace).

2. **Given** a service alert, **When** metrics are queried, **Then** the system retrieves relevant metrics (CPU, memory, network, error rates) for the affected service and its dependencies.

3. **Given** high-cardinality data, **When** queries are executed, **Then** the system applies appropriate sampling or aggregation to stay within query limits.

---

### User Story 4 - Remediation Suggestions (Priority: P2)

As an SRE engineer, I want the RCA report to include actionable remediation steps specific to the identified root cause so that I can resolve issues faster.

**Why this priority**: Identifying root cause is only half the value; providing remediation accelerates resolution.

**Independent Test**: Can be tested by verifying that RCA reports for known issue types include relevant, actionable remediation steps.

**Acceptance Scenarios**:

1. **Given** the root cause is identified as "disk space exhaustion on /var/log", **When** the RCA report is generated, **Then** it includes remediation steps such as "Clear old logs", "Increase disk allocation", "Configure log rotation".

2. **Given** a memory leak is identified, **When** remediation is suggested, **Then** it includes both immediate actions (restart service) and long-term fixes (investigate memory growth patterns).

3. **Given** the system has historical data on similar incidents, **When** generating remediation, **Then** it references past successful resolutions if available.

---

### User Story 5 - RCA Report Access & History (Priority: P3)

As an SRE engineer, I want to view current and historical RCA reports through a simple interface so that I can reference past incidents and track patterns.

**Why this priority**: Historical context improves future incident response and enables trend analysis.

**Independent Test**: Can be tested by generating multiple RCA reports and verifying they can be retrieved and searched.

**Acceptance Scenarios**:

1. **Given** multiple RCA reports have been generated, **When** I query the system, **Then** I can list reports filtered by time range, service, or severity.

2. **Given** an RCA report ID, **When** I request it, **Then** I receive the full report including logs, metrics, analysis, and remediation.

3. **Given** a service name, **When** I query historical incidents, **Then** I can see patterns and recurring issues.

---

### Edge Cases

- What happens when Alert Manager sends duplicate alerts? System deduplicates based on alert fingerprint.
- What happens when Loki or metrics backend is unreachable? System retries with exponential backoff, generates partial RCA with available data, and notes data gaps.
- What happens during an alert storm (>100 alerts/minute)? System applies rate limiting, prioritizes by severity, and batches low-priority alerts.
- What happens when the LLM rate limit is reached? System queues requests and processes them as capacity becomes available.
- How does system handle alerts with missing labels? System logs warning, attempts best-effort analysis with available metadata.
- What happens when correlation window overlaps multiple incidents? System uses graph-based analysis to separate distinct incident clusters.

## Requirements *(mandatory)*

### Functional Requirements

**Alert Ingestion & Processing**
- **FR-001**: System MUST expose a webhook endpoint compatible with Alert Manager's webhook receiver format
- **FR-002**: System MUST acknowledge alert receipt within 2 seconds to prevent Alert Manager retries
- **FR-003**: System MUST persist received alerts for at least 30 days for historical analysis
- **FR-004**: System MUST deduplicate alerts based on Alert Manager's fingerprint field

**Alert Correlation**
- **FR-005**: System MUST correlate alerts occurring within a configurable time window (default: 5 minutes)
- **FR-006**: System MUST correlate alerts sharing common labels (service, namespace, node, etc.)
- **FR-007**: System MUST identify primary root cause alert vs. secondary symptom alerts
- **FR-008**: System MUST support manual correlation override by operators

**Data Collection**
- **FR-009**: System MUST query Loki for logs using LogQL based on alert labels and time range
- **FR-010**: System MUST query the metrics backend using PromQL for relevant metrics
- **FR-011**: System MUST handle pagination for large result sets from Loki
- **FR-012**: System MUST respect rate limits on telemetry backends with exponential backoff
- **FR-013**: System MUST cache frequently accessed data to reduce backend load
- **FR-014**: System MUST collect data from a configurable time window (default: 15 minutes before alert to 5 minutes after)

**RCA Analysis**
- **FR-015**: System MUST analyze collected logs for error patterns, exceptions, and anomalies
- **FR-016**: System MUST analyze metrics for threshold violations, trend changes, and correlations
- **FR-017**: System MUST generate a confidence score (0-100%) for the identified root cause
- **FR-018**: System MUST provide supporting evidence (specific log lines, metric values) for conclusions
- **FR-019**: System MUST generate human-readable RCA reports in structured format

**Remediation**
- **FR-020**: System MUST suggest at least one remediation step for identified root causes
- **FR-021**: System MUST categorize remediation as "immediate" vs "long-term"
- **FR-022**: System SHOULD learn from operator feedback on remediation effectiveness

**Agent Architecture**
- **FR-023**: POC MUST implement a single unified agent with multiple tools (query_loki, query_cortex, generate_report); Production MUST evolve to three specialized agents (Orchestrator, Data Collection, RCA Analysis)
- **FR-024**: POC uses synchronous in-process tool execution; Production agents MUST communicate through a message queue (Redis) for asynchronous, resilient communication
- **FR-025**: System MUST maintain context/state throughout the analysis workflow using LLM conversation history
- **FR-026**: System MUST handle tool execution failures gracefully with retry and fallback mechanisms
- **FR-032**: System MUST use Claude API with native tool use for LLM integration (no framework dependencies like LangChain)

**Reporting & API**
- **FR-027**: System MUST expose an API to retrieve RCA reports by ID
- **FR-028**: System MUST expose an API to list RCA reports with filtering (time, service, severity)
- **FR-029**: System MUST support RCA report export in JSON and Markdown formats

**Metrics Backend Integration**
- **FR-030**: System MUST integrate with Cortex for metrics queries (horizontally scalable, PromQL-compatible, long-term storage)
- **FR-031**: System MUST support PromQL for metrics queries (applicable to Prometheus/Cortex)

### Key Entities

- **Alert**: An incoming notification from Alert Manager containing severity, labels (service, pod, node), annotations (description, runbook), fingerprint, firing time, and status
- **Incident**: A correlated group of related alerts representing a single operational issue, with a designated primary alert and symptom alerts
- **RCAReport**: The analysis output containing root cause identification, confidence score, evidence (logs, metrics), timeline, and remediation steps
- **TelemetryData**: Collected logs from Loki and metrics from the TSDB within the incident timeframe
- **RemediationSuggestion**: Actionable steps to resolve the identified issue, categorized by urgency

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System generates initial RCA report within 2 minutes of alert receipt for 95% of incidents
- **SC-002**: System correctly correlates related alerts with 90% accuracy (measured against operator validation)
- **SC-003**: Root cause identification achieves 75% accuracy for known issue types (validated by operator feedback)
- **SC-004**: System handles 50 concurrent incidents without performance degradation
- **SC-005**: Mean-time-to-resolution (MTTR) for incidents analyzed by the system improves by 40% compared to manual investigation baseline
- **SC-006**: 80% of suggested remediations are rated "helpful" or "very helpful" by operators
- **SC-007**: System maintains 99.5% availability for alert ingestion
- **SC-008**: RCA reports contain actionable insights for 90% of incidents (not just "unknown cause")

## Additional Features Implemented (Beyond Original Spec)

### Multi-Provider LLM Support
- **Anthropic Claude**: Cloud-based, high-quality analysis
- **Google Gemini**: Free tier available (gemini-2.5-flash)
- **Ollama**: Local models (llama3.1:8b) for offline/privacy use
- Configurable via `LLM_PROVIDER` environment variable

### Full Observability Stack
Complete monitoring infrastructure included:
- **Prometheus**: Metrics scraping and alerting
- **Alertmanager**: Alert routing to RCA webhook (30s resolve timeout)
- **Node Exporter**: Host metrics (CPU, memory, disk, network)
- **Loki**: Log aggregation
- **Cortex**: Long-term metrics storage
- **Promtail**: System log collection (syslog, kern.log, journald)
- **Grafana**: Visualization dashboards

### Alert Rules
Pre-configured alert rules in `prometheus/alerts/`:
- **network_alerts.yml**: Interface down, flapping, traffic, errors, saturation
- **host_alerts.yml**: CPU, memory, disk space, load average
- **service_alerts.yml**: Target down, latency, error rates

### Semantic Alert Correlation
LLM-based correlation beyond simple label matching:
- Cross-datacenter correlation analysis
- Causal chain identification
- Primary root cause vs symptom detection

### React Dashboard
Real-time web UI at `http://localhost:3001`:
- Incident list with status indicators (Analyzing animation)
- RCA report viewer with confidence scores
- Correlated alerts visualization with timeline
- Remediation steps with copy-able commands
- **Search**: Filter incidents by title, correlation reason, or affected services
- **Status Filter**: Clickable status cards (Total, Open, Analyzing, RCA Complete, Resolved)
- **Severity Filter**: Dropdown to filter by critical/warning/info
- **Auto-refresh**: Configurable interval (Off, 5s, 10s, 30s, 1m)
- **Manual Refresh**: Button to refresh incidents on demand

### Incident Lifecycle Management
- **Analyzing Status**: Visible in UI during RCA processing with animated indicator
- **Auto-Resolution**: Incidents auto-resolve when all alerts transition to resolved
- **New Incidents for Re-firing Alerts**: When an alert re-fires after its incident was resolved, creates a NEW incident (not reopening old ones)
- **Status Flow**: OPEN → ANALYZING → OPEN (with RCA) → RESOLVED

### Configurable RCA Expert Context
Domain-specific expertise can be injected into the RCA agent:
- **RCA_EXPERT_CONTEXT**: Inline context via environment variable
- **RCA_EXPERT_CONTEXT_FILE**: Path to file with expert context (e.g., `prompts/network_engineer.md`)
- **Default**: Generic SRE without special domain context
- **Network Engineer Context**: Pre-built in `prompts/network_engineer.md` with:
  - veth pair behavior (linked interfaces)
  - Admin action vs failure detection
  - Bridge, TUN/TAP, VPN interface knowledge
  - Confidence scoring guidelines
  - Diagnostic command reference

### Enhanced Remediation
RCA reports include actionable shell commands:
- **Verification commands**: `ip link show`, `df -h`, `free -m`
- **Fix commands**: `sudo ip link set up`, `systemctl restart`
- **Validation commands**: `ping`, `curl`, status checks
- **Command Inference Fallback**: Auto-generates commands based on action text if LLM doesn't provide them

## Assumptions

1. **Existing Infrastructure**: Loki, Node Exporter, and Alert Manager are already deployed and operational
2. **Alert Quality**: Alerts from Alert Manager have meaningful labels and annotations
3. **Network Access**: The system has network access to query Loki and the metrics backend
4. **LLM Provider**: System will use Claude (Anthropic) with native tool use API - no framework dependencies
5. **Phased Deployment**:
   - POC: Docker Compose with Python, single agent, PostgreSQL
   - Production: Docker/Kubernetes with Go, multi-agent, PostgreSQL
6. **Language Choice**:
   - POC: Python for rapid prototyping and validation
   - Production: Go for performance, concurrency, and native observability stack integration
7. **Data Retention**: Loki and metrics backend retain data for at least 7 days
8. **Authentication**: Integration with existing observability stack uses service accounts/tokens
9. **Agent Framework**: No external agent frameworks (LangChain, etc.) - using Claude's native tool calling API for simplicity and control

## Constraints

1. **Cost Management**: LLM API costs must be monitored; system should optimize token usage
2. **Latency**: RCA must complete within reasonable time (target: 2 minutes) to be useful during incidents
3. **Existing Stack**: Must integrate with current tooling without requiring infrastructure changes
4. **Security**: System handles potentially sensitive log data; must follow data handling best practices

## Dependencies

1. **External Systems**: Loki (log queries), Alert Manager (webhooks), TSDB (metric queries)
2. **LLM Provider**: Requires API access to an LLM service for analysis
3. **Persistent Storage**: Requires a database for storing alerts, incidents, and RCA reports
