# Data Model: Bazel Build Infrastructure

**Feature**: 002-bazel-build-infra | **Date**: 2026-01-03

## Overview

This document defines the build target schemas and relationships for the Bazel build infrastructure. Unlike typical data models, this describes the structure of Bazel targets, their dependencies, and outputs.

---

## Build Targets

### 1. Python Backend Targets

#### `//src:backend_lib`
**Type**: `py_library`
**Description**: Core Python library containing all backend source code

| Attribute | Value |
|-----------|-------|
| srcs | `glob(["**/*.py"], exclude=["**/test_*.py"])` |
| deps | `@pip//fastapi`, `@pip//uvicorn`, `@pip//sqlalchemy`, etc. |
| visibility | `["//visibility:public"]` |

#### `//src:backend`
**Type**: `py_binary`
**Description**: Runnable backend server

| Attribute | Value |
|-----------|-------|
| main | `main.py` |
| deps | `//src:backend_lib` |
| visibility | `["//visibility:public"]` |

---

### 2. Dashboard Targets

#### `//dashboard:dashboard_lib`
**Type**: `ts_project`
**Description**: TypeScript source compilation

| Attribute | Value |
|-----------|-------|
| srcs | `glob(["src/**/*.ts", "src/**/*.tsx"])` |
| deps | `@npm//react`, `@npm//react-dom`, `@npm//swr`, etc. |
| tsconfig | `tsconfig.json` |

#### `//dashboard:dashboard_bundle`
**Type**: `vite` (custom rule)
**Description**: Production bundle via Vite

| Attribute | Value |
|-----------|-------|
| srcs | `//dashboard:dashboard_lib` |
| config | `vite.config.ts` |
| output | `dist/` |

---

### 3. Container Image Targets

#### `//containers:backend_image`
**Type**: `oci_image`
**Description**: Backend container image

| Attribute | Value |
|-----------|-------|
| base | `@python_base` (python:3.11-slim) |
| entrypoint | `["/usr/bin/python", "-m", "uvicorn", "src.main:app"]` |
| tars | `//src:backend_layer` |
| env | `{"PYTHONUNBUFFERED": "1"}` |

#### `//containers:dashboard_image`
**Type**: `oci_image`
**Description**: Dashboard container image (nginx-based)

| Attribute | Value |
|-----------|-------|
| base | `@nginx_base` (nginx:alpine) |
| tars | `//dashboard:static_layer` |
| cmd | `["nginx", "-g", "daemon off;"]` |

#### `//containers:backend_push`
**Type**: `oci_push`
**Description**: Push backend image to registry

| Attribute | Value |
|-----------|-------|
| image | `//containers:backend_image` |
| repository | `ghcr.io/shashidhar-p/observeai-backend` |
| tag | `{STABLE_GIT_COMMIT}` |

#### `//containers:dashboard_push`
**Type**: `oci_push`
**Description**: Push dashboard image to registry

| Attribute | Value |
|-----------|-------|
| image | `//containers:dashboard_image` |
| repository | `ghcr.io/shashidhar-p/observeai-dashboard` |
| tag | `{STABLE_GIT_COMMIT}` |

---

### 4. Test Targets

#### `//tests/unit:backend_tests`
**Type**: `py_test`
**Description**: Backend unit tests via pytest

| Attribute | Value |
|-----------|-------|
| srcs | `glob(["test_*.py"])` |
| deps | `//src:backend_lib`, `@pip//pytest`, `@pip//pytest-asyncio` |
| size | `small` |

#### `//tests/integration:integration_tests`
**Type**: `py_test`
**Description**: Integration tests requiring database

| Attribute | Value |
|-----------|-------|
| srcs | `glob(["test_*.py"])` |
| deps | `//src:backend_lib`, `@pip//pytest` |
| size | `medium` |
| tags | `["requires-db"]` |

---

## Dependency Graph

```
                    ┌─────────────────┐
                    │  MODULE.bazel   │
                    │  (dependencies) │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │ @pip//... │      │ @npm//... │      │ @*_base   │
   │ (Python)  │      │   (JS)    │      │ (images)  │
   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘
         │                   │                   │
         ▼                   ▼                   │
   ┌───────────┐      ┌───────────┐              │
   │//src:lib  │      │//dashboard│              │
   └─────┬─────┘      │   :lib    │              │
         │            └─────┬─────┘              │
         ▼                   ▼                   │
   ┌───────────┐      ┌───────────┐              │
   │//src:bin  │      │//dashboard│              │
   └─────┬─────┘      │  :bundle  │              │
         │            └─────┬─────┘              │
         │                   │                   │
         └─────────┬─────────┘                   │
                   │                             │
                   ▼                             │
            ┌─────────────┐                      │
            │ //containers│◄─────────────────────┘
            │   :images   │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │ //containers│
            │    :push    │
            └─────────────┘
```

---

## Target Naming Conventions

| Pattern | Meaning | Example |
|---------|---------|---------|
| `//path:name` | Explicit target | `//src:backend` |
| `//path:name_lib` | Library target | `//src:backend_lib` |
| `//path:name_test` | Test target | `//tests/unit:backend_test` |
| `//path:name_image` | Container image | `//containers:backend_image` |
| `//path:name_push` | Registry push | `//containers:backend_push` |

---

## Build Outputs

| Target | Output Location | Description |
|--------|-----------------|-------------|
| `//src:backend` | `bazel-bin/src/backend` | Python executable |
| `//dashboard:dashboard_bundle` | `bazel-bin/dashboard/dist/` | Static web assets |
| `//containers:backend_image` | `bazel-bin/containers/backend_image/` | OCI image tarball |
| `//containers:dashboard_image` | `bazel-bin/containers/dashboard_image/` | OCI image tarball |
| `//tests/unit:*` | `bazel-testlogs/tests/unit/*/` | Test results + logs |

---

## Visibility Rules

| Package | Default Visibility |
|---------|-------------------|
| `//src` | `["//visibility:public"]` |
| `//dashboard` | `["//visibility:public"]` |
| `//containers` | `["//visibility:public"]` |
| `//tests` | `["//visibility:private"]` |
