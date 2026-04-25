# Tasks: German Legal Graph Foundation

**Input**: Design documents from `/specs/001-legal-graph-foundation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by the feature specification. Unit tests must stay offline.
Live Neo4j and Jina-compatible embedding checks must be marked integration or
smoke tests and excluded from default unit runs.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the clean project package and test layout without importing
old source snapshot modules.

- [ ] T001 Create package directories and `__init__.py` files for `src/app/`, `src/graph/`, `src/ingestion/`, `src/retrieval/`, `src/review/`, `src/evaluation/`, `tests/unit/`, `tests/integration/`, `tests/smoke/`, and `tests/fixtures/`
- [ ] T002 Update `pyproject.toml` with `pydantic-settings`, pytest marker configuration for `neo4j`, `embedding`, and `smoke`, and package discovery for `src/`
- [ ] T003 [P] Add offline fixture manifest for a minimal German legal XML corpus slice in `tests/fixtures/legal_xml_import_manifest.json`
- [ ] T004 [P] Add deterministic sample German legal XML fixtures in `tests/fixtures/legal_xml/`
- [ ] T005 [P] Add validation case fixture for exact references and traversal in `tests/fixtures/legal_validation_cases.json`

**Note**: T006 was intentionally removed after the redundant `.gitkeep`
placeholder task was dropped; task IDs remain stable to avoid renumbering churn.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared contracts, settings, graph types, schema definitions, and
test helpers that block all user stories.

**CRITICAL**: No user story implementation starts until this phase is complete.

- [ ] T007 [P] Implement typed settings and validation in `src/app/settings.py`
- [ ] T008 [P] Add offline unit tests for settings validation and redaction in `tests/unit/test_settings.py`
- [ ] T009 [P] Implement shared logging setup without secrets in `src/app/logging.py`
- [ ] T010 [P] Define graph domain dataclasses and report types in `src/graph/types.py`
- [ ] T011 [P] Define embedding profile contract and prefix constants in `src/retrieval/embedding_profile.py`
- [ ] T012 [P] Add offline unit tests for embedding profile validation and prefix policy in `tests/unit/test_embedding_profile.py`
- [ ] T013 [P] Define candidate/review schema placeholder contract in `src/review/schema_boundary.py`
- [ ] T014 [P] Implement schema definition assembly with stable names for source, legal, reference, embedding-profile, validation, vector, and candidate/review placeholder objects in `src/graph/schema.py`
- [ ] T015 [P] Add offline unit tests for schema definition assembly and vector dimensions in `tests/unit/test_schema.py`
- [ ] T016 [P] Implement artifact/report serializers for preview, readiness, load, embedding, verification, deletion, and traversal reports in `src/evaluation/load_cases.py`
- [ ] T017 [P] Add offline unit tests for artifact/report serializer contracts in `tests/unit/test_artifact_contracts.py`

**Checkpoint**: Shared contracts compile and offline unit tests for settings,
schema, embedding profile, and reports pass.

---

## Phase 3: User Story 1 - Prepare The Graph Foundation (Priority: P1)

**Goal**: Operators can validate configuration, connect to Neo4j 5/Aura with a
real driver-backed client, and bootstrap schema idempotently.

**Independent Test**: Starting from an empty Neo4j 5/Aura-compatible graph store
and complete configuration, preparation can run twice and report identical
schema object names; offline unit tests use fakes only.

### Tests for User Story 1

- [ ] T018 [P] [US1] Add offline unit tests for graph client protocol behavior with a fake driver in `tests/unit/test_graph_client.py`
- [ ] T019 [P] [US1] Add offline unit tests for graph readiness report assembly in `tests/unit/test_graph_readiness.py`
- [ ] T020 [P] [US1] Add marked live Neo4j integration test for connectivity and schema bootstrap idempotency in `tests/integration/test_neo4j_schema_bootstrap.py`

### Implementation for User Story 1

- [ ] T021 [US1] Implement real Neo4j official-driver client with parameterized read/write, database selection, connectivity check, vector query method, and close behavior in `src/graph/client.py`
- [ ] T022 [US1] Implement schema bootstrap executor using the real graph client and schema definitions in `src/graph/schema.py`
- [ ] T023 [US1] Implement graph readiness workflow and report creation in `src/graph/repositories.py`
- [ ] T024 [US1] Implement operator command handler for `foundation settings validate` and `foundation schema bootstrap` in `src/app/commands.py`
- [ ] T025 [US1] Wire command module entry point in `src/app/__main__.py`
- [ ] T026 [US1] Document US1 operator flow and live Neo4j prerequisites in `specs/001-legal-graph-foundation/quickstart.md`

**Checkpoint**: US1 works independently: settings validate offline, schema
definitions unit-test offline, and live Neo4j bootstrap runs only when marked
integration tests are enabled.

---

## Phase 4: User Story 2 - Preview German Legal XML Sources (Priority: P2)

**Goal**: Operators can generate deterministic legal XML previews without graph
writes.

**Independent Test**: Given a controlled corpus slice with an optional missing
file, preview output is deterministic across two runs and reports
`missing_inputs`.

### Tests for User Story 2

- [ ] T027 [P] [US2] Add offline unit tests for XML fixture parsing and malformed required-file reporting in `tests/unit/test_legal_xml_import.py`
- [ ] T028 [P] [US2] Add offline unit tests for stable source/fragment ids, ordering, checksums, and missing optional inputs in `tests/unit/test_legal_preview_loader.py`
- [ ] T029 [P] [US2] Add offline contract test for legal XML preview artifact shape in `tests/unit/test_preview_artifact_contract.py`

### Implementation for User Story 2

- [ ] T030 [P] [US2] Implement legal XML parser for `gesetze-im-internet` style files in `src/ingestion/legal_xml_import.py`
- [ ] T031 [P] [US2] Implement stable id and checksum helpers for source documents and fragments in `src/ingestion/legal_preview_loader.py`
- [ ] T032 [US2] Implement preview manifest loading, optional missing-input reporting, law-code filtering, and deterministic ordering in `src/ingestion/legal_preview_loader.py`
- [ ] T033 [US2] Implement preview artifact writer matching `contracts/artifacts.md` in `src/ingestion/legal_preview_loader.py`
- [ ] T034 [US2] Add operator command handler for `foundation preview legal-xml` in `src/app/commands.py`
- [ ] T035 [US2] Update `specs/001-legal-graph-foundation/quickstart.md` with preview fixture flow and expected artifact path

**Checkpoint**: US2 works independently: preview can run offline against
fixtures, produces stable artifacts, and does not require Neo4j.

---

## Phase 5: User Story 3 - Load, Verify, And Delete Structural Legal Graph Data (Priority: P3)

**Goal**: Operators can load selected preview data into Neo4j, verify structural
graph state, and delete selected law-code scope without full reset.

**Independent Test**: Given deterministic preview data, loading the same scope
twice keeps unique counts stable; delete removes only selected data and verify
reports the result.

### Tests for User Story 3

- [ ] T036 [P] [US3] Add offline unit tests for structural graph mapping from preview artifacts in `tests/unit/test_legal_structure_builder.py`
- [ ] T037 [P] [US3] Add offline unit tests for legal reference parsing and unresolved evidence in `tests/unit/test_legal_reference_parser.py`
- [ ] T038 [P] [US3] Add offline unit tests for load, verify, and delete report assembly in `tests/unit/test_load_verify_delete_reports.py`
- [ ] T039 [P] [US3] Add marked live Neo4j integration test for load idempotency, verify counts, and law-code delete in `tests/integration/test_neo4j_load_verify_delete.py`

### Implementation for User Story 3

- [ ] T040 [P] [US3] Implement legal reference parser for German law-code and section references in `src/ingestion/legal_reference_parser.py`
- [ ] T041 [P] [US3] Implement structural graph builder for LegalAct, LegalSection, LegalFragment, and LegalReference records in `src/ingestion/legal_structure_builder.py`
- [ ] T042 [US3] Implement Neo4j upsert writer for source, legal, fragment, and reference records in `src/graph/writer.py`
- [ ] T043 [US3] Implement graph repositories for load, verify, and delete by law-code scope in `src/graph/repositories.py`
- [ ] T044 [US3] Implement verification report builder with source/legal/reference/unresolved/embedding/profile/backend fields in `src/ingestion/verification.py`
- [ ] T045 [US3] Add operator command handlers for `foundation graph load`, `foundation graph verify`, and `foundation graph delete` in `src/app/commands.py`
- [ ] T046 [US3] Update `specs/001-legal-graph-foundation/quickstart.md` with load/verify/delete live Neo4j flow

**Checkpoint**: US3 works with live Neo4j when enabled and remains unit-testable
offline through mapping and report tests.

---

## Phase 6: User Story 4 - Embed Loaded Source Text (Priority: P4)

**Goal**: Operators can write source document and fragment embeddings using an
operator-started local-only Jina-compatible service, while unit tests remain
offline.

**Independent Test**: With local Jina-compatible service running, a selected
loaded law-code scope receives embeddings and verification reports profile,
dimensions, normalization, backend, and counts. Without the service, workflow
fails before partial graph writes.

### Tests for User Story 4

- [ ] T047 [P] [US4] Add offline unit tests for local embedding endpoint client request/response parsing and health preflight fakes in `tests/unit/test_embedding_endpoint_client.py`
- [ ] T048 [P] [US4] Add offline unit tests for embedding service prefixing, profile metadata, vector validation, and fail-fast policy in `tests/unit/test_embedding_service.py`
- [ ] T049 [P] [US4] Add offline unit tests for embedding run report assembly in `tests/unit/test_embedding_run_report.py`
- [ ] T050 [P] [US4] Add marked live embedding integration test for local-only Jina-compatible endpoint in `tests/integration/test_live_embedding_service.py`
- [ ] T051 [P] [US4] Add marked live Neo4j plus embedding integration test for graph-write embeddings in `tests/integration/test_neo4j_embedding_writes.py`

### Implementation for User Story 4

- [ ] T052 [P] [US4] Implement local embedding endpoint HTTP client with health/preflight in `src/retrieval/embedding_endpoint_client.py`
- [ ] T053 [P] [US4] Implement embedding backend protocol and local-only backend selection in `src/retrieval/embedding_backend.py`
- [ ] T054 [US4] Implement embedding service for `Document: ` and `Query: ` prefixes, profile validation, normalization checks, and runtime metadata in `src/retrieval/embedding_service.py`
- [ ] T055 [US4] Implement graph embedding writer for source documents and fragments with fail-fast preflight before graph mutation in `src/graph/writer.py`
- [ ] T056 [US4] Extend verification repository to report embedding count, profile ids, dimensions, backend names, and normalization status in `src/graph/repositories.py`
- [ ] T057 [US4] Add operator command handler for `foundation embeddings write` in `src/app/commands.py`
- [ ] T058 [US4] Update `specs/001-legal-graph-foundation/quickstart.md` with when to start the external Jina-compatible service

**Checkpoint**: US4 works only when explicitly enabled for live integration;
default unit tests stay offline and validate prefix/profile/fail-fast behavior.

---

## Phase 7: User Story 5 - Validate Structural Retrieval Baseline (Priority: P5)

**Goal**: Operators can resolve exact legal references and run bounded typed
traversal without answer generation.

**Independent Test**: Given loaded legal graph data, exact law-code plus section
reference resolves to expected section and bounded traversal returns source
refs, relation types, depth/fanout/node limit metadata, and no answer text.

### Tests for User Story 5

- [ ] T059 [P] [US5] Add offline unit tests for exact reference normalization and resolver decisions in `tests/unit/test_legal_reference_resolver.py`
- [ ] T060 [P] [US5] Add offline unit tests for traversal relation/depth/fanout/node limit policy in `tests/unit/test_legal_traversal.py`
- [ ] T061 [P] [US5] Add offline contract test that structural retrieval result omits `answer_text`, `answer`, and `generated_answer` fields in `tests/unit/test_structural_retrieval_contract.py`
- [ ] T062 [P] [US5] Add marked live Neo4j integration test for exact resolution and bounded traversal on loaded fixture data in `tests/integration/test_neo4j_structural_retrieval.py`

### Implementation for User Story 5

- [ ] T063 [P] [US5] Implement exact legal reference resolver with current-default and as-of-date hooks in `src/retrieval/legal_reference_resolver.py`
- [ ] T064 [P] [US5] Implement bounded typed traversal with allowed relations, depth limit, fanout limit, node limit, and cycle prevention in `src/retrieval/legal_traversal.py`
- [ ] T065 [US5] Implement graph repository read queries for exact reference resolution and traversal metadata in `src/graph/repositories.py`
- [ ] T066 [US5] Add operator command handlers for `foundation references resolve` and `foundation traversal run` in `src/app/commands.py`
- [ ] T067 [US5] Update `specs/001-legal-graph-foundation/quickstart.md` with structural retrieval baseline validation flow

**Checkpoint**: US5 proves structural retrieval baseline without semantic
expansion, reranking, LLM extraction, or answer generation.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Validate contracts, docs, test markers, and project boundaries
across all completed stories.

- [ ] T068 Run offline compile validation with `python -m compileall src tests` and record result in `specs/001-legal-graph-foundation/quickstart.md`
- [ ] T069 Run default offline unit tests with `python -m pytest tests/unit` and record result in `specs/001-legal-graph-foundation/quickstart.md`
- [ ] T070 [P] Verify no default unit test imports live Neo4j, live Jina, paid APIs, or remote notebooks in `tests/unit/`
- [ ] T071 [P] Verify no chatbot UX, LLM extraction, GraphRAG answer generation, fallback answer behavior, or old recording facade exists under `src/`
- [ ] T072 [P] Verify `export/source_snapshot` remains reference-only and no snapshot module was copied wholesale into `src/`
- [ ] T073 [P] Update `README.md` with foundation scope, offline test command, live Neo4j/Jina integration flags, and operator workflow
- [ ] T074 [P] Update `.env.example` with final non-secret Neo4j, embedding profile, embedding endpoint, and test flag settings
- [ ] T075 Review `specs/001-legal-graph-foundation/contracts/artifacts.md` against implemented report serializers and update contract examples if field names changed
- [ ] T076 Review `specs/001-legal-graph-foundation/tasks.md` and mark any implementation-deferred items before handoff

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 Prepare Graph Foundation (Phase 3)**: Depends on Foundational.
- **US2 Preview XML Sources (Phase 4)**: Depends on Foundational; can proceed after US1 for live schema confidence, but offline preview is independent.
- **US3 Load/Verify/Delete (Phase 5)**: Depends on US1 and US2.
- **US4 Embed Loaded Source Text (Phase 6)**: Depends on US3 loaded source documents/fragments.
- **US5 Validate Structural Retrieval Baseline (Phase 7)**: Depends on US3 loaded legal graph data.
- **Final Polish**: Depends on all desired stories.

### User Story Dependencies

- **US1 (P1)**: First foundation slice; required before live graph workflows.
- **US2 (P2)**: Independently testable offline after Foundational.
- **US3 (P3)**: Requires preview artifacts from US2 and live graph readiness from US1.
- **US4 (P4)**: Requires loaded source documents/fragments from US3 and operator-started Jina-compatible service for live checks.
- **US5 (P5)**: Requires loaded legal sections/references from US3.

### Within Each User Story

- Tests are written before implementation tasks in the same story.
- Unit tests must avoid live services.
- Integration tests must be marked and gated by environment flags.
- Contracts/models before services/repositories.
- Repositories before command handlers.
- Documentation updated after command behavior exists.

---

## Parallel Opportunities

- Setup fixture tasks T003-T005 can run in parallel.
- Foundational contract tasks T007-T017 can run in parallel by file, except tests should align with their target modules.
- US1 tests T018-T020 can run in parallel before implementing T021-T025.
- US2 parser/preview tests T027-T029 can run in parallel, and T030/T031 can be implemented in parallel before T032.
- US3 tests T036-T039 can run in parallel, and T040/T041 can be implemented in parallel before graph writer/repositories.
- US4 tests T047-T051 can run in parallel, and T052/T053 can be implemented in parallel before T054/T055.
- US5 tests T059-T062 can run in parallel, and T063/T064 can be implemented in parallel before T065/T066.
- Polish checks T070-T074 can run in parallel after story implementation.

## Parallel Example: US2 Preview XML Sources

```bash
Task: "T027 [P] [US2] Add offline unit tests for XML fixture parsing and malformed required-file reporting in tests/unit/test_legal_xml_import.py"
Task: "T028 [P] [US2] Add offline unit tests for stable source/fragment ids, ordering, checksums, and missing optional inputs in tests/unit/test_legal_preview_loader.py"
Task: "T029 [P] [US2] Add offline contract test for legal XML preview artifact shape in tests/unit/test_preview_artifact_contract.py"
```

## Parallel Example: US4 Embedding Writes

```bash
Task: "T047 [P] [US4] Add offline unit tests for local embedding endpoint client request/response parsing and health preflight fakes in tests/unit/test_embedding_endpoint_client.py"
Task: "T048 [P] [US4] Add offline unit tests for embedding service prefixing, profile metadata, vector validation, and fail-fast policy in tests/unit/test_embedding_service.py"
Task: "T050 [P] [US4] Add marked live embedding integration test for local-only Jina-compatible endpoint in tests/integration/test_live_embedding_service.py"
```

---

## Implementation Strategy

### Foundation Slice First (US1 Only)

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational contracts.
3. Complete US1 settings, real Neo4j client, schema bootstrap, and readiness reports.
4. Validate offline unit tests.
5. Run live Neo4j integration only when credentials are configured.

### Incremental Delivery

1. US1 establishes graph readiness.
2. US2 adds deterministic source preview without graph writes.
3. US3 loads, verifies, and deletes structural graph data.
4. US4 writes local-only Jina embeddings with live checks gated.
5. US5 validates exact references and bounded traversal without answer generation.

### Boundary Checks

- Do not implement chatbot UX, answer synthesis, LLM proposition extraction,
  review workflow, trusted promotion, bulk notebook execution, or GraphRAG
  answer generation in this feature.
- Do not copy modules wholesale from `export/source_snapshot`.
- Do not replace the real Neo4j client with the old recording facade.
- Do not make unit tests require live services.
