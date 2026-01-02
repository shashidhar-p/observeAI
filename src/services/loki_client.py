"""Loki client for querying logs via LogQL."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LokiClient:
    """
    Async client for querying Loki logs.

    Uses the Loki HTTP API to execute LogQL queries and retrieve log entries.
    """

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        """
        Initialize the Loki client.

        Args:
            base_url: Loki server URL (defaults to settings.loki_url)
            timeout: Query timeout in seconds (defaults to settings.loki_timeout_seconds)
        """
        self.base_url = (base_url or settings.loki_url).rstrip("/")
        self.timeout = timeout or settings.loki_timeout_seconds

    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
        direction: str = "backward",
    ) -> dict:
        """
        Execute a LogQL range query.

        Args:
            query: LogQL query string (e.g., '{job="api"} |= "error"')
            start: Start time for the query range
            end: End time for the query range
            limit: Maximum number of entries to return (default: 1000)
            direction: Query direction - "forward" or "backward" (default: backward)

        Returns:
            dict: Query results containing streams and values

        Raises:
            httpx.HTTPStatusError: If the Loki API returns an error
            httpx.TimeoutException: If the query times out
        """
        # Convert timestamps to nanoseconds (Loki's native format)
        start_ns = int(start.timestamp() * 1e9)
        end_ns = int(end.timestamp() * 1e9)

        params = {
            "query": query,
            "start": start_ns,
            "end": end_ns,
            "limit": limit,
            "direction": direction,
        }

        logger.debug(f"Executing Loki query: {query}")
        logger.debug(f"Time range: {start} to {end}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params,
            )
            response.raise_for_status()
            result = response.json()

        # Log query stats
        if "data" in result:
            streams = result["data"].get("result", [])
            total_entries = sum(len(s.get("values", [])) for s in streams)
            logger.debug(f"Query returned {len(streams)} streams, {total_entries} entries")

        return result

    async def query_instant(self, query: str, time: datetime | None = None) -> dict:
        """
        Execute a LogQL instant query.

        Args:
            query: LogQL query string
            time: Evaluation time (defaults to now)

        Returns:
            dict: Query results
        """
        params = {"query": query}
        if time:
            params["time"] = int(time.timestamp() * 1e9)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/query",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def labels(self, start: datetime | None = None, end: datetime | None = None) -> list[str]:
        """
        Get all label names.

        Args:
            start: Optional start time
            end: Optional end time

        Returns:
            list: Label names
        """
        params = {}
        if start:
            params["start"] = int(start.timestamp() * 1e9)
        if end:
            params["end"] = int(end.timestamp() * 1e9)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/labels",
                params=params,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [])

    async def label_values(
        self, label: str, start: datetime | None = None, end: datetime | None = None
    ) -> list[str]:
        """
        Get values for a specific label.

        Args:
            label: Label name
            start: Optional start time
            end: Optional end time

        Returns:
            list: Label values
        """
        params = {}
        if start:
            params["start"] = int(start.timestamp() * 1e9)
        if end:
            params["end"] = int(end.timestamp() * 1e9)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/label/{label}/values",
                params=params,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [])

    async def ready(self) -> bool:
        """Check if Loki is ready to accept queries."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/ready")
                return response.status_code == 200
        except Exception:
            return False

    def build_label_filter(self, labels: dict[str, str]) -> str:
        """
        Build a LogQL label filter from a dictionary.

        Args:
            labels: Dictionary of label key-value pairs

        Returns:
            str: LogQL label selector (e.g., '{service="api", pod="api-123"}')
        """
        if not labels:
            return "{}"

        filters = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ", ".join(filters) + "}"

    def build_error_query(self, labels: dict[str, str]) -> str:
        """
        Build a LogQL query for error logs.

        Args:
            labels: Dictionary of label key-value pairs

        Returns:
            str: LogQL query for error logs
        """
        label_filter = self.build_label_filter(labels)
        return f'{label_filter} |~ "(?i)(error|exception|fail|fatal)"'

    @staticmethod
    def sample_results(results: dict, max_entries: int = 500, strategy: str = "even") -> dict:
        """
        Sample log results for high-cardinality data.

        Args:
            results: Raw Loki API response
            max_entries: Maximum entries to keep after sampling
            strategy: Sampling strategy - "even" (evenly distributed),
                     "head" (first N), "tail" (last N), "priority" (keep errors)

        Returns:
            dict: Sampled results
        """
        if "data" not in results or "result" not in results["data"]:
            return results

        streams = results["data"]["result"]
        total_entries = sum(len(s.get("values", [])) for s in streams)

        if total_entries <= max_entries:
            return results  # No sampling needed

        sampled_streams = []

        if strategy == "priority":
            # Keep error logs preferentially
            error_patterns = ["error", "exception", "fail", "fatal", "panic", "critical"]

            error_entries = []
            other_entries = []

            for stream in streams:
                labels = stream.get("stream", {})
                for value in stream.get("values", []):
                    timestamp_ns, message = value
                    entry = {"timestamp": timestamp_ns, "message": message, "labels": labels}

                    if any(p in message.lower() for p in error_patterns):
                        error_entries.append(entry)
                    else:
                        other_entries.append(entry)

            # Keep all errors up to max, then fill with others
            kept_errors = error_entries[:max_entries]
            remaining = max_entries - len(kept_errors)
            kept_others = other_entries[:remaining] if remaining > 0 else []

            # Reconstruct stream format
            all_kept = kept_errors + kept_others
            all_kept.sort(key=lambda x: x["timestamp"], reverse=True)

            # Group by labels
            label_groups: dict[str, list] = {}
            for entry in all_kept:
                key = str(entry["labels"])
                if key not in label_groups:
                    label_groups[key] = {"stream": entry["labels"], "values": []}
                label_groups[key]["values"].append([entry["timestamp"], entry["message"]])

            sampled_streams = list(label_groups.values())

        elif strategy == "even":
            # Evenly sample from each stream
            sample_per_stream = max(1, max_entries // len(streams)) if streams else max_entries

            for stream in streams:
                values = stream.get("values", [])
                if len(values) <= sample_per_stream:
                    sampled_streams.append(stream)
                else:
                    # Take evenly spaced samples
                    step = len(values) / sample_per_stream
                    sampled_values = [values[int(i * step)] for i in range(sample_per_stream)]
                    sampled_streams.append({
                        "stream": stream.get("stream", {}),
                        "values": sampled_values,
                    })

        elif strategy == "head":
            # Keep first N entries
            entries_kept = 0
            for stream in streams:
                if entries_kept >= max_entries:
                    break
                values = stream.get("values", [])
                to_keep = min(len(values), max_entries - entries_kept)
                sampled_streams.append({
                    "stream": stream.get("stream", {}),
                    "values": values[:to_keep],
                })
                entries_kept += to_keep

        elif strategy == "tail":
            # Keep last N entries (most recent for backward queries)
            entries_kept = 0
            for stream in streams:
                if entries_kept >= max_entries:
                    break
                values = stream.get("values", [])
                to_keep = min(len(values), max_entries - entries_kept)
                sampled_streams.append({
                    "stream": stream.get("stream", {}),
                    "values": values[-to_keep:],
                })
                entries_kept += to_keep

        # Update result with sampled data
        sampled_total = sum(len(s.get("values", [])) for s in sampled_streams)
        return {
            "status": results.get("status"),
            "data": {
                "resultType": results["data"].get("resultType"),
                "result": sampled_streams,
                "stats": results["data"].get("stats", {}),
            },
            "_sampling": {
                "original_entries": total_entries,
                "sampled_entries": sampled_total,
                "strategy": strategy,
            },
        }
