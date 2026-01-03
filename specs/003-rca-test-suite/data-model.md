# Data Model: RCA Test Suite

**Feature**: 003-rca-test-suite
**Date**: 2026-01-03

## Overview

This document defines the test data models and fixtures used throughout the RCA test suite.

---

## Core Entities (Existing)

The test suite validates the following existing entities:

### Alert

| Field | Type | Constraints | Test Coverage |
|-------|------|-------------|---------------|
| id | UUID | Primary key | CRUD operations |
| fingerprint | String(64) | Unique, not null | Deduplication tests |
| alertname | String(255) | Not null | Validation tests |
| severity | Enum | critical/warning/info | Filter tests |
| status | Enum | firing/resolved | Status transition tests |
| labels | JSONB | Not null, default {} | Label preservation tests |
| annotations | JSONB | Nullable | Annotation tests |
| starts_at | DateTime(tz) | Not null | Timestamp tests |
| ends_at | DateTime(tz) | Nullable | Resolution tests |
| generator_url | Text | Nullable | URL handling tests |
| incident_id | UUID FK | Nullable | Correlation tests |
| received_at | DateTime(tz) | Server default now() | Clock skew tests |

### Incident

| Field | Type | Constraints | Test Coverage |
|-------|------|-------------|---------------|
| id | UUID | Primary key | CRUD operations |
| title | String(500) | Not null | Title generation tests |
| status | Enum | open/analyzing/resolved/closed | State transition tests |
| severity | Enum | critical/warning/info | Aggregation tests |
| primary_alert_id | UUID FK | Nullable | Primary alert selection |
| correlation_reason | Text | Nullable | Correlation reason tests |
| affected_services | ARRAY(String) | Not null | Service extraction tests |
| affected_labels | JSONB | Nullable | Label merging tests |
| started_at | DateTime(tz) | Not null | Time window tests |
| resolved_at | DateTime(tz) | Nullable | Resolution tracking |
| rca_completed_at | DateTime(tz) | Nullable | RCA completion tests |

### RCAReport

| Field | Type | Constraints | Test Coverage |
|-------|------|-------------|---------------|
| id | UUID | Primary key | CRUD operations |
| incident_id | UUID FK | Unique, not null, cascade delete | One-to-one tests |
| root_cause | Text | Not null | Report content tests |
| confidence_score | Integer | 0-100, not null | Confidence validation |
| summary | Text | Not null | Summary generation |
| timeline | JSONB | Not null, default [] | Timeline structure |
| evidence | JSONB | Not null, default {} | Evidence collection |
| remediation_steps | JSONB | Not null, default [] | Remediation format |
| analysis_metadata | JSONB | Nullable | Metadata capture |
| status | Enum | pending/complete/failed | Status transition |
| error_message | Text | Nullable | Error handling |
| started_at | DateTime(tz) | Not null | Duration tracking |
| completed_at | DateTime(tz) | Nullable | Completion tests |

---

## Test Fixture Entities

### AlertManagerPayload

```python
@dataclass
class AlertManagerPayload:
    """AlertManager webhook payload structure."""
    receiver: str
    status: Literal["firing", "resolved"]
    alerts: list[AlertManagerAlert]
    groupLabels: dict[str, str]
    commonLabels: dict[str, str]
    commonAnnotations: dict[str, str]
    externalURL: str
    version: str = "4"
    groupKey: str = ""
```

### AlertManagerAlert

```python
@dataclass
class AlertManagerAlert:
    """Individual alert within AlertManager payload."""
    status: Literal["firing", "resolved"]
    labels: dict[str, str]  # Must include alertname
    annotations: dict[str, str]
    startsAt: str  # ISO 8601 datetime
    endsAt: str    # ISO 8601 datetime (or "0001-01-01T00:00:00Z" for firing)
    generatorURL: str
    fingerprint: str  # 16-char hex string
```

---

## Test Data Categories

