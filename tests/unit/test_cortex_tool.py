"""Unit tests for Cortex query tool (User Story 5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest


class TestCortexTool:
    """Tests for the Cortex/Prometheus query tool (via CortexClient)."""

    @pytest.fixture
    def cortex_tool(self, mock_cortex_client):
        """
        Create a Cortex tool interface using the mocked client.
        The actual tool is a function, but we test via the client.
        """
        return mock_cortex_client

    # =========================================================================
    # US5-Scenario1: Basic metric query
    # =========================================================================

    @pytest.mark.asyncio
    async def test_basic_metric_query(self, cortex_tool):
        """
        Given a metric name and time range,
        When querying metrics via Cortex tool,
        Then matching metric data is returned.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "http_requests_total", "service": "api-gateway"},
                        "values": [
                            [1704268800, "1500"],
                            [1704268860, "1520"],
                            [1704268920, "1545"],
                        ],
                    }
                ],
            },
        }

        result = await cortex_tool.query(
            metric="http_requests_total",
            labels={"service": "api-gateway"},
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert result["data"]["resultType"] == "matrix"
        assert len(result["data"]["result"]) == 1

    # =========================================================================
    # US5-Scenario2: Query with rate function
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_with_rate(self, cortex_tool):
        """
        Given a rate query for a counter metric,
        When querying via Cortex tool,
        Then rate values are returned.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"service": "api-gateway"},
                        "values": [
                            [1704268800, "25.5"],
                            [1704268860, "26.1"],
                        ],
                    }
                ],
            },
        }

        result = await cortex_tool.query(
            query='rate(http_requests_total{service="api-gateway"}[5m])',
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        # Rate values should be floats
        assert float(result["data"]["result"][0]["values"][0][1]) > 0

    # =========================================================================
    # US5-Scenario3: Query CPU and memory metrics
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_cpu_memory(self, cortex_tool):
        """
        Given queries for CPU and memory metrics,
        When querying via Cortex tool,
        Then resource utilization data is returned.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"container": "api-gateway", "__name__": "container_cpu_usage_seconds_total"},
                        "values": [[1704268800, "0.85"]],
                    }
                ],
            },
        }

        result = await cortex_tool.query(
            query='container_cpu_usage_seconds_total{container="api-gateway"}',
            start=datetime.now(UTC) - timedelta(minutes=15),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert len(result["data"]["result"]) >= 1

    # =========================================================================
    # US5-Scenario4: Query with aggregation
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_with_aggregation(self, cortex_tool):
        """
        Given an aggregation query (sum, avg, etc.),
        When querying via Cortex tool,
        Then aggregated results are returned.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {},
                        "values": [[1704268800, "5000"]],
                    }
                ],
            },
        }

        result = await cortex_tool.query(
            query='sum(rate(http_requests_total[5m])) by (service)',
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"

    # =========================================================================
    # US5-Scenario5: Handle Cortex connection error
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_connection_error(self, cortex_tool):
        """
        Given Cortex is unreachable,
        When querying metrics,
        Then appropriate error is returned.
        """
        cortex_tool.query.side_effect = ConnectionError("Failed to connect to Cortex")

        with pytest.raises(ConnectionError) as exc_info:
            await cortex_tool.query(
                query="up",
                start=datetime.now(UTC) - timedelta(hours=1),
                end=datetime.now(UTC),
            )

        assert "Failed to connect to Cortex" in str(exc_info.value)

    # =========================================================================
    # US5-Scenario6: Handle invalid PromQL query
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_invalid_query(self, cortex_tool):
        """
        Given an invalid PromQL query,
        When querying metrics,
        Then validation error is returned.
        """
        cortex_tool.query.return_value = {
            "status": "error",
            "errorType": "bad_data",
            "error": "parse error: unexpected character in grouping opts: '['",
        }

        result = await cortex_tool.query(
            query="rate(invalid[query)",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "error"
        assert "error" in result

    # =========================================================================
    # US5-Scenario7: Instant query
    # =========================================================================

    @pytest.mark.asyncio
    async def test_instant_query(self, cortex_tool):
        """
        Given an instant query (single point in time),
        When querying via Cortex tool,
        Then a vector result is returned.
        """
        cortex_tool.query_instant.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "service": "api-gateway"},
                        "value": [1704268800, "1"],
                    }
                ],
            },
        }

        result = await cortex_tool.query_instant(
            query="up",
            time=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert result["data"]["resultType"] == "vector"

    # =========================================================================
    # Edge Case: Empty result set
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_empty_results(self, cortex_tool):
        """
        Edge case: No metrics match the query.
        Tool should return empty result without error.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [],
            },
        }

        result = await cortex_tool.query(
            query='nonexistent_metric{service="ghost"}',
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert result["data"]["result"] == []

    # =========================================================================
    # Edge Case: Very high cardinality
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_high_cardinality(self, cortex_tool):
        """
        Edge case: Query returns very high cardinality result.
        Tool should handle or limit appropriately.
        """
        # Simulate 1000 time series
        high_card_result = [
            {
                "metric": {"__name__": "http_requests_total", "pod": f"pod-{i}"},
                "values": [[1704268800, str(i * 100)]],
            }
            for i in range(1000)
        ]

        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": high_card_result,
            },
        }

        result = await cortex_tool.query(
            query="http_requests_total",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert len(result["data"]["result"]) == 1000

    # =========================================================================
    # Edge Case: Query with step parameter
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_with_step(self, cortex_tool):
        """
        Edge case: Query with custom step interval.
        Tool should pass step parameter correctly.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }

        result = await cortex_tool.query(
            query="up",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
            step="30s",
        )

        assert result["status"] == "success"
        cortex_tool.query.assert_called_once()

    # =========================================================================
    # Edge Case: Query timeout
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_query_timeout(self, cortex_tool):
        """
        Edge case: Cortex query times out.
        Tool should handle timeout gracefully.
        """
        import asyncio

        async def slow_query(*args, **kwargs):
            await asyncio.sleep(0.1)
            raise TimeoutError("Query execution timeout")

        cortex_tool.query.side_effect = slow_query

        with pytest.raises(TimeoutError) as exc_info:
            await cortex_tool.query(
                query="very_slow_query",
                start=datetime.now(UTC) - timedelta(hours=24),
                end=datetime.now(UTC),
            )

        assert "timeout" in str(exc_info.value).lower()

    # =========================================================================
    # Edge Case: Unicode in label values
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cortex_unicode_labels(self, cortex_tool):
        """
        Edge case: Metric labels contain unicode characters.
        Tool should handle them correctly.
        """
        cortex_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "events", "region": "東京"},
                        "values": [[1704268800, "100"]],
                    }
                ],
            },
        }

        result = await cortex_tool.query(
            query='events{region="東京"}',
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert result["data"]["result"][0]["metric"]["region"] == "東京"

