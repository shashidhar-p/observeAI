# Research: RCA Test Suite

**Feature**: 003-rca-test-suite
**Date**: 2026-01-03

## Overview

This document captures research findings for implementing the comprehensive RCA test suite.

---

## 1. Testing Framework Selection

### Decision
Use **pytest** with **pytest-asyncio** for async test support.

### Rationale
- Already configured in pyproject.toml (pytest 8.3+, pytest-asyncio 0.24+)
- Native async/await support for testing SQLAlchemy 2.0 async sessions
- pytest-cov integrated for coverage reporting
- Excellent fixture system for test data management

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| unittest | No native async support, less flexible fixtures |
| nose2 | Less community adoption, pytest is standard |

---

## 2. Mocking Strategy

### Decision
- **Unit tests**: Mock external services (Loki, Cortex, database) using `unittest.mock` and `pytest-mock`
- **Integration tests**: Use live AI APIs, containerized Loki/Cortex/PostgreSQL

### Rationale
- Unit tests must be fast (<5 minutes total) and deterministic
- Integration tests with live AI validate real RCA behavior (per clarification decision)
- Containerized services via docker-compose provide realistic integration environment

### Implementation Pattern
```python
# Unit test - mock external services
@pytest.fixture
def mock_loki_client(mocker):
    mock = mocker.patch("src.services.loki_client.LokiClient")
    mock.return_value.query.return_value = {"data": {"result": []}}
    return mock

# Integration test - use TestClient with real database
@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()
```

---

## 3. Test Data Fixtures

### Decision
Create reusable fixtures in `tests/fixtures/` directory with AlertManager-format JSON payloads.

### Rationale
- AlertManager webhook format is well-defined (Prometheus standard)
- Fixtures enable consistent test scenarios across unit and integration tests
- JSON files allow easy modification without code changes

### Fixture Categories
| Category | Purpose |
|----------|---------|
| `alert_single_firing.json` | Basic single alert ingestion |
| `alert_batch_multiple.json` | Batch alert handling |
| `alert_duplicate_fingerprint.json` | Deduplication testing |
| `alert_malformed.json` | Error handling |
| `alerts_same_service.json` | Correlation testing |
| `alerts_different_services.json` | Separate incident creation |
| `alerts_semantic_similar.json` | 70% similarity threshold |

---

## 4. Database Testing Strategy

### Decision
Use SQLAlchemy async sessions with transaction rollback for test isolation.

### Rationale
- Each test runs in an isolated transaction that rolls back
- No test pollution between test cases
- Fast execution (no cleanup queries needed)

### Implementation Pattern
```python
@pytest.fixture
async def db_session():
    """Provide a transactional database session."""
    async with engine.begin() as conn:
        async with AsyncSession(conn) as session:
            yield session
            await conn.rollback()
```

---

## 5. Async Testing Patterns

### Decision
Use `pytest.mark.asyncio` with `asyncio_mode = "auto"` in pyproject.toml.

### Rationale
- Already configured in existing pyproject.toml
- Simplifies async test function definitions
- Consistent async fixture handling

### Key Patterns
- Use `async def test_*` for all async tests
- Use `@pytest.fixture` with `async def` for async fixtures
- Use `AsyncMock` for mocking async methods

---

## 6. API Testing Approach

### Decision
Use `httpx.AsyncClient` with FastAPI's `ASGITransport` for API testing.

### Rationale
- httpx already in dependencies
- Native async support matches FastAPI's async handlers
- Avoids needing separate test server process

### Implementation Pattern
```python
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

---

## 7. Concurrent Testing Approach

### Decision
Use `asyncio.gather()` for concurrent RCA execution tests with semaphore limiting.

### Rationale
- Tests spec requirement: max 3 concurrent RCA executions
- Validates no race conditions or data corruption
- Uses asyncio primitives (native Python, no external dependencies)

### Implementation Pattern
```python
async def test_concurrent_rca_limit():
    semaphore = asyncio.Semaphore(3)
    tasks = [run_rca_with_limit(semaphore, incident_id) for incident_id in incident_ids]
    results = await asyncio.gather(*tasks)
    assert all(r.success for r in results)
```

---

## 8. Coverage Requirements

### Decision
Target 80% unit test coverage, 70% integration test coverage per spec.

### Rationale
- 80% unit coverage ensures core logic is well-tested
- 70% integration coverage ensures API endpoints work end-to-end
- pytest-cov already configured for coverage reporting

### Configuration (existing in pyproject.toml)
```toml
[tool.coverage.run]
source = ["src"]
branch = true
```

---

## 9. Test Organization

### Decision
Organize tests by type: `unit/`, `integration/`, `stress/`

### Rationale
- Clear separation of fast unit tests from slower integration tests
- Allows selective test execution (e.g., `pytest tests/unit/`)
- Stress tests isolated for optional CI execution

### Directory Structure
```
tests/
├── conftest.py          # Shared fixtures
├── fixtures/            # JSON test data
├── unit/                # Fast, isolated tests
├── integration/         # End-to-end with services
└── stress/              # Performance/concurrency tests
```

---

## 10. Edge Case Testing

### Decision
Create dedicated test methods for each of the 10 specified edge cases.

### Edge Cases Mapped to Tests
| Edge Case | Test Location |
|-----------|---------------|
| Missing required fields | `test_webhook.py::test_missing_required_fields` |
| Long labels/annotations | `test_alert_service.py::test_long_labels_truncation` |
| Incident merging | `test_correlation_service.py::test_incident_merge` |
| Non-English semantic | `test_semantic_correlator.py::test_non_english` |
| Unexpected Loki format | `test_loki_tool.py::test_unexpected_format` |
| Clock skew | `test_webhook.py::test_clock_skew_handling` |
| Duplicate RCA trigger | `test_rca_agent.py::test_already_analyzing` |
| Future timestamps | `test_alert_service.py::test_future_timestamp` |
| Malformed AI response | `test_rca_agent.py::test_malformed_tool_response` |
| Crash recovery | `test_rca_agent.py::test_crash_recovery` |

---

## Summary

All NEEDS CLARIFICATION items from Technical Context have been resolved:
- Testing framework: pytest with pytest-asyncio
- Mocking strategy: Mock externals in unit tests, live AI in integration
- Database strategy: Transaction rollback isolation
- API testing: httpx AsyncClient with ASGITransport
- Concurrent testing: asyncio.gather with semaphore
- Coverage targets: 80% unit, 70% integration
