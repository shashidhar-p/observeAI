# Data Model: Multi-Agent AI Observability & RCA System

**Branch**: `001-multi-agent-rca` | **Date**: 2025-12-28

## Entity Overview

```
┌─────────────┐     1:N     ┌─────────────┐     1:1     ┌─────────────┐
│    Alert    │────────────▶│   Incident  │────────────▶│  RCAReport  │
└─────────────┘             └─────────────┘             └─────────────┘
      │                           │                           │
      │                           │                           │
      ▼                           ▼                           ▼
 AlertManager              Correlation                  Analysis
   Webhook                   Engine                      Agent
```

## Entities

### Alert

Represents an incoming notification from Alert Manager.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Internal unique identifier |
| `fingerprint` | String(64) | Unique, indexed | Alert Manager fingerprint for deduplication |
| `alertname` | String(255) | Required | Name of the alert rule |
| `severity` | Enum | Required | `critical`, `warning`, `info` |
| `status` | Enum | Required | `firing`, `resolved` |
| `labels` | JSONB | Required | Key-value pairs (service, pod, namespace, etc.) |
| `annotations` | JSONB | Optional | Description, runbook_url, summary |
| `starts_at` | Timestamp | Required | When the alert started firing |
| `ends_at` | Timestamp | Nullable | When the alert resolved (null if still firing) |
| `generator_url` | String(2048) | Optional | Link to the alert source |
| `incident_id` | UUID | FK → Incident, nullable | Associated incident (null if not yet correlated) |
| `received_at` | Timestamp | Required, default NOW | When system received the alert |
| `created_at` | Timestamp | Required, default NOW | Record creation time |
| `updated_at` | Timestamp | Required, auto-update | Record last update time |

**Indexes**:
- `idx_alert_fingerprint` on `fingerprint` (unique)
- `idx_alert_incident` on `incident_id`
- `idx_alert_starts_at` on `starts_at`
- `idx_alert_labels_service` on `labels->>'service'`

**Validation Rules**:
- `fingerprint` must be non-empty
- `starts_at` must be before or equal to `received_at`
- `ends_at` must be after `starts_at` when present

---

### Incident

A correlated group of related alerts representing a single operational issue.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Unique incident identifier |
| `title` | String(500) | Required | Human-readable incident title |
| `status` | Enum | Required | `open`, `analyzing`, `resolved`, `closed` |
| `severity` | Enum | Required | Highest severity from correlated alerts |
| `primary_alert_id` | UUID | FK → Alert, nullable | The root cause alert |
| `correlation_reason` | String(1000) | Optional | Why alerts were grouped |
| `affected_services` | Array[String] | Computed | List of affected service names |
| `affected_labels` | JSONB | Computed | Common labels across alerts |
| `started_at` | Timestamp | Required | Earliest alert start time |
| `resolved_at` | Timestamp | Nullable | When incident was resolved |
| `created_at` | Timestamp | Required, default NOW | Record creation time |
| `updated_at` | Timestamp | Required, auto-update | Record last update time |

**Indexes**:
- `idx_incident_status` on `status`
- `idx_incident_started_at` on `started_at`
- `idx_incident_severity` on `severity`

**State Transitions**:
```
                 ┌─────────────────┐
                 │      open       │ ← Initial state
                 └────────┬────────┘
                          │ RCA agent starts
                          ▼
                 ┌─────────────────┐
                 │    analyzing    │
                 └────────┬────────┘
                          │ Analysis complete
              ┌───────────┴───────────┐
              ▼                       ▼
     ┌─────────────────┐     ┌─────────────────┐
     │    resolved     │     │     closed      │ ← Manual close
     └────────┬────────┘     └─────────────────┘
              │ Manual close
              ▼
     ┌─────────────────┐
     │     closed      │
     └─────────────────┘
```

**Validation Rules**:
- Must have at least one associated alert
- `primary_alert_id` must reference an alert belonging to this incident
- `resolved_at` can only be set when all alerts are resolved

---

### RCAReport

