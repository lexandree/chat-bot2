# Tasks: Telegram Q/A Evaluation Dataset

## Phase 0: Spec And Boundaries

- [x] T001 Define 006 purpose as evaluation dataset construction, not trusted
  legal graph enrichment.
- [x] T002 Document full end-to-end pipeline in `pipeline.md`.
- [x] T003 Document artifact data model in `data-model.md`.
- [x] T004 Document final dataset contract in `contracts/final-dataset.md`.
- [x] T005 Ensure raw Telegram exports, generated vectors, LLM results, review
  artifacts, and final dataset artifacts stay ignored under `data/evaluation/`.

## Phase 1: Candidate Extraction

- [x] T006 Parse Telegram `result.json` exports deterministically.
- [x] T007 Normalize Telegram string/list text shapes.
- [x] T008 Redact obvious PII from emitted text.
- [x] T009 Load known wiki-bot catalog.
- [x] T010 Detect question candidates with deterministic heuristics.
- [x] T011 Detect current topic/law candidates for migration, asylum, and
  employment themes.
- [x] T012 Link direct reply answer candidates.
- [x] T013 Mark known wiki-bot and other bot-like answer sources.
- [x] T014 Link admin-triggered wiki-bot answers through direct trigger replies.
- [x] T015 Link nearby admin-triggered wiki-bot answers through bounded
  message/time windows.
- [x] T016 Preserve trigger messages as `trigger_evidence`, not answer
  candidates.
- [x] T017 Emit extraction summary and answer/link/source counts.
- [ ] T018 Emit orphan trigger/bot chain counts across the whole export.

## Phase 2: Embedding Batch And Embedding Records

- [x] T019 Emit question and answer embedding batch JSONL.
- [ ] T020 Add optional Q/A-pair embedding batch items with explicit
  `text_role=qa_pair`.
- [ ] T021 Reuse existing `EmbeddingProfile` metadata contract for 006
  evaluation runs instead of defining a parallel embedding profile.
- [ ] T022 Implement embedding-record import from external JSONL output.
- [ ] T023 Validate embedding dimensions, normalization, profile id, and failed
  item reporting against the existing Jina-compatible embedding contract.
- [ ] T024 Add fixture embedding records for default offline tests.
- [ ] T025 Add embedding run summary artifact.

## Phase 3: Similarity Search

- [ ] T026 Build local similarity index over fixture/imported embedding records.
- [ ] T027 Emit top-k question-neighbor JSONL.
- [ ] T028 Emit top-k answer-neighbor JSONL.
- [ ] T029 Emit top-k Q/A-pair-neighbor JSONL when pair embeddings exist.
- [ ] T030 Record similarity thresholds, top-k, index implementation, and
  embedding profile id.
- [ ] T031 Add tests proving similarity search does not merge or approve cases.

## Phase 4: Semantic Clustering

- [ ] T032 Generate stable `question_cluster_id` records from question
  neighbors.
- [ ] T033 Generate stable `answer_cluster_id` records from answer neighbors.
- [ ] T034 Generate stable `qa_cluster_id` records from combined evidence.
- [ ] T035 Combine question similarity, answer similarity, optional pair
  similarity, topic/law overlap, bot/source markers, and answer-link metadata.
- [ ] T036 Bound transitive merges with max component size and quality flags.
- [ ] T037 Emit cluster summary metrics and policy version.
- [ ] T038 Add split/merge test fixtures for ambiguous clusters.

## Phase 5: Cluster Selection And Drift

- [ ] T039 Select latest usable answer inside each `qa_cluster_id`.
- [ ] T040 Preserve older answer variants as `historical_answer_variants`.
- [ ] T041 Compute `answer_drift_status`: `stable`, `changed`,
  `conflicting`, `insufficient_history`, or `not_evaluated`.
- [ ] T042 Route high-confidence stable clusters to `auto_selected`.
- [ ] T043 Route medium/conflicting/underspecified clusters to LLM or manual
  review.
- [ ] T044 Emit `cluster_selection.jsonl` and selection summary.

## Phase 6: LLM Analysis

- [x] T045 Emit initial LLM batch JSONL for candidate classification.
- [ ] T046 Emit cluster-level LLM batch JSONL for non-trivial clusters.
- [ ] T047 Define LLM result import schema with run id, model/provider, status,
  and failure reason.
- [ ] T048 Import LLM results as review evidence only.
- [ ] T049 Ensure LLM output cannot directly create `auto_selected` or final
  dataset records.
- [ ] T050 Add offline fixture LLM results for default tests.

## Phase 7: Manual Review

- [ ] T051 Emit manual review queue JSONL for `needs_manual_review`,
  `needs_llm_review`, `uncertain`, and `conflicting` clusters.
- [ ] T052 Include redacted question, selected answer candidate, historical
  variants, trigger evidence, similarity evidence, and LLM notes.
- [ ] T053 Define manual review decisions: `approve`, `reject`, `merge`,
  `split`, `needs_more_context`, `uncertain`.
- [ ] T054 Import manual review decisions.
- [ ] T055 Ensure manual decisions can override LLM recommendations but remain
  evaluation metadata, not legal truth.

## Phase 8: Final Dataset Build

- [ ] T056 Build final JSONL only from `auto_selected` and `review_approved`
  records.
- [ ] T057 Emit `case_id`, normalized question, redacted original question,
  selected redacted answer, cluster ids, answer source/link metadata,
  topic/law candidates, status, drift status, and provenance.
- [ ] T058 Exclude rejected, uncertain, and raw/private records from final
  dataset.
- [ ] T059 Emit dataset manifest with source artifact paths and stage run ids.
- [ ] T060 Emit dataset quality report.
- [ ] T061 Add offline tests for final dataset eligibility and exclusions.

## Phase 9: Operational Smoke

- [x] T062 Run real-data extraction smoke on local Telegram exports.
- [ ] T063 Run embedding import smoke with fixture vectors.
- [ ] T064 Run similarity/clustering smoke with fixture vectors.
- [ ] T065 Run final dataset build smoke with fixture review decisions.
- [ ] T066 Document remaining uncertainty/backlog counts after each run.

## Non-Negotiable Boundaries

- [ ] T067 No graph mutation in any 006 stage.
- [ ] T068 No chatbot answer generation in any 006 stage.
- [ ] T069 No raw Telegram text, secrets, `.env` values, generated vectors, LLM
  results, or final data artifacts in tracked source files.
- [ ] T070 No default test may require network, paid APIs, LangChain, LangGraph,
  live embeddings, or live LLM services.
