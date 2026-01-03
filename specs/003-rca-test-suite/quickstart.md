# Quickstart: RCA Test Suite

**Feature**: 003-rca-test-suite
**Date**: 2026-01-03

## Overview

This guide explains how to run and extend the RCA test suite.

---

## Prerequisites

1. Python 3.11+
2. PostgreSQL (for integration tests)
3. Docker Compose (for containerized services)
4. Anthropic API key (for live AI integration tests)

---

## Setup

### 1. Install Dependencies

```bash
# Install main dependencies
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

### 2. Environment Configuration

Create a `.env` file for integration tests:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://rca:rca123@localhost:5432/rca_db

# External services
LOKI_URL=http://localhost:3100
CORTEX_URL=http://localhost:9009

# AI API (required for integration tests)
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Start Infrastructure (Integration Tests)

```bash
# Start database and observability stack
bazel run //:deploy --no-build

# Or using docker-compose directly
docker-compose -f docker/docker-compose.yaml up -d postgres
docker-compose -f docker-compose.observability.yml up -d
```

---

## Running Tests

### All Tests

```bash
# Run all tests via Bazel
bazel test //...

# Run all tests via pytest
pytest
```

### Unit Tests Only (Fast)

```bash
pytest tests/unit/ -v
```

### Integration Tests Only

```bash
# Requires infrastructure running
pytest tests/integration/ -v
```

### Stress Tests Only

```bash
# Optional - longer running
pytest tests/stress/ -v --timeout=300
```

### Specific Test File

```bash
pytest tests/unit/test_webhook.py -v
```

### Specific Test Function

```bash
pytest tests/unit/test_webhook.py::test_single_alert_stored -v
```

---

## Coverage Reports

### Generate Coverage

```bash
pytest --cov=src --cov-report=html
```

### View Report

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Targets

| Type | Target | Current |
|------|--------|---------|
| Unit | 80% | TBD |
| Integration | 70% | TBD |

---

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests that mock external dependencies:

| File | Tests |
|------|-------|
| `test_alert_service.py` | Alert CRUD, deduplication |
| `test_incident_service.py` | Incident lifecycle |
| `test_correlation_service.py` | Alert grouping logic |
| `test_semantic_correlator.py` | 70% similarity threshold |
| `test_rca_agent.py` | Agent tool calls |
| `test_loki_tool.py` | LogQL queries |
| `test_cortex_tool.py` | PromQL queries |
| `test_report_service.py` | Report generation |
| `test_webhook.py` | Webhook processing |
| `test_schemas.py` | Pydantic validation |

### Integration Tests (`tests/integration/`)

End-to-end tests with real services:

| File | Tests |
|------|-------|
| `test_webhook_e2e.py` | Full webhook flow |
| `test_correlation_e2e.py` | Multi-alert correlation |
| `test_rca_e2e.py` | Live AI RCA execution |
| `test_api_alerts.py` | Alert API endpoints |
| `test_api_incidents.py` | Incident API endpoints |
| `test_api_reports.py` | Report API endpoints |

### Stress Tests (`tests/stress/`)

Concurrency and load tests:

| File | Tests |
|------|-------|
| `test_concurrent_alerts.py` | Parallel alert ingestion |
| `test_concurrent_rca.py` | 3 concurrent RCA limit |

---

## Writing New Tests

### Unit Test Template

```python
"""Unit tests for {module}."""

import pytest
from unittest.mock import AsyncMock, patch

from src.services.{module} import {Service}


class Test{Service}:
    """Tests for {Service}."""

    @pytest.fixture
    def service(self, mock_session):
        """Create service with mocked dependencies."""
        return {Service}(mock_session)

    @pytest.mark.asyncio
    async def test_create_success(self, service):
        """Test successful creation."""
        result = await service.create(...)
        assert result is not None
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_validation_error(self, service):
        """Test validation error handling."""
        with pytest.raises(ValueError):
            await service.create(invalid_data)
```

### Integration Test Template

```python
"""Integration tests for {endpoint}."""

import pytest
from httpx import AsyncClient

from src.main import app


class TestAPI{Resource}:
    """Integration tests for {Resource} API."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        """Test listing when no items exist."""
        response = await client.get("/api/v1/{resources}")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_create_and_get(self, client, sample_data):
        """Test create and retrieve flow."""
        # Create
        create_response = await client.post("/api/v1/{resources}", json=sample_data)
        assert create_response.status_code == 201

        # Get
        resource_id = create_response.json()["id"]
        get_response = await client.get(f"/api/v1/{resources}/{resource_id}")
        assert get_response.status_code == 200
```

---

## Fixtures Reference

### Common Fixtures (`conftest.py`)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `db_session` | function | Transactional database session |
| `client` | function | httpx AsyncClient for API tests |
| `mock_loki` | function | Mocked Loki client |
| `mock_cortex` | function | Mocked Cortex client |
| `mock_llm` | function | Mocked AI provider |
| `sample_alert` | function | Sample Alert object |
| `sample_incident` | function | Sample Incident with alerts |
| `alertmanager_payload` | function | AlertManager webhook payload |

### Loading JSON Fixtures

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> dict:
    """Load JSON fixture by name."""
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)

# Usage
payload = load_fixture("alert_single_firing")
```

---

## Debugging Tests

### Verbose Output

```bash
pytest -v --tb=long
```

### Stop on First Failure

```bash
pytest -x
```

### Enter Debugger on Failure

```bash
pytest --pdb
```

### Show Print Statements

```bash
pytest -s
```

### Run Last Failed

```bash
pytest --lf
```

---

## CI/CD Integration

Tests run automatically in GitHub Actions:

```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    pytest --cov=src --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
```

### Required Checks

- All tests must pass
- Coverage must meet thresholds (80% unit, 70% integration)
- No flaky tests (verified by reruns)
