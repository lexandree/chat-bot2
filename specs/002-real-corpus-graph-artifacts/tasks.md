# Tasks: Real Corpus Graph Artifacts

**Input**: Design documents from `/specs/002-real-corpus-graph-artifacts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. Unit tests stay offline. Live Neo4j checks are marked integration. File artifact validation is covered by unit or smoke tests as appropriate.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [Story] Description`

- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish real-corpus graph artifacts scaffolding without changing runtime behavior.

- [X] T001 Create feature documentation files in `specs/002-real-corpus-graph-artifacts/` and confirm `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, and `contracts/artifacts.md` exist
- [X] T002 Update operator-facing docs in `README.md` and `AGENTS.md` to distinguish preview artifacts, loaded graph state, snapshot artifacts, and the legacy AufenthG baseline graph snapshot
- [X] T003 Update ignored artifact paths in `.gitignore` for real-corpus snapshot/comparison outputs and any temporary legacy baseline files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared contracts and reusable helpers required by all user stories.

- [X] T004 Define real corpus manifest and preview contracts in `src/ingestion/legal_preview_loader.py`
- [X] T005 Define graph snapshot artifact and comparison report record shapes in `src/evaluation/load_cases.py`
- [X] T006 Define loaded-scope summary and verification evidence extensions in `src/graph/types.py`
- [X] T007 Add offline unit tests for preview/file artifact separation in `tests/unit/test_preview_artifact_contract.py`
- [X] T008 Add offline unit tests for snapshot/comparison artifact shape in `tests/unit/test_artifact_contracts.py`

**Checkpoint**: Preview, snapshot, and comparison artifact contracts are available for story work.

---

## Phase 3: User Story 1 - Preview Real Corpus (Priority: P1)

**Goal**: Operators can preview selected real German legal XML sources as a file artifact before changing graph state.

**Independent Test**: Given a real corpus manifest and selected law-code scope, preview generation can be run twice and yields the same preview file artifact contents for coverage, identifiers, ordering, and checksum summary.

### Tests for User Story 1

- [X] T009 [US1] Add offline unit tests for real-corpus manifest filtering and deterministic preview output in `tests/unit/test_legal_preview_loader.py`
- [X] T010 [US1] Add offline unit tests for missing optional input reporting in `tests/unit/test_legal_xml_import.py`
- [X] T011 [US1] Add CLI smoke test for preview artifact generation in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 1

- [X] T012 [US1] Implement real-corpus manifest loading and preview assembly in `src/ingestion/legal_preview_loader.py`
- [X] T013 [US1] Implement deterministic preview artifact writer for real corpus slices in `src/ingestion/legal_preview_loader.py`
- [X] T014 [US1] Wire `foundation preview legal-xml` command output to the real-corpus preview artifact in `src/app/commands.py`

**Checkpoint**: Preview artifacts can be generated repeatedly without persisting graph state.

---

## Phase 4: User Story 2 - Load And Manage Real Corpus Scope (Priority: P2)

**Goal**: Operators can load, verify, and delete a selected real corpus scope in the new graph.

**Independent Test**: Given a real corpus preview, load can be repeated with stable counts, verification reports loaded graph evidence, and delete removes only the selected scope.

### Tests for User Story 2

- [X] T015 [US2] Add offline unit tests for loaded-scope count reporting in `tests/unit/test_load_verify_delete_reports.py`
- [X] T016 [US2] Add live Neo4j integration test for load idempotency, verify counts, and scoped delete in `tests/integration/test_neo4j_load_verify_delete.py`

### Implementation for User Story 2

- [X] T017 [US2] Implement real-corpus load workflow against the graph writer in `src/graph/repositories.py`
- [X] T018 [US2] Implement scoped verify report assembly for loaded real corpus data in `src/graph/repositories.py`
- [X] T019 [US2] Implement scoped delete workflow for loaded real corpus data in `src/graph/repositories.py`
- [X] T020 [US2] Wire `foundation graph load`, `foundation graph verify`, and `foundation graph delete` command handling in `src/app/commands.py`

**Checkpoint**: The real corpus can be loaded, verified, and deleted as persisted graph state.

---

## Phase 5: User Story 3 - Generate Snapshot Artifacts (Priority: P3)

**Goal**: Operators can generate file-based snapshot artifacts from a loaded graph scope.

**Independent Test**: Given a loaded selected scope, snapshot generation can be repeated without graph changes and yields stable counts, labels, relation types, sample ids, source coverage, and embedding metadata.

### Tests for User Story 3

- [X] T021 [US3] Add offline unit tests for graph snapshot artifact assembly in `tests/unit/test_artifact_contracts.py`
- [X] T022 [US3] Add offline unit tests for snapshot reproducibility and scope filtering in `tests/unit/test_load_verify_delete_reports.py`
- [X] T023 [US3] Add smoke test for snapshot file generation in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 3

- [X] T024 [US3] Implement graph snapshot artifact assembly from loaded scope state in `src/evaluation/load_cases.py`
- [X] T025 [US3] Implement snapshot file writer for selected graph scopes in `src/evaluation/load_cases.py`
- [X] T026 [US3] Wire `foundation graph snapshot` command handling in `src/app/commands.py`

**Checkpoint**: Loaded graph state can be summarized as repeatable file artifacts.

---

## Phase 6: User Story 4 - Legacy AufenthG Baseline Coverage Check (Priority: P4)

**Goal**: Operators can check a new graph snapshot against the legacy AufenthG baseline graph snapshot without migrating legacy data.

**Independent Test**: Given a new graph snapshot and a read-only legacy AufenthG baseline graph snapshot, the coverage check reports missing, extra, and matching coverage without copying old nodes or promoting baseline content.

### Tests for User Story 4

- [X] T027 [US4] Add offline unit tests for comparison report assembly in `tests/unit/test_artifact_contracts.py`
- [X] T028 [US4] Add offline unit tests for read-only baseline handling in `tests/unit/test_load_verify_delete_reports.py`
- [X] T029 [US4] Add smoke test for graph artifact file generation in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 4

- [X] T030 [US4] Capture the legacy AufenthG baseline graph snapshot as a read-only structural artifact in `src/evaluation/load_cases.py`
- [X] T031 [US4] Implement file-to-file comparison report generation between the new graph snapshot and the legacy AufenthG baseline graph snapshot in `src/evaluation/load_cases.py`
- [X] T032 [US4] Wire `foundation graph compare` command handling in `src/app/commands.py`

**Checkpoint**: The legacy AufenthG baseline graph snapshot can be checked without becoming part of the new graph workflow.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Validate contracts, docs, and operational boundaries across all completed stories.

- [X] T033 Update `specs/002-real-corpus-graph-artifacts/quickstart.md` with the final preview, load, snapshot, legacy baseline, and compare workflow
- [X] T034 Update `specs/002-real-corpus-graph-artifacts/contracts/artifacts.md` if artifact fields changed during implementation
- [X] T035 Verify no default unit test imports live Neo4j, live Jina, paid APIs, or remote notebooks in `tests/unit/`
- [X] T036 Verify no chatbot UX, LLM extraction, answer generation, GraphRAG inference, or fallback answer behavior exists under `src/`
- [X] T037 Verify comparison evidence remains file-based and the legacy AufenthG baseline graph snapshot is not treated as source of truth in `specs/002-real-corpus-graph-artifacts/`
- [X] T038 Run `python -m compileall src tests` and record the result in `specs/002-real-corpus-graph-artifacts/quickstart.md`
- [X] T039 Run `python -m pytest tests/unit tests/smoke` and record the result in `specs/002-real-corpus-graph-artifacts/quickstart.md`
- [X] T040 Run marked live Neo4j integration checks for load/baseline-check workflows and record the result in `specs/002-real-corpus-graph-artifacts/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Stories (Phase 3+)**: Depend on Foundational completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational phase
- **User Story 2 (P2)**: Can start after Foundational phase and may integrate with US1 preview artifacts
- **User Story 3 (P3)**: Can start after User Story 2 because it consumes loaded graph state
- **User Story 4 (P4)**: Can start after User Story 3 because it consumes snapshot artifacts

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Deliver User Story 1 preview artifacts.
3. Validate that preview remains a file artifact and does not mutate graph state.

### Incremental Delivery

1. Add real-corpus graph load, verify, and delete workflows.
2. Add graph snapshot artifacts from loaded scope.
3. Add file-to-file comparison against the legacy AufenthG baseline graph snapshot.
4. Finish with cleanup, docs, and live verification evidence.
