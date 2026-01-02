"""Unit tests for API schemas."""

from __future__ import annotations

from datetime import datetime

from src.api.schemas import (
    AlertManagerAlert,
    AlertManagerWebhookPayload,
    AlertSeverity,
    AlertStatus,
)


class TestAlertManagerSchemas:
    """Tests for Alert Manager webhook schemas."""

    def test_alert_manager_alert_valid(self):
        """Test valid alert parsing."""
        alert = AlertManagerAlert(
            status=AlertStatus.FIRING,
            labels={"alertname": "HighCPU", "severity": "critical"},
            annotations={"summary": "CPU is high"},
            startsAt=datetime.now(),
            fingerprint="abc123",
        )
        assert alert.status == AlertStatus.FIRING
        assert alert.labels["alertname"] == "HighCPU"
        assert alert.fingerprint == "abc123"

    def test_alert_manager_alert_defaults(self):
        """Test alert with minimal required fields."""
        alert = AlertManagerAlert(
            status=AlertStatus.RESOLVED,
            labels={},
            annotations={},
            startsAt=datetime.now(),
            fingerprint="def456",
        )
        assert alert.endsAt is None
        assert alert.generatorURL is None

    def test_webhook_payload(self):
        """Test webhook payload parsing."""
        payload = AlertManagerWebhookPayload(
            receiver="test",
            status="firing",
            alerts=[
                AlertManagerAlert(
                    status=AlertStatus.FIRING,
                    labels={"alertname": "Test"},
                    annotations={},
                    startsAt=datetime.now(),
                    fingerprint="test123",
                )
            ],
            groupLabels={"alertname": "Test"},
            commonLabels={},
            commonAnnotations={},
            externalURL="http://localhost:9093",
        )
        assert payload.receiver == "test"
        assert len(payload.alerts) == 1
        assert payload.alerts[0].fingerprint == "test123"


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.INFO.value == "info"


class TestAlertStatus:
    """Tests for AlertStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert AlertStatus.FIRING.value == "firing"
        assert AlertStatus.RESOLVED.value == "resolved"
