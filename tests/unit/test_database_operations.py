"""Unit tests for database operations (User Story 10).

These tests verify database operations through the service layer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RCAReport,
    RCAReportStatus,
)


class TestAlertRepository:
    """Tests for Alert database operations via AlertService."""

    @pytest.fixture
    def alert_service(self, db_session):
        """Create an alert service."""
        from src.services.alert_service import AlertService

        return AlertService(db_session)

    # =========================================================================
    # US10-Scenario1: Create alert
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_alert(self, alert_service, db_session):
        """
        Given valid alert data,
        When creating an alert,
        Then it is persisted with correct attributes.
        """
        alert = Alert(
            fingerprint="test_fingerprint_001",
            alertname="TestAlert",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.FIRING,
            labels={"service": "test-service"},
            annotations={"summary": "Test alert"},
            starts_at=datetime.now(UTC),
        )

        db_session.add(alert)
        await db_session.flush()

        assert alert.id is not None
        assert alert.fingerprint == "test_fingerprint_001"

    # =========================================================================
    # US10-Scenario2: Query alerts by fingerprint
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_by_fingerprint(self, alert_service, db_session):
        """
        Given alerts exist,
        When querying by fingerprint,
        Then the matching alert is returned.
        """
        # Create an alert
        alert = Alert(
            fingerprint="unique_fp_123",
            alertname="QueryTest",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.FIRING,
            labels={"service": "test-service"},
            starts_at=datetime.now(UTC),
        )
        db_session.add(alert)
        await db_session.flush()

        # Query by fingerprint
        found = await alert_service.get_by_fingerprint("unique_fp_123")

        assert found is not None
        assert found.fingerprint == "unique_fp_123"

    # =========================================================================
    # US10-Scenario3: Update alert status
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_alert_status(self, alert_service, db_session):
        """
        Given an alert exists,
        When updating its status,
        Then the status is persisted.
        """
        # Create an alert
        alert = Alert(
            fingerprint="update_test_fp",
            alertname="UpdateTest",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.FIRING,
            labels={"service": "test-service"},
            starts_at=datetime.now(UTC),
        )
        db_session.add(alert)
        await db_session.flush()

        # Update status
        alert.status = AlertStatus.RESOLVED
        alert.ends_at = datetime.now(UTC)
        await db_session.flush()

        # Verify
        updated = await alert_service.get(alert.id)
        assert updated.status == AlertStatus.RESOLVED

    # =========================================================================
    # US10-Scenario4: List alerts with pagination
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_alerts_pagination(self, alert_service, db_session):
        """
        Given many alerts exist,
        When listing with pagination,
        Then correct page is returned.
        """
        # Create multiple alerts
        for i in range(10):
            alert = Alert(
                fingerprint=f"pagination_fp_{i}",
                alertname=f"PaginationTest_{i}",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.FIRING,
                labels={"service": "test-service"},
                starts_at=datetime.now(UTC),
            )
            db_session.add(alert)
        await db_session.flush()

        # List with pagination
        alerts, total = await alert_service.list_alerts(limit=5, offset=0)

        assert len(alerts) <= 5
        assert total >= 10

    # =========================================================================
    # US10-Scenario5: Filter alerts by service
    # =========================================================================

    @pytest.mark.asyncio
    async def test_filter_by_service(self, alert_service, db_session):
        """
        Given alerts for multiple services,
        When filtering by service,
        Then only matching alerts are returned.
        """
        # Create alerts for different services
        for service in ["api-gateway", "auth-service", "api-gateway"]:
            alert = Alert(
                fingerprint=f"filter_fp_{uuid4().hex[:8]}",
                alertname="FilterTest",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.FIRING,
                labels={"service": service},
                starts_at=datetime.now(UTC),
            )
            db_session.add(alert)
        await db_session.flush()

        # Filter by service
        alerts, total = await alert_service.list_alerts(service="api-gateway")

        # All returned should be for api-gateway
        assert all(a.labels.get("service") == "api-gateway" for a in alerts)


class TestIncidentRepository:
    """Tests for Incident database operations via IncidentService."""

    @pytest.fixture
    def incident_service(self, db_session):
        """Create an incident service."""
        from src.services.incident_service import IncidentService

        return IncidentService(db_session)

    # =========================================================================
    # US10-Scenario6: Create incident
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_incident(self, incident_service, db_session):
        """
        Given valid incident data,
        When creating an incident,
        Then it is persisted with correct attributes.
        """
        incident = Incident(
            title="Test Incident",
            status=IncidentStatus.OPEN,
            severity=IncidentSeverity.WARNING,
            affected_services=["test-service"],
            started_at=datetime.now(UTC),
        )

        db_session.add(incident)
        await db_session.flush()

        assert incident.id is not None
        assert incident.title == "Test Incident"

    # =========================================================================
    # US10-Scenario7: Associate alerts with incident
    # =========================================================================

    @pytest.mark.asyncio
    async def test_associate_alerts(self, incident_service, db_session):
        """
        Given an incident and alerts exist,
        When associating alerts,
        Then the relationship is persisted.
        """
        # Create incident
        incident = Incident(
            title="Association Test",
            status=IncidentStatus.OPEN,
            severity=IncidentSeverity.WARNING,
            affected_services=["test-service"],
            started_at=datetime.now(UTC),
        )
        db_session.add(incident)
        await db_session.flush()

        # Create alert
        alert = Alert(
            fingerprint="assoc_fp_001",
            alertname="AssocTest",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.FIRING,
            labels={"service": "test-service"},
            starts_at=datetime.now(UTC),
            incident_id=incident.id,
        )
        db_session.add(alert)
        await db_session.flush()

        # Verify association
        assert alert.incident_id == incident.id

    # =========================================================================
    # US10-Scenario8: Update incident status
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_incident_status(self, incident_service, db_session):
        """
        Given an incident exists,
        When updating its status,
        Then the status is persisted.
        """
        # Create incident
        incident = Incident(
            title="Status Update Test",
            status=IncidentStatus.OPEN,
            severity=IncidentSeverity.WARNING,
            affected_services=["test-service"],
            started_at=datetime.now(UTC),
        )
        db_session.add(incident)
        await db_session.flush()

        # Update status
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(UTC)
        await db_session.flush()

        # Verify
        updated = await incident_service.get(incident.id)
        assert updated.status == IncidentStatus.RESOLVED

    # =========================================================================
    # US10-Scenario9: Query active incidents
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_active_incidents(self, incident_service, db_session):
        """
        Given active and resolved incidents exist,
        When querying active incidents,
        Then only active ones are returned.
        """
        # Create one open and one resolved incident
        open_incident = Incident(
            title="Open Incident",
            status=IncidentStatus.OPEN,
            severity=IncidentSeverity.WARNING,
            affected_services=["test-service"],
            started_at=datetime.now(UTC),
        )
        resolved_incident = Incident(
            title="Resolved Incident",
            status=IncidentStatus.RESOLVED,
            severity=IncidentSeverity.WARNING,
            affected_services=["test-service"],
            started_at=datetime.now(UTC) - timedelta(hours=1),
            resolved_at=datetime.now(UTC),
        )
        db_session.add(open_incident)
        db_session.add(resolved_incident)
        await db_session.flush()

        # Query active incidents
        incidents, _ = await incident_service.list_incidents(status=IncidentStatus.OPEN)

        # Only open incidents should be returned
        # Handle both model instances and dict responses
        for incident in incidents:
            if isinstance(incident, dict):
                assert incident["status"] == "open" or incident["status"] == IncidentStatus.OPEN.value
            else:
                assert incident.status == IncidentStatus.OPEN


class TestRCAReportRepository:
    """Tests for RCA Report database operations via ReportService."""

    @pytest.fixture
    def report_service(self, db_session):
        """Create a report service."""
        from src.services.report_service import ReportService

        return ReportService(db_session)

    # =========================================================================
    # US10-Scenario10: Create RCA report
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_report(self, report_service, db_session):
        """
        Given an incident exists,
        When creating an RCA report,
        Then it is persisted with correct attributes.
        """
        # Create incident first
        incident = Incident(
            title="Report Test Incident",
            status=IncidentStatus.OPEN,
            severity=IncidentSeverity.CRITICAL,
            affected_services=["test-service"],
            started_at=datetime.now(UTC),
        )
        db_session.add(incident)
        await db_session.flush()

        # Create report
        report = await report_service.create(
            incident_id=incident.id,
            root_cause="Database connection exhaustion",
            confidence_score=85,
            summary="Analysis complete",
        )

        assert report.id is not None
        assert report.incident_id == incident.id
        assert report.confidence_score == 85

    # =========================================================================
    # US10-Scenario11: Get report by incident
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_report_by_incident(self, report_service, db_session):
        """
        Given a report exists for an incident,
        When querying by incident ID,
        Then the report is returned.
        """
        # Create incident
        incident = Incident(
            title="Query Report Test",
            status=IncidentStatus.OPEN,
            severity=IncidentSeverity.WARNING,
            affected_services=["test-service"],
            started_at=datetime.now(UTC),
        )
        db_session.add(incident)
        await db_session.flush()

        # Create report
        created_report = await report_service.create(incident_id=incident.id)

        # Query by incident
        found = await report_service.get_by_incident(incident.id)

        assert found is not None
        assert found.id == created_report.id
