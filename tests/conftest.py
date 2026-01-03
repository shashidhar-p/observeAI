"""Pytest fixtures for the RCA system tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.database import get_session
from src.main import app
from src.models.base import Base

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


# =============================================================================
# Fixtures Directory
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture by name."""
    fixture_path = FIXTURES_DIR / f"{name}.json"
    with open(fixture_path) as f:
        return json.load(f)


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture(scope="function")
async def test_engine(test_settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine with isolated transactions."""
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional database session for tests.

    Each test runs in an isolated transaction that is rolled back after the test.
    This ensures test isolation without database cleanup.
    """
    async_session_factory = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.connect() as conn:
        # Begin a transaction
        trans = await conn.begin()

        async with async_session_factory(bind=conn) as session:
            # Nested savepoint for test isolation
            nested = await conn.begin_nested()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def restart_savepoint(session, trans):
                if trans.nested and not trans._parent.nested:
                    session.expire_all()
                    session.begin_nested()

            yield session

            # Rollback the transaction
            await trans.rollback()


@pytest.fixture
def override_db_session(db_session):
    """Override the database session dependency for FastAPI."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    yield db_session
    app.dependency_overrides.clear()


# =============================================================================
# HTTP Client Fixtures
# =============================================================================


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def client_with_db(override_db_session):
    """Create an async test client with database session override."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_loki_client():
    """Mock the Loki client for unit tests."""
    with patch("src.services.loki_client.LokiClient") as mock_class:
        mock_instance = AsyncMock()
        mock_instance.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"service": "api-gateway", "level": "error"},
                        "values": [
                            ["1704278400000000000", "Error: Connection timeout"],
                            ["1704278401000000000", "Error: Database unavailable"],
                        ],
                    }
                ],
            },
        }
        mock_instance.ready.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_cortex_client():
    """Mock the Cortex client for unit tests."""
    with patch("src.services.cortex_client.CortexClient") as mock_class:
        mock_instance = AsyncMock()
        mock_instance.query.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "cpu_usage", "service": "api-gateway"},
                        "values": [
                            [1704278400, "85.5"],
                            [1704278460, "92.3"],
                            [1704278520, "78.1"],
                        ],
                    }
                ],
            },
        }
        mock_instance.ready.return_value = True
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_llm_provider():
    """Mock the LLM provider for unit tests."""
    mock_provider = AsyncMock()
    mock_provider.analyze.return_value = {
        "success": True,
        "report": {
            "root_cause": "Database connection pool exhausted due to connection leak",
            "confidence_score": 85,
            "summary": "The incident was caused by a connection leak in the payment service.",
            "timeline": [
                {"time": "2026-01-03T09:55:00Z", "event": "Connection pool started degrading"},
                {"time": "2026-01-03T10:00:00Z", "event": "Connection pool exhausted"},
            ],
            "evidence": {
                "logs": ["Connection timeout", "Pool exhausted"],
                "metrics": {"connection_count": 100, "max_connections": 100},
            },
            "remediation_steps": [
                "Restart the payment service to clear connection pool",
                "Fix the connection leak in the query handler",
                "Add connection pool monitoring alerts",
            ],
        },
        "metadata": {
            "model": "claude-3-sonnet",
            "tokens_used": 4500,
            "duration_seconds": 45,
        },
    }

    with patch("src.services.llm.factory.create_llm_provider", return_value=mock_provider):
        yield mock_provider


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_alert_payload():
    """Load sample single firing alert payload."""
    return load_fixture("alert_single_firing")


@pytest.fixture
def sample_resolved_payload():
    """Load sample resolved alert payload."""
    return load_fixture("alert_single_resolved")


@pytest.fixture
def sample_batch_payload():
    """Load sample batch alert payload."""
    return load_fixture("alert_batch_3")


@pytest.fixture
def sample_duplicate_payload():
    """Load sample duplicate alert payload."""
    return load_fixture("alert_duplicate")


@pytest.fixture
def sample_malformed_payload():
    """Load sample malformed alert payload."""
    return load_fixture("alert_malformed")


