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
- [x] T018 Emit orphan trigger/bot chain counts across the whole export.

## Phase 2: Embedding Batch And Embedding Records

- [x] T019 Emit question and answer embedding batch JSONL.
- [x] T020 Add optional Q/A-pair embedding batch items with explicit
  `text_role=qa_pair`.
- [x] T021 Reuse existing `EmbeddingProfile` metadata contract for 006
  evaluation runs instead of defining a parallel embedding profile.
- [x] T022 Implement embedding-record import from external JSONL output.
- [x] T023 Validate embedding dimensions, normalization, profile id, and failed
  item reporting against the existing Jina-compatible embedding contract.
- [x] T024 Add fixture embedding records for default offline tests.
- [x] T025 Add embedding run summary artifact.

## Phase 3: Similarity Search

- [x] T026 Build local similarity index over fixture/imported embedding records.
- [x] T027 Emit top-k question-neighbor JSONL.
- [x] T028 Emit top-k answer-neighbor JSONL.
- [x] T029 Emit top-k Q/A-pair-neighbor JSONL when pair embeddings exist.
- [x] T030 Record similarity thresholds, top-k, index implementation, and
  embedding profile id using `tg_qa_cluster_policy_v1` defaults.
- [x] T031 Add tests proving similarity search does not merge or approve cases.

## Phase 4: Semantic Clustering

- [x] T032 Generate stable `question_cluster_id` records from question
  neighbors.
- [x] T033 Generate stable `answer_cluster_id` records from answer neighbors.
- [x] T034 Generate stable `qa_cluster_id` records from combined evidence.
- [x] T035 Combine question similarity, answer similarity, optional pair
  similarity, topic/law overlap, bot/source markers, and answer-link metadata.
- [x] T036 Bound transitive merges with max component size and quality flags.
- [x] T037 Emit cluster summary metrics and policy version.
- [x] T038 Add split/merge test fixtures for ambiguous clusters.

## Phase 5: Cluster Selection And Drift

- [x] T039 Select latest usable answer inside each `qa_cluster_id` using the
  explicit usable-answer predicate.
- [x] T040 Preserve older answer variants as `historical_answer_variants`.
- [x] T041 Compute `answer_drift_status` using the deterministic drift decision
  table: `stable`, `changed`, `conflicting`, `insufficient_history`, or
  `not_evaluated`.
- [x] T042 Route high-confidence stable clusters to `auto_selected`.
- [x] T043 Route medium/conflicting/underspecified clusters to LLM or manual
  review.
- [x] T044 Emit `cluster_selection.jsonl` and selection summary.

## Phase 6: LLM Analysis

- [x] T045 Emit initial LLM batch JSONL for candidate classification with
  operator-managed `llama-server` runtime hint.
- [x] T046 Emit cluster-level LLM batch JSONL for non-trivial clusters.
- [x] T047 Define LLM result import schema with run id, model/provider, status,
  and failure reason in `contracts/llm-analysis.md`.
- [x] T048 Define and validate redacted LLM run manifest with JSON-valid,
  schema-valid, failed, skipped, unprocessed, and deterministic manual
  spot-check counts.
- [x] T049 Import LLM results as review evidence only with idempotent
  `(llm_run_id, task_scope, task_id)` keys and partial JSONL resume behavior.
- [x] T050 Ensure LLM output cannot directly create `auto_selected` or final
  dataset records.
- [x] T051 Add offline fixture LLM results and run manifests for default tests.
- [x] T051a Add compact cluster LLM batch emission with full overflow batch for
  temporary small-context endpoints.
- [x] T051b Add optional OpenAI-compatible chat runner that extracts the first
  valid JSON object from Gemma/llama-server wrapped responses.

## Phase 7: Manual Review

- [x] T052 Emit manual review queue JSONL for `needs_manual_review`,
  `needs_llm_review`, `uncertain`, and `conflicting` clusters.
- [x] T053 Include redacted question, selected answer candidate, historical
  variants, trigger evidence, similarity evidence, and LLM notes.
- [x] T054 Define manual review decisions: `approve`, `reject`, `merge`,
  `split`, `needs_more_context`, `uncertain`.
- [x] T055 Import manual review decisions.
- [x] T056 Ensure manual decisions can override LLM recommendations but remain
  evaluation metadata, not legal truth.

## Phase 8: Final Dataset Build

- [x] T057 Build final JSONL only from `auto_selected` and `review_approved`
  records.
- [x] T058 Emit `case_id`, normalized question, redacted original question,
  selected redacted answer, cluster ids, answer source/link metadata,
  topic/law candidates, status, drift status, and provenance.
- [x] T059 Exclude rejected, uncertain, and raw/private records from final
  dataset.
- [x] T060 Emit dataset manifest with source artifact paths, stage run ids,
  drift/conflict counts, known limitations, and backlog counts.
- [x] T061 Emit dataset quality report.
- [x] T062 Add offline tests for final dataset eligibility and exclusions.

## Phase 9: Operational Smoke

- [x] T063 Run real-data extraction smoke on local Telegram exports.
- [x] T064 Run embedding import smoke with fixture vectors.
- [x] T065 Run similarity/clustering smoke with fixture vectors.
- [x] T066 Run final dataset build smoke with fixture review decisions.
- [x] T067 Document remaining uncertainty/backlog counts after each run.

## Non-Negotiable Boundaries

- [x] T068 Add or run static verification that 006 evaluation code does not
  import graph writers or mutate Neo4j.
- [x] T069 Add or run static verification that 006 has no chatbot answer
  generation path.
- [x] T070 Verify raw Telegram text, secrets, `.env` values, generated vectors,
  LLM results, and final data artifacts remain ignored/untracked.
- [x] T071 Verify default test command does not require network, paid APIs,
  LangChain, LangGraph, live embeddings, or live LLM services.
