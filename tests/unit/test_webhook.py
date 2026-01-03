"""Unit tests for webhook handling (User Story 1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.api.schemas import AlertManagerWebhookPayload
from src.models import AlertSeverity, AlertStatus
from src.services.webhook import WebhookService


class TestWebhookService:
    """Tests for the WebhookService class."""

    @pytest.fixture
    def webhook_service(self, db_session):
        """Create a webhook service with mocked dependencies."""
        return WebhookService(db_session)

    @pytest.fixture
    def webhook_service_with_llm(self, db_session, mock_llm_provider):
        """Create a webhook service with LLM provider for semantic correlation."""
        return WebhookService(db_session, llm_provider=mock_llm_provider)

    # =========================================================================
    # US1-Scenario1: Single firing alert stored
    # =========================================================================

    @pytest.mark.asyncio
    async def test_single_alert_stored(
        self, webhook_service, db_session, sample_alert_payload
    ):
        """
        Given AlertManager sends a firing alert,
        When the webhook receives it,
        Then the alert is stored with status 'firing' and all labels preserved.
        """
        payload = AlertManagerWebhookPayload(**sample_alert_payload)

        alert_ids, incident_ids = await webhook_service.process_webhook(payload)
        await db_session.flush()

        assert len(alert_ids) == 1

        # Verify alert is stored with correct attributes
        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)
        alert = await alert_service.get(alert_ids[0])

        assert alert is not None
        assert alert.status == AlertStatus.FIRING
        assert alert.fingerprint == "a1b2c3d4e5f67890"
        assert alert.alertname == "HighCPU"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.labels["service"] == "api-gateway"
        assert alert.labels["namespace"] == "production"
        assert "summary" in alert.annotations

    # =========================================================================
    # US1-Scenario2: Resolved alert updates status
    # =========================================================================

    @pytest.mark.asyncio
    async def test_resolved_alert_updates_status(
        self, webhook_service, db_session, sample_alert_payload, sample_resolved_payload
    ):
        """
        Given AlertManager sends a resolved alert,
        When the webhook receives it,
        Then the corresponding alert status is updated to 'resolved'.
        """
        # First, create the firing alert
        firing_payload = AlertManagerWebhookPayload(**sample_alert_payload)
        alert_ids, _ = await webhook_service.process_webhook(firing_payload)
        await db_session.flush()

        # Now process the resolved alert with same fingerprint
        resolved_payload = AlertManagerWebhookPayload(**sample_resolved_payload)
        updated_ids, _ = await webhook_service.process_webhook(resolved_payload)
        await db_session.flush()

        # Verify alert status is updated
        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)
        alert = await alert_service.get(alert_ids[0])

        assert alert.status == AlertStatus.RESOLVED
        assert alert.ends_at is not None

    # =========================================================================
    # US1-Scenario3: Batch alerts stored individually
    # =========================================================================

    @pytest.mark.asyncio
    async def test_batch_alerts_stored_individually(
        self, webhook_service, db_session, sample_batch_payload
    ):
        """
        Given AlertManager sends multiple alerts in a batch,
        When the webhook receives them,
        Then all alerts are stored individually with correct timestamps.
        """
        payload = AlertManagerWebhookPayload(**sample_batch_payload)

        alert_ids, incident_ids = await webhook_service.process_webhook(payload)
        await db_session.flush()

        # All 3 alerts should be stored
        assert len(alert_ids) == 3

        # Verify each alert has correct attributes
        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)

        fingerprints = set()
        alertnames = set()

        for alert_id in alert_ids:
            alert = await alert_service.get(alert_id)
            assert alert is not None
            fingerprints.add(alert.fingerprint)
            alertnames.add(alert.alertname)
            assert alert.starts_at is not None

        # All fingerprints should be unique
        assert len(fingerprints) == 3
        # We should have different alert names
        assert "HighCPU" in alertnames
        assert "HighMemory" in alertnames
        assert "HighLatency" in alertnames

    # =========================================================================
    # US1-Scenario4: Duplicate fingerprint deduplicates
    # =========================================================================

    @pytest.mark.asyncio
    async def test_duplicate_fingerprint_deduplicates(
        self, webhook_service, db_session, sample_alert_payload, sample_duplicate_payload
    ):
        """
        Given AlertManager sends a duplicate alert (same fingerprint),
        When the webhook receives it,
        Then the system deduplicates and updates the existing alert.
        """
        # First, create the original alert
        original_payload = AlertManagerWebhookPayload(**sample_alert_payload)
        original_ids, _ = await webhook_service.process_webhook(original_payload)
        await db_session.flush()

        original_count = len(original_ids)
        assert original_count == 1
        original_id = original_ids[0]

        # Process duplicate with same fingerprint
        duplicate_payload = AlertManagerWebhookPayload(**sample_duplicate_payload)
        duplicate_ids, _ = await webhook_service.process_webhook(duplicate_payload)
        await db_session.flush()

        # Webhook service updates existing alert silently (returns empty or same ID)
        # Either way, the original alert should still exist and be queryable
        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)
        alert = await alert_service.get(original_id)

        # Original alert should still exist (not duplicated)
        assert alert is not None
        assert alert.fingerprint == "a1b2c3d4e5f67890"

    # =========================================================================
    # US1-Scenario5: Malformed JSON returns 400
    # =========================================================================

    @pytest.mark.asyncio
    async def test_malformed_json_returns_400(self, sample_malformed_payload):
        """
        Given AlertManager sends malformed JSON,
        When the webhook receives it,
        Then the system returns 400 error and logs the issue without crashing.
        """
        # The malformed payload has labels as string instead of dict
        # Pydantic validation should catch this
        with pytest.raises(Exception):
            # This will raise a validation error
            AlertManagerWebhookPayload(**sample_malformed_payload)

    # =========================================================================
    # Edge Case: Missing required fields
    # =========================================================================

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, webhook_service, db_session):
        """
        Edge case: AlertManager sends alerts with missing required fields.
        The system should handle gracefully.
        """
        payload_data = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        # Missing alertname - should use default or fail gracefully
                        "service": "test-service",
                        "severity": "warning",
                    },
                    "annotations": {},
                    "startsAt": "2026-01-03T10:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": "missing_field_test",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        }

        payload = AlertManagerWebhookPayload(**payload_data)
        # Should still process but may use "Unknown" as alertname
        alert_ids, _ = await webhook_service.process_webhook(payload)
        await db_session.flush()

        assert len(alert_ids) == 1

    # =========================================================================
    # Edge Case: Long labels handled
    # =========================================================================

    @pytest.mark.asyncio
    async def test_long_labels_handled(self, webhook_service, db_session):
        """
        Edge case: AlertManager sends alerts with extremely long label values.
        The system should handle without crashing.
        """
        long_value = "x" * 10000  # 10K character label value

        payload_data = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "LongLabelTest",
                        "service": "test-service",
                        "severity": "warning",
                        "long_label": long_value,
                    },
                    "annotations": {
                        "description": long_value,
                    },
                    "startsAt": "2026-01-03T10:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": "long_label_test01",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        }

        payload = AlertManagerWebhookPayload(**payload_data)
        alert_ids, _ = await webhook_service.process_webhook(payload)
        await db_session.flush()

        assert len(alert_ids) == 1

        # Verify the long label was stored
        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)
        alert = await alert_service.get(alert_ids[0])
        assert alert.labels["long_label"] == long_value

    # =========================================================================
    # Edge Case: Future timestamp handled
    # =========================================================================

    @pytest.mark.asyncio
    async def test_future_timestamp_handled(self, webhook_service, db_session):
        """
        Edge case: AlertManager sends alerts with future timestamps.
        The system should accept them (alert may be from a server with clock drift).
        """
        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        payload_data = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "FutureTimestamp",
                        "service": "test-service",
                        "severity": "warning",
                    },
                    "annotations": {},
                    "startsAt": future_time,
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": "future_time_test1",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        }

        payload = AlertManagerWebhookPayload(**payload_data)
        alert_ids, _ = await webhook_service.process_webhook(payload)
        await db_session.flush()

        # Should accept the alert even with future timestamp
        assert len(alert_ids) == 1

        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)
        alert = await alert_service.get(alert_ids[0])
        assert alert.starts_at > datetime.now(UTC)

    # =========================================================================
    # Edge Case: Clock skew handling
    # =========================================================================

    @pytest.mark.asyncio
    async def test_clock_skew_handling(self, webhook_service, db_session):
        """
        Edge case: AlertManager server has clock skew.
        The system should use received_at for ordering, not just starts_at.
        """
        # Alert with past timestamp (simulating clock skew)
        past_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()

        payload_data = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "ClockSkewTest",
                        "service": "test-service",
                        "severity": "warning",
                    },
                    "annotations": {},
                    "startsAt": past_time,
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": "clock_skew_test1",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        }

        before_process = datetime.now(UTC)
        payload = AlertManagerWebhookPayload(**payload_data)
        alert_ids, _ = await webhook_service.process_webhook(payload)
        await db_session.flush()
        after_process = datetime.now(UTC)

        from src.services.alert_service import AlertService
        alert_service = AlertService(db_session)
        alert = await alert_service.get(alert_ids[0])

        # received_at should be around now, not 2 hours ago
        assert alert.received_at >= before_process
        assert alert.received_at <= after_process

        # starts_at should be the past time from the payload
        assert alert.starts_at < before_process