@pytest.fixture
def sample_same_service_payload():
    """Load sample payload with alerts from same service."""
    return load_fixture("alerts_same_service_2")


@pytest.fixture
def sample_different_services_payload():
    """Load sample payload with alerts from different services."""
    return load_fixture("alerts_different_services_2")


@pytest.fixture
def sample_semantic_similar_payload():
    """Load sample payload with semantically similar alerts."""
    return load_fixture("alerts_semantic_similar")


@pytest.fixture
def sample_alerts_same_service():
    """
    Create two separate webhook payloads for same service correlation testing.
    Returns a list of two payloads that should correlate into one incident.
    """
    return [
        {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPU",
                        "service": "api-gateway",
                        "namespace": "production",
                        "severity": "warning",
                    },
                    "annotations": {"summary": "High CPU on api-gateway"},
                    "startsAt": datetime.now(UTC).isoformat(),
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": f"same_svc_1_{uuid4().hex[:8]}",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        },
        {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighMemory",
                        "service": "api-gateway",
                        "namespace": "production",
                        "severity": "warning",
                    },
                    "annotations": {"summary": "High Memory on api-gateway"},
                    "startsAt": datetime.now(UTC).isoformat(),
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": f"same_svc_2_{uuid4().hex[:8]}",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        },
    ]


@pytest.fixture
def sample_alerts_different_services():
    """
    Create two separate webhook payloads for different service correlation testing.
    Returns a list of two payloads that should create separate incidents.
    """
    return [
        {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPU",
                        "service": "user-service",
                        "namespace": "production",
                        "severity": "warning",
                    },
                    "annotations": {"summary": "High CPU on user-service"},
                    "startsAt": datetime.now(UTC).isoformat(),
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": f"diff_svc_1_{uuid4().hex[:8]}",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        },
        {
            "receiver": "observeai",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPU",
                        "service": "order-service",
                        "namespace": "production",
                        "severity": "warning",
                    },
                    "annotations": {"summary": "High CPU on order-service"},
                    "startsAt": datetime.now(UTC).isoformat(),
                    "endsAt": "0001-01-01T00:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph",
                    "fingerprint": f"diff_svc_2_{uuid4().hex[:8]}",
                }
            ],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "http://alertmanager:9093",
            "version": "4",
            "groupKey": "",
        },
    ]


# =============================================================================
# Model Instance Fixtures
# =============================================================================


@pytest.fixture
def sample_alert_data():
    """Generate sample alert data for model creation."""
    return {
        "fingerprint": f"test_{uuid4().hex[:16]}",
        "alertname": "HighCPU",
        "severity": "critical",
        "status": "firing",
        "labels": {"service": "test-service", "namespace": "test"},
        "annotations": {"summary": "Test alert"},
        "starts_at": datetime.now(UTC),
        "ends_at": None,
        "generator_url": "http://prometheus:9090/graph",
    }


@pytest.fixture
def sample_incident_data():
    """Generate sample incident data for model creation."""
    return {
        "title": "Test Incident - HighCPU on test-service",
        "status": "open",
        "severity": "critical",
        "affected_services": ["test-service"],
        "affected_labels": {"namespace": "test"},
        "started_at": datetime.now(UTC),
        "correlation_reason": "Same service within 5 minute window",
    }


@pytest.fixture
def sample_report_data():
    """Generate sample RCA report data."""
    return {
        "root_cause": "Database connection pool exhausted",
        "confidence_score": 85,
        "summary": "The incident was caused by a connection leak.",
        "timeline": [
            {"time": "2026-01-03T09:55:00Z", "event": "Pool degrading"},
        ],
        "evidence": {"logs": ["Error: timeout"]},
        "remediation_steps": ["Restart service", "Fix leak"],
        "started_at": datetime.now(UTC),
    }


# =============================================================================
# Time Helpers
# =============================================================================


@pytest.fixture
def now():
    """Get current UTC time."""
    return datetime.now(UTC)


@pytest.fixture
def past_time(now):
    """Get time 10 minutes in the past."""
    return now - timedelta(minutes=10)


@pytest.fixture
def future_time(now):
    """Get time 10 minutes in the future."""
    return now + timedelta(minutes=10)
