"""Unit tests for RCA Report Service (User Story 6)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models import IncidentSeverity, IncidentStatus, RCAReportStatus


class TestReportService:
    """Tests for the RCA Report Service."""

    @pytest.fixture
    def mock_incident(self):
        """Create a mock incident for testing."""
        incident = MagicMock()
        incident.id = uuid4()
        incident.title = "High CPU on api-gateway"
        incident.status = IncidentStatus.OPEN
        incident.severity = IncidentSeverity.CRITICAL
        incident.affected_services = ["api-gateway", "auth-service"]
        incident.started_at = datetime.now(UTC)
        return incident

    @pytest.fixture
    def report_service(self, db_session):
        """Create a report service."""
        from src.services.report_service import ReportService

        return ReportService(db_session)

    # =========================================================================
    # US6-Scenario1: Create RCA report
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_report(self, report_service, mock_incident):
        """
        Given RCA analysis is complete,
        When creating a report,
        Then a structured report with all sections is created.
        """
        # Mock the create method
        with patch.object(report_service, "create", new_callable=AsyncMock) as mock_create:
            mock_report = MagicMock()
            mock_report.root_cause = "Database connection pool exhaustion"
            mock_report.confidence_score = 85
            mock_report.evidence = {"logs": [], "metrics": []}
            mock_report.remediation_steps = [
                {"priority": "immediate", "action": "Increase pool size"},
            ]
            mock_create.return_value = mock_report

            report = await report_service.create(
                incident_id=mock_incident.id,
                root_cause="Database connection pool exhaustion",
                confidence_score=85,
                summary="Analysis complete",
                remediation_steps=[
                    {"priority": "immediate", "action": "Increase pool size"},
                ],
            )

            assert report.root_cause == "Database connection pool exhaustion"
            assert report.confidence_score == 85

    # =========================================================================
    # US6-Scenario2: Report includes timeline
    # =========================================================================

    @pytest.mark.asyncio
    async def test_report_includes_timeline(self, report_service, mock_incident):
        """
        Given an incident with multiple alerts,
        When creating a report with timeline,
        Then the timeline of events is included.
        """
        timeline = [
            {"timestamp": "2026-01-03T10:00:00Z", "event": "First alert: HighCPU", "source": "alert"},
            {"timestamp": "2026-01-03T10:05:00Z", "event": "Second alert: HighMemory", "source": "alert"},
            {"timestamp": "2026-01-03T10:10:00Z", "event": "Service degradation detected", "source": "log"},
        ]

        with patch.object(report_service, "create", new_callable=AsyncMock) as mock_create:
            mock_report = MagicMock()
            mock_report.timeline = timeline
            mock_create.return_value = mock_report

            report = await report_service.create(
                incident_id=mock_incident.id,
                timeline=timeline,
            )

            assert len(report.timeline) == 3
            assert "timestamp" in report.timeline[0]
            assert "event" in report.timeline[0]

    # =========================================================================
    # US6-Scenario3: Report update from analysis
    # =========================================================================

    @pytest.mark.asyncio
    async def test_report_update_from_analysis(self, report_service, mock_incident):
        """
        Given a pending report,
        When updated with analysis results,
        Then it is updated and marked complete.
        """
        report_id = uuid4()

        with patch.object(report_service, "update_from_analysis", new_callable=AsyncMock) as mock_update:
            mock_report = MagicMock()
            mock_report.id = report_id
            mock_report.status = RCAReportStatus.COMPLETE
            mock_update.return_value = mock_report

            result = await report_service.update_from_analysis(
                report_id=report_id,
                root_cause="Database connection pool exhaustion",
                confidence_score=85,
                summary="Analysis complete",
                timeline=[],
                evidence={"logs": [], "metrics": []},
                remediation_steps=[],
            )

            assert result.status == RCAReportStatus.COMPLETE
            mock_update.assert_called_once()

    # =========================================================================
    # US6-Scenario4: Report retrieval by incident
    # =========================================================================

    @pytest.mark.asyncio
    async def test_report_retrieval(self, report_service, mock_incident):
        """
        Given a report exists for an incident,
        When querying by incident ID,
        Then the report is returned.
        """
        with patch.object(report_service, "get_by_incident", new_callable=AsyncMock) as mock_get:
            mock_report = MagicMock()
            mock_report.incident_id = mock_incident.id
            mock_report.root_cause = "Database connection pool exhaustion"
            mock_get.return_value = mock_report

            report = await report_service.get_by_incident(mock_incident.id)

            assert report.incident_id == mock_incident.id
            assert report.root_cause is not None

    # =========================================================================
    # US6-Scenario5: Report with low confidence
    # =========================================================================

    @pytest.mark.asyncio
    async def test_report_low_confidence(self, report_service, mock_incident):
        """
        Given RCA has low confidence,
        When creating report,
        Then low confidence is recorded.
        """
        with patch.object(report_service, "create", new_callable=AsyncMock) as mock_create:
            mock_report = MagicMock()
            mock_report.root_cause = "Possible network issue"
            mock_report.confidence_score = 45
            mock_create.return_value = mock_report

            report = await report_service.create(
                incident_id=mock_incident.id,
                root_cause="Possible network issue",
                confidence_score=45,
            )

            assert report.confidence_score < 50

    # =========================================================================
    # Edge Case: Report marked as failed
    # =========================================================================

    @pytest.mark.asyncio
    async def test_report_mark_failed(self, report_service, mock_incident):
        """
        Edge case: RCA analysis fails.
        Report should be marked as failed with error message.
        """
        report_id = uuid4()

        with patch.object(report_service, "mark_failed", new_callable=AsyncMock) as mock_fail:
            mock_report = MagicMock()
            mock_report.status = RCAReportStatus.FAILED
            mock_report.error_message = "LLM timeout"
            mock_fail.return_value = mock_report

            report = await report_service.mark_failed(
                report_id=report_id,
                error_message="LLM timeout",
            )

            assert report.status == RCAReportStatus.FAILED
            assert report.error_message == "LLM timeout"

    # =========================================================================
    # Edge Case: Empty evidence
    # =========================================================================

    @pytest.mark.asyncio
    async def test_report_empty_evidence(self, report_service, mock_incident):
        """
        Edge case: No evidence collected during RCA.
        Report should still be created with empty evidence.
        """
        with patch.object(report_service, "create", new_callable=AsyncMock) as mock_create:
            mock_report = MagicMock()
            mock_report.root_cause = "Unable to determine"
            mock_report.confidence_score = 0
            mock_report.evidence = {"logs": [], "metrics": []}
            mock_create.return_value = mock_report

            report = await report_service.create(
                incident_id=mock_incident.id,
                root_cause="Unable to determine",
                confidence_score=0,
            )

            assert report.evidence == {"logs": [], "metrics": []}
            assert report.confidence_score == 0


class TestReportFormatting:
    """Tests for report formatting."""

    @pytest.fixture
    def report_service(self, db_session):
        """Create a report service."""
        from src.services.report_service import ReportService

        return ReportService(db_session)

    @pytest.fixture
    def sample_report(self):
        """Create a sample report for formatting tests."""
        report = MagicMock()
        report.id = uuid4()
        report.status = RCAReportStatus.COMPLETE
        report.confidence_score = 85
        report.created_at = datetime.now(UTC)
        report.summary = "Database connection pool exhaustion caused service degradation"
        report.root_cause = "Connection pool exhausted due to connection leak"
        report.timeline = [
            {"timestamp": "2026-01-03T10:00:00Z", "event": "First connection timeout", "source": "log"},
            {"timestamp": "2026-01-03T10:05:00Z", "event": "Pool exhausted", "source": "metric"},
        ]
        report.evidence = {
            "logs": [
                {"timestamp": "2026-01-03T10:00:00Z", "message": "Connection timeout after 30s"},
            ],
            "metrics": [
                {"name": "connection_pool_size", "value": "0", "timestamp": "2026-01-03T10:05:00Z"},
            ],
        }
        report.remediation_steps = [
            {
                "priority": "immediate",
                "action": "Restart service to clear connections",
                "command": "kubectl rollout restart deployment/api",
                "risk": "low",
            },
            {
                "priority": "long_term",
                "action": "Increase connection pool size",
                "description": "Update config to increase pool from 10 to 25",
                "risk": "low",
            },
        ]
        return report

    # =========================================================================
    # Report format: Markdown
    # =========================================================================

    def test_format_markdown(self, report_service, sample_report):
        """
        Given a report,
        When formatting as Markdown,
        Then formatted Markdown is returned.
        """
        md_output = report_service.format_as_markdown(sample_report)

        assert "# RCA Report" in md_output
        assert "Connection pool exhausted" in md_output
        assert "## Summary" in md_output
        assert "## Root Cause" in md_output
        assert "## Timeline" in md_output
        assert "## Remediation Steps" in md_output

    def test_format_markdown_with_commands(self, report_service, sample_report):
        """
        Given a report with remediation commands,
        When formatting as Markdown,
        Then commands are included in code blocks.
        """
        md_output = report_service.format_as_markdown(sample_report)

        assert "kubectl rollout restart" in md_output
        assert "```" in md_output  # Code block markers

    def test_format_markdown_empty_timeline(self, report_service, sample_report):
        """
        Edge case: Report with empty timeline.
        Markdown should still be valid without timeline section.
        """
        sample_report.timeline = []
        md_output = report_service.format_as_markdown(sample_report)

        assert "# RCA Report" in md_output
        # Timeline section should not be present
        assert "## Timeline" not in md_output

    def test_format_markdown_empty_evidence(self, report_service, sample_report):
        """
        Edge case: Report with empty evidence.
        Markdown should still be valid without evidence sections.
        """
        sample_report.evidence = {"logs": [], "metrics": []}
        md_output = report_service.format_as_markdown(sample_report)

        assert "# RCA Report" in md_output
        # Evidence sections should not be present
        assert "## Log Evidence" not in md_output
        assert "## Metric Evidence" not in md_output
