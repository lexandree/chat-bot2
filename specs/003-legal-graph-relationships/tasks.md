# Tasks: Legal Graph Relationship Foundation

**Input**: Design documents from `/specs/003-legal-graph-relationships/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. Unit tests stay offline. Live Neo4j checks are marked integration
and gated by `RUN_LIVE_NEO4J_TESTS=true`. No test in the default unit suite may
require live Neo4j, live Jina, paid APIs, GraphRAG sidecars, remote notebooks, or
private corpora.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [Story] Description`

- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Every task includes an exact file path
- Parallel markers are intentionally omitted for this feature because the parser,
  builder, writer, repository, and CLI changes share core files and should be
  applied in a conservative order

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish fixtures, ignores, and reference docs for relationship
work without changing runtime behavior.

- [X] T001 Create mandatory relation classifier fixture cases for `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO` in `tests/fixtures/legal_relationship_cases.json`
- [X] T002 Add ignored relationship-quality artifact paths such as `data/relationship_quality/*.json` to `.gitignore`
- [X] T003 Confirm `LEGAL_GRAPH_RELATIONSHIP_METHODS.md` exists and is available as methodology-only reference input without finalizing feature boundary content
- [X] T004 Extend live test fixture helpers with a compact multi-reference legal preview scope in `tests/integration/live_support.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared relationship contracts before story-specific parser,
writer, repository, or CLI work.

**CRITICAL**: No user story implementation starts until this phase is complete.

- [X] T005 Define shared relationship taxonomy, resolution status constants, and classifier policy metadata in `src/graph/types.py`
- [X] T006 Extend shared graph record types with relationship evidence, temporal/version evidence, relationship refresh report, and relationship-quality artifact records in `src/graph/types.py`
- [X] T007 Update the graph writer relation allowlist to use the shared relationship taxonomy in `src/graph/writer.py`
- [X] T008 Add relationship-quality artifact serialization helpers and no-answer-field enforcement in `src/evaluation/load_cases.py`
- [X] T009 Add shared typed relation policy helpers for bounded traversal compatibility in `src/retrieval/legal_traversal.py`

**Checkpoint**: Shared taxonomy, status, evidence, refresh, and artifact contracts
exist before parser or graph write behavior changes.

---

## Phase 3: User Story 1 - Parse Context-Aware Legal References (Priority: P1)

**Goal**: Operators can parse explicit German legal references with context,
source provenance, classifier evidence, target candidates, subsection anchors,
and resolution status evidence.

**Independent Test**: Given fixture legal text for the five mandatory relation
types, parsing and structural graph assembly produce deterministic
`LegalReference` evidence with raw text, normalized text, source IDs, context,
target candidate, classifier version, primary relation type, secondary signals,
subsection anchor, and resolution status.

### Tests for User Story 1

- [X] T010 [US1] Add fixture-driven offline unit tests for mandatory relation classification in `tests/unit/test_legal_reference_parser.py`
- [X] T011 [US1] Add offline unit tests for deterministic `context_before`, `context_text`, `context_after`, context checksum, source identifiers, subsection anchors, and classifier policy version in `tests/unit/test_legal_reference_parser.py`
- [X] T012 [US1] Add offline tests that optional source temporal metadata input fields are preserved in `LegalReference` evidence and missing metadata produces `available`, `partial`, `not_available`, or `not_applicable` status in `tests/unit/test_legal_reference_parser.py`
- [X] T013 [US1] Add offline unit tests for `resolved`, `out_of_scope`, `unresolved`, and `ambiguous` reference evidence in `tests/unit/test_legal_structure_builder.py`
- [X] T014 [US1] Update existing parser regression tests for `primary_relation_type` while preserving current section/law normalization coverage in `tests/unit/test_legal_reference_parser.py`

### Implementation for User Story 1

- [X] T015 [US1] Extend parsed reference output fields for context, source, classifier, primary relation, secondary signals, and target candidate evidence in `src/ingestion/legal_reference_parser.py`
- [X] T016 [US1] Implement deterministic context-window extraction and context checksum generation in `src/ingestion/legal_reference_parser.py`
- [X] T017 [US1] Implement deterministic rule-based classifier coverage for `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO` in `src/ingestion/legal_reference_parser.py`
- [X] T018 [US1] Implement target law, target section, subsection anchor, and range evidence extraction without creating subsection target nodes in `src/ingestion/legal_reference_parser.py`
- [X] T019 [US1] Extract temporal/version evidence from optional parser input metadata, headings, amendment wording, and context windows in `src/ingestion/legal_reference_parser.py`
- [X] T020 [US1] Map parsed reference candidate evidence into resolved `LegalReference` records during relationship evidence assembly in `src/ingestion/legal_structure_builder.py`
- [X] T021 [US1] Preserve temporal/version evidence and explicit `temporal_evidence_status` while assembling `LegalReference` records in `src/ingestion/legal_structure_builder.py`
- [X] T022 [US1] Implement selected-scope-aware resolution status assignment for resolved, out-of-scope, unresolved, and ambiguous targets in `src/ingestion/legal_structure_builder.py`
- [X] T023 [US1] Update fixture-backed structural graph expectations for parsed reference candidate fields and resolved `LegalReference` evidence fields in `tests/unit/test_legal_structure_builder.py`

**Checkpoint**: US1 is independently testable offline through parser and
structural builder tests.

---

## Phase 4: User Story 2 - Materialize Typed Legal Edges (Priority: P2)

**Goal**: Operators can refresh relationship state so resolved references become
one primary section-level typed edge while unresolved, ambiguous, and
out-of-scope references remain audit records only.

**Independent Test**: Given a loaded selected graph scope, a relationship refresh
run is idempotent, creates no duplicate `LegalReference` records or typed edges,
creates no generic `RELATED` edge, and never materializes edges for unresolved,
ambiguous, or out-of-scope references. Before refresh runs, the base graph-load
state contains source/legal structure only and contains no trusted
`LegalReference` records or typed legal relationship edges.

### Tests for User Story 2

- [X] T024 [US2] Add offline unit tests that the base graph-load writer path writes only source/legal structure and does not write `LegalReference` records or typed legal edges in `tests/unit/test_graph_writer.py`
- [X] T025 [US2] Add offline unit tests that only resolved references create typed section-level edges during relationship refresh in `tests/unit/test_graph_writer.py`
- [X] T026 [US2] Add offline unit tests that one `LegalReference` creates at most one primary edge and secondary signals do not create extra edges in `tests/unit/test_graph_writer.py`
- [X] T027 [US2] Add offline writer tests that temporal/version evidence is persisted on `LegalReference` records and does not block typed edge creation in `tests/unit/test_graph_writer.py`
- [X] T028 [US2] Add offline unit tests for relationship refresh report counts and failure visibility in `tests/unit/test_load_verify_delete_reports.py`
- [X] T029 [US2] Add marked live Neo4j integration test that base graph load leaves `LegalReference` records and typed legal relationship edges absent before relationship refresh in `tests/integration/test_neo4j_relationship_refresh.py`
- [X] T030 [US2] Add marked live Neo4j integration test for relationship refresh idempotency and duplicate prevention in `tests/integration/test_neo4j_relationship_refresh.py`
- [X] T031 [US2] Add marked live Neo4j integration test for relationship verification status counts in `tests/integration/test_neo4j_relationship_refresh.py`

### Implementation for User Story 2

- [X] T032 [US2] Enforce that the base graph-load repository path writes only source/legal structure and defers `LegalReference` evidence and typed legal relationship edges to relationship refresh in `src/graph/repositories.py`
- [X] T033 [US2] Update legal reference node writes to persist full evidence fields and section-level primary edge metadata in `src/graph/writer.py`
- [X] T034 [US2] Persist temporal/version evidence on `LegalReference` records and copy allowed temporal metadata onto primary typed edges in `src/graph/writer.py`
- [X] T035 [US2] Add scoped relationship-edge cleanup for stale primary typed edges before refresh upserts in `src/graph/writer.py`
- [X] T036 [US2] Implement idempotent relationship refresh from loaded source/legal fragment state in `src/graph/repositories.py`
- [X] T037 [US2] Implement relationship verification queries for counts by relation type and resolution status in `src/graph/repositories.py`
- [X] T038 [US2] Wire `foundation relationships refresh` and `foundation relationships verify` command handling in `src/app/commands.py`
- [X] T039 [US2] Refactor relationship command handlers to accept repository factory dependencies so offline CLI tests can run without opening Neo4j in `src/app/commands.py`
- [X] T040 [US2] Ensure bounded traversal accepts the expanded typed relation taxonomy without introducing `RELATED` in `src/retrieval/legal_traversal.py`

**Checkpoint**: US2 works with live Neo4j when explicitly enabled and remains
covered offline through writer/report tests.

---

## Phase 5: User Story 3 - Generate Relationship Quality Artifacts (Priority: P3)

**Goal**: Operators can produce deterministic file-based relationship-quality
artifacts for a selected new graph scope.

**Independent Test**: Given a selected loaded graph scope, relationship-quality
artifact generation can be repeated and yields stable counts, status summaries,
bounded samples, coverage, fanout, temporal completeness, classifier metadata,
and deferred relation strategy without answer text fields or legacy comparison.

### Tests for User Story 3

- [X] T041 [US3] Add offline unit tests for relationship-quality artifact shape, required keys, and all eight relation-type counts in `tests/unit/test_relationship_quality_artifact.py`
- [X] T042 [US3] Add offline unit tests for deterministic bounded samples, no answer fields, and required resolution-status counts in `tests/unit/test_relationship_quality_artifact.py`
- [X] T043 [US3] Add artifact tests for `temporal_metadata_completeness` minimum shape, counts by temporal evidence status, counts by relation type, selected scope, and missing-field summary in `tests/unit/test_relationship_quality_artifact.py`
- [X] T044 [US3] Add offline unit tests for relationship-quality repository collection using a fake graph client in `tests/unit/test_relationship_quality_repository.py`
- [X] T045 [US3] Add offline smoke test for `foundation relationships quality --law-code ... --output ...` artifact writing through injected fake repository dependencies in `tests/smoke/test_cli_offline.py`
- [X] T046 [US3] Add marked live Neo4j integration test for relationship-quality artifact generation from loaded graph state in `tests/integration/test_neo4j_relationship_quality.py`

### Implementation for User Story 3

- [X] T047 [US3] Implement relationship-quality artifact assembly with stable IDs and deterministic ordering in `src/evaluation/load_cases.py`
- [X] T048 [US3] Implement repository collection for relation counts, resolution counts, sample edges, evidence samples, and unresolved targets in `src/graph/repositories.py`
- [X] T049 [US3] Include temporal evidence completeness by relation type and selected scope in relationship-quality collection in `src/graph/repositories.py`
- [X] T050 [US3] Implement source coverage, fanout summary, temporal metadata completeness, and deferred relation strategy assembly in `src/graph/repositories.py`
- [X] T051 [US3] Wire `foundation relationships quality --law-code ... --output ...` command handling in `src/app/commands.py`
- [X] T052 [US3] Document the relationship-quality artifact command and expected output fields in `specs/003-legal-graph-relationships/quickstart.md`

**Checkpoint**: US3 produces repeatable file artifacts from the new graph only,
with no legacy baseline dependency.

---

## Phase 6: User Story 4 - Preserve Framework-Guided Boundaries (Priority: P4)

**Goal**: The project can use Microsoft GraphRAG and Neo4j GraphRAG as
methodological references without making them trusted graph writers, mandatory
sidecars, inference runtimes, or acceptance dependencies.

**Independent Test**: Source and tests contain no chatbot UX, answer generation,
LLM proposition extraction, GraphRAG inference, mandatory GraphRAG sidecar, old
source migration, or legacy comparison dependency for relationship acceptance.

### Tests for User Story 4

- [X] T053 [US4] Add static offline unit tests that relationship source code imports no chatbot, LLM extraction, or GraphRAG sidecar runtime modules in `tests/unit/test_relationship_framework_boundary.py`
- [X] T054 [US4] Add static offline unit tests that relationship acceptance docs do not promote legacy comparison or framework output as source of truth in `tests/unit/test_relationship_framework_boundary.py`

### Implementation for User Story 4

- [X] T055 [US4] Update methodology-only framework guidance with adopted principles and excluded runtime behavior in `LEGAL_GRAPH_RELATIONSHIP_METHODS.md`
- [X] T056 [US4] Update project agent guidance for relationship feature boundaries in `AGENTS.md`
- [X] T057 [US4] Update quickstart boundary notes for no sidecar, no legacy migration, and no answer generation in `specs/003-legal-graph-relationships/quickstart.md`

**Checkpoint**: US4 protects the database-first boundary before any future
inference or GraphRAG runtime work.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Validate contracts, docs, and operational boundaries across all
completed stories.

- [X] T058 Review `specs/003-legal-graph-relationships/contracts/relationship-evidence.md` against implemented parser, builder, writer, and repository fields
- [X] T059 Review `specs/003-legal-graph-relationships/contracts/relationship-quality-artifact.md` against implemented artifact fields and deterministic ordering
- [X] T060 Update final validation commands and results for `python -m compileall src tests` in `specs/003-legal-graph-relationships/quickstart.md`
- [X] T061 Update final validation commands and results for `python -m pytest tests/unit` in `specs/003-legal-graph-relationships/quickstart.md`
- [X] T062 Update final validation commands and results for `python -m pytest tests/smoke` in `specs/003-legal-graph-relationships/quickstart.md`
- [X] T063 Update final validation commands and results for `RUN_LIVE_NEO4J_TESTS=true python -m pytest tests/integration -m neo4j` in `specs/003-legal-graph-relationships/quickstart.md`
- [X] T064 Verify default unit tests do not depend on live Neo4j, live Jina, paid APIs, remote notebooks, or private corpora and record the result in `specs/003-legal-graph-relationships/quickstart.md`
- [X] T065 Verify no relationship code adds chatbot UX, LLM proposition extraction, answer generation, GraphRAG inference, mandatory framework sidecars, old graph migration, or legacy comparison acceptance and record the result in `specs/003-legal-graph-relationships/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 Parse Context-Aware Legal References (Phase 3)**: Depends on Foundational.
- **US2 Materialize Typed Legal Edges (Phase 4)**: Depends on US1 evidence and resolution status output.
- **US3 Generate Relationship Quality Artifacts (Phase 5)**: Depends on US2 persisted references and typed edges.
- **US4 Preserve Framework-Guided Boundaries (Phase 6)**: Depends on the implemented relationship surface and can be completed before final polish.
- **Final Polish**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: First deliverable; independently testable offline through parser and builder tests.
- **US2 (P2)**: Requires US1 reference evidence and a loaded graph scope for live checks.
- **US3 (P3)**: Requires US2 relationship refresh and verification state.
- **US4 (P4)**: Requires enough implemented surface to validate framework and legacy boundaries.

