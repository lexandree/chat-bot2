# Tasks: Legal Question Canonicalization And Cluster Coverage

**Input**: Design documents from `/specs/007-legal-question-canonicalization/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit and offline smoke coverage are required by the specification.
Default tests must not require live Neo4j, live Jina, paid APIs, network
services, or remote notebooks. Live embedding or LLM checks are explicit
operator-managed smoke contours only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the 007 implementation surface without adding runtime behavior outside the evaluation layer.

- [X] T001 Create 007 evaluation module skeleton and public API constants in `src/evaluation/tg_question_canonicalization.py`
- [X] T002 [P] Create canonicalization fixture directory and README in `tests/fixtures/tg_question_canonicalization/README.md`
- [X] T003 Add 007 CLI command placeholders to the evaluation parser in `src/app/commands.py`
- [X] T004 [P] Verify generated 007 artifact ignore patterns in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schemas, helpers, and boundaries required before any user story can be implemented.

**CRITICAL**: No user story work should begin until this phase is complete.

- [X] T005 Define 007 contract versions, prompt/policy versions, allowed statuses, exclusion reasons, confidence values, coverage statuses, review decisions, and promotion statuses in `src/evaluation/tg_question_canonicalization.py`
- [X] T006 Implement shared JSONL/JSON readers and writers with deterministic ordering and parent directory creation in `src/evaluation/tg_question_canonicalization.py`
- [X] T007 Implement shared redaction/privacy guard helpers that reject raw Telegram inputs, secrets, endpoint URLs, and `.env`-like values in `src/evaluation/tg_question_canonicalization.py`
- [X] T008 Implement shared id generation and slug normalization helpers for canonicalization evidence, issue clusters, coverage records, question-bank entries, and case candidates in `src/evaluation/tg_question_canonicalization.py`
- [X] T009 Implement embedding profile metadata adapter for canonical embedding records using existing retrieval profile fields in `src/evaluation/tg_question_canonicalization.py`
- [X] T010 [P] Add unit tests for constants, enum validation, slug normalization, privacy guards, and id stability in `tests/unit/test_tg_question_canonicalization.py`
- [X] T011 Add offline CLI smoke coverage for 007 command availability and no-live-service defaults in `tests/smoke/test_cli_offline.py`
- [X] T012 Implement `verify_tg_question_canonicalization_boundaries()` to assert no graph mutation, chatbot answer generation, raw Telegram paths, or hidden live-service dependency in `src/evaluation/tg_question_canonicalization.py`
- [X] T013 Wire the 007 boundary check into the CLI command `tg-qa-canonical-boundary-check` in `src/app/commands.py`

**Checkpoint**: Foundation ready - user story implementation can start.

---

## Phase 3: User Story 1 - Canonicalize Telegram Questions (Priority: P1)

**Goal**: Convert redacted 006 Telegram question candidates into schema-valid canonicalization evidence with provenance, exclusions, confidence, and review-only LLM boundaries.

**Independent Test**: A small redacted fixture with repeated legal situations, dialogue fragments, and non-legal keyword noise produces canonicalization batch/evidence artifacts without trusted answers.

### Tests for User Story 1

- [X] T014 [US1] Add unit tests for canonicalization batch emission from redacted 006 candidates in `tests/unit/test_tg_question_canonicalization.py`
- [X] T015 [US1] Add unit tests for canonicalization result import validation, idempotency, exclusions, malformed results, and source-language preservation in `tests/unit/test_tg_question_canonicalization.py`
- [X] T016 [US1] Add offline CLI smoke test for `tg-qa-canonicalization-batch` and `tg-qa-canonicalization-import` in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 1

- [X] T017 [US1] Implement `emit_tg_qa_canonicalization_batch()` with bounded scope controls and redacted 006 candidate provenance in `src/evaluation/tg_question_canonicalization.py`
- [X] T018 [US1] Implement canonicalization expected-output schema and batch summary counts in `src/evaluation/tg_question_canonicalization.py`
- [X] T019 [US1] Implement `import_tg_qa_canonicalization_results()` with `(canonicalization_run_id, task_scope, task_id)` idempotency in `src/evaluation/tg_question_canonicalization.py`
- [X] T020 [US1] Implement canonicalization evidence validation for required fields, source-language canonical question, stable issue-frame slug, confidence, exclusion reason, and failure status in `src/evaluation/tg_question_canonicalization.py`
- [X] T021 [US1] Implement canonicalization run manifest generation with processed, completed, failed, skipped, excluded, uncertain, and limitation counts in `src/evaluation/tg_question_canonicalization.py`
- [X] T022 [US1] Wire `tg-qa-canonicalization-batch` and `tg-qa-canonicalization-import` CLI commands in `src/app/commands.py`

**Checkpoint**: User Story 1 is functional and testable independently.

---

## Phase 4: User Story 2 - Cluster Canonical Legal Issues (Priority: P2)

**Goal**: Create legal issue clusters from canonicalized evidence, keeping representative raw questions and quality flags while avoiding raw-similarity-only approval.

**Independent Test**: A fixture with five surface forms of one residence-document issue groups into one cluster, while similar wording with different legal obligations remains separate or flagged.

### Tests for User Story 2

- [X] T023 [US2] Add unit tests for canonical embedding batch emission and query-prefix semantics in `tests/unit/test_tg_question_canonicalization.py`
- [X] T024 [US2] Add unit tests for canonical embedding import profile metadata, vector validation, and failed item reporting in `tests/unit/test_tg_question_canonicalization.py`
- [X] T025 [US2] Add unit tests for issue clustering, representative examples, bounded merges, low-confidence routing, and quality flags in `tests/unit/test_tg_question_canonicalization.py`
- [X] T026 [US2] Add offline CLI smoke test for canonical embedding batch/import and `tg-qa-issue-clusters` summary/manifest outputs in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 2

- [X] T027 [US2] Implement `emit_tg_qa_canonical_embedding_batch()` for `canonical_question` and `legal_issue_frame` query-style embedding inputs in `src/evaluation/tg_question_canonicalization.py`
- [X] T028 [US2] Implement `import_tg_qa_canonical_embedding_records()` with existing embedding profile metadata and failure handling in `src/evaluation/tg_question_canonicalization.py`
- [X] T029 [US2] Implement deterministic legal issue merge policy over issue-frame slug, canonical question similarity evidence, law area, authority context, confidence, and exclusion state in `src/evaluation/tg_question_canonicalization.py`
- [X] T030 [US2] Implement `cluster_tg_qa_legal_issues()` with representative raw question examples, cluster ids, cluster confidence, quality flags, review route, issue-cluster summary counts, and manifest metadata in `src/evaluation/tg_question_canonicalization.py`
- [X] T031 [US2] Ensure clustering never approves a cluster solely from raw question similarity, broad keyword overlap, or LLM confidence in `src/evaluation/tg_question_canonicalization.py`
- [X] T032 [US2] Wire `tg-qa-canonical-embedding-batch`, `tg-qa-canonical-embeddings-import`, and `tg-qa-issue-clusters` CLI commands with required summary/manifest output arguments in `src/app/commands.py`

**Checkpoint**: User Story 2 is functional and testable independently after US1 evidence or equivalent fixture evidence exists.

---

## Phase 5: User Story 3 - Measure Corpus Coverage By Canonical Frame (Priority: P3)

**Goal**: Compare canonical issue clusters against the reviewed 006 final dataset and report covered, partial, uncovered, excluded, and uncertain clusters with limitations.

**Independent Test**: A fixture with reviewed seed cases, uncovered canonical issues, partial overlaps, and non-legal exclusions produces a coverage report that does not reuse raw-embedding coverage as a legal question-space estimate.

### Tests for User Story 3

- [X] T033 [US3] Add unit tests for canonical coverage status decisions and coverage-gap flags in `tests/unit/test_tg_question_canonicalization.py`
- [X] T034 [US3] Add unit tests that excluded and uncertain clusters are not counted as uncovered legal questions in `tests/unit/test_tg_question_canonicalization.py`
- [X] T035 [US3] Add offline CLI smoke test for `tg-qa-canonical-coverage` summary generation in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 3

- [X] T036 [US3] Implement reviewed 006 final-case loader with answer trust-boundary preservation in `src/evaluation/tg_question_canonicalization.py`
- [X] T037 [US3] Implement canonical issue matching against reviewed 006 cases and optional question-bank entries in `src/evaluation/tg_question_canonicalization.py`
- [X] T038 [US3] Implement `build_tg_qa_canonical_coverage_report()` with covered, partial, uncovered, excluded, uncertain, and limitation records in `src/evaluation/tg_question_canonicalization.py`
- [X] T039 [US3] Implement canonical coverage summary counts by status, law area, authority context, cluster quality flag, excluded count, uncertain count, and top uncovered issue clusters in `src/evaluation/tg_question_canonicalization.py`
- [X] T040 [US3] Wire `tg-qa-canonical-coverage` CLI command in `src/app/commands.py`

**Checkpoint**: User Story 3 is functional and testable independently once issue clusters or equivalent fixture clusters exist.

---

## Phase 6: User Story 4 - Review And Promote Issue Clusters (Priority: P4)

**Goal**: Let reviewers approve, reject, merge, split, or hold issue clusters, build question-bank entries, gate final evaluation case candidates, and export a reviewed evaluation dataset containing only eligible cases with reviewed reference answer material.

**Independent Test**: A review fixture approves some clusters into the question bank without answers, blocks answerless final promotions, promotes only clusters with accepted Telegram or manual reference answer material, and exports a reviewed dataset that excludes blocked, rejected, and LLM-only records.

### Tests for User Story 4

- [X] T041 [US4] Add unit tests for cluster review decision import, duplicate cluster decision rejection, and redaction of manual reference answers in `tests/unit/test_tg_question_canonicalization.py`
- [X] T042 [US4] Add unit tests for question-bank build without final reference answers in `tests/unit/test_tg_question_canonicalization.py`
- [X] T043 [US4] Add unit tests for final evaluation promotion gating, LLM-only rejection, missing-reference blocking, accepted Telegram answers, and manual override answers in `tests/unit/test_tg_question_canonicalization.py`
- [X] T044 [US4] Add unit tests for reviewed evaluation dataset export, manifest counts, quality summary, canonical issue provenance, and exclusion of blocked final case candidates in `tests/unit/test_tg_question_canonicalization.py`
- [X] T045 [US4] Add offline CLI smoke test for question-bank build, final case candidate promotion, reviewed dataset export, and their summary/manifest artifacts in `tests/smoke/test_cli_offline.py`

### Implementation for User Story 4

- [X] T046 [US4] Implement `import_tg_qa_cluster_review_decisions()` with allowed decisions, reference answer actions, reviewer metadata, duplicate handling, and privacy guards in `src/evaluation/tg_question_canonicalization.py`
- [X] T047 [US4] Implement `build_tg_qa_question_bank()` for approved issue clusters with representative examples, coverage status, review status, missing-reference state, provenance, question-bank JSONL, summary counts, and manifest metadata in `src/evaluation/tg_question_canonicalization.py`
- [X] T048 [US4] Implement `build_tg_qa_issue_final_case_candidates()` with `eligible`, `blocked_missing_reference_answer`, and `rejected` promotion statuses plus final-candidate JSONL, summary counts, and manifest metadata in `src/evaluation/tg_question_canonicalization.py`
- [X] T049 [US4] Enforce that `approve_final_evaluation` requires reviewed reference answer material and that LLM canonicalization evidence alone cannot create eligibility in `src/evaluation/tg_question_canonicalization.py`
- [X] T050 [US4] Implement `build_tg_qa_reviewed_evaluation_dataset()` that consumes eligible final case candidates, writes reviewed final cases JSONL plus manifest and quality artifacts, preserves canonical issue cluster provenance, and excludes blocked, rejected, and LLM-only records in `src/evaluation/tg_question_canonicalization.py`
- [X] T051 [US4] Wire `tg-qa-question-bank-build`, `tg-qa-issue-final-candidates`, and `tg-qa-reviewed-evaluation-dataset-build` CLI commands with required summary/manifest or quality output arguments in `src/app/commands.py`

**Checkpoint**: User Story 4 is functional and testable independently once issue clusters or equivalent fixture clusters and review decisions can produce a question bank, gated final case candidates, and a reviewed evaluation dataset artifact.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete 007 artifact pipeline and governance boundaries.

- [X] T052 [P] Update `specs/007-legal-question-canonicalization/quickstart.md` with any final CLI names or required fixture paths after implementation
- [X] T053 [P] Update `specs/007-legal-question-canonicalization/data-model.md` if implementation discovers contract field clarifications
- [X] T054 [P] Update `specs/007-legal-question-canonicalization/contracts/canonicalization.md` with any final manifest or validation clarifications
- [X] T055 Create or update `specs/007-legal-question-canonicalization/implementation-notes.md` with the implementation run log template, verification section, skipped live-service test notes, and known limitations
- [X] T056 Run `python -m compileall src tests` and record the result in `specs/007-legal-question-canonicalization/implementation-notes.md`
- [X] T057 Run `python -m pytest tests/unit/test_tg_question_canonicalization.py tests/smoke/test_cli_offline.py` and record the result in `specs/007-legal-question-canonicalization/implementation-notes.md`
- [X] T058 Run `python -m pytest` and record skipped live-service tests separately in `specs/007-legal-question-canonicalization/implementation-notes.md`
- [X] T059 Run `PYTHONPATH=src python -m app evaluation tg-qa-canonical-boundary-check` and verify no graph mutation, chatbot answer generation, raw Telegram text, or hidden live-service dependency exists
- [X] T060 Verify generated 007 artifacts remain ignored under `data/evaluation/` and no raw Telegram exports, vectors, LLM results, tunnel URLs, API keys, or `.env` values are staged
- [X] T061 Review `AGENTS.md` and `TECHNICAL_SPEC.md` only if implementation changes behavior, contracts, operational contours, or test boundaries

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers canonicalization evidence
- **User Story 2 (Phase 4)**: Depends on Foundational for implementation sequencing and consumes canonicalization evidence from US1 or equivalent fixtures; delivers issue clusters
- **User Story 3 (Phase 5)**: Depends on issue clusters from US2 or equivalent fixtures; delivers canonical coverage
- **User Story 4 (Phase 6)**: Depends on issue clusters from US2 or equivalent fixtures and may consume US3 coverage or equivalent fixtures; delivers question bank, promotion candidates, and reviewed evaluation dataset artifacts
- **Polish (Phase 7)**: Depends on desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: MVP foundation slice after Foundational
- **User Story 2 (P2)**: Requires canonicalization evidence from US1 or equivalent fixtures
- **User Story 3 (P3)**: Requires issue clusters from US2 or equivalent fixtures
- **User Story 4 (P4)**: Requires issue clusters from US2 or equivalent fixtures; coverage from US3 or equivalent fixtures improves review context but is not required for question-bank import tests

### Within Each User Story

- Write required tests before implementation tasks in the same phase
- Unit tests must avoid live services
- Smoke tests must use local fixtures unless explicitly marked operator-managed
- Contract/schema validation before batch import or promotion
- Services before CLI wiring
- Story complete before moving to the next priority unless parallel work is explicitly coordinated

### Parallel Opportunities

- T002 and T004 can run in parallel with T001/T003 after the branch is ready
- T010 can run in parallel with foundational implementation tasks once constants are agreed
- Tests in each story can be drafted before implementation, but tasks touching the same test file should be coordinated
- Documentation polish tasks T052-T054 can run in parallel after implementation behavior stabilizes

---

## Parallel Example: User Story 1

```bash
# Draft story-specific tests together with implementation planning:
Task: "T014 [US1] Add unit tests for canonicalization batch emission from redacted 006 candidates in tests/unit/test_tg_question_canonicalization.py"
Task: "T016 [US1] Add offline CLI smoke test for tg-qa-canonicalization-batch and tg-qa-canonicalization-import in tests/smoke/test_cli_offline.py"

