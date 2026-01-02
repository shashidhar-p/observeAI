"""Loki query tool for the RCA agent."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.services.loki_client import LokiClient

logger = logging.getLogger(__name__)

# Tool definition for Claude
QUERY_LOKI_TOOL = {
    "name": "query_loki",
    "description": (
        "Query logs from Loki using LogQL. Use this tool to retrieve relevant log entries "
        "for alert analysis. Returns log lines with timestamps and labels."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "logql_query": {
                "type": "string",
                "description": (
                    "LogQL query string. Examples:\n"
                    "- '{job=\"api\"}' - all logs from api job\n"
                    "- '{service=\"payment\"} |= \"error\"' - logs containing 'error'\n"
                    "- '{namespace=\"prod\"} |~ \"(ERROR|WARN)\"' - regex match\n"
                    "- '{app=\"web\"} | json | level=\"error\"' - JSON parsing"
                ),
            },
            "start_time": {
                "type": "string",
                "description": "ISO 8601 start time for log range (e.g., '2025-01-15T10:00:00Z')",
            },
            "end_time": {
                "type": "string",
                "description": "ISO 8601 end time for log range (e.g., '2025-01-15T10:30:00Z')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of log entries to return (default: 500, max: 2000)",
                "default": 500,
            },
        },
        "required": ["logql_query", "start_time", "end_time"],
    },
}


async def execute_query_loki(
    logql_query: str,
    start_time: str,
    end_time: str,
    limit: int = 500,
) -> dict[str, Any]:
    """
    Execute a Loki query and return formatted results.

    Args:
        logql_query: LogQL query string
        start_time: ISO 8601 start time
        end_time: ISO 8601 end time
        limit: Maximum entries to return

    Returns:
        dict: Formatted query results with logs and metadata
    """
    try:
        # Parse timestamps
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        # Validate limit
        limit = min(max(1, limit), 2000)

        # Execute query
        client = LokiClient()
        result = await client.query_range(
            query=logql_query,
            start=start,
            end=end,
            limit=limit,
        )

        # Format results for Claude
        formatted = format_loki_results(result)

        return {
            "success": True,
            "query": logql_query,
            "time_range": {"start": start_time, "end": end_time},
            "result_count": formatted["total_entries"],
            "streams_count": formatted["streams_count"],
            "logs": formatted["logs"],
            "truncated": formatted["total_entries"] >= limit,
        }

    except Exception as e:
        logger.exception(f"Loki query failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": logql_query,
        }


def format_loki_results(result: dict) -> dict[str, Any]:
    """
    Format Loki query results for Claude consumption.

    Args:
        result: Raw Loki API response

    Returns:
        dict: Formatted results with logs list
    """
    logs = []
    streams_count = 0
    total_entries = 0

    if "data" in result and "result" in result["data"]:
        streams = result["data"]["result"]
        streams_count = len(streams)

        for stream in streams:
            labels = stream.get("stream", {})
            values = stream.get("values", [])
            total_entries += len(values)

            for value in values:
                timestamp_ns, message = value
                # Convert nanoseconds to datetime
                timestamp = datetime.fromtimestamp(
                    int(timestamp_ns) / 1e9, tz=UTC
                )

                logs.append({
                    "timestamp": timestamp.isoformat(),
                    "message": message,
                    "labels": labels,
                })

    # Sort by timestamp (most recent first for backward queries)
    logs.sort(key=lambda x: x["timestamp"], reverse=True)

    # Truncate message for very long logs
    for log in logs:
        if len(log["message"]) > 2000:
            log["message"] = log["message"][:2000] + "... [truncated]"

    return {
        "logs": logs,
        "streams_count": streams_count,
        "total_entries": total_entries,
    }


def build_alert_query(labels: dict[str, str], include_errors: bool = True) -> str:
    """
    Build a LogQL query from alert labels.

    Args:
        labels: Alert labels to use as filters
        include_errors: Whether to filter for error logs only

    Returns:
        str: LogQL query string
    """
    # Extract relevant labels for log querying
    query_labels = {}
    for key in ["service", "device", "namespace", "pod", "container", "job", "app"]:
        if key in labels:
            query_labels[key] = labels[key]

    if not query_labels:
        # Fallback: use any available labels
        query_labels = {k: v for k, v in labels.items() if k not in ["alertname", "severity"]}

    # Build label selector
    if query_labels:
        selectors = [f'{k}="{v}"' for k, v in query_labels.items()]
        label_filter = "{" + ", ".join(selectors) + "}"
    else:
        label_filter = "{}"

    # Add error filter if requested
    if include_errors:
        return f'{label_filter} |~ "(?i)(error|exception|fail|fatal|panic)"'

    return label_filter


# Common log patterns for different alert types
ALERT_QUERY_PATTERNS: dict[str, list[str]] = {
    "disk": [
        '|~ "(?i)(disk|space|storage|quota|full)"',
        '|~ "(?i)(no space left|disk quota)"',
    ],
    "memory": [
        '|~ "(?i)(oom|out of memory|memory|heap)"',
        '|~ "(?i)(killed by oom|memory pressure)"',
    ],
    "cpu": [
        '|~ "(?i)(cpu|throttl|load)"',
    ],
    "network": [
        '|~ "(?i)(connection|timeout|refused|unreachable|network)"',
        '|~ "(?i)(dial|socket|port)"',
    ],
    "database": [
        '|~ "(?i)(database|db|sql|query|transaction|deadlock)"',
        '|~ "(?i)(postgres|mysql|redis|mongodb)"',
    ],
    "health": [
        '|~ "(?i)(health|ready|liveness|probe)"',
    ],
}


class LogQLQueryBuilder:
    """
    Intelligent LogQL query builder for context-aware log retrieval.

    Builds optimized queries based on alert context and labels.
    """

    # Labels that are useful for log filtering
    FILTER_LABELS = ["service", "device", "namespace", "pod", "container", "job", "app", "instance"]

    # Labels to exclude from query (not useful for log filtering)
    EXCLUDE_LABELS = ["alertname", "severity", "prometheus", "monitor", "__name__"]

    def __init__(self, labels: dict[str, str] | None = None):
        """Initialize with optional alert labels."""
        self.labels = labels or {}

    def build_base_selector(self) -> str:
        """Build the base label selector from alert labels."""
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
            return "{" + ", ".join(selectors) + "}"

        return "{}"

    def build_error_query(self) -> str:
        """Build a query for error logs."""
        base = self.build_base_selector()
        return f'{base} |~ "(?i)(error|exception|fail|fatal|panic|critical)"'

    def build_alertname_specific_query(self, alertname: str) -> str:
        """Build a query based on the alert name."""
        base = self.build_base_selector()
        alertname_lower = alertname.lower()

        # Check for matching patterns
        for pattern_key, patterns in ALERT_QUERY_PATTERNS.items():
            if pattern_key in alertname_lower:
                # Use the first pattern for simplicity
                return f"{base} {patterns[0]}"

        # Default to error logs
        return self.build_error_query()

    def build_dependency_query(self, dependency: str) -> str:
        """Build a query for a service dependency."""
        base = self.build_base_selector()
        return f'{base} |~ "(?i)({dependency}|connecting to {dependency})"'

    def suggest_queries(self, alertname: str) -> list[dict[str, str]]:
        """
        Suggest relevant queries based on alert context.

        Returns a list of query suggestions with descriptions.
        """
        suggestions = []

        # Base error query
        base = self.build_base_selector()
        suggestions.append({
            "query": self.build_error_query(),
            "description": "Error logs from the affected service",
        })

        # Alert-specific query
        alertname_lower = alertname.lower()
        for pattern_key, patterns in ALERT_QUERY_PATTERNS.items():
            if pattern_key in alertname_lower:
                suggestions.append({
                    "query": f"{base} {patterns[0]}",
                    "description": f"Logs related to {pattern_key} issues",
                })

        # All logs (no filter) for context
        suggestions.append({
            "query": base,
            "description": "All logs from the affected service for context",
        })

        return suggestions

    def get_query_hints(self, alertname: str) -> str:
        """
        Get query hints for the LLM based on alert context.

        Returns a formatted string of suggested queries.
        """
        suggestions = self.suggest_queries(alertname)
        hints = ["Suggested LogQL queries for this alert:"]

        for i, suggestion in enumerate(suggestions, 1):
            hints.append(f"  {i}. {suggestion['description']}:")
            hints.append(f"     {suggestion['query']}")

        return "\n".join(hints)