### Within Each User Story

- Tests are written before implementation tasks in the same story.
- Unit tests must avoid live services.
- Integration tests must be marked and gated by environment flags.
- Shared types before parser, parser before builder, builder before writer, writer before repository, repository before command handlers.
- Documentation and contract review happen after command behavior exists.

---

## Parallel Opportunities

No tasks are marked parallel for this feature. The official execution order is
sequential because the feature intentionally changes tightly related parser,
builder, writer, repository, CLI, and contract files. If implementation is later
split manually, only independent test-file edits should be considered for
parallel work after the foundational phase is complete.

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Deliver US1 parser and structural builder evidence.
3. Validate all US1 behavior with offline tests before touching graph writes.

### Incremental Delivery

1. Add idempotent relationship refresh and typed edge materialization in US2.
2. Add relationship-quality artifact generation in US3.
3. Add framework and legacy-boundary checks in US4.
4. Finish with contract review, smoke tests, and live Neo4j integration evidence.

### Boundary Rules

- Do not migrate old graph data.
- Do not treat legacy comparison as a relationship acceptance dependency.
- Do not add chatbot UX, answer synthesis, LLM proposition extraction, trusted semantic candidates, or GraphRAG inference.
- Do not require live Jina or any GraphRAG sidecar for unit tests or relationship acceptance.
- Do not implement framework sidecar export, run-record, or proposal-review code in `003`; that belongs in a separate future research feature after the deterministic relationship foundation exists.
