# Implementation Plan: Bazel Build Infrastructure

**Branch**: `002-bazel-build-infra` | **Date**: 2026-01-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-bazel-build-infra/spec.md`

## Summary

Implement a reproducible, hermetic build system using Bazel to build, test, and package the observeAI platform. This covers Python backend builds with rules_python, React/TypeScript dashboard builds with rules_js, OCI container image generation with rules_oci, and GitHub Actions CI/CD integration with remote caching.

## Technical Context

**Language/Version**: Starlark (Bazel BUILD files), Python 3.11+, TypeScript/React 18+
**Primary Dependencies**:
- `bazel` 7.x (via bazelisk)
- `rules_python` - Python toolchain and pip integration
- `rules_js` - JavaScript/TypeScript toolchain with pnpm
- `rules_oci` - OCI container image building
- `aspect_bazel_lib` - Common utilities for container layers

**Storage**: N/A (build system, no runtime storage)
**Testing**: Bazel test with pytest (Python), vitest (dashboard)
**Target Platform**: Linux (CI/production), macOS (development)
**Project Type**: Build infrastructure (monorepo tooling)
**Performance Goals**:
- Cold build <5 minutes
- Incremental build <30 seconds
- CI with cache <3 minutes
**Constraints**:
- Must integrate with existing src/ and dashboard/ structure
- Secrets via environment variables only
- Container images <500MB each
**Scale/Scope**: Single monorepo with 2 build targets (backend, dashboard) + container images

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Constitution file contains template placeholders only. No project-specific principles defined yet.

| Principle | Status | Notes |
|-----------|--------|-------|
| Constitution not configured | N/A | Template placeholders present - no violations possible |

**Recommendation**: Run `/speckit.constitution` to define project principles before production phase.

## Project Structure

### Documentation (this feature)

```text
specs/002-bazel-build-infra/
├── plan.md              # This file
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - build target schemas
├── quickstart.md        # Phase 1 output - getting started guide
├── contracts/           # Phase 1 output - N/A for build system
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Bazel workspace configuration
MODULE.bazel             # Bzlmod module definition
.bazelrc                 # Bazel configuration flags
.bazelversion            # Bazel version pin (for bazelisk)
BUILD.bazel              # Root BUILD file

# Python backend
src/
├── BUILD.bazel          # Python library and binary targets
├── main.py
├── models/
│   └── BUILD.bazel
├── services/
│   └── BUILD.bazel
├── api/
│   └── BUILD.bazel
└── tools/
    └── BUILD.bazel

# React dashboard
dashboard/
├── BUILD.bazel          # JS/TS library and bundle targets
├── src/
└── package.json

# Container images
containers/
├── BUILD.bazel          # OCI image targets
├── backend.bzl          # Backend image definition
└── dashboard.bzl        # Dashboard image definition

# Tests (Bazel-managed)
tests/
├── BUILD.bazel          # Test targets
├── unit/
│   └── BUILD.bazel
└── integration/
    └── BUILD.bazel

# CI/CD
.github/
└── workflows/
    └── bazel.yml        # GitHub Actions workflow
```

**Structure Decision**: Bazel BUILD files added alongside existing source structure. Container definitions in dedicated `containers/` directory. No refactoring of existing src/ or dashboard/ layouts required.

## Complexity Tracking

> No constitution violations to justify - constitution not yet configured.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
