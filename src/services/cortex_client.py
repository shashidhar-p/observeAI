"""Cortex client for querying metrics via PromQL."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CortexClient:
    """
    Async client for querying Cortex metrics.

    Uses the Cortex HTTP API (Prometheus-compatible) to execute PromQL queries.
    """

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        """
        Initialize the Cortex client.

        Args:
            base_url: Cortex server URL (defaults to settings.cortex_url)
            timeout: Query timeout in seconds (defaults to settings.cortex_timeout_seconds)
        """
        self.base_url = (base_url or settings.cortex_url).rstrip("/")
        self.timeout = timeout or settings.cortex_timeout_seconds

    async def range_query(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "60s",
    ) -> dict:
        """
        Execute a PromQL range query.

        Args:
            query: PromQL query string
            start: Start time for the query range
            end: End time for the query range
            step: Query resolution step (default: 60s)

        Returns:
            dict: Query results containing metric series

        Raises:
            httpx.HTTPStatusError: If the Cortex API returns an error
            httpx.TimeoutException: If the query times out
        """
        params = {
            "query": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "step": step,
        }

        logger.debug(f"Executing Cortex query: {query}")
        logger.debug(f"Time range: {start} to {end}, step: {step}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/prom/query_range",
                params=params,
            )
            response.raise_for_status()
            result = response.json()

        # Log query stats
        if "data" in result:
            series = result["data"].get("result", [])
            logger.debug(f"Query returned {len(series)} series")

        return result

    async def instant_query(self, query: str, time: datetime | None = None) -> dict:
        """
        Execute a PromQL instant query.

        Args:
            query: PromQL query string
            time: Evaluation time (defaults to now)

        Returns:
            dict: Query results
        """
        params = {"query": query}
        if time:
            params["time"] = int(time.timestamp())

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/prom/query",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def series(
        self,
        match: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict]:
        """
        Find series by label matchers.

        Args:
            match: List of series selectors (e.g., ['up{job="api"}'])
            start: Optional start time
            end: Optional end time

        Returns:
            list: Matching series
        """
        params = {"match[]": match}
        if start:
            params["start"] = int(start.timestamp())
        if end:
            params["end"] = int(end.timestamp())

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/prom/series",
                params=params,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [])

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
            params["start"] = int(start.timestamp())
        if end:
            params["end"] = int(end.timestamp())

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/prom/labels",
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
            params["start"] = int(start.timestamp())
        if end:
            params["end"] = int(end.timestamp())

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/prom/label/{label}/values",
                params=params,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [])

    async def ready(self) -> bool:
        """Check if Cortex is ready to accept queries."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/ready")
                return response.status_code == 200
        except Exception:
            return False

    def build_label_selector(self, labels: dict[str, str]) -> str:
        """
        Build a PromQL label selector from a dictionary.

        Args:
            labels: Dictionary of label key-value pairs

        Returns:
            str: PromQL label selector (e.g., '{service="api", pod="api-123"}')
        """
        if not labels:
            return "{}"

        filters = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ", ".join(filters) + "}"

    def build_cpu_query(self, instance: str | None = None) -> str:
        """
        Build a PromQL query for CPU utilization.

        Args:
            instance: Optional instance filter

        Returns:
            str: PromQL query for CPU percentage
        """
        selector = f'mode="idle", instance="{instance}"' if instance else 'mode="idle"'
        return f'100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{{{selector}}}[5m])))'

    def build_memory_query(self, instance: str | None = None) -> str:
        """
        Build a PromQL query for memory utilization.

        Args:
            instance: Optional instance filter

        Returns:
            str: PromQL query for memory percentage
        """
        selector = f'{{instance="{instance}"}}' if instance else ""
        return f"100 * (1 - (node_memory_MemAvailable_bytes{selector} / node_memory_MemTotal_bytes{selector}))"

    def build_error_rate_query(self, service: str | None = None) -> str:
        """
        Build a PromQL query for HTTP error rate.

        Args:
            service: Optional service filter

        Returns:
            str: PromQL query for error rate
        """
        if service:
            error_selector = f'status=~"5..", service="{service}"'
            total_selector = f'service="{service}"'
            return f'sum(rate(http_requests_total{{{error_selector}}}[5m])) / sum(rate(http_requests_total{{{total_selector}}}[5m]))'
        else:
            return 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))'

    @staticmethod
    def aggregate_results(
        results: dict,
        aggregation: str = "avg",
        max_series: int = 50,
    ) -> dict:
        """
        Aggregate metric results for easier consumption.

        Args:
            results: Raw Cortex API response
            aggregation: Aggregation method - "avg", "max", "min", "sum", "latest"
            max_series: Maximum number of series to keep

        Returns:
            dict: Aggregated results with summary statistics
        """
        if "data" not in results or "result" not in results["data"]:
            return results

        series_list = results["data"]["result"]

        if len(series_list) <= max_series:
            # Just add summaries
            return CortexClient._add_summaries(results, aggregation)

        # Need to downsample series
        # Sort by relevance (series with higher values first for avg/max/sum)
        scored_series = []
        for s in series_list:
            values = s.get("values", [])
            numeric_values = [
                float(v[1]) for v in values
                if v[1] != "NaN" and v[1] is not None
            ]

            if not numeric_values:
                score = 0
            elif aggregation in ("max", "sum"):
                score = max(numeric_values)
            elif aggregation == "min":
                score = -min(numeric_values)  # Negative so lower values rank higher
            else:  # avg, latest
                score = sum(numeric_values) / len(numeric_values)

            scored_series.append((score, s))

        # Sort and keep top series
        scored_series.sort(key=lambda x: x[0], reverse=True)
        kept_series = [s for _, s in scored_series[:max_series]]

        sampled_result = {
            "status": results.get("status"),
            "data": {
                "resultType": results["data"].get("resultType"),
                "result": kept_series,
            },
            "_aggregation": {
                "original_series": len(series_list),
                "kept_series": len(kept_series),
                "method": aggregation,
            },
        }

        return CortexClient._add_summaries(sampled_result, aggregation)

    @staticmethod
    def _add_summaries(results: dict, _aggregation: str) -> dict:
        """Add summary statistics to each series."""
        if "data" not in results or "result" not in results["data"]:
            return results

        for series in results["data"]["result"]:
            values = series.get("values", [])
            numeric_values = [
                float(v[1]) for v in values
                if v[1] != "NaN" and v[1] is not None
            ]

            if numeric_values:
                series["_summary"] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "latest": numeric_values[-1],
                    "count": len(numeric_values),
                }
            else:
                series["_summary"] = {"min": None, "max": None, "avg": None, "latest": None, "count": 0}

        return results

    @staticmethod
    def compute_rate_of_change(values: list[tuple]) -> float | None:
        """
        Compute rate of change for a metric series.

        Args:
            values: List of (timestamp, value) tuples

        Returns:
            float: Rate of change per second, or None if insufficient data
        """
        if len(values) < 2:
            return None

        numeric_values = [
            (float(v[0]), float(v[1]))
            for v in values
            if v[1] != "NaN" and v[1] is not None
        ]

        if len(numeric_values) < 2:
            return None

        first_ts, first_val = numeric_values[0]
        last_ts, last_val = numeric_values[-1]

        time_diff = last_ts - first_ts
        if time_diff <= 0:
            return None

        return (last_val - first_val) / time_diff

    @staticmethod
    def detect_anomalies(
        results: dict,
        threshold_std: float = 2.0,
    ) -> list[dict]:
        """
        Detect anomalies in metric data using standard deviation.

        Args:
            results: Cortex API response
            threshold_std: Number of standard deviations for anomaly threshold

        Returns:
            list: Detected anomalies with timestamps and values
        """
        anomalies = []

        if "data" not in results or "result" not in results["data"]:
            return anomalies

        for series in results["data"]["result"]:
            values = series.get("values", [])
            numeric_values = [
                (float(v[0]), float(v[1]))
                for v in values
                if v[1] != "NaN" and v[1] is not None
            ]

            if len(numeric_values) < 3:
                continue

            vals = [v[1] for v in numeric_values]
            mean = sum(vals) / len(vals)
            variance = sum((x - mean) ** 2 for x in vals) / len(vals)
            std = variance ** 0.5

            if std == 0:
                continue

            for ts, val in numeric_values:
                z_score = abs(val - mean) / std
                if z_score > threshold_std:
                    anomalies.append({
                        "timestamp": ts,
                        "value": val,
                        "z_score": z_score,
                        "metric": series.get("metric", {}),
                    })

        return anomalies
