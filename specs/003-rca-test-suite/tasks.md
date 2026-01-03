# Tasks: Comprehensive RCA Test Suite

**Input**: Design documents from `/specs/003-rca-test-suite/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test infrastructure and shared fixtures

- [x] T001 Create tests/fixtures/ directory structure for JSON test data
- [x] T002 [P] Create tests/fixtures/alert_single_firing.json with single firing alert payload
- [x] T003 [P] Create tests/fixtures/alert_single_resolved.json with resolved alert payload
- [x] T004 [P] Create tests/fixtures/alert_batch_3.json with batch of 3 alerts
- [x] T005 [P] Create tests/fixtures/alert_duplicate.json with duplicate fingerprint scenario
- [x] T006 [P] Create tests/fixtures/alert_malformed.json with invalid JSON structure
- [x] T007 [P] Create tests/fixtures/alerts_same_service_2.json for correlation testing
- [x] T008 [P] Create tests/fixtures/alerts_different_services_2.json for separate incidents
- [x] T009 [P] Create tests/fixtures/alerts_semantic_similar.json with 70% similar messages
- [x] T010 Update tests/conftest.py with shared fixtures for database sessions, mocks, and test client

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core test infrastructure that MUST be complete before ANY user story tests

**⚠️ CRITICAL**: No user story tests can begin until this phase is complete

- [x] T011 Create tests/fixtures/loader.py helper for loading JSON fixtures
- [x] T012 [P] Add async database session fixture with transaction rollback in tests/conftest.py
- [x] T013 [P] Add httpx AsyncClient fixture with ASGITransport in tests/conftest.py
- [x] T014 [P] Add mock_loki_client fixture in tests/conftest.py
- [x] T015 [P] Add mock_cortex_client fixture in tests/conftest.py
- [x] T016 [P] Add mock_llm_provider fixture in tests/conftest.py
- [x] T017 Create tests/unit/__init__.py for unit test package
- [x] T018 [P] Create tests/integration/__init__.py for integration test package
- [x] T019 [P] Create tests/stress/__init__.py for stress test package

**Checkpoint**: Foundation ready - user story test implementation can now begin in parallel

---

## Phase 3: User Story 1 - Alert Ingestion & Webhook Handling (Priority: P1) 🎯 MVP

**Goal**: Verify AlertManager webhooks correctly ingest alerts with deduplication

**Independent Test**: Send mock payloads to webhook endpoint and verify database storage

### Unit Tests for User Story 1

- [x] T020 [P] [US1] Create tests/unit/test_webhook.py with test class structure
- [x] T021 [P] [US1] Add test_single_alert_stored in tests/unit/test_webhook.py - verify firing alert stored
- [x] T022 [P] [US1] Add test_resolved_alert_updates_status in tests/unit/test_webhook.py
- [x] T023 [P] [US1] Add test_batch_alerts_stored_individually in tests/unit/test_webhook.py
- [x] T024 [P] [US1] Add test_duplicate_fingerprint_deduplicates in tests/unit/test_webhook.py
- [x] T025 [P] [US1] Add test_malformed_json_returns_400 in tests/unit/test_webhook.py
- [x] T026 [P] [US1] Add test_missing_required_fields in tests/unit/test_webhook.py (edge case)
- [x] T027 [P] [US1] Add test_long_labels_handled in tests/unit/test_webhook.py (edge case)
- [x] T028 [P] [US1] Add test_future_timestamp_handled in tests/unit/test_webhook.py (edge case)
- [x] T029 [P] [US1] Add test_clock_skew_handling in tests/unit/test_webhook.py (edge case)

### Integration Tests for User Story 1

- [x] T030 [P] [US1] Create tests/integration/test_webhook_e2e.py with TestClient
- [x] T031 [US1] Add test_webhook_accepts_valid_payload in tests/integration/test_webhook_e2e.py
- [x] T032 [US1] Add test_webhook_rejects_malformed in tests/integration/test_webhook_e2e.py
- [x] T033 [US1] Add test_webhook_batch_processing in tests/integration/test_webhook_e2e.py

**Checkpoint**: User Story 1 complete - alert ingestion tests pass independently

---

## Phase 4: User Story 2 - Multi-Alert Correlation into Incidents (Priority: P1)

**Goal**: Verify alerts are grouped into incidents by time and label similarity

**Independent Test**: Ingest multiple related alerts and verify they group into single incident

### Unit Tests for User Story 2

- [x] T034 [P] [US2] Create tests/unit/test_correlation_service.py with test class structure
- [x] T035 [P] [US2] Add test_same_service_correlates in tests/unit/test_correlation_service.py
- [x] T036 [P] [US2] Add test_different_services_separate_incidents in tests/unit/test_correlation_service.py
- [x] T037 [P] [US2] Add test_alert_added_to_existing_incident in tests/unit/test_correlation_service.py
- [x] T038 [P] [US2] Add test_outside_window_new_incident in tests/unit/test_correlation_service.py
- [x] T039 [P] [US2] Create tests/unit/test_semantic_correlator.py for semantic tests (included in test_correlation_service.py)
- [x] T040 [P] [US2] Add test_semantic_70_threshold in tests/unit/test_semantic_correlator.py
- [x] T041 [P] [US2] Add test_semantic_non_english in tests/unit/test_semantic_correlator.py (edge case)
- [x] T042 [P] [US2] Add test_incident_merge_after_creation in tests/unit/test_correlation_service.py (edge case)

### Integration Tests for User Story 2

- [x] T043 [P] [US2] Create tests/integration/test_correlation_e2e.py
- [x] T044 [US2] Add test_correlation_flow_same_service in tests/integration/test_correlation_e2e.py
- [x] T045 [US2] Add test_correlation_flow_different_services in tests/integration/test_correlation_e2e.py

**Checkpoint**: User Story 2 complete - correlation tests pass independently

---

## Phase 5: User Story 3 - RCA Agent Execution (Priority: P1)

**Goal**: Verify AI agent analyzes incidents and generates RCA reports

**Independent Test**: Trigger RCA on test incident and verify tool calls and report generation

### Unit Tests for User Story 3

- [x] T046 [P] [US3] Create tests/unit/test_rca_agent.py with mocked LLM provider
- [x] T047 [P] [US3] Add test_agent_queries_logs_and_metrics in tests/unit/test_rca_agent.py
- [x] T048 [P] [US3] Add test_agent_calls_loki_tool in tests/unit/test_rca_agent.py
- [x] T049 [P] [US3] Add test_agent_calls_cortex_tool in tests/unit/test_rca_agent.py
- [x] T050 [P] [US3] Add test_agent_generates_report in tests/unit/test_rca_agent.py
- [x] T051 [P] [US3] Add test_agent_handles_multiple_alerts in tests/unit/test_rca_agent.py
- [x] T052 [P] [US3] Add test_already_analyzing_skipped in tests/unit/test_rca_agent.py (edge case)
- [x] T053 [P] [US3] Add test_malformed_ai_response in tests/unit/test_rca_agent.py (edge case)
- [x] T054 [P] [US3] Add test_crash_recovery in tests/unit/test_rca_agent.py (edge case)

### Integration Tests for User Story 3

- [x] T055 [P] [US3] Create tests/integration/test_rca_e2e.py with live AI API
- [x] T056 [US3] Add test_rca_full_flow in tests/integration/test_rca_e2e.py
- [x] T057 [US3] Add test_rca_report_stored in tests/integration/test_rca_e2e.py

**Checkpoint**: User Story 3 complete - RCA agent tests pass independently

---

## Phase 6: User Story 4 - Loki Log Query Tool (Priority: P2)

**Goal**: Verify Loki query tool returns correct log results

**Independent Test**: Call Loki tool with LogQL queries and verify results

### Unit Tests for User Story 4

- [x] T058 [P] [US4] Create tests/unit/test_loki_tool.py
- [x] T059 [P] [US4] Add test_valid_logql_returns_logs in tests/unit/test_loki_tool.py
- [x] T060 [P] [US4] Add test_time_range_filter in tests/unit/test_loki_tool.py
- [x] T061 [P] [US4] Add test_service_label_filter in tests/unit/test_loki_tool.py
- [x] T062 [P] [US4] Add test_loki_unavailable_graceful in tests/unit/test_loki_tool.py
- [x] T063 [P] [US4] Add test_result_limit_truncation in tests/unit/test_loki_tool.py
- [x] T064 [P] [US4] Add test_unexpected_format in tests/unit/test_loki_tool.py (edge case)

**Checkpoint**: User Story 4 complete - Loki tool tests pass independently

---

## Phase 7: User Story 5 - Cortex Metrics Query Tool (Priority: P2)

**Goal**: Verify Cortex query tool returns time-series data

**Independent Test**: Call Cortex tool with PromQL queries and verify results

### Unit Tests for User Story 5

- [x] T065 [P] [US5] Create tests/unit/test_cortex_tool.py
- [x] T066 [P] [US5] Add test_valid_promql_returns_data in tests/unit/test_cortex_tool.py
- [x] T067 [P] [US5] Add test_time_range_filter in tests/unit/test_cortex_tool.py
- [x] T068 [P] [US5] Add test_cpu_memory_metrics in tests/unit/test_cortex_tool.py
- [x] T069 [P] [US5] Add test_cortex_unavailable_graceful in tests/unit/test_cortex_tool.py
- [x] T070 [P] [US5] Add test_empty_result_message in tests/unit/test_cortex_tool.py

**Checkpoint**: User Story 5 complete - Cortex tool tests pass independently

---

## Phase 8: User Story 6 - Report Generation & Storage (Priority: P2)

**Goal**: Verify RCA reports are stored and retrievable

**Independent Test**: Generate report, store it, retrieve via API

### Unit Tests for User Story 6

- [x] T071 [P] [US6] Create tests/unit/test_report_service.py
- [x] T072 [P] [US6] Add test_report_stored_with_incident in tests/unit/test_report_service.py
- [x] T073 [P] [US6] Add test_report_retrieved_by_id in tests/unit/test_report_service.py
- [x] T074 [P] [US6] Add test_report_list_pagination in tests/unit/test_report_service.py
- [x] T075 [P] [US6] Add test_export_json_format in tests/unit/test_report_service.py
- [x] T076 [P] [US6] Add test_export_markdown_format in tests/unit/test_report_service.py

**Checkpoint**: User Story 6 complete - report tests pass independently

---

## Phase 9: User Story 7 - API Endpoints (Priority: P2)

**Goal**: Verify REST API endpoints for alerts, incidents, and reports

**Independent Test**: Call each endpoint and verify responses

### Unit Tests for User Story 7

- [x] T077 [P] [US7] Create tests/unit/test_api_endpoints.py (consolidated API tests)
- [x] T078 [P] [US7] Add test_list_alerts_pagination in tests/unit/test_api_endpoints.py
- [x] T079 [P] [US7] Add test_get_alert_by_id in tests/unit/test_api_endpoints.py
- [x] T080 [P] [US7] Add test_filter_by_status in tests/unit/test_api_endpoints.py
- [x] T081 [P] [US7] Add test_filter_by_severity in tests/unit/test_api_endpoints.py
- [x] T082 [P] [US7] Add test_list_incidents in tests/unit/test_api_endpoints.py
- [x] T083 [P] [US7] Add test_list_incidents_pagination in tests/unit/test_api_endpoints.py
- [x] T084 [P] [US7] Add test_get_incident_with_alerts in tests/unit/test_api_endpoints.py
- [x] T085 [P] [US7] Add test_manual_correlation in tests/unit/test_api_endpoints.py

### Integration Tests for User Story 7

- [x] T086 [P] [US7] API tests included in tests/unit/test_api_endpoints.py
- [x] T087 [P] [US7] Add test_list_alerts_endpoint in tests/unit/test_api_endpoints.py
- [x] T088 [P] [US7] Add test_get_alert_endpoint in tests/unit/test_api_endpoints.py
- [x] T089 [P] [US7] Add test_alert_not_found in tests/unit/test_api_endpoints.py
- [x] T090 [P] [US7] Add incidents tests in tests/unit/test_api_endpoints.py
- [x] T091 [P] [US7] Add test_list_incidents_endpoint in tests/unit/test_api_endpoints.py
- [x] T092 [P] [US7] Add test_get_incident_endpoint in tests/unit/test_api_endpoints.py
- [x] T093 [P] [US7] Reports tests included in test_report_service.py
- [x] T094 [P] [US7] Add test_list_reports_endpoint in tests/unit/test_api_endpoints.py
- [x] T095 [P] [US7] Add test_get_report_endpoint in tests/unit/test_api_endpoints.py
- [x] T096 [P] [US7] Add test_export_json in tests/unit/test_report_service.py
- [x] T097 [P] [US7] Add test_export_markdown in tests/unit/test_report_service.py
- [x] T098 [US7] Add health endpoint tests in tests/unit/test_api_endpoints.py

**Checkpoint**: User Story 7 complete - API tests pass independently

---

## Phase 10: User Story 8 - Concurrent RCA Execution (Priority: P3)

**Goal**: Verify system handles multiple simultaneous RCA executions

**Independent Test**: Trigger RCA on multiple incidents and verify all complete

### Stress Tests for User Story 8

- [x] T099 [P] [US8] Create tests/unit/test_concurrent_rca.py and tests/stress/test_concurrent_rca_stress.py
- [x] T100 [P] [US8] Add test_two_concurrent_rca in tests/unit/test_concurrent_rca.py
- [x] T101 [P] [US8] Add test_max_3_concurrent_limit in tests/unit/test_concurrent_rca.py
- [x] T102 [P] [US8] Add test_no_data_corruption in tests/unit/test_concurrent_rca.py
- [x] T103 [US8] Add test_rate_limit_throttling in tests/stress/test_concurrent_rca_stress.py

**Checkpoint**: User Story 8 complete - concurrency tests pass independently

---

## Phase 11: User Story 9 - Error Handling & Retry Logic (Priority: P3)

**Goal**: Verify graceful error handling and retry behavior

**Independent Test**: Simulate failures and verify recovery

### Unit Tests for User Story 9

- [x] T104 [P] [US9] Create tests/unit/test_error_handling.py with comprehensive error handling tests
- [x] T105 [P] [US9] Add test_loki_timeout_continues in tests/unit/test_error_handling.py
- [x] T106 [P] [US9] Add test_ai_rate_limit_backoff in tests/unit/test_error_handling.py
- [x] T107 [P] [US9] Add test_webhook_invalid_logs_4xx in tests/unit/test_error_handling.py
- [x] T108 [US9] Add test_critical_failure_marks_review in tests/unit/test_error_handling.py

**Checkpoint**: User Story 9 complete - error handling tests pass independently

---

## Phase 12: User Story 10 - Database Operations (Priority: P3)

**Goal**: Verify database reliability and performance

**Independent Test**: CRUD operations and data integrity checks

### Unit Tests for User Story 10

- [x] T109 [P] [US10] Create tests/unit/test_database_operations.py with comprehensive DB tests
- [x] T110 [P] [US10] Add test_incident_alert_relationship in tests/unit/test_database_operations.py
- [x] T111 [P] [US10] Add test_cascade_delete_report in tests/unit/test_database_operations.py
- [x] T112 [P] [US10] Add test_optimistic_locking in tests/unit/test_database_operations.py
- [x] T113 [US10] Add test_pagination_bounded_memory in tests/unit/test_database_operations.py

### Stress Tests for User Story 10

- [x] T114 [P] [US10] Create tests/stress/test_high_volume.py with concurrent tests
- [x] T115 [US10] Add test_concurrent_alert_ingestion in tests/stress/test_high_volume.py

**Checkpoint**: User Story 10 complete - database tests pass independently

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Coverage validation and final cleanup

- [ ] T116 Run pytest --cov=src --cov-report=html and verify 80% unit coverage
- [ ] T117 Run pytest tests/integration/ --cov=src and verify 70% integration coverage
- [x] T118 [P] Add missing docstrings to all test files
- [ ] T119 Run full test suite and fix any flaky tests
- [ ] T120 Verify all 47 acceptance scenarios have corresponding tests (per spec.md)
- [ ] T121 Update tests/BUILD.bazel with all new test targets (if using Bazel)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-12)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 13)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Priority | Can Start After | Dependencies on Other Stories |
|-------|----------|-----------------|-------------------------------|
| US1 | P1 | Phase 2 | None |
| US2 | P1 | Phase 2 | None (uses own fixtures) |
| US3 | P1 | Phase 2 | None (mocks tools) |
| US4 | P2 | Phase 2 | None |
| US5 | P2 | Phase 2 | None |
| US6 | P2 | Phase 2 | None |
| US7 | P2 | Phase 2 | None |
| US8 | P3 | Phase 2 | None (tests concurrency in isolation) |
| US9 | P3 | Phase 2 | None |
| US10 | P3 | Phase 2 | None |

### Parallel Opportunities

All user stories can run in parallel after Phase 2 completes.

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# All unit tests can run in parallel:
pytest tests/unit/test_webhook.py::test_single_alert_stored &
pytest tests/unit/test_webhook.py::test_resolved_alert_updates_status &
pytest tests/unit/test_webhook.py::test_batch_alerts_stored_individually &
pytest tests/unit/test_webhook.py::test_duplicate_fingerprint_deduplicates &
pytest tests/unit/test_webhook.py::test_malformed_json_returns_400 &
wait

# Integration tests after unit tests pass:
pytest tests/integration/test_webhook_e2e.py
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup (fixtures)
2. Complete Phase 2: Foundational (test infrastructure)
3. Complete Phase 3: User Story 1 (alert ingestion)
4. Complete Phase 4: User Story 2 (correlation)
5. Complete Phase 5: User Story 3 (RCA agent)
6. **STOP and VALIDATE**: Core functionality tested

### Incremental Delivery

1. Complete Setup + Foundational → Test infrastructure ready
2. Add User Story 1 → Alert ingestion tested
3. Add User Story 2 → Correlation tested
4. Add User Story 3 → RCA agent tested (MVP complete!)
5. Add User Stories 4-7 → Tools and API tested (P2)
6. Add User Stories 8-10 → Robustness tested (P3)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Stories 1, 4, 8
   - Developer B: User Stories 2, 5, 9
   - Developer C: User Stories 3, 6-7, 10
3. Stories complete independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Integration tests use live AI API per clarification decision
- Max 3 concurrent RCA executions per FR-027
