# Research: Bazel Build Infrastructure

**Feature**: 002-bazel-build-infra | **Date**: 2026-01-03

## Overview

This document captures research findings and technology decisions for implementing Bazel build infrastructure for the observeAI project.

---

## 1. Bazel Module System (bzlmod vs WORKSPACE)

### Decision: Use bzlmod (MODULE.bazel)

### Rationale
- bzlmod is the modern dependency management system, replacing legacy WORKSPACE
- Better dependency resolution with proper version conflict detection
- Hermetic by default - external dependencies are locked
- Bazel 7.x has bzlmod enabled by default
- Cleaner syntax and better tooling support

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| WORKSPACE file | Legacy system, deprecated in Bazel 7+, harder to maintain |
| Hybrid approach | Adds complexity, bzlmod is mature enough for full adoption |

---

## 2. Python Build Rules

### Decision: Use rules_python with pip.parse

### Rationale
- Official Bazel rules for Python, actively maintained
- `pip.parse` in MODULE.bazel creates hermetic pip dependencies
- Supports Python 3.11+ with proper toolchain selection
- Generates `requirements_lock.txt` for reproducibility
- Works well with existing `pyproject.toml` structure

### Configuration Approach
```starlark
# MODULE.bazel
bazel_dep(name = "rules_python", version = "0.31.0")

python = use_extension("@rules_python//python/extensions:python.bzl", "python")
python.toolchain(python_version = "3.11")

pip = use_extension("@rules_python//python/extensions:pip.bzl", "pip")
pip.parse(
    hub_name = "pip",
    python_version = "3.11",
    requirements_lock = "//:requirements_lock.txt",
)
use_repo(pip, "pip")
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| rules_python with requirements.txt directly | Less hermetic, no lockfile support |
| Poetry2nix + Bazel | Adds Nix complexity, overkill for this project |
| Custom pip wrapper | Reinventing the wheel, maintenance burden |

---

## 3. JavaScript/TypeScript Build Rules

### Decision: Use rules_js with pnpm

### Rationale
- Official Aspect Build rules for JS/TS, production-ready
- pnpm integration provides fast, hermetic node_modules
- Works with existing Vite configuration
- Supports TypeScript compilation and bundling
- Better caching than npm/yarn

### Configuration Approach
```starlark
# MODULE.bazel
bazel_dep(name = "aspect_rules_js", version = "1.42.0")
bazel_dep(name = "aspect_rules_ts", version = "2.4.0")

npm = use_extension("@aspect_rules_js//npm:extensions.bzl", "npm")
npm.npm_translate_lock(
    name = "npm",
    pnpm_lock = "//dashboard:pnpm-lock.yaml",
)
use_repo(npm, "npm")
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| rules_nodejs (legacy) | Deprecated, migrated to rules_js |
| esbuild only | Doesn't integrate well with Vite HMR |
| Turborepo + Bazel | Redundant, Bazel handles caching |

---

## 4. Container Image Building

### Decision: Use rules_oci (not rules_docker)

### Rationale
- rules_docker is deprecated, rules_oci is the successor
- Produces OCI-compliant images directly (no Docker daemon needed)
- Better reproducibility - no layer caching issues
- Supports multi-platform builds (linux/amd64, linux/arm64)
- Integrates with container registries via crane

### Configuration Approach
```starlark
# MODULE.bazel
bazel_dep(name = "rules_oci", version = "1.7.0")
bazel_dep(name = "rules_pkg", version = "0.10.0")

oci = use_extension("@rules_oci//oci:extensions.bzl", "oci")
oci.pull(
    name = "python_base",
    image = "python",
    tag = "3.11-slim",
    platforms = ["linux/amd64"],
)
use_repo(oci, "python_base")
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| rules_docker | Deprecated, requires Docker daemon |
| ko (Go images) | Only for Go, not applicable |
| Dockerfile + Bazel genrule | Not hermetic, loses Bazel benefits |

---

## 5. Remote Caching Strategy

### Decision: GitHub Actions Cache with bazel-contrib/setup-bazel

### Rationale
- Free for GitHub-hosted repos
- No additional infrastructure to maintain
- bazel-contrib/setup-bazel action handles cache management
- Sufficient for current project scale
- Can upgrade to BuildBuddy/EngFlow later if needed

### Configuration Approach
```yaml
# .github/workflows/bazel.yml
- uses: bazel-contrib/setup-bazel@0.8.0
  with:
    bazelisk-cache: true
    disk-cache: ${{ github.workflow }}
    repository-cache: true
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| BuildBuddy | Overkill for current scale, adds cost |
| Self-hosted cache (nginx) | Maintenance overhead |
| No remote cache | CI too slow, defeats purpose |

---

## 6. Development Server Integration

### Decision: Bazel + ibazel for watch mode

### Rationale
- ibazel (iterative bazel) watches files and rebuilds on change
- Integrates with existing Vite dev server for dashboard
- uvicorn --reload for Python backend
- Single command to start both: `bazel run //:dev`

### Configuration Approach
```starlark
# BUILD.bazel
sh_binary(
    name = "dev",
    srcs = ["scripts/dev.sh"],
    data = [
        "//src:backend",
        "//dashboard:dev_server",
    ],
)
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Pure ibazel | Doesn't support Vite HMR natively |
| Bazel query + entr | More complex setup |
| Separate dev workflow | Loses Bazel benefits, inconsistent |

---

## 7. Test Execution

### Decision: Bazel test with pytest runner

### Rationale
- `py_test` rule wraps pytest execution
- Automatic test caching based on file changes
- Parallel test execution with `--test_sharding_strategy`
- Consistent with build system

### Configuration Approach
```starlark
# tests/BUILD.bazel
py_test(
    name = "unit_tests",
    srcs = glob(["unit/**/*.py"]),
    deps = [
        "//src:backend_lib",
        "@pip//pytest",
    ],
    main = "conftest.py",
)
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| pytest directly | Loses caching, inconsistent with build |
| Bazel test + coverage genrule | Covered by pytest-cov integration |

---

## 8. Dependency Locking

### Decision: Lockfiles for both Python and JavaScript

### Rationale
- `requirements_lock.txt` for Python (generated from pyproject.toml)
- `pnpm-lock.yaml` for JavaScript (already exists)
- Ensures reproducible builds across machines
- Lockfiles committed to repo

### Tooling
- Python: `bazel run //:pip_compile` (custom target)
- JavaScript: `pnpm install --frozen-lockfile` in CI

---

## Summary of Technology Stack

| Component | Choice | Version |
|-----------|--------|---------|
| Build System | Bazel | 7.x |
| Module System | bzlmod | (built-in) |
| Python Rules | rules_python | 0.31.0 |
| JS/TS Rules | aspect_rules_js | 1.42.0 |
| Container Rules | rules_oci | 1.7.0 |
| Remote Cache | GitHub Actions | N/A |
| Watch Mode | ibazel | latest |
| Version Manager | bazelisk | latest |
