# Research: Multi-Agent AI Observability & RCA System

**Branch**: `001-multi-agent-rca` | **Date**: 2025-12-28

## Research Areas

1. [Claude API Tool Use Patterns](#1-claude-api-tool-use-patterns)
2. [Loki LogQL Query Patterns](#2-loki-logql-query-patterns)
3. [Cortex/Prometheus PromQL Patterns](#3-cortexpromql-patterns)
4. [Alert Manager Webhook Integration](#4-alert-manager-webhook-integration)

---

## 1. Claude API Tool Use Patterns

### Decision: Use Anthropic Python SDK with Native Tool Calling

**Rationale**:
- Direct API control without framework overhead
- Production-tested patterns for agentic loops
- Full control over error handling, retries, and token optimization
- Clean migration path to Go for production phase

**Alternatives Considered**:
- LangChain: Rejected due to abstraction overhead and rapid API changes
- CrewAI: Rejected due to immaturity for production workloads
- OpenAI Assistants: Rejected due to vendor lock-in

### Tool Definition Schema Pattern

```python
tools = [
    {
        "name": "query_loki",
        "description": "Query logs from Loki using LogQL. Returns relevant log entries for alert analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "logql_query": {
                    "type": "string",
                    "description": "LogQL query string (e.g., '{job=\"api\"} |= \"error\"')"
                },
                "start_time": {
                    "type": "string",
                    "description": "ISO 8601 start time for log range"
                },
                "end_time": {
                    "type": "string",
                    "description": "ISO 8601 end time for log range"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum entries to return",
                    "default": 1000
                }
            },
            "required": ["logql_query", "start_time", "end_time"]
        }
    }
]
```

### Agentic Loop Implementation

```python
def run_rca_analysis(self, alert_data: dict) -> dict:
    messages = [{"role": "user", "content": format_alert_prompt(alert_data)}]
    iteration = 0

    while iteration < self.max_iterations:
        iteration += 1

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.system_prompt,
            tools=self.tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return self._extract_final_analysis(response)

        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Max iterations ({self.max_iterations}) exceeded")
```

### Error Handling Strategy

| Error Type | Strategy |
|------------|----------|
| `RateLimitError` | Exponential backoff (1s, 2s, 4s) with jitter |
| `APIConnectionError` | Retry 3 times with 5s delay |
| `TimeoutError` | Retry 2 times, then proceed with partial data |
| Tool execution failure | Return error message to Claude for adaptation |

### Token Optimization Techniques

1. **Concise system prompts**: Focus on role and output format
2. **Log truncation**: Limit to 2000 tokens, prioritize errors
3. **Metric sampling**: Sample high-cardinality metrics at 50%
4. **Result caching**: Cache tool results for repeated queries
5. **Summary injection**: Summarize conversation history if > 8000 tokens

---

## 2. Loki LogQL Query Patterns

### Decision: Use httpx Async Client with LogQL v2

**Rationale**:
- Native async support for concurrent log queries
- Direct HTTP API access without library overhead
- Full control over pagination and rate limiting

### LogQL Syntax Reference

**Label Filtering**:
```logql
{job="api-server", env="prod"}           # Exact match
{job!="debug"}                            # Negation
{job=~"api-.*"}                          # Regex match
{namespace!~"test-.*"}                   # Regex negation
```

**Log Pipeline**:
```logql
{job="api"} |= "error"                   # Contains "error"
{job="api"} != "debug"                   # Excludes "debug"
{job="api"} |~ "error|warn"              # Regex match
{job="api"} | json | level="error"       # JSON parsing + filter
{job="api"} | logfmt | status>=500       # logfmt parsing
```

### Python Client Pattern

```python
import httpx
from datetime import datetime

class LokiClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=timeout)

    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 1000
    ) -> dict:
        params = {
            "query": query,
            "start": int(start.timestamp() * 1e9),
            "end": int(end.timestamp() * 1e9),
            "limit": limit
        }
        response = await self.client.get(
            f"{self.base_url}/loki/api/v1/query_range",
            params=params
        )
        response.raise_for_status()
        return response.json()
```

### RCA-Specific Query Patterns

```logql
# Error detection for service
{service="payment-api"} | json | level="error"

# Stack traces
{service="payment-api"} |~ "Exception|Error|Traceback"

# OOM events
{service="payment-api"} |= "OOMKilled" or |= "out of memory"

# Connection failures
{service="payment-api"} |~ "connection refused|timeout|ECONNREFUSED"
```

---

## 3. Cortex/PromQL Patterns

### Decision: Use Cortex HTTP API with PromQL

**Rationale**:
- PromQL compatibility with existing Prometheus queries
- Horizontal scalability for long-term storage
- Native support for range queries and aggregations

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/prom/query` | Instant query (current value) |
| `/api/prom/query_range` | Range query (time series) |
| `/api/prom/series` | Find series by label matchers |
| `/api/prom/labels` | List all label names |

### Python Client Pattern

```python
class CortexClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30)

    async def range_query(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "60s"
    ) -> dict:
        params = {
            "query": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "step": step
        }
        response = await self.client.get(
            f"{self.base_url}/api/prom/query_range",
            params=params
        )
        response.raise_for_status()
        return response.json()
```

### RCA-Specific Metric Queries

```promql
# CPU utilization (percentage)
100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))

# Memory utilization (percentage)
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m]))
/ sum(rate(http_requests_total[5m]))

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Pod restarts
increase(kube_pod_container_status_restarts_total[1h])

