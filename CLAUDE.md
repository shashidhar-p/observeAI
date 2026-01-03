# observeAI Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-28

## Active Technologies
- Starlark (Bazel BUILD files), Python 3.11+, TypeScript/React 18+ (002-bazel-build-infra)
- N/A (build system, no runtime storage) (002-bazel-build-infra)
- Python 3.11+ + FastAPI, SQLAlchemy 2.0 (asyncio), Pydantic 2.x, httpx, anthropic (003-rca-test-suite)
- PostgreSQL with asyncpg driver (003-rca-test-suite)

- Python 3.11+ (001-multi-agent-rca)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 003-rca-test-suite: Added Python 3.11+ + FastAPI, SQLAlchemy 2.0 (asyncio), Pydantic 2.x, httpx, anthropic
- 002-bazel-build-infra: Added Starlark (Bazel BUILD files), Python 3.11+, TypeScript/React 18+

- 001-multi-agent-rca: Added Python 3.11+

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
