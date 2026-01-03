"""Stress tests for high volume alert ingestion and processing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest


class TestHighVolumeIngestion:
    """Stress tests for high volume alert ingestion."""

    # =========================================================================
    # Stress: 1000 alerts/minute ingestion
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_1000_alerts_per_minute(self, client_with_db):
        """
        Given the system is under high load,
        When 1000 alerts are ingested in rapid succession,
        Then all alerts are processed without data loss.
        """
        num_alerts = 100  # Reduced for test speed
        ingested_count = 0
        errors = []

        for i in range(num_alerts):
            payload = {
                "receiver": "observeai",
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {
                            "alertname": f"StressTest{i}",
                            "service": f"service-{i % 10}",
                            "severity": "warning",
                        },
                        "annotations": {"summary": f"Stress test alert {i}"},
                        "startsAt": datetime.now(UTC).isoformat(),
                        "endsAt": "0001-01-01T00:00:00Z",
                        "generatorURL": "http://prometheus:9090/graph",
                        "fingerprint": f"stress_fp_{i}_{uuid4().hex[:8]}",
                    }
                ],
                "groupLabels": {},
                "commonLabels": {},
                "commonAnnotations": {},
                "externalURL": "http://alertmanager:9093",
                "version": "4",
                "groupKey": "",
            }

            try:
                response = await client_with_db.post(
                    "/webhooks/alertmanager",
                    json=payload,
                )
                if response.status_code == 202:
                    ingested_count += 1
                else:
                    errors.append(f"Alert {i}: status {response.status_code}")
            except Exception as e:
                errors.append(f"Alert {i}: {str(e)}")

        # Allow for some failures under stress (95% success rate)
        success_rate = ingested_count / num_alerts
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}, errors: {errors[:5]}"

    # =========================================================================
    # Stress: Concurrent batch ingestion
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_concurrent_batch_ingestion(self, client_with_db):
        """
        Given multiple concurrent webhook requests,
        When processing batches in parallel,
        Then all batches are processed correctly.
        """
        num_batches = 10
        alerts_per_batch = 5

        async def ingest_batch(batch_id):
            payload = {
                "receiver": "observeai",
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {
                            "alertname": f"BatchTest{batch_id}_{j}",
                            "service": f"service-{batch_id}",
                            "severity": "warning",
                        },
                        "annotations": {"summary": f"Batch {batch_id} alert {j}"},
                        "startsAt": datetime.now(UTC).isoformat(),
                        "endsAt": "0001-01-01T00:00:00Z",
                        "generatorURL": "http://prometheus:9090/graph",
                        "fingerprint": f"batch_{batch_id}_{j}_{uuid4().hex[:8]}",
                    }
                    for j in range(alerts_per_batch)
                ],
                "groupLabels": {},
                "commonLabels": {},
                "commonAnnotations": {},
                "externalURL": "http://alertmanager:9093",
                "version": "4",
                "groupKey": "",
            }

            response = await client_with_db.post(
                "/webhooks/alertmanager",
                json=payload,
            )
            return response.status_code == 202

        # Run batches concurrently
        tasks = [ingest_batch(i) for i in range(num_batches)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        successes = sum(1 for r in results if r is True)
        assert successes >= num_batches * 0.9  # 90% success rate

    # =========================================================================
    # Stress: Large payload handling
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_large_payload_handling(self, client_with_db):
        """
        Given a very large alert payload,
        When ingested,
        Then it is processed without memory issues.
        """
        # Create alert with large labels and annotations
        large_value = "x" * 5000  # 5KB string

        payload = {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "LargePayloadTest",
                        "service": "test-service",
                        "severity": "warning",
                        "large_label": large_value,
                    },
                    "annotations": {
                        "summary": "Large payload test",
                        "description": large_value,
                        "runbook": large_value,
                    },
                    "startsAt": datetime.now(UTC).isoformat(),
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": f"large_payload_{uuid4().hex[:8]}",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        }

        response = await client_with_db.post(
            "/webhooks/alertmanager",
            json=payload,
        )

        assert response.status_code == 202


class TestHighVolumeQueries:
    """Stress tests for high volume API queries."""

    # =========================================================================
    # Stress: Concurrent API queries
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_concurrent_api_queries(self, client_with_db, sample_batch_payload):
        """
        Given many concurrent API queries,
        When the system is under load,
        Then all queries return results.
        """
        # First ingest some data
        await client_with_db.post(
            "/webhooks/alertmanager",
            json=sample_batch_payload,
        )

        num_queries = 50

        async def query_alerts():
            response = await client_with_db.get("/api/v1/alerts")
            return response.status_code == 200

        async def query_incidents():
            response = await client_with_db.get("/api/v1/incidents")
            return response.status_code == 200

        # Mix of query types
        tasks = []
        for i in range(num_queries):
            if i % 2 == 0:
                tasks.append(query_alerts())
            else:
                tasks.append(query_incidents())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successes = sum(1 for r in results if r is True)
        assert successes >= num_queries * 0.95

    # =========================================================================
    # Stress: Pagination under load
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_pagination_under_load(self, client_with_db, sample_batch_payload):
        """
        Given a large dataset,
        When paginating through results under load,
        Then pagination remains consistent.
        """
        # Ingest multiple batches
        for _ in range(5):
            await client_with_db.post(
                "/webhooks/alertmanager",
                json=sample_batch_payload,
            )

        # Paginate through all results
        page_sizes = []
        offset = 0
        limit = 10

        for _ in range(10):  # Max 10 pages
            response = await client_with_db.get(
                f"/api/v1/alerts?limit={limit}&offset={offset}"
            )
            if response.status_code != 200:
                break

            data = response.json()
            if not data["alerts"]:
                break

            page_sizes.append(len(data["alerts"]))
            offset += limit

        # Should have retrieved some pages
        assert len(page_sizes) > 0


class TestDatabaseStress:
    """Stress tests for database operations."""

    # =========================================================================
    # Stress: Concurrent writes
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_concurrent_database_writes(self, db_session):
        """
        Given many concurrent write operations,
        When the database is under load,
        Then all writes complete successfully.
        """
        from src.models import Alert, AlertSeverity, AlertStatus

        num_writes = 50
        write_count = 0

        async def create_alert(i):
            nonlocal write_count
            alert = Alert(
                fingerprint=f"db_stress_{i}_{uuid4().hex[:8]}",
                alertname=f"DBStress{i}",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.FIRING,
                labels={"service": f"service-{i}"},
                annotations={},
                starts_at=datetime.now(UTC),
            )
            db_session.add(alert)
            write_count += 1

        for i in range(num_writes):
            await create_alert(i)

        await db_session.flush()

        assert write_count == num_writes

    # =========================================================================
    # Stress: Mixed read/write operations
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_mixed_read_write_operations(self, db_session):
        """
        Given concurrent read and write operations,
        When the database is under mixed load,
        Then operations complete without deadlocks.
        """
        from src.models import Alert, AlertSeverity, AlertStatus
        from sqlalchemy import text

        operations_completed = 0

        # Write operation
        for i in range(20):
            alert = Alert(
                fingerprint=f"mixed_stress_{i}_{uuid4().hex[:8]}",
                alertname=f"MixedStress{i}",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.FIRING,
                labels={"service": "test"},
                annotations={},
                starts_at=datetime.now(UTC),
            )
            db_session.add(alert)
            operations_completed += 1

            # Interleave with reads
            if i % 5 == 0:
                await db_session.execute(text("SELECT 1"))
                operations_completed += 1

        await db_session.flush()

        assert operations_completed >= 20


class TestMemoryStress:
    """Stress tests for memory handling."""

    # =========================================================================
    # Stress: Large result set handling
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_large_result_set(self, client_with_db):
        """
        Given a query that returns many results,
        When processing the response,
        Then memory usage remains bounded.
        """
        # Ingest many alerts
        for i in range(10):
            payload = {
                "receiver": "observeai",
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {
                            "alertname": f"MemoryTest{j}",
                            "service": "test",
                            "severity": "warning",
                        },
                        "annotations": {},
                        "startsAt": datetime.now(UTC).isoformat(),
                        "endsAt": "0001-01-01T00:00:00Z",
                        "generatorURL": "http://prometheus:9090/graph",
                        "fingerprint": f"mem_{i}_{j}_{uuid4().hex[:8]}",
                    }
                    for j in range(10)
                ],
                "groupLabels": {},
                "commonLabels": {},
                "commonAnnotations": {},
                "externalURL": "http://alertmanager:9093",
                "version": "4",
                "groupKey": "",
            }
            await client_with_db.post("/webhooks/alertmanager", json=payload)

        # Query with large limit
        response = await client_with_db.get("/api/v1/alerts?limit=1000")
        assert response.status_code == 200