# Disk usage
100 * (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes)
```

### Query Optimization

| Technique | Impact |
|-----------|--------|
| Use specific label matchers | Reduces cardinality scan |
| Set appropriate `step` (60-300s) | Reduces data points |
| Aggregate early with `sum by` | Reduces result size |
| Cache frequent queries (30s TTL) | Reduces backend load |

---

## 4. Alert Manager Webhook Integration

### Decision: FastAPI Async Webhook with Immediate Acknowledgment

**Rationale**:
- Async processing meets 2-second acknowledgment requirement
- Pydantic validation ensures payload correctness
- Background task processing prevents timeouts

### Webhook Payload Structure

```json
{
  "receiver": "rca-system",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighCPU",
        "severity": "critical",
        "service": "payment-api",
        "pod": "payment-api-7d4f5b9-abc12",
        "namespace": "production"
      },
      "annotations": {
        "summary": "High CPU usage detected",
        "description": "CPU usage above 90% for 5 minutes",
        "runbook": "https://runbook.example.com/high-cpu"
      },
      "startsAt": "2025-01-15T10:30:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus:9090/graph",
      "fingerprint": "5e27a9c0edce13f2"
    }
  ],
  "groupLabels": {"alertname": "HighCPU"},
  "commonLabels": {"severity": "critical"},
  "externalURL": "http://alertmanager:9093"
}
```

### Key Fields for RCA

| Field | Priority | Usage |
|-------|----------|-------|
| `fingerprint` | Critical | Deduplication, unique alert tracking |
| `labels` | Critical | Context for Loki/Cortex queries |
| `status` | High | Determine firing vs resolved |
| `startsAt` | High | Define query time window |
| `annotations` | Medium | Human-readable context for report |
| `commonLabels` | Medium | Alert correlation |

### FastAPI Implementation Pattern

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

@app.post("/webhooks/alertmanager")
async def receive_webhook(
    payload: AlertManagerWebhookPayload,
    background_tasks: BackgroundTasks
):
    # Immediate acknowledgment
    for alert in payload.alerts:
        # Check deduplication
        if not await is_duplicate(alert.fingerprint, alert.status):
            # Queue for async processing
            background_tasks.add_task(process_alert, alert)

    return {"status": "accepted", "alerts_received": len(payload.alerts)}
```

### Deduplication Strategy

```python
async def is_duplicate(fingerprint: str, status: str) -> bool:
    """Check if alert was recently processed"""
    recent_alert = await db.alerts.find_one({
        "fingerprint": fingerprint,
        "status": status,
        "received_at": {"$gte": datetime.now() - timedelta(minutes=5)}
    })
    return recent_alert is not None
```

---

## Summary of Technology Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| **LLM Integration** | Claude API + native tools | No framework overhead, full control |
| **HTTP Client** | httpx (async) | Modern async support, clean API |
| **Log Queries** | Loki HTTP API + LogQL | Native to observability stack |
| **Metric Queries** | Cortex HTTP API + PromQL | PromQL compatibility |
| **Webhook Server** | FastAPI | Async, Pydantic validation, fast |
| **Database ORM** | SQLAlchemy + asyncpg | Async PostgreSQL support |
| **Deduplication** | Fingerprint-based | Alert Manager native identifier |

---

## Implementation Priorities

1. **Week 1 Focus**: Alert webhook + database storage
2. **Week 2 Focus**: Loki/Cortex clients + basic queries
3. **Week 3 Focus**: RCA agent with Claude tools
4. **Week 4 Focus**: Report generation + API
