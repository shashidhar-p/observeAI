"""Cortex query tool for the RCA agent."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.services.cortex_client import CortexClient

logger = logging.getLogger(__name__)

# Tool definition for Claude
QUERY_CORTEX_TOOL = {
    "name": "query_cortex",
    "description": (
        "Query metrics from Cortex using PromQL. Use this tool to retrieve metric data "
        "for performance analysis. Returns time series data with labels and values."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "promql_query": {
                "type": "string",
                "description": (
                    "PromQL query string. Examples:\n"
                    "- 'up{job=\"api\"}' - service availability\n"
                    "- 'rate(http_requests_total[5m])' - request rate\n"
                    "- 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))' - p95 latency\n"
                    "- '100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])))' - CPU usage"
                ),
            },
            "start_time": {
                "type": "string",
                "description": "ISO 8601 start time for metric range (e.g., '2025-01-15T10:00:00Z')",
            },
            "end_time": {
                "type": "string",
                "description": "ISO 8601 end time for metric range (e.g., '2025-01-15T10:30:00Z')",
            },
            "step": {
                "type": "string",
                "description": "Query resolution step (default: '60s'). Use larger steps for longer time ranges.",
                "default": "60s",
            },
        },
        "required": ["promql_query", "start_time", "end_time"],
    },
}


async def execute_query_cortex(
    promql_query: str,
    start_time: str,
    end_time: str,
    step: str = "60s",
) -> dict[str, Any]:
    """
    Execute a Cortex query and return formatted results.

    Args:
        promql_query: PromQL query string
        start_time: ISO 8601 start time
        end_time: ISO 8601 end time
        step: Query resolution step

    Returns:
        dict: Formatted query results with metrics and metadata
    """
    try:
        # Parse timestamps
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        # Execute query
        client = CortexClient()
        result = await client.range_query(
            query=promql_query,
            start=start,
            end=end,
            step=step,
        )

        # Format results for Claude
        formatted = format_cortex_results(result)

        return {
            "success": True,
            "query": promql_query,
            "time_range": {"start": start_time, "end": end_time},
            "step": step,
            "series_count": formatted["series_count"],
            "metrics": formatted["metrics"],
        }

    except Exception as e:
        logger.exception(f"Cortex query failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": promql_query,
        }


def format_cortex_results(result: dict) -> dict[str, Any]:
    """
    Format Cortex query results for Claude consumption.

    Args:
        result: Raw Cortex API response

    Returns:
        dict: Formatted results with metrics list
    """
    metrics = []
    series_count = 0

    if "data" in result and "result" in result["data"]:
        series = result["data"]["result"]
        series_count = len(series)

        for s in series:
            metric_labels = s.get("metric", {})
            values = s.get("values", [])

            # Convert values to readable format
            data_points = []
            for timestamp, value in values:
                dt = datetime.fromtimestamp(float(timestamp), tz=UTC)
                data_points.append({
                    "timestamp": dt.isoformat(),
                    "value": float(value) if value != "NaN" else None,
                })

            # Calculate summary statistics
            numeric_values = [p["value"] for p in data_points if p["value"] is not None]
            summary = {}
            if numeric_values:
                summary = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "latest": numeric_values[-1] if numeric_values else None,
                }

            metrics.append({
                "labels": metric_labels,
                "data_points": data_points[-100:],  # Limit to last 100 points
                "total_points": len(data_points),
                "summary": summary,
            })

    return {
        "metrics": metrics,
        "series_count": series_count,
    }


def build_cpu_query(labels: dict[str, str] | None = None) -> str:
    """
    Build a PromQL query for CPU utilization.

    Args:
        labels: Optional labels to filter by

    Returns:
        str: PromQL query for CPU percentage
    """
    if labels:
        filters = [f'{k}="{v}"' for k, v in labels.items()]
        label_str = ", ".join(filters)
        selector = f'mode="idle", {label_str}'
    else:
        selector = 'mode="idle"'

    return f'100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{{{selector}}}[5m])))'


def build_memory_query(labels: dict[str, str] | None = None) -> str:
    """
    Build a PromQL query for memory utilization.

    Args:
        labels: Optional labels to filter by

    Returns:
        str: PromQL query for memory percentage
    """
    selector = ""
    if labels:
        filters = [f'{k}="{v}"' for k, v in labels.items()]
        selector = "{" + ", ".join(filters) + "}"

    return f"100 * (1 - (node_memory_MemAvailable_bytes{selector} / node_memory_MemTotal_bytes{selector}))"


def build_error_rate_query(service: str | None = None) -> str:
    """
    Build a PromQL query for HTTP error rate.

    Args:
        service: Optional service name to filter

    Returns:
        str: PromQL query for error rate (0-1)
    """
    if service:
        return f'sum(rate(http_requests_total{{service="{service}", status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m]))'
    return 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))'


def build_latency_query(service: str | None = None, percentile: float = 0.95) -> str:
    """
    Build a PromQL query for request latency percentile.

    Args:
        service: Optional service name to filter
        percentile: Percentile to calculate (default: 0.95 for p95)

    Returns:
        str: PromQL query for latency
    """
    selector = f'{{service="{service}"}}' if service else ""
    return f"histogram_quantile({percentile}, rate(http_request_duration_seconds_bucket{selector}[5m]))"


# Common metric patterns for different alert types
ALERT_METRIC_PATTERNS: dict[str, list[dict[str, str]]] = {
    "disk": [
        {"query": "100 - (node_filesystem_avail_bytes{SELECTOR} / node_filesystem_size_bytes{SELECTOR} * 100)", "desc": "Disk usage percentage"},
        {"query": "node_filesystem_avail_bytes{SELECTOR}", "desc": "Available disk space"},
    ],
    "memory": [
        {"query": "100 * (1 - node_memory_MemAvailable_bytes{SELECTOR} / node_memory_MemTotal_bytes{SELECTOR})", "desc": "Memory usage percentage"},
        {"query": "container_memory_working_set_bytes{SELECTOR}", "desc": "Container memory usage"},
    ],
    "cpu": [
        {"query": "100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\",SELECTOR}[5m])))", "desc": "Node CPU usage"},
        {"query": "sum(rate(container_cpu_usage_seconds_total{SELECTOR}[5m])) by (container)", "desc": "Container CPU usage"},
    ],
    "network": [
        {"query": "rate(node_network_receive_bytes_total{SELECTOR}[5m])", "desc": "Network receive rate"},
        {"query": "rate(node_network_transmit_bytes_total{SELECTOR}[5m])", "desc": "Network transmit rate"},
    ],
    "error": [
        {"query": "sum(rate(http_requests_total{status=~\"5..\",SELECTOR}[5m]))", "desc": "5xx error rate"},
        {"query": "sum(rate(http_requests_total{status=~\"4..\",SELECTOR}[5m]))", "desc": "4xx error rate"},
    ],
    "latency": [
        {"query": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{SELECTOR}[5m]))", "desc": "P95 latency"},
        {"query": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{SELECTOR}[5m]))", "desc": "P99 latency"},
    ],
    "availability": [
        {"query": "up{SELECTOR}", "desc": "Service availability"},
        {"query": "sum(up{SELECTOR}) / count(up{SELECTOR})", "desc": "Availability ratio"},
    ],
}


class PromQLQueryBuilder:
    """
    Intelligent PromQL query builder for context-aware metric retrieval.

    Builds optimized queries based on alert context and labels.
    """

    # Labels that are useful for metric filtering
    FILTER_LABELS = ["service", "namespace", "pod", "container", "job", "app", "instance", "node"]

    # Labels to exclude from query
    EXCLUDE_LABELS = ["alertname", "severity", "__name__"]

    def __init__(self, labels: dict[str, str] | None = None):
        """Initialize with optional alert labels."""
        self.labels = labels or {}

    def build_label_selector(self) -> str:
        """Build a PromQL label selector from alert labels."""
        query_labels = {}
        for key in self.FILTER_LABELS:
            if key in self.labels:
                query_labels[key] = self.labels[key]

        if not query_labels:
            # Fallback: use any available labels except excluded ones
            query_labels = {
                k: v for k, v in self.labels.items()
                if k not in self.EXCLUDE_LABELS
            }

        if query_labels:
            selectors = [f'{k}="{v}"' for k, v in query_labels.items()]
            return ", ".join(selectors)

        return ""

    def apply_selector(self, query_template: str) -> str:
        """Apply label selector to a query template."""
        selector = self.build_label_selector()
        return query_template.replace("{SELECTOR}", selector).replace("SELECTOR", selector)

    def build_alertname_specific_queries(self, alertname: str) -> list[dict[str, str]]:
        """Build queries based on the alert name."""
        alertname_lower = alertname.lower()
        queries = []

        # Check for matching patterns
        for pattern_key, patterns in ALERT_METRIC_PATTERNS.items():
            if pattern_key in alertname_lower:
                for pattern in patterns:
                    queries.append({
                        "query": self.apply_selector(pattern["query"]),
                        "description": pattern["desc"],
                    })

        # Always include general availability check
        queries.append({
            "query": self.apply_selector("up{SELECTOR}"),
            "description": "Service availability",
        })

        return queries

    def suggest_queries(self, alertname: str) -> list[dict[str, str]]:
        """
        Suggest relevant queries based on alert context.

        Returns a list of query suggestions with descriptions.
        """
        suggestions = self.build_alertname_specific_queries(alertname)

        # Add error rate if we have service info
        if "service" in self.labels:
            service = self.labels["service"]
            suggestions.append({
                "query": f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m]))',
                "description": f"Error rate for {service}",
            })

        return suggestions

    def get_query_hints(self, alertname: str) -> str:
        """
        Get query hints for the LLM based on alert context.

        Returns a formatted string of suggested queries.
        """
        suggestions = self.suggest_queries(alertname)
        hints = ["Suggested PromQL queries for this alert:"]

        for i, suggestion in enumerate(suggestions, 1):
            hints.append(f"  {i}. {suggestion['description']}:")
            hints.append(f"     {suggestion['query']}")

        return "\n".join(hints)

    def get_resource_queries(self) -> dict[str, str]:
        """Get standard resource utilization queries."""
        return {
            "cpu": self.apply_selector("100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\",SELECTOR}[5m])))"),
            "memory": self.apply_selector("100 * (1 - node_memory_MemAvailable_bytes{SELECTOR} / node_memory_MemTotal_bytes{SELECTOR})"),
            "disk": self.apply_selector("100 - (node_filesystem_avail_bytes{SELECTOR} / node_filesystem_size_bytes{SELECTOR} * 100)"),
            "network_in": self.apply_selector("rate(node_network_receive_bytes_total{SELECTOR}[5m])"),
            "network_out": self.apply_selector("rate(node_network_transmit_bytes_total{SELECTOR}[5m])"),
        }
