# API Contracts: RCA Test Suite

**Feature**: 003-rca-test-suite
**Date**: 2026-01-03

## Overview

This document defines the API contracts that the test suite validates.

---

## Health Endpoints

### GET /health

**Purpose**: Basic health check

**Response 200**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600
}
```

**Test Coverage**: `test_api_health.py::test_health_endpoint`

---

### GET /health/ready

**Purpose**: Readiness check with dependency status

**Response 200**:
```json
{
  "ready": true,
  "checks": {
    "database": true,
    "loki": true,
    "cortex": true,
    "llm": true
  }
}
```

**Response 503** (service unavailable):
```json
{
  "ready": false,
  "checks": {
    "database": true,
    "loki": false,
    "cortex": true,
    "llm": true
  }
}
```

**Test Coverage**: `test_api_health.py::test_readiness_all_healthy`, `test_api_health.py::test_readiness_partial_failure`

---

## Webhook Endpoints

### POST /webhooks/alertmanager

**Purpose**: Receive AlertManager webhooks

**Request Body** (AlertManager format):
```json
{
  "receiver": "observeai",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighCPU",
        "service": "api-gateway",
        "severity": "critical"
      },
      "annotations": {
        "summary": "CPU usage above 90%",
        "description": "API gateway CPU at 95%"
      },
      "startsAt": "2026-01-03T10:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus:9090/graph",
      "fingerprint": "abc123def456"
    }
  ],
  "groupLabels": {"alertname": "HighCPU"},
  "commonLabels": {"service": "api-gateway"},
  "commonAnnotations": {},
  "externalURL": "http://alertmanager:9093",
  "version": "4",
  "groupKey": "{}:{alertname=\"HighCPU\"}"
}
```

**Response 202**:
```json
{
  "status": "accepted",
  "message": "Alert received and queued for processing",
  "alerts_received": 1,
  "processing_ids": ["550e8400-e29b-41d4-a716-446655440000"]
}
```

**Response 400** (malformed request):
```json
{
  "detail": "Invalid request body"
}
```

**Test Coverage**:
- `test_webhook_e2e.py::test_single_alert_accepted`
- `test_webhook_e2e.py::test_batch_alerts_accepted`
- `test_webhook_e2e.py::test_malformed_rejected`

---

## Alert Endpoints

### GET /api/v1/alerts

**Purpose**: List alerts with filtering and pagination

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | null | Filter by status (firing/resolved) |
| severity | string | null | Filter by severity (critical/warning/info) |
| service | string | null | Filter by service label |
| since | datetime | null | Filter alerts after this time |
| until | datetime | null | Filter alerts before this time |
| limit | integer | 50 | Max results (capped at 100) |
| offset | integer | 0 | Skip N results |

**Response 200**:
```json
{
  "alerts": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "fingerprint": "abc123def456",
      "alertname": "HighCPU",
      "severity": "critical",
      "status": "firing",
      "labels": {"service": "api-gateway"},
      "annotations": {"summary": "CPU high"},
      "starts_at": "2026-01-03T10:00:00Z",
      "ends_at": null,
      "incident_id": "660e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-01-03T10:00:01Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

**Test Coverage**: `test_api_alerts.py::test_list_alerts_*`

---

### GET /api/v1/alerts/{alert_id}

**Purpose**: Get alert by ID

**Response 200**: Single alert object (see above)

**Response 404**:
```json
{
  "detail": "Alert 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

**Test Coverage**: `test_api_alerts.py::test_get_alert_by_id`, `test_api_alerts.py::test_get_alert_not_found`

---

## Incident Endpoints

### GET /api/v1/incidents

**Purpose**: List incidents with filtering and pagination

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | null | Filter by status (open/analyzing/resolved/closed) |
| severity | string | null | Filter by severity |
| service | string | null | Filter by affected service |
| since | datetime | null | Filter incidents after this time |
| until | datetime | null | Filter incidents before this time |
| limit | integer | 50 | Max results (capped at 100) |
| offset | integer | 0 | Skip N results |

**Response 200**:
```json
{
  "incidents": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "title": "HighCPU on api-gateway",
      "status": "open",
      "severity": "critical",
      "alert_count": 3,
      "affected_services": ["api-gateway"],
      "started_at": "2026-01-03T10:00:00Z",
      "created_at": "2026-01-03T10:00:01Z"
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0
}
```

**Test Coverage**: `test_api_incidents.py::test_list_incidents_*`

---

### GET /api/v1/incidents/{incident_id}

**Purpose**: Get incident with all alerts

**Response 200**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "title": "HighCPU on api-gateway",
  "status": "open",
  "severity": "critical",
  "correlation_reason": "Same service within 5 minute window",
  "affected_services": ["api-gateway"],
  "affected_labels": {"namespace": "production"},
  "started_at": "2026-01-03T10:00:00Z",
  "resolved_at": null,
  "rca_completed_at": null,
  "alerts": [/* array of alert objects */],
  "created_at": "2026-01-03T10:00:01Z"
}
```

**Test Coverage**: `test_api_incidents.py::test_get_incident_with_alerts`

---

### POST /api/v1/incidents/{incident_id}/correlate

**Purpose**: Manually correlate alerts with incident

**Request Body**:
```json
{
  "alert_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

**Response 200**:
```json
{
  "success": true,
  "incident_id": "660e8400-e29b-41d4-a716-446655440000",
  "alerts_correlated": 2,
  "message": "Successfully correlated 2 alert(s) with incident"
}
```

**Test Coverage**: `test_api_incidents.py::test_manual_correlation`

---

## Report Endpoints

### GET /api/v1/reports

**Purpose**: List RCA reports

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | null | Filter by status (pending/complete/failed) |
| service | string | null | Filter by affected service |
| severity | string | null | Filter by incident severity |
| min_confidence | integer | null | Minimum confidence score (0-100) |
| limit | integer | 50 | Max results |
| offset | integer | 0 | Skip N results |

**Response 200**:
```json
{
  "reports": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "incident_id": "660e8400-e29b-41d4-a716-446655440000",
      "status": "complete",
      "confidence_score": 85,
      "summary": "Root cause identified as memory leak in cache service",
      "completed_at": "2026-01-03T10:05:00Z"
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

**Test Coverage**: `test_api_reports.py::test_list_reports_*`

---

### GET /api/v1/reports/{report_id}

**Purpose**: Get full RCA report

**Response 200**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "incident_id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "complete",
  "root_cause": "Memory leak in cache service connection pool",
  "confidence_score": 85,
  "summary": "Analysis identified memory leak causing OOM kills",
  "timeline": [
    {"time": "2026-01-03T09:55:00Z", "event": "Memory usage began increasing"},
    {"time": "2026-01-03T10:00:00Z", "event": "OOM killer triggered"}
  ],
  "evidence": {
    "logs": ["Error: out of memory", "OOM killed process"],
    "metrics": {"memory_usage_peak": "98%"}
  },
  "remediation_steps": [
    "Restart cache service",
    "Increase connection pool timeout",
    "Add memory limit alerts"
  ],
  "analysis_metadata": {
    "model": "claude-3-sonnet",
    "tokens_used": 4500,
    "duration_seconds": 45
  },
  "started_at": "2026-01-03T10:00:01Z",
  "completed_at": "2026-01-03T10:05:00Z"
}
```

**Test Coverage**: `test_api_reports.py::test_get_report_full`

---

### GET /api/v1/reports/{report_id}/export

**Purpose**: Export report in JSON or Markdown format

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| format | string | json | Export format (json/markdown) |

**Response 200** (format=json): Same as GET /reports/{id}

**Response 200** (format=markdown):
```markdown
# RCA Report: HighCPU on api-gateway

**Confidence Score**: 85%
**Status**: Complete

## Root Cause
Memory leak in cache service connection pool

## Summary
Analysis identified memory leak causing OOM kills...

## Timeline
- 2026-01-03T09:55:00Z: Memory usage began increasing
- 2026-01-03T10:00:00Z: OOM killer triggered

## Evidence
### Logs
- Error: out of memory
- OOM killed process

## Remediation Steps
1. Restart cache service
2. Increase connection pool timeout
3. Add memory limit alerts
```

**Test Coverage**: `test_api_reports.py::test_export_json`, `test_api_reports.py::test_export_markdown`

---

### GET /api/v1/incidents/{incident_id}/report

**Purpose**: Get RCA report for specific incident

**Response 200**: Same as GET /reports/{id}

**Response 404**:
```json
{
  "detail": "No RCA report found for incident 660e8400-e29b-41d4-a716-446655440000"
}
```

**Test Coverage**: `test_api_reports.py::test_get_report_by_incident`
