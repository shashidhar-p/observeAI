# Cross-Namespace Correlation & RCA Test Documentation

## Overview

This document describes the test scenario for validating cross-namespace alert correlation and Root Cause Analysis (RCA) in the Multi-Agent Observability System.

---

## Test Scenario: Virtual Router Interface Failure

**Root Cause**: Interface `eth1` went down on virtual router node `vrouter-prod-02`, causing cascading failures across multiple services in different namespaces.

### Affected Components

| Component | Namespace | Impact |
|-----------|-----------|--------|
| vrouter-prod-02 | network-infra | Interface down, BGP session terminated |
| network-monitor | monitoring | Cannot reach vrouter-prod-02 |
| payment-api | production | Backend connectivity lost |
| api-gateway | production | High latency due to rerouting |
| order-service | production | Database connection timeouts |

---

## Test Logs Injected into Loki

```python
# Logs injected with timestamps relative to current time
logs = [
    # Network Infrastructure Logs (vrouter-prod-02)
    {
        "service": "vrouter-prod-02",
        "namespace": "network-infra",
        "msg": "CRITICAL: Interface eth1 DOWN - physical carrier lost"
    },
    {
        "service": "vrouter-prod-02",
        "namespace": "network-infra",
        "msg": "ERROR: BGP session terminated - all routes withdrawn"
    },
    {
        "service": "vrouter-prod-02",
        "namespace": "network-infra",
        "msg": "ERROR: OSPF neighbor adjacency LOST on eth1"
    },

    # Monitoring Logs
    {
        "service": "network-monitor",
        "namespace": "monitoring",
        "msg": "ERROR: Node vrouter-prod-02 unreachable - ICMP timeout"
    },

    # Application Impact Logs
    {
        "service": "payment-api",
        "namespace": "production",
        "msg": "ERROR: Backend connection timeout via prod-backend network"
    },
    {
        "service": "order-service",
        "namespace": "production",
        "msg": "CRITICAL: Database connection timeout via prod-backend network"
    }
]
```

### Log Labels Structure

```json
{
    "service": "<service-name>",
    "namespace": "<namespace>",
    "datacenter": "dc-west-1"
}
```

---

## Test Alerts Sent to Alertmanager Webhook

### Full Multi-Alert Payload

```json
{
    "receiver": "rca-system",
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "fingerprint": "vrouter-interface-001",
            "labels": {
                "alertname": "InterfaceDown",
                "severity": "critical",
                "service": "vrouter-prod-02",
                "namespace": "network-infra",
                "node": "vrouter-prod-02",
                "interface": "eth1",
                "datacenter": "dc-west-1",
                "network_segment": "prod-backend"
            },
            "annotations": {
                "summary": "Network interface eth1 is down on vrouter-prod-02",
                "description": "Interface eth1 on virtual router vrouter-prod-02 has been down for 2 minutes. This interface handles prod-backend traffic."
            },
            "startsAt": "2025-12-29T11:15:00Z"
        },
        {
            "status": "firing",
            "fingerprint": "vrouter-bgp-002",
            "labels": {
                "alertname": "BGPSessionDown",
                "severity": "critical",
                "service": "vrouter-prod-02",
                "namespace": "network-infra",
                "node": "vrouter-prod-02",
                "peer": "10.0.1.1",
                "datacenter": "dc-west-1",
                "network_segment": "prod-backend"
            },
            "annotations": {
                "summary": "BGP session to peer 10.0.1.1 is down",
                "description": "BGP peering session from vrouter-prod-02 to core-router has been down."
            },
            "startsAt": "2025-12-29T11:15:30Z"
        },
        {
            "status": "firing",
            "fingerprint": "node-unreachable-003",
            "labels": {
                "alertname": "NodeUnreachable",
                "severity": "critical",
                "service": "network-monitor",
                "namespace": "monitoring",
                "target_node": "vrouter-prod-02",
                "datacenter": "dc-west-1"
            },
            "annotations": {
                "summary": "Node vrouter-prod-02 is unreachable via ICMP",
                "description": "Network monitor cannot reach vrouter-prod-02 management interface."
            },
            "startsAt": "2025-12-29T11:16:00Z"
        },
        {
            "status": "firing",
            "fingerprint": "payment-connectivity-004",
            "labels": {
                "alertname": "ServiceConnectivityLoss",
                "severity": "critical",
                "service": "payment-api",
                "namespace": "production",
                "datacenter": "dc-west-1",
                "destination": "payment-processor",
                "network_path": "prod-backend"
            },
            "annotations": {
                "summary": "payment-api cannot reach payment-processor backend",
                "description": "Connection attempts to payment-processor via vrouter-prod-02 are failing."
            },
            "startsAt": "2025-12-29T11:16:30Z"
        },
        {
            "status": "firing",
            "fingerprint": "gateway-latency-005",
            "labels": {
                "alertname": "HighLatency",
                "severity": "warning",
                "service": "api-gateway",
                "namespace": "production",
                "datacenter": "dc-west-1",
                "network_path": "prod-backend"
            },
            "annotations": {
                "summary": "High latency on api-gateway payment endpoints",
                "description": "P99 latency increased due to traffic rerouting around vrouter-prod-02"
            },
            "startsAt": "2025-12-29T11:17:00Z"
        },
        {
            "status": "firing",
            "fingerprint": "order-db-timeout-006",
            "labels": {
                "alertname": "DatabaseConnectionTimeout",
                "severity": "critical",
                "service": "order-service",
                "namespace": "production",
                "datacenter": "dc-west-1",
                "network_path": "prod-backend"
            },
            "annotations": {
                "summary": "order-service experiencing database connection timeouts",
                "description": "Unable to reach orders-primary database via prod-backend network path"
            },
            "startsAt": "2025-12-29T11:17:30Z"
        }
    ],
    "groupLabels": {
        "datacenter": "dc-west-1"
    },
    "commonLabels": {
        "datacenter": "dc-west-1"
    }
}
```

