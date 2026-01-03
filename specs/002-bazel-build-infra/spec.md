# Feature Specification: Bazel Build Infrastructure

**Feature Branch**: `002-bazel-build-infra`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "Bazel build infrastructure for observeAI - containerized builds for Python backend and React dashboard with local development and CI/CD support"

## Overview

A reproducible, hermetic build system using Bazel to build, test, and package the observeAI platform. This enables consistent builds across developer machines and CI/CD pipelines, with containerized outputs for deployment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Development Build (Priority: P1)

As a developer, I want to build the entire observeAI project (Python backend + React dashboard) with a single command so that I can quickly verify my changes work together before committing.

**Why this priority**: Fast local builds are the foundation of developer productivity. Without this, every other build capability is blocked.

**Independent Test**: Can be fully tested by running a single build command from a fresh clone and verifying both backend and dashboard artifacts are produced.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the repository with Bazel installed, **When** I run the build command, **Then** both Python backend and React dashboard are built successfully with all dependencies resolved.

2. **Given** I modify a source file in the backend, **When** I rebuild, **Then** only affected targets are rebuilt (incremental build) and the build completes faster than a full build.

3. **Given** I modify a source file in the dashboard, **When** I rebuild, **Then** only the dashboard and its dependents are rebuilt.

---

### User Story 2 - Container Image Building (Priority: P1)

As a DevOps engineer, I want to build production-ready container images for the backend and dashboard using Bazel so that I have reproducible, hermetic images without relying on Docker build cache.

**Why this priority**: Container images are required for deployment. This is essential for shipping the product.

**Independent Test**: Can be tested by building container images and running them locally to verify the application starts correctly.

**Acceptance Scenarios**:

1. **Given** the project is built successfully, **When** I run the container build target, **Then** OCI-compliant container images are produced for both backend and dashboard.

2. **Given** I build the same commit twice on different machines, **When** I compare the image digests, **Then** they are identical (reproducible builds).

3. **Given** a container image is built, **When** I run it with required environment variables, **Then** the application starts and responds to health checks.

---

### User Story 3 - Test Execution (Priority: P2)

As a developer, I want to run all tests (unit, integration) through Bazel so that I have consistent test execution with proper dependency tracking and caching.

**Why this priority**: Tests validate correctness. While builds can work without tests, reliable testing is essential for quality.

**Independent Test**: Can be tested by running the test command and verifying all test suites execute and report results.

**Acceptance Scenarios**:

1. **Given** the project has unit tests, **When** I run the test command, **Then** all Python unit tests execute and report pass/fail status.

2. **Given** tests passed in a previous run with no code changes, **When** I run tests again, **Then** cached results are used and tests complete instantly.

3. **Given** I modify a source file, **When** I run tests, **Then** only tests affected by the change are re-executed.

---

### User Story 4 - CI/CD Integration (Priority: P2)

As a DevOps engineer, I want to integrate Bazel builds into GitHub Actions so that every pull request is automatically built, tested, and produces deployable artifacts.

**Why this priority**: CI/CD automation ensures code quality and enables continuous delivery. Depends on local build working first.

**Independent Test**: Can be tested by creating a PR and verifying the CI workflow executes build, test, and container image steps.

**Acceptance Scenarios**:

1. **Given** a pull request is opened, **When** the CI workflow runs, **Then** Bazel builds the project, runs tests, and reports status to the PR.

2. **Given** a PR is merged to main, **When** the CI workflow completes, **Then** container images are built and pushed to the container registry.

3. **Given** the CI uses remote caching, **When** a build runs with unchanged dependencies, **Then** cached artifacts are retrieved and build time is reduced.

---

### User Story 5 - Development Server (Priority: P3)

As a developer, I want to run the backend and dashboard in development mode with hot-reload so that I can see changes immediately without manual rebuilds.

**Why this priority**: Improves developer experience but is not blocking for initial Bazel adoption.

**Independent Test**: Can be tested by starting dev servers and verifying file changes trigger automatic rebuilds.

**Acceptance Scenarios**:

1. **Given** I start the development server, **When** I modify a Python file, **Then** the backend reloads automatically within seconds.

2. **Given** I start the dashboard dev server, **When** I modify a React component, **Then** the browser hot-reloads the change.

---

### Edge Cases

