---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tasks must respect the constitution's test boundaries. Unit tests do
not use live Neo4j, live Jina, paid APIs, or remote notebooks. Integration and
smoke tests are included when the specification or plan requires live services,
filesystem behavior, operator-managed runtimes, or managed contours.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Legal GraphRAG foundation**: `src/app/`, `src/graph/`, `src/ingestion/`,
  `src/retrieval/`, `src/enrichment/`, `src/bulk/`, `src/review/`,
  `src/evaluation/`, and `tests/` at repository root
- Paths shown below assume the legal GraphRAG foundation layout - adjust only
  when the plan documents a constitution-compliant exception

<!-- 
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.
  
  The /speckit.tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Contracts from contracts/
  
  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as a validated increment
  
  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize [language] project with [framework] dependencies
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on your project):

- [ ] T004 Define or update Neo4j schema, constraints, and vector indexes with stable names
- [ ] T005 [P] Define source, legal, provenance, temporal, and checksum data contracts
- [ ] T006 [P] Define embedding profile metadata and query/document prefix contract
- [ ] T007 Define review boundary for LLM-derived candidates, flags, isolation, and approval state
- [ ] T008 Define verification evidence for load, delete, reindex, traversal, and retrieval behavior
- [ ] T009 Configure explicit unit, integration, and smoke test markers
- [ ] T010 [P] Configure environment settings without secrets or hidden live-service dependencies
- [ ] T011 [P] Define bulk runtime guards, checkpoint state, and artifact bundle contract if applicable

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 Foundation Slice

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 ⚠️

> **NOTE**: Write required tests before implementation. Keep unit tests
> deterministic; mark live-service checks as integration or smoke tests.
> Include only the test types required by the specification and plan.

- [ ] T012 [P] [US1] Unit test for [pure policy/parser/state behavior] in tests/unit/test_[name].py
- [ ] T013 [P] [US1] Integration test for [Neo4j/Jina/filesystem behavior] in tests/integration/test_[name].py
- [ ] T014 [P] [US1] Smoke test for [operator/runtime contour] in tests/smoke/test_[name].py

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create [Entity1] model or contract in src/[layer]/[entity1].py
- [ ] T016 [P] [US1] Create [Entity2] model or contract in src/[layer]/[entity2].py
- [ ] T017 [US1] Implement [Service] in src/[layer]/[service].py (depends on T015, T016)
- [ ] T018 [US1] Preserve provenance, temporal metadata, embedding profile, or review state touched by this story
- [ ] T019 [US1] Implement [endpoint/feature/workflow] in src/[location]/[file].py
- [ ] T020 [US1] Add validation, error handling, and visible failure reporting
- [ ] T021 [US1] Add operation metadata or audit logging required by the plan

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 ⚠️

> **NOTE**: Include only the test types required by the specification and plan.

- [ ] T022 [P] [US2] Unit test for [pure policy/parser/state behavior] in tests/unit/test_[name].py
- [ ] T023 [P] [US2] Integration test for [Neo4j/Jina/filesystem behavior] in tests/integration/test_[name].py
- [ ] T024 [P] [US2] Smoke test for [operator/runtime contour] in tests/smoke/test_[name].py

### Implementation for User Story 2

- [ ] T025 [P] [US2] Create [Entity] model or contract in src/[layer]/[entity].py
- [ ] T026 [US2] Implement [Service] in src/[layer]/[service].py
- [ ] T027 [US2] Preserve provenance, temporal metadata, embedding profile, or review state touched by this story
- [ ] T028 [US2] Implement [endpoint/feature/workflow] in src/[location]/[file].py
- [ ] T029 [US2] Integrate with User Story 1 components (if needed)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 ⚠️

> **NOTE**: Include only the test types required by the specification and plan.

- [ ] T030 [P] [US3] Unit test for [pure policy/parser/state behavior] in tests/unit/test_[name].py
- [ ] T031 [P] [US3] Integration test for [Neo4j/Jina/filesystem behavior] in tests/integration/test_[name].py
- [ ] T032 [P] [US3] Smoke test for [operator/runtime contour] in tests/smoke/test_[name].py

### Implementation for User Story 3

- [ ] T033 [P] [US3] Create [Entity] model or contract in src/[layer]/[entity].py
- [ ] T034 [US3] Implement [Service] in src/[layer]/[service].py
- [ ] T035 [US3] Preserve provenance, temporal metadata, embedding profile, or review state touched by this story
- [ ] T036 [US3] Implement [endpoint/feature/workflow] in src/[location]/[file].py

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit, integration, or smoke tests required by the plan
- [ ] TXXX [P] Verify no hidden live-service dependency exists in default unit tests
- [ ] TXXX [P] Verify generated candidates remain untrusted unless explicitly approved
- [ ] TXXX [P] Verify bulk/runtime artifacts, logs, manifests, and checkpoints are exported coherently
- [ ] TXXX Security and privacy hardening
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Required tests MUST be written and FAIL before implementation
- Unit tests MUST avoid live services; integration and smoke tests MUST be
  marked and runnable separately
- Data contracts and models before services
- Services before workflows, commands, or endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch applicable tests for User Story 1 together:
Task: "Unit test for [pure policy/parser/state behavior] in tests/unit/test_[name].py"
Task: "Integration test for [Neo4j/Jina/filesystem behavior] in tests/integration/test_[name].py"
Task: "Smoke test for [operator/runtime contour] in tests/smoke/test_[name].py"

# Launch independent contracts/models for User Story 1 together:
Task: "Create [Entity1] model or contract in src/[layer]/[entity1].py"
Task: "Create [Entity2] model or contract in src/[layer]/[entity2].py"
```

---

## Implementation Strategy

### Foundation Slice First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Validate evidence and documentation before expanding scope

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → validate evidence
3. Add User Story 2 → Test independently → validate evidence
4. Add User Story 3 → Test independently → validate evidence
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify required tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
