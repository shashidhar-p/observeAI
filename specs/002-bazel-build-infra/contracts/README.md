# Contracts: Bazel Build Infrastructure

**Feature**: 002-bazel-build-infra | **Date**: 2026-01-03

## Note

This feature is a build infrastructure implementation, not a service with APIs. Therefore, traditional API contracts (OpenAPI, GraphQL schemas) are not applicable.

Instead, the "contracts" for this feature are:

1. **Build Target Names** - Defined in `data-model.md`
2. **Environment Variables** - For secret injection
3. **CI/CD Workflow Interface** - GitHub Actions integration

---

## Environment Variable Contract

The following environment variables are expected for CI/CD operations:

| Variable | Required | Description | Used By |
|----------|----------|-------------|---------|
| `GITHUB_TOKEN` | Yes (CI) | GitHub API access for cache and registry | `oci_push`, remote cache |
| `CONTAINER_REGISTRY` | No | Override default registry (ghcr.io) | `oci_push` |

---

## CLI Contract

### Build Commands

| Command | Description | Exit Code |
|---------|-------------|-----------|
| `bazel build //...` | Build all targets | 0 = success |
| `bazel test //...` | Run all tests | 0 = all pass, 1 = failures |
| `bazel run //containers:backend_push` | Push backend image | 0 = success |
| `bazel run //containers:dashboard_push` | Push dashboard image | 0 = success |
| `bazel run //:dev` | Start development servers | N/A (long-running) |

### Query Commands

| Command | Output |
|---------|--------|
| `bazel query //...` | List all targets |
| `bazel query 'deps(//src:backend)'` | Show backend dependencies |
| `bazel query 'rdeps(//..., //src:config)'` | Show what depends on config |

---

## GitHub Actions Workflow Contract

### Inputs (Workflow Dispatch)

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `push_images` | boolean | false | Whether to push container images |

### Outputs

| Output | Description |
|--------|-------------|
| `backend_image_digest` | SHA256 digest of backend image |
| `dashboard_image_digest` | SHA256 digest of dashboard image |
| `build_cache_hit` | Whether cache was used (true/false) |

### Status Checks

| Check Name | Triggers |
|------------|----------|
| `bazel-build` | All PRs, push to main |
| `bazel-test` | All PRs, push to main |
| `bazel-push` | Push to main only |
