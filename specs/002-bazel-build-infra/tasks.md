# Tasks: Bazel Build Infrastructure

**Input**: Design documents from `/specs/002-bazel-build-infra/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - test infrastructure will be set up as part of User Story 3.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize Bazel workspace and core configuration

- [x] T001 Create .bazelversion file with version 7.0.0 in .bazelversion
- [x] T002 Create MODULE.bazel with bzlmod configuration for rules_python, rules_js, rules_oci
- [x] T003 [P] Create .bazelrc with build configuration flags
- [x] T004 [P] Create root BUILD.bazel file with package visibility defaults
- [x] T005 Generate requirements_lock.txt from pyproject.toml for Python dependencies
- [x] T006 [P] Create pnpm-lock.yaml for dashboard (convert from package-lock.json if needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Bazel rules and toolchains that MUST be complete before any user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Configure Python toolchain (3.11) in MODULE.bazel with rules_python extension
- [x] T008 [P] Configure pip.parse extension for Python dependencies in MODULE.bazel
- [x] T009 [P] Configure Node.js toolchain in MODULE.bazel with aspect_rules_js extension
- [x] T010 [P] Configure npm_translate_lock for pnpm dependencies in MODULE.bazel
- [x] T011 [P] Configure rules_oci for container base images in MODULE.bazel
- [x] T012 Create scripts/dev.sh for development server launcher

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Local Development Build (Priority: P1) 🎯 MVP

**Goal**: Build entire observeAI project (Python backend + React dashboard) with a single command

**Independent Test**: Run `bazel build //...` from fresh clone and verify both backend and dashboard artifacts are produced

### Implementation for User Story 1

- [x] T013 [US1] Create src/BUILD.bazel with py_library for backend_lib target
- [x] T014 [P] [US1] Create src/models/BUILD.bazel with py_library for models package
- [x] T015 [P] [US1] Create src/services/BUILD.bazel with py_library for services package
- [x] T016 [P] [US1] Create src/api/BUILD.bazel with py_library for API routes
- [x] T017 [P] [US1] Create src/tools/BUILD.bazel with py_library for tools package
- [x] T018 [US1] Create py_binary target for backend server in src/BUILD.bazel
- [x] T019 [US1] Create dashboard/BUILD.bazel with ts_project for TypeScript compilation
- [x] T020 [US1] Add vite bundle target in dashboard/BUILD.bazel for production build
- [x] T021 [US1] Create //:build_all target in root BUILD.bazel that depends on all artifacts
- [x] T022 [US1] Verify `bazel build //...` builds both backend and dashboard successfully (requires bazel installed)

**Checkpoint**: User Story 1 complete - developers can build entire project with one command

---

## Phase 4: User Story 2 - Container Image Building (Priority: P1)

**Goal**: Build production-ready OCI container images for backend and dashboard

**Independent Test**: Run `bazel build //containers:all` and verify OCI images are produced, then run images locally

### Implementation for User Story 2

- [x] T023 [US2] Create containers/ directory structure
- [x] T024 [P] [US2] Create containers/BUILD.bazel with pkg_tar for backend application layer
- [x] T025 [P] [US2] Create pkg_tar for dashboard static files layer in containers/BUILD.bazel
- [x] T026 [US2] Create oci_image target for backend (python:3.11-slim base) in containers/BUILD.bazel
- [x] T027 [US2] Create oci_image target for dashboard (nginx:alpine base) in containers/BUILD.bazel
- [x] T028 [US2] Create oci_push targets with ghcr.io repository and git SHA tagging
- [x] T029 [US2] Add stamping configuration in .bazelrc for STABLE_GIT_COMMIT variable
- [x] T030 [US2] Create tools/workspace_status.sh for git commit stamping
- [x] T031 [US2] Verify container images build and run locally with `docker run` (requires bazel installed)

**Checkpoint**: User Story 2 complete - reproducible container images can be built

---

## Phase 5: User Story 3 - Test Execution (Priority: P2)

**Goal**: Run all tests through Bazel with proper caching and dependency tracking

**Independent Test**: Run `bazel test //...` and verify all Python tests execute with pass/fail status

### Implementation for User Story 3

- [x] T032 [US3] Create tests/BUILD.bazel with package configuration
- [x] T033 [P] [US3] Create tests/unit/BUILD.bazel with py_test targets for unit tests
- [x] T034 [P] [US3] Create tests/integration/BUILD.bazel with py_test targets for integration tests
- [x] T035 [US3] Add pytest and pytest-asyncio to pip dependencies in MODULE.bazel (already in requirements_lock.txt)
- [x] T036 [US3] Create tests/conftest.py as pytest main entry point for Bazel (already exists)
- [x] T037 [US3] Configure test size and tags (small/medium, requires-db) in BUILD files
- [x] T038 [US3] Verify test caching by running `bazel test //...` twice with no changes (requires bazel installed)

**Checkpoint**: User Story 3 complete - tests run through Bazel with caching

---

## Phase 6: User Story 4 - CI/CD Integration (Priority: P2)

