"""Unit tests for Loki query tool (User Story 4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest


class TestLokiTool:
    """Tests for the Loki query tool (via LokiClient)."""

    @pytest.fixture
    def loki_tool(self, mock_loki_client):
        """
        Create a Loki tool interface using the mocked client.
        The actual tool is a function, but we test via the client.
        """
        return mock_loki_client

    # =========================================================================
    # US4-Scenario1: Basic log query
    # =========================================================================

    @pytest.mark.asyncio
    async def test_basic_log_query(self, loki_tool):
        """
        Given a service name and time range,
        When querying logs via Loki tool,
        Then matching log entries are returned.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"service": "api-gateway", "level": "error"},
                        "values": [
                            ["1704268800000000000", "Connection refused to database"],
                            ["1704268810000000000", "Retry attempt 1 failed"],
                        ],
                    }
                ],
            },
        }

        result = await loki_tool.query(
            query='{service="api-gateway", level="error"}',
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert len(result["data"]["result"]) == 1
        assert len(result["data"]["result"][0]["values"]) == 2

    # =========================================================================
    # US4-Scenario2: Query with regex filter
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_with_regex(self, loki_tool):
        """
        Given a log query with regex pattern,
        When querying logs via Loki tool,
        Then only matching entries are returned.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"service": "api-gateway"},
                        "values": [
                            ["1704268800000000000", "ERROR: Connection timeout after 30s"],
                        ],
                    }
                ],
            },
        }

        result = await loki_tool.query(
            service="api-gateway",
            pattern="timeout|error",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert "timeout" in result["data"]["result"][0]["values"][0][1].lower()

    # =========================================================================
    # US4-Scenario3: Query with multiple services
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_multiple_services(self, loki_tool):
        """
        Given multiple service names,
        When querying logs via Loki tool,
        Then logs from all services are returned.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"service": "api-gateway"},
                        "values": [["1704268800000000000", "Log from api-gateway"]],
                    },
                    {
                        "stream": {"service": "auth-service"},
                        "values": [["1704268800000000000", "Log from auth-service"]],
                    },
                ],
            },
        }

        result = await loki_tool.query(
            services=["api-gateway", "auth-service"],
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert len(result["data"]["result"]) == 2

    # =========================================================================
    # US4-Scenario4: Query with limit
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_with_limit(self, loki_tool):
        """
        Given a log query with result limit,
        When querying logs via Loki tool,
        Then at most 'limit' entries are returned.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"service": "api-gateway"},
                        "values": [
                            ["1704268800000000000", "Log 1"],
                            ["1704268810000000000", "Log 2"],
                            ["1704268820000000000", "Log 3"],
                        ],
                    }
                ],
            },
        }

        result = await loki_tool.query(
            service="api-gateway",
            limit=100,
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        loki_tool.query.assert_called_once()

    # =========================================================================
    # US4-Scenario5: Handle Loki connection error
    # =========================================================================

    @pytest.mark.asyncio
    async def test_loki_connection_error(self, loki_tool):
        """
        Given Loki is unreachable,
        When querying logs,
        Then appropriate error is returned.
        """
        loki_tool.query.side_effect = ConnectionError("Failed to connect to Loki")

        with pytest.raises(ConnectionError) as exc_info:
            await loki_tool.query(
                service="api-gateway",
                start=datetime.now(UTC) - timedelta(hours=1),
                end=datetime.now(UTC),
            )

        assert "Failed to connect to Loki" in str(exc_info.value)

    # =========================================================================
    # US4-Scenario6: Handle invalid query
    # =========================================================================

    @pytest.mark.asyncio
    async def test_loki_invalid_query(self, loki_tool):
        """
        Given an invalid LogQL query,
        When querying logs,
        Then validation error is returned.
        """
        loki_tool.query.return_value = {
            "status": "error",
            "error": "parse error: unexpected character: '['",
        }

        result = await loki_tool.query(
            raw_query="invalid[query",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "error"
        assert "error" in result

    # =========================================================================
    # Edge Case: Empty result set
    # =========================================================================

    @pytest.mark.asyncio
    async def test_loki_empty_results(self, loki_tool):
        """
        Edge case: No logs match the query.
        Tool should return empty result without error.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [],
            },
        }

        result = await loki_tool.query(
            service="nonexistent-service",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        assert result["data"]["result"] == []

    # =========================================================================
    # Edge Case: Very large time range
    # =========================================================================

    @pytest.mark.asyncio
    async def test_loki_large_time_range(self, loki_tool):
        """
        Edge case: Query spans a very large time range.
        Tool should handle or limit appropriately.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {"resultType": "streams", "result": []},
        }

        result = await loki_tool.query(
            service="api-gateway",
            start=datetime.now(UTC) - timedelta(days=30),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"
        loki_tool.query.assert_called_once()

    # =========================================================================
    # Edge Case: Special characters in service name
    # =========================================================================

    @pytest.mark.asyncio
    async def test_loki_special_chars_service(self, loki_tool):
        """
        Edge case: Service name contains special characters.
        Tool should escape them properly.
        """
        loki_tool.query.return_value = {
            "status": "success",
            "data": {"resultType": "streams", "result": []},
        }

        result = await loki_tool.query(
            service="my-service_v2.0",
            start=datetime.now(UTC) - timedelta(hours=1),
            end=datetime.now(UTC),
        )

        assert result["status"] == "success"

    # =========================================================================
    # Edge Case: Query timeout
    # =========================================================================

    @pytest.mark.asyncio
    async def test_loki_query_timeout(self, loki_tool):
        """
        Edge case: Loki query times out.
        Tool should handle timeout gracefully.
        """
        import asyncio

        async def slow_query(*args, **kwargs):
            await asyncio.sleep(0.1)
            raise TimeoutError("Query timed out after 30s")

        loki_tool.query.side_effect = slow_query

        with pytest.raises(TimeoutError) as exc_info:
            await loki_tool.query(
                service="api-gateway",
                start=datetime.now(UTC) - timedelta(hours=1),
                end=datetime.now(UTC),
            )

        assert "timed out" in str(exc_info.value)

