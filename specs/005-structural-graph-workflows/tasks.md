# Tasks: Structural Graph Workflows With Coverage Boundaries

**Input**: Design documents from `/specs/005-structural-graph-workflows/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. Unit tests stay offline. Live Neo4j checks are marked integration and gated by `RUN_LIVE_NEO4J_TESTS=true`. No default unit or smoke test may require live Neo4j, live Jina, paid APIs, GraphRAG sidecars, remote notebooks, or private corpora.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare generated artifact handling and reusable fixture data without changing graph semantics.

- [X] T001 Add `data/structural_workflows/*.json` to `.gitignore`
- [X] T002 [P] Add structural workflow fixture cases with `seed_neighborhood`, `law_scope_overview`, resolved edges, missing-target references, source-sample limits, fanout, edge-limit, inactive section, and cycle cases in `tests/fixtures/structural_workflow_cases.json`
- [X] T003 [P] Add smoke CLI fixture expectations for seed and law-scope structural workflow artifact output in `tests/fixtures/structural_workflow_cli_cases.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared structural workflow contracts, artifact assembly, and repository collection primitives before story-specific behavior.

**CRITICAL**: No user story implementation starts until this phase is complete.

- [X] T004 [P] Add structural workflow dataclasses and artifact models in `src/graph/types.py`
- [X] T005 [P] Add structural workflow artifact builder and answer-field enforcement in `src/evaluation/load_cases.py`
- [X] T006 [P] Extend bounded traversal policy types for path metadata, direction, truncation, and cycle markers in `src/retrieval/legal_traversal.py`
- [X] T007 Add repository collection primitives for seed neighborhoods, law-code scope overviews, resolved traversal edges, and unresolved reference evidence in `src/graph/repositories.py`
- [X] T008 Add `data/structural_workflows/` artifact path handling to CLI JSON writer expectations in `src/app/commands.py`

**Checkpoint**: Shared workflow data contracts and read-only collection primitives exist before user-story work begins.

---

## Phase 3: User Story 1 - Inspect Resolved Section Neighborhoods (Priority: P1)

**Goal**: Operators can generate deterministic structural workflow artifacts for selected legal sections or bounded law-code scopes using only resolved typed legal edges.

**Independent Test**: Can be tested with fixture graph data containing active sections, law-code scope membership, resolved typed edges, and unresolved references; output must include deterministic sections, resolved edges, workflow mode, provenance, and no inferred missing edges.

### Tests for User Story 1

- [X] T009 [P] [US1] Add offline unit tests for structural workflow artifact shape, `workflow_mode`, and forbidden answer fields in `tests/unit/test_structural_neighborhood_artifact.py`
- [X] T010 [P] [US1] Add offline unit tests for resolved-edge-only traversal output in `tests/unit/test_legal_traversal.py`
- [X] T011 [P] [US1] Add repository unit tests for collecting seed sections, law-code scope sections, and resolved typed edges in `tests/unit/test_structural_workflow_repository.py`
- [X] T012 [P] [US1] Add smoke tests for `traversal neighborhood` seed and law-code-only artifact writing without live services, including two-run deterministic field comparison excluding `generated_at`, `artifact_id`, and `workflow_id`, in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement structural workflow artifact assembly for seed neighborhoods, law-scope overviews, sections, and resolved edges in `src/evaluation/load_cases.py`
- [X] T014 [US1] Implement repository methods for read-only seed-neighborhood and law-scope overview collection in `src/graph/repositories.py`
- [X] T015 [US1] Add `traversal neighborhood` parser arguments for `--workflow-mode seed_neighborhood|law_scope_overview` and handler wiring in `src/app/commands.py`
- [X] T016 [US1] Preserve section, edge, legal-reference, source-fragment, status, and temporal provenance fields in `src/graph/repositories.py`
- [X] T017 [US1] Add deterministic ordering for sections, resolved edges, and law-scope overview output in `src/evaluation/load_cases.py`

**Checkpoint**: US1 can produce resolved-edge-only seed-neighborhood and law-scope overview artifacts independently.

---

## Phase 4: User Story 2 - Expose Coverage Boundary Stops (Priority: P1)

**Goal**: Missing-target references appear as explicit coverage-boundary stops instead of inferred neighbors or hidden gaps.

**Independent Test**: Can be tested with fixture references where some targets resolve and others use `missing_target_in_corpus`; output must include reason, target law/section, source samples, counts, and no trusted inferred edge.

### Tests for User Story 2

- [X] T018 [P] [US2] Add offline unit tests for coverage-boundary stop normalization, grouping keys, source-sample limit, and deterministic sample ordering in `tests/unit/test_structural_neighborhood_artifact.py`
- [X] T019 [P] [US2] Add repository unit tests for unresolved reference boundary collection in `tests/unit/test_structural_workflow_repository.py`
- [X] T020 [P] [US2] Add CLI smoke coverage for `--missing-target-inventory` status values and metadata handling in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 2

- [X] T021 [US2] Implement coverage-boundary stop artifact items with `missing_target_in_corpus` reason, grouped counts, bounded source samples, deterministic sample ordering, and inventory match status in `src/evaluation/load_cases.py`
- [X] T022 [US2] Extend repository collection to return missing-target boundary stops without producing neighbor sections in `src/graph/repositories.py`
- [X] T023 [US2] Add optional missing-target inventory path parsing and `not_provided`, `available`, `missing_file`, `stale`, and `scope_mismatch` inventory status reporting in `src/app/commands.py`
- [X] T024 [US2] Ensure traversal output excludes unresolved references from resolved-edge traversal in `src/retrieval/legal_traversal.py`

**Checkpoint**: US2 can report missing-target coverage boundaries without blocking successful workflow output.

---

## Phase 5: User Story 3 - Control Traversal Scope And Fanout (Priority: P2)

**Goal**: Operators can bound traversal and overview collection by direction, depth, relation type, fanout, node limits, and edge limits, with visible truncation and cycle metadata.

**Independent Test**: Can be tested with fixture graphs containing multiple relation types, high fanout, and cycles; traversal must respect all limits and report affected paths.

### Tests for User Story 3

- [X] T025 [P] [US3] Add offline unit tests for default bounds, max bounds, direction, depth, relation-type, fanout, node-limit, edge-limit, invalid values, and deterministic ordering behavior in `tests/unit/test_legal_traversal.py`
- [X] T026 [P] [US3] Add artifact unit tests for truncation and cycle boundary metadata in `tests/unit/test_structural_neighborhood_artifact.py`
- [X] T027 [P] [US3] Add repository unit tests for bounded traversal query parameters in `tests/unit/test_structural_workflow_repository.py`

### Implementation for User Story 3

- [X] T028 [US3] Implement direction-aware bounded traversal and deterministic fanout truncation in `src/retrieval/legal_traversal.py`
- [X] T029 [US3] Add truncation, skipped-path, and cycle-boundary metadata to workflow artifact assembly in `src/evaluation/load_cases.py`
- [X] T030 [US3] Wire `--direction`, `--depth`, `--relation-type`, `--fanout`, `--node-limit`, `--edge-limit`, and `--source-sample-limit` defaults and validation into `src/app/commands.py`
- [X] T031 [US3] Enforce trusted relation-type allowlist from relationship-refresh typed edges and clear validation errors for unknown relation types in `src/retrieval/legal_traversal.py`

**Checkpoint**: US3 can run bounded structural workflows deterministically under high fanout and cyclic graph fixtures.

---

## Phase 6: User Story 4 - Produce Workflow-Quality Evidence (Priority: P3)

**Goal**: Workflow artifacts summarize coverage, traversal, provenance, boundary, and truncation quality without semantic or answer output.

**Independent Test**: Can be tested by generating workflow artifacts twice for unchanged fixture or live graph state and verifying stable quality summaries and no inference leakage.

### Tests for User Story 4

- [X] T032 [P] [US4] Add offline unit tests for workflow quality summary counts, required identity provenance, optional provenance gaps, provenance completeness, and repeated artifact comparison excluding `generated_at`, `artifact_id`, and `workflow_id` in `tests/unit/test_structural_neighborhood_artifact.py`
- [X] T033 [P] [US4] Add live Neo4j integration coverage for seed-neighborhood and law-scope structural workflow generation in `tests/integration/test_neo4j_structural_workflows.py`
- [X] T034 [P] [US4] Add smoke test assertions that workflow artifacts contain no answer text, generated legal conclusions, or semantic candidate fields in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 4

- [X] T035 [US4] Implement quality summary counts for workflow mode, visited sections, resolved edges by relation type, boundary stops by reason, edge-limit truncations, cycles, inactive sections, required identity provenance, optional provenance gaps, and provenance completeness in `src/evaluation/load_cases.py`
- [X] T036 [US4] Add structural workflow repository live-read integration for selected law-code scopes in `src/graph/repositories.py`
- [X] T037 [US4] Add CLI response payload summary fields for workflow mode, artifact path, status, counts, and warnings in `src/app/commands.py`
- [X] T038 [US4] Update quickstart validation examples with final command names and expected summary fields in `specs/005-structural-graph-workflows/quickstart.md`

**Checkpoint**: US4 gives maintainers stable workflow-quality evidence for future retrieval planning.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation, validation, and consistency checks across all completed stories.

- [X] T039 Verify `specs/005-structural-graph-workflows/contracts/structural-neighborhood-artifact.md` and `specs/005-structural-graph-workflows/contracts/structural-workflow-cli.md` match implemented artifact and CLI shapes
- [X] T040 [P] Verify default unit and smoke tests do not require live Neo4j, embeddings, paid APIs, GraphRAG sidecars, remote notebooks, or private corpora
- [X] T041 [P] Run final offline validation commands from `specs/005-structural-graph-workflows/quickstart.md`
- [X] T042 Run gated live Neo4j structural workflow smoke and record results in `specs/005-structural-graph-workflows/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (P1)**: Depends on Foundational.
- **User Story 2 (P1)**: Depends on Foundational and integrates with US1 artifact structures, but remains independently testable through boundary fixtures.
- **User Story 3 (P2)**: Depends on Foundational and should follow US1 because it extends traversal behavior used by neighborhood output.
- **User Story 4 (P3)**: Depends on User Stories 1, 2, and 3 because it summarizes resolved edges, boundaries, and traversal-limit metadata.
- **Final Phase**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1**: Foundation slice and recommended MVP; includes both
  `seed_neighborhood` and `law_scope_overview`.
- **User Story 2**: Can be built after Foundational; best integrated immediately after US1 so boundary stops appear in the same artifact surface.
- **User Story 3**: Can be built after Foundational; it extends traversal limits and should not change boundary-stop semantics.
- **User Story 4**: Requires completed artifact sections from US1-US3 for complete quality evidence.

### Parallel Opportunities

- Setup tasks T002 and T003 can run in parallel.
- Foundational tasks T004, T005, and T006 can run in parallel.
- US1 tests T009, T010, T011, and T012 can run in parallel.
- US2 tests T018, T019, and T020 can run in parallel.
- US3 tests T025, T026, and T027 can run in parallel.
- US4 tests T032, T033, and T034 can run in parallel.
- Final checks T040 and T041 can run in parallel after implementation is complete.

---

## Parallel Example: User Story 1

```bash
Task: "Add offline unit tests for structural workflow artifact shape, workflow_mode, and forbidden answer fields in tests/unit/test_structural_neighborhood_artifact.py"
Task: "Add offline unit tests for resolved-edge-only traversal output in tests/unit/test_legal_traversal.py"
Task: "Add repository unit tests for collecting seed sections, law-code scope sections, and resolved typed edges in tests/unit/test_structural_workflow_repository.py"
Task: "Add smoke tests for traversal neighborhood seed and law-code-only artifact writing without live services, including two-run deterministic field comparison excluding generated_at, artifact_id, and workflow_id, in tests/smoke/test_cli_offline.py"
```

## Parallel Example: User Story 2

```bash
Task: "Add offline unit tests for coverage-boundary stop normalization, grouping keys, source-sample limit, and deterministic sample ordering in tests/unit/test_structural_neighborhood_artifact.py"
Task: "Add repository unit tests for unresolved reference boundary collection in tests/unit/test_structural_workflow_repository.py"
Task: "Add CLI smoke coverage for --missing-target-inventory metadata handling in tests/smoke/test_cli_offline.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add offline unit tests for default bounds, max bounds, direction, depth, relation-type, fanout, node-limit, edge-limit, invalid values, and deterministic ordering behavior in tests/unit/test_legal_traversal.py"
Task: "Add artifact unit tests for truncation and cycle boundary metadata in tests/unit/test_structural_neighborhood_artifact.py"
Task: "Add repository unit tests for bounded traversal query parameters in tests/unit/test_structural_workflow_repository.py"
```

## Parallel Example: User Story 4

```bash
Task: "Add offline unit tests for workflow quality summary counts, required identity provenance, optional provenance gaps, provenance completeness, and repeated artifact comparison excluding generated_at, artifact_id, and workflow_id in tests/unit/test_structural_neighborhood_artifact.py"
Task: "Add live Neo4j integration coverage for seed-neighborhood and law-scope structural workflow generation in tests/integration/test_neo4j_structural_workflows.py"
Task: "Add smoke test assertions that workflow artifacts contain no answer text, generated legal conclusions, or semantic candidate fields in tests/smoke/test_cli_offline.py"
```

---

## Implementation Strategy

### MVP First: User Story 1

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational contracts and collection primitives.
3. Implement US1 to produce deterministic resolved-edge-only
   `seed_neighborhood` and `law_scope_overview` artifacts.
4. Stop and validate US1 independently with unit and smoke tests.

### Incremental Delivery

1. Add US2 so missing targets become explicit coverage-boundary stops.
2. Add US3 to harden traversal bounds, direction, fanout, truncation, and cycle handling.
3. Add US4 to produce full workflow-quality evidence and live Neo4j smoke coverage.
4. Run final quickstart validations and update documentation with observed results.

### Parallel Team Strategy

After Foundational phase:

- Developer A: US1 resolved seed-neighborhood and law-scope overview artifacts.
- Developer B: US2 coverage boundary stop normalization.
- Developer C: US3 traversal policy limits.
- Developer D: US4 quality summary and live smoke after artifacts stabilize.