---

## Correlation Results

### Incident Created

```json
{
    "id": "7340ae10-f779-40ff-a3bf-ac6ec66316aa",
    "title": "[CRITICAL] InterfaceDown",
    "status": "resolved",
    "severity": "critical",
    "affected_services": [
        "vrouter-prod-02",
        "payment-api",
        "network-monitor",
        "api-gateway",
        "order-service"
    ],
    "affected_labels": {
        "node": "vrouter-prod-02",
        "service": "vrouter-prod-02",
        "namespace": "network-infra",
        "datacenter": "dc-west-1",
        "network_segment": "prod-backend"
    },
    "correlation_reason": "Correlated by shared datacenter: dc-west-1, shared network_path: prod-backend, symptom of infrastructure incident",
    "started_at": "2025-12-29T11:15:00Z"
}
```

### Correlation Logic Applied

| Alert | Namespace | Correlation Match |
|-------|-----------|-------------------|
| InterfaceDown | network-infra | **Primary** - Infrastructure alert, earliest timestamp |
| BGPSessionDown | network-infra | Same service, same namespace, same node |
| NodeUnreachable | monitoring | `target_node` references `vrouter-prod-02` |
| ServiceConnectivityLoss | production | Shared `datacenter`, `network_path` matches `network_segment` |
| HighLatency | production | Shared `datacenter`, `network_path` matches `network_segment` |
| DatabaseConnectionTimeout | production | Shared `datacenter`, `network_path` matches `network_segment` |

---

## RCA Agent Analysis

### Agent Configuration

```yaml
Provider: Ollama
Model: llama3.1:8b
Max Iterations: 10
Tools Available:
  - query_loki: Search logs in Loki
  - query_cortex: Query metrics from Cortex
  - generate_report: Generate final RCA report
```

### Agent Execution Flow

```
Iteration 1: Called query_loki for vrouter-prod-02 logs
             → Found: "Interface eth1 DOWN - physical carrier lost"
             → Found: "BGP session terminated - all routes withdrawn"

Iteration 2: Analyzed log results

Iteration 3: Called generate_report with findings
```

### RCA Report Generated