### Fixture Files (tests/fixtures/)

| File | Purpose | User Story |
|------|---------|------------|
| `alert_single_firing.json` | Single firing alert | US1-Scenario1 |
| `alert_single_resolved.json` | Single resolved alert | US1-Scenario2 |
| `alert_batch_3.json` | Batch of 3 alerts | US1-Scenario3 |
| `alert_duplicate.json` | Duplicate fingerprint | US1-Scenario4 |
| `alert_malformed.json` | Invalid JSON structure | US1-Scenario5 |
| `alerts_same_service_2.json` | 2 alerts, same service | US2-Scenario1 |
| `alerts_different_services_2.json` | 2 alerts, different services | US2-Scenario2 |
| `alerts_outside_window.json` | Alert outside 5-min window | US2-Scenario4 |
| `alerts_semantic_similar.json` | 70%+ similarity messages | US2-Scenario5 |
| `incident_with_alerts.json` | Incident with 3 alerts | US3 testing |
| `loki_response_success.json` | Valid Loki query response | US4-Scenario1 |
| `loki_response_empty.json` | Empty Loki response | US4 edge case |
| `cortex_response_success.json` | Valid Cortex query response | US5-Scenario1 |
| `cortex_response_empty.json` | Empty Cortex response | US5-Scenario5 |
| `rca_report_complete.json` | Complete RCA report | US6 testing |

---

## Validation Rules

### Alert Validation

| Rule | Test Method |
|------|-------------|
| fingerprint required and unique | `test_fingerprint_required`, `test_fingerprint_duplicate` |
| alertname required | `test_alertname_required` |
| severity must be valid enum | `test_invalid_severity_rejected` |
| labels must be dict | `test_labels_type_validation` |
| starts_at required | `test_starts_at_required` |
| future timestamps handled | `test_future_timestamp_handling` |

### Incident Validation

| Rule | Test Method |
|------|-------------|
| title auto-generated from alerts | `test_title_generation` |
| severity derived from max alert severity | `test_severity_aggregation` |
| affected_services extracted from labels | `test_service_extraction` |
| status transitions validated | `test_invalid_transition_rejected` |

### Correlation Rules

| Rule | Test Method |
|------|-------------|
| 5-minute default window | `test_correlation_window_default` |
| service label matching | `test_service_label_correlation` |
| 70% semantic similarity threshold | `test_semantic_threshold_70` |
| namespace label matching | `test_namespace_correlation` |

---

## State Transitions

### Incident Status

```
       ┌──────────────────────────────────────┐
       │                                      │
       ▼                                      │
    [OPEN] ────────► [ANALYZING] ────┬───► [OPEN] (RCA complete/failed)
       │                             │
       │                             │
       ▼                             ▼
  [RESOLVED] ◄──────────────────────────────────── (all alerts resolved)
       │
       ▼
   [CLOSED] (manual close)
```

### RCAReport Status

```
[PENDING] ────► [COMPLETE] (analysis succeeded)
    │
    └─────────► [FAILED] (analysis error)
```

---

## Relationships

```
Alert *──────────────────────1 Incident
  │                              │
  │ incident_id FK               │ primary_alert_id FK
  │                              │
  └──────────────────────────────┘

Incident 1──────────────────0..1 RCAReport
             incident_id FK (unique, cascade delete)
```

---

## Index Coverage

Tests should verify query performance using these indexes:

| Index | Table | Test Purpose |
|-------|-------|--------------|
| idx_alert_fingerprint | alerts | Deduplication lookup |
| idx_alert_starts_at | alerts | Time range queries |
| idx_alert_labels_service | alerts | Service filtering |
| idx_incident_status | incidents | Status filtering |
| idx_incident_started_at | incidents | Time range queries |
| idx_incident_severity | incidents | Severity filtering |
| idx_rca_status | rca_reports | Status filtering |
| idx_rca_completed_at | rca_reports | Completion queries |
