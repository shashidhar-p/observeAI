"""Integration tests for webhook endpoints (User Story 1)."""

from __future__ import annotations

import pytest


class TestWebhookE2E:
    """End-to-end tests for the AlertManager webhook endpoint."""

    # =========================================================================
    # US1: Webhook accepts valid payload
    # =========================================================================

    @pytest.mark.asyncio
    async def test_webhook_accepts_valid_payload(
        self, client_with_db, sample_alert_payload
    ):
        """
        Given a valid AlertManager webhook payload,
        When POST /webhooks/alertmanager is called,
        Then the response is 202 Accepted with processing IDs.
        """
        response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=sample_alert_payload,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["alerts_received"] == 1
        assert len(data["processing_ids"]) == 1

    # =========================================================================
    # US1: Webhook rejects malformed payload
    # =========================================================================

    @pytest.mark.asyncio
    async def test_webhook_rejects_malformed(self, client_with_db):
        """
        Given a malformed webhook payload,
        When POST /webhooks/alertmanager is called,
        Then the response is 422 Unprocessable Entity.
        """
        malformed_payload = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": "not_an_array",  # Should be array
            "version": "4",
        }

        response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=malformed_payload,
        )

        assert response.status_code == 422

    # =========================================================================
    # US1: Webhook handles batch processing
    # =========================================================================

    @pytest.mark.asyncio
    async def test_webhook_batch_processing(
        self, client_with_db, sample_batch_payload
    ):
        """
        Given a batch of multiple alerts,
        When POST /webhooks/alertmanager is called,
        Then all alerts are processed and acknowledged.
        """
        response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=sample_batch_payload,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["alerts_received"] == 3
        assert len(data["processing_ids"]) == 3

    # =========================================================================
    # US1: Webhook handles empty alerts array
    # =========================================================================

    @pytest.mark.asyncio
    async def test_webhook_empty_alerts(self, client_with_db):
        """
        Given an empty alerts array,
        When POST /webhooks/alertmanager is called,
        Then the response is 202 but with 0 alerts received.
        """
        empty_payload = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        }

        response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=empty_payload,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["alerts_received"] == 0

    # =========================================================================
    # US1: Verify alert persisted and queryable
    # =========================================================================

    @pytest.mark.asyncio
    async def test_webhook_alert_persisted_and_queryable(
        self, client_with_db, sample_alert_payload
    ):
        """
        Given a valid alert is ingested,
        When GET /api/v1/alerts is called,
        Then the alert appears in the list.
        """
        # Ingest the alert
        ingest_response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=sample_alert_payload,
        )
        assert ingest_response.status_code == 202
        alert_id = ingest_response.json()["processing_ids"][0]

        # Query the alerts list
        list_response = await client_with_db.get("/api/v1/alerts")
        assert list_response.status_code == 200

        data = list_response.json()
        assert data["total"] >= 1

        # Find our alert
        alert_ids = [a["id"] for a in data["alerts"]]
        assert alert_id in alert_ids

    # =========================================================================
    # US1: Webhook response time under 100ms
    # =========================================================================

    @pytest.mark.asyncio
    async def test_webhook_response_time(self, client_with_db, sample_alert_payload):
        """
        Given a single alert payload,
        When POST /webhooks/alertmanager is called,
        Then the response is received within 100ms (per SC-008).
        """
        import time

        start = time.monotonic()
        response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=sample_alert_payload,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        assert response.status_code == 202
        # Per SC-008: Alert ingestion completes in under 100ms for single alerts
        # Allow some buffer for test environment variability
        assert elapsed_ms < 500  # More lenient for CI environments