# Implement batch emission before import:
Task: "T017 [US1] Implement emit_tg_qa_canonicalization_batch() with bounded scope controls and redacted 006 candidate provenance in src/evaluation/tg_question_canonicalization.py"
Task: "T019 [US1] Implement import_tg_qa_canonicalization_results() with idempotency in src/evaluation/tg_question_canonicalization.py"
```

## Parallel Example: User Story 2

```bash
# After US1 evidence exists:
Task: "T023 [US2] Add unit tests for canonical embedding batch emission and query-prefix semantics in tests/unit/test_tg_question_canonicalization.py"
Task: "T026 [US2] Add offline CLI smoke test for canonical embedding batch/import and tg-qa-issue-clusters in tests/smoke/test_cli_offline.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational schemas, helpers, boundary check, and CLI placeholders.
3. Complete Phase 3 canonicalization batch/import.
4. Stop and validate US1 independently with fixture unit and smoke tests.

### Incremental Delivery

1. Add US1 canonicalization evidence.
2. Add US2 canonical embeddings and issue clusters.
3. Add US3 canonical coverage reports.
4. Add US4 question-bank review and final promotion gating.
5. Run polish checks and boundary verification after the selected scope.

### Commit Strategy

- Commit after each completed story or coherent artifact boundary.
- Do not commit generated data, vectors, LLM outputs, review sheets, tunnel URLs, API keys, raw Telegram exports, or `.env` values.
- Keep graph mutation, chatbot answer generation, and trusted legal answer support out of 007.