- What happens when a Python dependency is not available in PyPI? System falls back to vendored dependencies or fails with clear error message.
- What happens when npm registry is unavailable? System uses cached node_modules or fails with actionable error.
- How does system handle platform-specific dependencies (Linux vs macOS)? Bazel platform constraints ensure correct dependencies per OS.
- What happens when Bazel cache is corrupted? Clear cache command is documented; builds can recover.

## Requirements *(mandatory)*

### Functional Requirements

**Build System Core**
- **FR-001**: System MUST support building Python 3.11+ backend with all pip dependencies
- **FR-002**: System MUST support building React/TypeScript dashboard with npm dependencies
- **FR-003**: System MUST support incremental builds (only rebuild changed targets)
- **FR-004**: System MUST produce deterministic build outputs (same inputs → same outputs)
- **FR-005**: System MUST support parallel builds utilizing available CPU cores

**Container Images**
- **FR-006**: System MUST build OCI-compliant container images for backend
- **FR-007**: System MUST build OCI-compliant container images for dashboard
- **FR-008**: System MUST support multi-stage builds (build vs runtime layers)
- **FR-009**: System MUST produce minimal container images (no build tools in runtime)
- **FR-010**: System MUST tag images with git commit SHA for traceability

**Testing**
- **FR-011**: System MUST execute pytest tests for Python backend
- **FR-012**: System MUST cache test results for unchanged code
- **FR-013**: System MUST support running specific test targets

**Developer Experience**
- **FR-014**: System MUST provide single-command full project build
- **FR-015**: System MUST provide clear error messages for build failures
- **FR-016**: System MUST support local development mode with fast rebuilds

**CI/CD**
- **FR-017**: System MUST support remote build caching for CI pipelines
- **FR-018**: System MUST integrate with GitHub Actions
- **FR-019**: System MUST produce build status badges/reports

**Security**
- **FR-020**: System MUST handle all secrets (registry credentials, cache auth, API keys) via environment variables only
- **FR-021**: System MUST NOT store secrets in Bazel configuration files, BUILD files, or build outputs
- **FR-022**: System MUST ensure secrets are not exposed in build logs or cached artifacts

### Key Entities

- **Build Target**: A buildable unit (Python library, binary, container image) with defined inputs and outputs
- **Workspace**: The root project configuration defining external dependencies and toolchains
- **Container Image**: A packaged application with runtime dependencies, ready for deployment
- **Build Cache**: Stored build artifacts keyed by input hashes for incremental builds

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Full project build completes in under 5 minutes on a developer machine (cold cache)
- **SC-002**: Incremental builds complete in under 30 seconds for single-file changes
- **SC-003**: Container images for backend and dashboard are under 500MB each
- **SC-004**: CI builds with warm cache complete in under 3 minutes
- **SC-005**: 100% of existing tests pass under Bazel test execution
- **SC-006**: Builds are reproducible: same commit produces identical artifacts on different machines
- **SC-007**: Developer can build and run locally with 3 or fewer commands after initial setup

## Assumptions

1. **Bazel Version**: Using Bazel 7.x with bzlmod for dependency management
2. **Python Toolchain**: rules_python for Python builds with pip integration
3. **Container Toolchain**: rules_oci for container image builds (replacing rules_docker)
4. **Node.js Toolchain**: rules_js for React/TypeScript builds
5. **Remote Cache**: GitHub Actions cache or dedicated remote cache service for CI
6. **Registry**: Container images pushed to GitHub Container Registry (ghcr.io)
7. **Platform Support**: Linux (primary), macOS (development) - Windows not required

## Constraints

1. **Existing Project**: Must integrate with existing Python/npm project structure without major refactoring
2. **Learning Curve**: Team may need time to learn Bazel concepts (BUILD files, targets, dependencies)
3. **Toolchain Maintenance**: Bazel rules require periodic updates for security and compatibility
4. **Build Time**: Initial cold builds may be slower than existing tools until cache is warm

## Dependencies

1. **Bazel**: Core build system (installable via bazelisk)
2. **rules_python**: Python build rules
3. **rules_js**: JavaScript/TypeScript build rules
4. **rules_oci**: Container image build rules
5. **Remote Cache Service**: For CI/CD build caching (optional but recommended)

## Clarifications

### Session 2026-01-03

- Q: How should sensitive data (registry credentials, remote cache auth, API keys) be handled in builds? → A: Environment variables only (e.g., `GITHUB_TOKEN`, injected at runtime) - never stored in Bazel files