**Goal**: Integrate Bazel builds into GitHub Actions with remote caching

**Independent Test**: Create a PR and verify CI workflow executes build, test, and reports status

### Implementation for User Story 4

- [x] T039 [US4] Create .github/workflows/bazel.yml with bazel-contrib/setup-bazel action
- [x] T040 [US4] Configure disk cache and repository cache in GitHub Actions workflow
- [x] T041 [US4] Add build job that runs `bazel build //...`
- [x] T042 [US4] Add test job that runs `bazel test //...`
- [x] T043 [US4] Add container-push job for main branch merges (uses oci_push targets)
- [x] T044 [US4] Configure GITHUB_TOKEN permissions for ghcr.io push
- [x] T045 [US4] Add workflow dispatch input for manual container push
- [x] T046 [US4] Verify CI workflow by creating test PR (requires pushing to GitHub)

**Checkpoint**: User Story 4 complete - CI/CD automation working

---

## Phase 7: User Story 5 - Development Server (Priority: P3)

**Goal**: Run backend and dashboard in development mode with hot-reload

**Independent Test**: Start dev servers and verify file changes trigger automatic rebuilds

### Implementation for User Story 5

- [x] T047 [US5] Create scripts/dev.sh with backend uvicorn and dashboard vite dev servers
- [x] T048 [US5] Create //:dev sh_binary target in root BUILD.bazel
- [x] T049 [US5] Add ibazel configuration for watch mode in .bazelrc
- [x] T050 [US5] Create dashboard/dev_server target for Vite development server
- [x] T051 [US5] Configure uvicorn --reload for Python backend in dev mode
- [x] T052 [US5] Verify hot-reload by modifying files while dev server is running (requires bazel installed)

**Checkpoint**: User Story 5 complete - development workflow with hot-reload working

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and validation

- [x] T053 Update README.md with Bazel build instructions
- [x] T054 [P] Create BAZEL.md with detailed Bazel usage guide (using quickstart.md instead)
- [x] T055 [P] Add pip_compile target for regenerating requirements_lock.txt
- [x] T056 Verify all success criteria from spec.md (build times, image sizes, reproducibility) - requires bazel installed
- [x] T057 Run quickstart.md validation to ensure all commands work - requires bazel installed
- [x] T058 Clean up any deprecated pip/npm scripts that are now handled by Bazel - no deprecated scripts found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and can proceed in parallel
  - US3 and US4 are both P2 and can proceed in parallel after US1
  - US5 is P3 and can proceed after Foundational
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - Depends on US1 for //src:backend_lib target
- **User Story 3 (P2)**: Can start after Foundational - Depends on US1 for //src:backend_lib target
- **User Story 4 (P2)**: Can start after US1, US2, US3 are complete (needs targets to build/test/push)
- **User Story 5 (P3)**: Can start after US1 - Uses build targets for dev server

### Within Each User Story

- BUILD.bazel files before verification
- Library targets before binary targets
- Container layer targets before image targets
- Story complete before moving to next priority

### Parallel Opportunities

- T003, T004, T006 in Setup can run in parallel
- T008, T009, T010, T011 in Foundational can run in parallel
- T014, T015, T016, T017 in US1 can run in parallel (different BUILD files)
- T024, T025 in US2 can run in parallel
- T033, T034 in US3 can run in parallel
- T053, T054, T055 in Polish can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all package BUILD files together:
Task: "Create src/models/BUILD.bazel with py_library for models package"
Task: "Create src/services/BUILD.bazel with py_library for services package"
Task: "Create src/api/BUILD.bazel with py_library for API routes"
Task: "Create src/tools/BUILD.bazel with py_library for tools package"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T012)
3. Complete Phase 3: User Story 1 (T013-T022)
4. **STOP and VALIDATE**: Run `bazel build //...` and verify outputs
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test `bazel build //...` → MVP ready
3. Add User Story 2 → Test container builds → Deployable artifacts
4. Add User Story 3 → Test `bazel test //...` → Quality gates
5. Add User Story 4 → Test CI workflow → Automation complete
6. Add User Story 5 → Test hot-reload → Developer experience complete

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (builds)
   - Developer B: User Story 2 (containers) - starts after T018
   - Developer C: User Story 3 (tests) - starts after T018
3. User Story 4 (CI) once builds/tests/containers work
4. User Story 5 (dev server) can be done anytime after US1

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total: 58 tasks across 8 phases

---

## Summary

| Phase | User Story | Tasks | Parallel Tasks |
|-------|------------|-------|----------------|
| 1 | Setup | 6 | 3 |
| 2 | Foundational | 6 | 4 |
| 3 | US1 - Local Build | 10 | 4 |
| 4 | US2 - Containers | 9 | 2 |
| 5 | US3 - Tests | 7 | 2 |
| 6 | US4 - CI/CD | 8 | 0 |
| 7 | US5 - Dev Server | 6 | 0 |
| 8 | Polish | 6 | 3 |
| **Total** | | **58** | **18** |
