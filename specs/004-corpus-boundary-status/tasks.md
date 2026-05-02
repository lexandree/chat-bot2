# Tasks: Corpus Boundary And Source Status Hardening

**Input**: Design documents from `/specs/004-corpus-boundary-status/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. Unit tests stay offline. Live Neo4j checks are marked integration and gated by `RUN_LIVE_NEO4J_TESTS=true`. No test in the default unit suite may require live Neo4j, live Jina, paid APIs, GraphRAG sidecars, remote notebooks, or private corpora.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare fixtures and artifact ignores for source-status and corpus-readiness work without changing runtime behavior.

- [X] T001 [P] Add `data/corpus_readiness/*.json` to `.gitignore` and create a dedicated source-status XML fixture in `tests/fixtures/legal_xml/corpus_boundary_status.xml` with title/status-field markers, documented leading body markers, and false-positive explanatory body marker text
- [X] T002 [P] Add corpus-boundary sample cases covering active, inactive, missing-target, and out-of-scope references in `tests/fixtures/legal_relationship_cases.json` and `tests/fixtures/legal_validation_cases.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared data, artifact, and repository contracts before any user story work starts.

**CRITICAL**: No user story implementation starts until this phase is complete.

- [X] T003 [P] Extend shared graph dataclasses with source-unit status, target-unit status, explicit unresolved reasons, and corpus-readiness artifact fields in `src/graph/types.py`
- [X] T004 [P] Add source-status and corpus-readiness serialization helpers plus answer-field enforcement to `src/evaluation/load_cases.py`
- [X] T005 Update structural graph assembly to preserve source document build/version metadata and inactive-source markers in `src/ingestion/legal_structure_builder.py`
- [X] T006 Update legal reference parsing and candidate resolution to preserve inactive target-status evidence and explicit unresolved reason inputs in `src/ingestion/legal_reference_parser.py` and `src/ingestion/legal_structure_builder.py`
- [X] T007 Update graph persistence and repository collection so source-status, target-status, and unresolved-reason metadata survive load, refresh, verify, and quality workflows in `src/graph/writer.py` and `src/graph/repositories.py`

**Identity rule**: Do not create a `SourceStructuralUnit` graph node or new
canonical id. Source-unit status attaches to the existing `LegalSection`
identified by `legal_section_id`; `LegalReference.source_legal_section_id`
points to that same id, while `LegalFragment` and `SourceFragment` remain linked
provenance/text anchors.

**Checkpoint**: Shared status, reason, and artifact contracts exist before story-specific work begins.

---

## Phase 3: User Story 1 - Preserve Source Unit Status (Priority: P1)

**Goal**: Operators can detect inactive legal sections and keep source-status evidence visible in load and verification workflows.

**Independent Test**: Can be fully tested offline with XML fixtures containing active sections, `(weggefallen)` headings, documented structural `aufgehoben` or `außer Kraft` markers, and false-positive explanatory body text. The parsed preview and graph records preserve unit status and source evidence.

### Tests for User Story 1

- [X] T008 [P] [US1] Add offline unit tests for inactive-marker detection, structural marker policy, false-positive explanatory body markers, and source-status propagation in `tests/unit/test_legal_structure_builder.py`
- [X] T009 [P] [US1] Add offline unit tests for source-status persistence on graph writes in `tests/unit/test_graph_writer.py`
- [X] T010 [P] [US1] Add live Neo4j integration coverage for active/inactive source-unit persistence in `tests/integration/test_neo4j_source_status.py`
- [X] T011 [US1] Add offline unit tests for source document version/build metadata propagation from structural graph assembly through graph-write records in `tests/unit/test_legal_structure_builder.py` and `tests/unit/test_graph_writer.py`

### Implementation for User Story 1

- [X] T012 [US1] Implement inactive source-unit detection and status mapping with title/status-field marker support plus documented leading-body marker policy in `src/ingestion/legal_structure_builder.py`
- [X] T013 [US1] Persist source-status metadata and expose active/inactive counts in `src/graph/writer.py` and `src/graph/repositories.py`
- [X] T014 [US1] Update load and verification reports to surface source-unit status counts in `src/ingestion/verification.py` and `src/graph/types.py`

**Checkpoint**: Source-status detection and persistence are independently testable.

---

## Phase 4: User Story 2 - Classify Relationship Resolution Reasons (Priority: P1)

**Goal**: Operators can see why references are non-resolved and when resolved targets are inactive, including inactive target-status evidence, missing in-corpus targets, out-of-scope laws, parsing gaps, and ambiguous matches.

**Independent Test**: Can be fully tested offline by running parser and builder fixtures that cover resolved inactive targets, missing targets in the corpus slice, out-of-scope laws, ambiguous matches, and parse-incomplete cases.

### Tests for User Story 2

- [X] T015 [P] [US2] Add offline unit tests for explicit unresolved-reason classification and conditional target-field requirements in `tests/unit/test_legal_reference_parser.py`
- [X] T016 [P] [US2] Add offline unit tests for resolved inactive-target status versus missing-target reason evidence in `tests/unit/test_legal_structure_builder.py`
- [X] T017 [P] [US2] Extend live Neo4j relationship-quality coverage for unresolved-reason counts in `tests/integration/test_neo4j_relationship_quality.py`

### Implementation for User Story 2

- [X] T018 [US2] Update the parser and candidate assembly flow to preserve explicit unresolved reasons, raw/normalized text, unresolved-target evidence, conditional target fields, and resolved inactive-target status evidence in `src/ingestion/legal_reference_parser.py` and `src/ingestion/legal_structure_builder.py`
- [X] T019 [US2] Update repository verification and quality collectors to count unresolved reasons and target-status buckets in `src/graph/repositories.py`
- [X] T020 [US2] Extend `LegalReference` data handling to carry reason-specific evidence through graph writes in `src/graph/types.py` and `src/graph/writer.py`

**Checkpoint**: Relationship evidence now explains non-resolved cases and keeps inactive existing targets as resolved target-status evidence.

---

## Phase 5: User Story 3 - Preserve Idempotency During Relationship Refresh (Priority: P2)

**Goal**: Repeating relationship refresh on unchanged inputs preserves the same graph state, evidence, and stale-edge cleanup semantics.

**Independent Test**: Can be fully tested by running the same refresh twice and confirming identical reference counts, edge counts, status counts, and no duplicate trusted records.

### Tests for User Story 3

- [X] T021 [P] [US3] Add offline unit tests for repeated refresh idempotency and stale-edge cleanup in `tests/unit/test_graph_writer.py`
- [X] T022 [P] [US3] Add offline unit tests for stable refresh reports after status/reason changes in `tests/unit/test_load_verify_delete_reports.py`
- [X] T023 [P] [US3] Add live Neo4j integration coverage for repeated refresh behavior in `tests/integration/test_neo4j_relationship_refresh.py`

### Implementation for User Story 3

- [X] T024 [US3] Keep relationship refresh idempotent after source-status, target-status, and unresolved-reason changes in `src/graph/repositories.py`
- [X] T025 [US3] Preserve stale-edge cleanup and upsert semantics across repeated refresh passes in `src/graph/writer.py`
- [X] T026 [US3] Update refresh and verification report models so stable status and reason counts are visible in `src/graph/types.py` and `src/graph/repositories.py`

**Checkpoint**: Refresh remains repeatable and does not duplicate trusted graph state.

---

## Phase 6: User Story 4 - Produce Corpus Readiness Evidence Without Semantic Extraction (Priority: P3)

**Goal**: Operators can generate a deterministic corpus-readiness artifact that separates active and inactive structural units and classifies structural complexity without creating semantic nodes.

**Independent Test**: Can be fully tested offline by assembling a corpus-readiness artifact from fixture structural units that deterministically trigger `inactive_skipped`, `definition_heavy`, `list_heavy`, `mixed_content`, `simple_paragraph`, and `unknown` under the documented thresholds.

### Tests for User Story 4

- [X] T027 [P] [US4] Add offline unit tests for corpus-readiness artifact shape, top-level `structure_class_rules_version`, deterministic structure-class thresholds, priority order, and all required buckets in `tests/unit/test_corpus_readiness_artifact.py`
- [X] T028 [P] [US4] Add offline unit tests for repository collection of active/inactive counts in `tests/unit/test_corpus_readiness_repository.py`
- [X] T029 [P] [US4] Add smoke coverage for `corpus readiness` CLI artifact writing in `tests/smoke/test_cli_offline.py`
- [X] T030 [P] [US4] Add live Neo4j integration coverage for corpus-readiness artifact generation in `tests/integration/test_neo4j_corpus_readiness.py`

### Implementation for User Story 4

- [X] T031 [US4] Implement corpus-readiness artifact assembly with top-level `structure_class_rules_version` and stable ordering in `src/evaluation/load_cases.py`
- [X] T032 [US4] Implement repository collectors for active/inactive unit counts and deterministic structural complexity signals in `src/graph/repositories.py`
- [X] T033 [US4] Add `corpus readiness` CLI dispatch and output handling in `src/app/commands.py`

**Checkpoint**: Corpus-readiness output is available as a deterministic structural artifact.

---

## Phase 7: User Story 5 - Report Hardened Relationship Quality (Priority: P3)

**Goal**: Relationship-quality artifacts preserve the existing baseline fields while exposing source status, target status, unresolved reasons, and top missing targets instead of a generic unresolved bucket.

**Independent Test**: Can be fully tested by generating the relationship-quality artifact twice for unchanged graph state and confirming stable counts and summaries.

### Tests for User Story 5

- [X] T034 [P] [US5] Add offline unit tests for hardened relationship-quality counts, preserved baseline fields, and `top_missing_targets` item shape/exclusion rules in `tests/unit/test_relationship_quality_artifact.py`
- [X] T035 [P] [US5] Add offline unit tests for repository source/target status summaries in `tests/unit/test_relationship_quality_repository.py`
- [X] T036 [P] [US5] Add live Neo4j integration coverage for hardened quality artifacts in `tests/integration/test_neo4j_relationship_quality.py`

### Implementation for User Story 5

- [X] T037 [US5] Extend relationship-quality artifact assembly with source status, target status, unresolved-reason summaries, and preserved baseline fields in `src/evaluation/load_cases.py`
- [X] T038 [US5] Extend repository collectors for `top_missing_targets` with `reason = missing_target_in_corpus`, bounded source samples, ambiguous/parse-incomplete exclusions, noisy source sections, and target-status breakdowns in `src/graph/repositories.py`
- [X] T039 [US5] Update `relationships quality` CLI output and quickstart examples in `src/app/commands.py` and `specs/004-corpus-boundary-status/quickstart.md`

**Checkpoint**: Relationship-quality artifacts now drive corpus work from actionable buckets without breaking existing baseline artifact consumers.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation and validation cleanup across all completed stories.

- [X] T040 Update `specs/004-corpus-boundary-status/quickstart.md` with final validation commands and structural-output examples
- [X] T041 Verify `specs/004-corpus-boundary-status/contracts/source-status.md`, `specs/004-corpus-boundary-status/contracts/relationship-quality-artifact.md`, and `specs/004-corpus-boundary-status/contracts/corpus-readiness-artifact.md` match the implemented data shapes
- [X] T042 Run the final offline unit, smoke, and live integration validations and record the results in `specs/004-corpus-boundary-status/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (P1)**: Depends on Foundational.
- **User Story 2 (P1)**: Depends on Foundational.
- **User Story 3 (P2)**: Depends on User Stories 1 and 2 because the refresh path must preserve the new status and reason metadata.
- **User Story 4 (P3)**: Depends on User Story 1 and the foundational artifact contracts.
- **User Story 5 (P3)**: Depends on User Stories 1 and 2 because the quality artifact reports source status, target status, and unresolved reasons.
- **Final Phase**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1**: Can start after Foundational; no dependency on other stories.
- **User Story 2**: Can start after Foundational; no dependency on other stories.
- **User Story 3**: Should run after User Stories 1 and 2 so repeated refreshes preserve the new metadata cleanly.
- **User Story 4**: Can run after User Story 1; it only needs source-status evidence and structural collection.
- **User Story 5**: Should run after User Stories 1 and 2 so artifact summaries can include the new status and reason buckets.

### Within Each User Story

- Required tests MUST be written before implementation or at least added in the same change set
- Unit tests MUST avoid live services; integration and smoke tests MUST be marked and runnable separately
- Data contracts and models before services
- Services before workflows, commands, or endpoints
- Core implementation before integration wiring
- Story complete before moving to the next priority unless parallel staffing is available

### Parallel Opportunities

- Setup tasks T001 and T002 can run in parallel
- Foundational tasks T003 and T004 can run in parallel
- User Story 1 tests T008, T009, and T010 can run in parallel; T011 follows them because it extends the same builder and writer test files
- User Story 2 tests T015, T016, and T017 can run in parallel
- User Story 3 tests T021, T022, and T023 can run in parallel
- User Story 4 tests T027, T028, T029, and T030 can run in parallel
- User Story 5 tests T034, T035, and T036 can run in parallel

---

## Parallel Example: User Story 1

```bash
Task: "Add offline unit tests for inactive-marker detection, structural marker policy, false-positive explanatory body markers, and source-status propagation in tests/unit/test_legal_structure_builder.py"
Task: "Add offline unit tests for source-status persistence on graph writes in tests/unit/test_graph_writer.py"
Task: "Add live Neo4j integration coverage for active/inactive source-unit persistence in tests/integration/test_neo4j_source_status.py"
```

Then run T011 separately because it extends the same builder and writer test
files used by T008 and T009.

## Parallel Example: User Story 2

```bash
Task: "Add offline unit tests for explicit unresolved-reason classification and conditional target-field requirements in tests/unit/test_legal_reference_parser.py"
Task: "Add offline unit tests for resolved inactive-target status versus missing-target reason evidence in tests/unit/test_legal_structure_builder.py"
Task: "Extend live Neo4j relationship-quality coverage for unresolved-reason counts in tests/integration/test_neo4j_relationship_quality.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add offline unit tests for repeated refresh idempotency and stale-edge cleanup in tests/unit/test_graph_writer.py"
Task: "Add offline unit tests for stable refresh reports after status/reason changes in tests/unit/test_load_verify_delete_reports.py"
Task: "Add live Neo4j integration coverage for repeated refresh behavior in tests/integration/test_neo4j_relationship_refresh.py"
```

## Parallel Example: User Story 4

```bash
Task: "Add offline unit tests for corpus-readiness artifact shape and structural complexity buckets in tests/unit/test_corpus_readiness_artifact.py"
Task: "Add offline unit tests for repository collection of active/inactive counts in tests/unit/test_corpus_readiness_repository.py"
Task: "Add smoke coverage for corpus readiness CLI artifact writing in tests/smoke/test_cli_offline.py"
Task: "Add live Neo4j integration coverage for corpus-readiness artifact generation in tests/integration/test_neo4j_corpus_readiness.py"
```

## Parallel Example: User Story 5

```bash
Task: "Add offline unit tests for hardened relationship-quality counts, preserved baseline fields, and top_missing_targets item shape/exclusion rules in tests/unit/test_relationship_quality_artifact.py"
Task: "Add offline unit tests for repository source/target status summaries in tests/unit/test_relationship_quality_repository.py"
Task: "Add live Neo4j integration coverage for hardened quality artifacts in tests/integration/test_neo4j_relationship_quality.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Validate source-status detection and persistence independently
5. Stop and confirm the structural status boundary before expanding scope

### Incremental Delivery

1. Setup + Foundational → shared status/reason/artifact contracts exist
2. Add User Story 1 → source-status detection and persistence are testable
3. Add User Story 2 → unresolved reasons become explicit and reviewable
4. Add User Story 3 → repeated refresh stays idempotent
5. Add User Story 4 → structural corpus-readiness artifacts become available
6. Add User Story 5 → quality artifacts expose actionable buckets

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 4
   - Developer D: User Story 5
3. User Story 3 follows after the status and reason model is stable
4. Final phase consolidates docs and validation evidence