The analysis output containing root cause identification and remediation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Unique report identifier |
| `incident_id` | UUID | FK → Incident, unique | One report per incident |
| `root_cause` | Text | Required | Identified root cause description |
| `confidence_score` | Integer | Required, 0-100 | Confidence in root cause (percentage) |
| `summary` | Text | Required | Executive summary of findings |
| `timeline` | JSONB | Required | Chronological event sequence |
| `evidence` | JSONB | Required | Supporting logs and metrics |
| `remediation_steps` | JSONB | Required | Array of remediation suggestions |
| `analysis_metadata` | JSONB | Optional | LLM tokens used, duration, model version |
| `status` | Enum | Required | `pending`, `complete`, `failed` |
| `error_message` | Text | Nullable | Error details if status is `failed` |
| `started_at` | Timestamp | Required | When analysis began |
| `completed_at` | Timestamp | Nullable | When analysis finished |
| `created_at` | Timestamp | Required, default NOW | Record creation time |
| `updated_at` | Timestamp | Required, auto-update | Record last update time |

**Indexes**:
- `idx_rca_incident` on `incident_id` (unique)
- `idx_rca_status` on `status`
- `idx_rca_completed_at` on `completed_at`

**JSONB Structures**:

```json
// timeline
[
  {
    "timestamp": "2025-01-15T10:30:00Z",
    "event": "Disk usage exceeded 90% threshold",
    "source": "alert",
    "alert_id": "uuid"
  },
  {
    "timestamp": "2025-01-15T10:32:00Z",
    "event": "Service payment-api OOMKilled",
    "source": "alert",
    "alert_id": "uuid"
  }
]

// evidence
{
  "logs": [
    {
      "timestamp": "2025-01-15T10:31:45Z",
      "message": "Cannot write to /var/log: No space left on device",
      "source": "loki",
      "labels": {"service": "payment-api", "pod": "payment-api-abc123"}
    }
  ],
  "metrics": [
    {
      "name": "node_filesystem_avail_bytes",
      "value": 0,
      "timestamp": "2025-01-15T10:30:00Z",
      "labels": {"device": "/dev/sda1", "mountpoint": "/var/log"}
    }
  ]
}

// remediation_steps
[
  {
    "priority": "immediate",
    "action": "Clear old log files from /var/log",
    "command": "find /var/log -name '*.log.*' -mtime +7 -delete",
    "risk": "low"
  },
  {
    "priority": "long_term",
    "action": "Implement log rotation policy",
    "description": "Configure logrotate to prevent future disk exhaustion",
    "risk": "low"
  }
]
```

**Validation Rules**:
- `confidence_score` must be between 0 and 100
- `evidence` must contain at least one log or metric entry
- `remediation_steps` must contain at least one item
- `completed_at` required when status is `complete`

---

### TelemetrySnapshot (Embedded in RCAReport)

Captured telemetry data for the incident timeframe. Stored as part of RCAReport evidence.

| Field | Type | Description |
|-------|------|-------------|
| `query` | String | LogQL or PromQL query used |
| `source` | Enum | `loki`, `cortex` |
| `time_range` | Object | `{start: timestamp, end: timestamp}` |
| `result_count` | Integer | Number of results returned |
| `data` | JSONB | Actual log lines or metric values |
| `truncated` | Boolean | Whether results were truncated |

---

## Enumerations

### AlertSeverity
```
critical  - Immediate action required
warning   - Attention needed soon
info      - Informational, no action required
```

### AlertStatus
```
firing    - Alert is currently active
resolved  - Alert condition no longer true
```

### IncidentStatus
```
open       - Incident created, awaiting analysis
analyzing  - RCA agent is processing
resolved   - Root cause identified and incident resolved
closed     - Manually closed by operator
```

### RCAReportStatus
```
pending   - Analysis queued or in progress
complete  - Analysis finished successfully
failed    - Analysis failed (see error_message)
```

---

## Relationships Summary

| Relationship | Type | Description |
|--------------|------|-------------|
| Alert → Incident | Many-to-One | Multiple alerts can belong to one incident |
| Incident → RCAReport | One-to-One | Each incident has exactly one RCA report |
| Incident → Alert (primary) | One-to-One | One alert is designated as root cause |

---

## POC Simplifications

For the POC phase, the following simplifications apply:

1. **No Incident entity initially**: Each alert maps directly to an RCAReport (1:1)
2. **Correlation deferred**: Multi-alert correlation is a production feature
3. **Simplified evidence structure**: May store raw text instead of structured JSONB initially

POC Entity Relationship:
```
┌─────────────┐     1:1     ┌─────────────┐
│    Alert    │────────────▶│  RCAReport  │
└─────────────┘             └─────────────┘
```
