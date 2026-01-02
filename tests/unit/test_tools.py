"""Unit tests for RCA agent tools."""

from __future__ import annotations

import pytest

from src.tools.generate_report import (
    RemediationStep,
    execute_generate_report,
)
from src.tools.query_cortex import (
    QUERY_CORTEX_TOOL,
    PromQLQueryBuilder,
    build_cpu_query,
    build_error_rate_query,
    build_latency_query,
    build_memory_query,
    format_cortex_results,
)
from src.tools.query_loki import (
    QUERY_LOKI_TOOL,
    LogQLQueryBuilder,
    build_alert_query,
    format_loki_results,
)


class TestReportGeneration:
    """Tests for report generation tool."""

    def test_remediation_step_validation(self):
        """Test RemediationStep validation."""
        step = RemediationStep(
            priority="immediate",
            action="Restart the service",
            command="kubectl rollout restart deployment/api",
            risk="low",
        )
        assert step.priority == "immediate"
        assert step.risk == "low"

    def test_remediation_step_invalid_priority(self):
        """Test RemediationStep rejects invalid priority."""
        with pytest.raises(ValueError):
            RemediationStep(
                priority="unknown",
                action="Test action",
            )

    def test_remediation_step_invalid_risk(self):
        """Test RemediationStep rejects invalid risk."""
        with pytest.raises(ValueError):
            RemediationStep(
                priority="immediate",
                action="Test action",
                risk="unknown",
            )

    def test_execute_generate_report(self):
        """Test report generation execution."""
        result = execute_generate_report(
            root_cause="Test root cause",
            confidence_score=85,
            summary="Test summary",
            timeline=[
                {"timestamp": "2025-01-15T10:00:00Z", "event": "Alert fired", "source": "alert"}
            ],
            evidence={
                "logs": [{"timestamp": "2025-01-15T10:00:00Z", "message": "Error occurred"}],
                "metrics": [{"name": "cpu_usage", "value": 95.0, "timestamp": "2025-01-15T10:00:00Z"}],
            },
            remediation_steps=[
                {"priority": "immediate", "action": "Restart service", "risk": "low"}
            ],
        )
        assert result["success"] is True
        assert result["report"]["root_cause"] == "Test root cause"
        assert result["report"]["confidence_score"] == 85


class TestLogQLQueryBuilder:
    """Tests for LogQL query builder."""

    def test_build_base_selector_with_labels(self):
        """Test building base selector with labels."""
        builder = LogQLQueryBuilder(labels={"service": "api", "namespace": "prod"})
        selector = builder.build_base_selector()
        assert 'service="api"' in selector
        assert 'namespace="prod"' in selector

    def test_build_base_selector_empty(self):
        """Test building base selector with no labels."""
        builder = LogQLQueryBuilder()
        selector = builder.build_base_selector()
        assert selector == "{}"

    def test_build_error_query(self):
        """Test building error log query."""
        builder = LogQLQueryBuilder(labels={"service": "api"})
        query = builder.build_error_query()
        assert 'service="api"' in query
        assert "error|exception|fail|fatal|panic|critical" in query

    def test_build_alert_query(self):
        """Test building query from alert labels."""
        query = build_alert_query({"service": "payment", "namespace": "prod"})
        assert 'service="payment"' in query
        assert 'namespace="prod"' in query


class TestPromQLQueryBuilder:
    """Tests for PromQL query builder."""

    def test_build_label_selector(self):
        """Test building label selector."""
        builder = PromQLQueryBuilder(labels={"service": "api", "instance": "localhost:8080"})
        selector = builder.build_label_selector()
        assert 'service="api"' in selector
        assert 'instance="localhost:8080"' in selector

    def test_build_cpu_query(self):
        """Test CPU query generation."""
        query = build_cpu_query()
        assert "node_cpu_seconds_total" in query
        assert 'mode="idle"' in query

    def test_build_cpu_query_with_labels(self):
        """Test CPU query with labels."""
        query = build_cpu_query(labels={"instance": "node1"})
        assert 'instance="node1"' in query

    def test_build_memory_query(self):
        """Test memory query generation."""
        query = build_memory_query()
        assert "node_memory_MemAvailable_bytes" in query
        assert "node_memory_MemTotal_bytes" in query

    def test_build_error_rate_query(self):
        """Test error rate query generation."""
        query = build_error_rate_query(service="api")
        assert 'service="api"' in query
        assert 'status=~"5.."' in query

    def test_build_latency_query(self):
        """Test latency query generation."""
        query = build_latency_query(service="api", percentile=0.99)
        assert "histogram_quantile(0.99" in query
        assert "http_request_duration_seconds_bucket" in query


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_loki_tool_definition(self):
        """Test Loki tool has required fields."""
        assert QUERY_LOKI_TOOL["name"] == "query_loki"
        assert "input_schema" in QUERY_LOKI_TOOL
        assert "logql_query" in QUERY_LOKI_TOOL["input_schema"]["properties"]

    def test_cortex_tool_definition(self):
        """Test Cortex tool has required fields."""
        assert QUERY_CORTEX_TOOL["name"] == "query_cortex"
        assert "input_schema" in QUERY_CORTEX_TOOL
        assert "promql_query" in QUERY_CORTEX_TOOL["input_schema"]["properties"]


class TestResultFormatters:
    """Tests for result formatting functions."""

    def test_format_loki_empty_results(self):
        """Test formatting empty Loki results."""
        result = format_loki_results({})
        assert result["logs"] == []
        assert result["streams_count"] == 0
        assert result["total_entries"] == 0

    def test_format_loki_results(self):
        """Test formatting Loki results with data."""
        raw_result = {
            "data": {
                "result": [
                    {
                        "stream": {"service": "api"},
                        "values": [
                            ["1705312800000000000", "Log message 1"],
                            ["1705312801000000000", "Log message 2"],
                        ]
                    }
                ]
            }
        }
        result = format_loki_results(raw_result)
        assert result["streams_count"] == 1
        assert result["total_entries"] == 2
        assert len(result["logs"]) == 2

    def test_format_cortex_empty_results(self):
        """Test formatting empty Cortex results."""
        result = format_cortex_results({})
        assert result["metrics"] == []
        assert result["series_count"] == 0

    def test_format_cortex_results(self):
        """Test formatting Cortex results with data."""
        raw_result = {
            "data": {
                "result": [
                    {
                        "metric": {"service": "api"},
                        "values": [
                            [1705312800, "95.5"],
                            [1705312860, "96.2"],
                        ]
                    }
                ]
            }
        }
        result = format_cortex_results(raw_result)
        assert result["series_count"] == 1
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["summary"]["max"] == 96.2