```json
{
    "id": "40585ef1-665d-4271-ae85-82b8638587b5",
    "incident_id": "7340ae10-f779-40ff-a3bf-ac6ec66316aa",
    "status": "complete",
    "root_cause": "Network interface down event on vrouter-prod-02",
    "confidence_score": 90,
    "summary": "The root cause of the incident was a network interface down event on vrouter-prod-02, which caused the payment-api to timeout and fail.",
    "remediation_steps": [
        {
            "priority": "immediate",
            "action": "Restart the vrouter-prod-02 pod",
            "risk": "low"
        },
        {
            "priority": "long_term",
            "action": "Increase the network interface redundancy",
            "risk": "low"
        }
    ],
    "analysis_metadata": {
        "model": "llama3.1:8b",
        "tokens_used": 9998,
        "duration_seconds": 10.49,
        "tool_calls": 4
    }
}
```

---

## Key Labels for Cross-Namespace Correlation

### Infrastructure Labels (High Priority)

These labels enable correlation across different namespaces:

| Label | Description | Example |
|-------|-------------|---------|
| `datacenter` | Physical/logical datacenter | `dc-west-1` |
| `network_segment` | Network segment identifier | `prod-backend` |
| `cluster` | Kubernetes cluster name | `prod-cluster-1` |
| `zone` | Availability zone | `us-west-2a` |
| `region` | Geographic region | `us-west-2` |
| `network_path` | Network path identifier | `prod-backend` |

### Cross-Reference Labels

These labels reference other entities:

| Label | Description | Usage |
|-------|-------------|-------|
| `target_node` | Node being monitored | Monitoring alerts referencing infra |
| `destination` | Target service/endpoint | Connectivity alerts |
| `peer` | Network peer | BGP/routing alerts |
| `upstream` | Upstream dependency | Service dependency alerts |
| `downstream` | Downstream dependency | Impact tracking |

---

## Correlation Scoring

### Score Breakdown

| Match Type | Score | Description |
|------------|-------|-------------|
| Same service | +3 | Direct service match |
| Same namespace | +2 | Same namespace |
| Direct label match | +2 | Exact label value match |
| Infrastructure label match | +4 | datacenter, network_segment, etc. |
| Cross-reference match | +5 | target_node matches incident node |
| Annotation reference | +3 | Service/node mentioned in description |
| Infrastructure affinity | +3 | Infra alert + shared datacenter |

### Minimum Score for Correlation

**Threshold: 2 points**

With cross-namespace correlation, alerts can be grouped even when they don't share `namespace`:

```
InterfaceDown (network-infra) + ServiceTimeout (production)
  → shared datacenter: dc-west-1 (+4)
  → infrastructure affinity (+3)
  → Total: 7 points ✓ Correlated
```

---

## Commands Used for Testing

### Inject Logs into Loki

```bash
curl -X POST http://localhost:3100/loki/api/v1/push \
  -H "Content-Type: application/json" \
  -d '{
    "streams": [{
      "stream": {
        "service": "vrouter-prod-02",
        "namespace": "network-infra",
        "datacenter": "dc-west-1"
      },
      "values": [
        ["1735470000000000000", "CRITICAL: Interface eth1 DOWN - carrier lost"]
      ]
    }]
  }'
```

### Send Alerts via Webhook

```bash
curl -X POST http://localhost:8000/webhooks/alertmanager \
  -H "Content-Type: application/json" \
  -d @alerts.json
```

### Query Incidents

```bash
curl http://localhost:8000/api/v1/incidents | jq
```

### Query RCA Reports

```bash
curl http://localhost:8000/api/v1/reports | jq
```

---

## Files Modified for Cross-Namespace Correlation

### `src/services/correlation_service.py`

Added:
- `INFRASTRUCTURE_LABELS` - datacenter, network_segment, cluster, zone, region
- `CROSS_REFERENCE_LABELS` - target_node, destination, peer, upstream
- `_calculate_cross_reference_score()` - Score based on entity references
- `_calculate_infrastructure_affinity()` - Infra alert + app symptom correlation
- `_check_annotation_references()` - Find mentions in descriptions

### `src/services/rca_agent.py`

Added:
- Explicit tool usage instructions for multi-alert incidents
- Primary service hint for initial query_loki call

### `src/tools/generate_report.py`

Fixed:
- Removed example in root_cause description that llama3.1:8b was copying
- Added JSON parsing for string arguments from Ollama
