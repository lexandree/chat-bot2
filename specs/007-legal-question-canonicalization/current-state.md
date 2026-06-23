# 007 Current State

Date: 2026-06-22

This document is an operator-facing status snapshot for 007. It records the
current evaluation, review, and retrieval state without including private
Telegram text, generated vectors, LLM outputs, API endpoints, or local secrets.

## Scope Boundary

007 remains an evaluation and canonicalization layer for the database-first
legal GraphRAG foundation. It does not create chatbot inference, production
answer synthesis, or trusted legal answer support.

All generated dataset, review, LLM, embedding, and HTML artifacts under
`data/evaluation/` are private generated artifacts and remain ignored by git.

## Implementation Status

The tracked 007 implementation tasks are complete through Phase 14:

- canonicalization batch/import;
- canonical embeddings and deterministic issue clusters;
- canonical coverage reports;
- cluster review import, question-bank build, final-candidate gating, reviewed
  dataset export;
- legal-intent equivalence diagnostics;
- private snapshot and explicit-reference benchmark;
- semantic retrieval diagnostics;
- human retrieval relevance review;
- clean curated retrieval baseline;
- route-ambiguity diagnostic;
- temporal-currentness promotion gate.

Latest recorded verification after Phase 14:

- `python -m pytest -q`: 202 passed, 11 skipped;
- `tg-qa-boundary-check`: passed;
- `tg-qa-canonical-boundary-check`: passed;
- `git diff --check`: passed.

## Frozen Prompt State

The accepted Qwen3.6 canonicalizer baseline is:

`tg_question_canonicalizer_v22_positive`

Operator rule: do not revise the canonicalizer prompt for isolated wording
defects. Route isolated defects to residual review or omit them from dataset
promotion. New prompt rules require repeated critical defects or a clear
high-impact deterministic routing defect as defined in `operator-runbook.md`.

## Active Private Dataset Snapshot

The current private canonical dataset contour is `last_2000_v1`.

Current high-level artifact identities:

- issue clusters:
  `data/evaluation/tg_qa_issue_clusters/real_data_007_canonical_question_dataset_last_2000_v1_issue_clusters.jsonl`
- temporal queue:
  `data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_temporal_currentness_review_queue.jsonl`
- cluster review seed:
  `data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_cluster_review_seed_120.jsonl`
- agentic research request experiment:
  `data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_agentic_research_requests_30.jsonl`

These paths are private artifact references, not publication material.

Source question dates have been restored from the original canonicalization
batch metadata (`input.question_date`) for this contour:

- canonical dataset records with `question_date`: 985 / 985
- canonicalization evidence records with `question_date`: 994 / 994
- issue clusters with `source_question_dates`: 984 / 984

Backfill summary:
`data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_question_date_backfill_summary.json`

## Legal-Intent Equivalence State

Current balanced benchmark:

`data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_pair_benchmark_v2_balanced.jsonl`

Current imported human labels:

`data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_pair_review_labels_balanced_v2_imported.jsonl`

Status on 2026-06-23:

- benchmark pairs: 118
- random negative controls: 100
- random negative anchor distribution: 100 unique left candidates, 100 unique
  right candidates, max reuse 1
- reviewed labels retained in balanced benchmark: 41
- unreviewed pairs: 77
- reviewed label classes: 23 `different`, 2 `exact_duplicate`, 4
  `related_context`, 5 `same_legal_intent`, 7
  `same_topic_different_issue`

Historical note: the first `pair_benchmark_v1` random-negative contour pinned
all 100 random controls to one left candidate. It is retained only as a
historical artifact. Use `pair_benchmark_v2_balanced` for further review.

Method reports:

- historical qwen37 pair judge on `pair_benchmark_v1`:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_pair_judge_qwen37_report_summary.json`
  - exact pair-class match: 12 / 23
  - answer-reuse safety match: 18 / 23
  - false duplicate risk examples: 2
  - false separation risk examples: 4
- similarity cosine+recos baseline on `pair_benchmark_v2_balanced`:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_balanced_v2_report_summary.json`
  - reviewed labels: 41
  - exact pair-class match: 27 / 41
  - answer-reuse safety match: 35 / 41
  - false duplicate risk examples: 9
  - false separation risk examples: 0

The latest balanced review UIs are:

- all 118 pairs:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_balanced_v2_review.html`
- unreviewed 77 remaining pairs:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_balanced_v2_unreviewed77_review.html`

Prepared source-hard Qwen3.7 judge contour:

- source-hard batch: 18 pairs
- source-hard labels imported: 18 completed, 0 failed
- no-thinking one-step runner:
  `tmp/run_007_legal_intent_source_hard_qwen37.sh`
- no-thinking one-step command:
  `bash tmp/run_007_legal_intent_source_hard_qwen37.sh full`
- structured-output mode: Qwen3.7 thinking disabled; the failed historical
  `real_data_007_last_2000_source_hard_qwen37_v2_positive_*` attempt combined
  thinking with forced tool calling and is not usable.
- reasoning two-step runner:
  `tmp/run_007_legal_intent_source_hard_qwen37_two_step.sh`
- two-step command:
  `bash tmp/run_007_legal_intent_source_hard_qwen37_two_step.sh full`
- two-step mode: Qwen3.7 Max writes plain-text reasoning first; Qwen3.6 Plus
  with thinking disabled converts that rationale and the pair payload into
  `LegalIntentPairDecisionPayload`.
- if Qwen3.7 rationales are already present and only schema output must be
  rebuilt, use:
  `bash tmp/run_007_legal_intent_source_hard_qwen37_two_step.sh rerun-schema`
- current two-step source-hard result after schema rerun:
  `real_data_007_last_2000_source_hard_qwen37_reasoning_qwen36_schema_v2_positive_*`
  completed 18/18 with no failed records. Strict `pair_class` match against
  the 18 human labels is 7/18; answer-reuse safety match is 13/18; canonical
  question reuse safety match is 16/18. Treat this as useful reasoning evidence
  and a hard-pair diagnostic, not yet as a reliable automatic equivalence
  classifier.

Note: the full qwen37 run currently recorded under
`real_data_007_last_2000_pair_judge_qwen37_*` used prompt version
`tg_legal_intent_pair_judge_v1`. Future qwen37 pair-judge runs should set
`TG_LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION=tg_legal_intent_pair_judge_v2_positive`
unless intentionally comparing against the historical v1 run.

## Temporal Currentness State

Current temporal queue aggregate:

- queue records: 984
- suggested temporal state: 984 `unresolved_currentness`
- source question date available: 984
- source question date missing: 0

Generated temporal review UI:

`data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_temporal_currentness_review.html`

Command notes:

`tmp/007_temporal_currentness_review_commands.md`

Interpretation:

The current temporal gate blocks current-default promotion unless a reviewer
explicitly sets `current_reusable` or `historical_but_generalizable`. Source
question dates are available for review, but they remain metadata only: age
alone does not prove obsolescence, and recent date alone does not prove current
reusable status.

## Retrieval State

See `retrieval-diagnostics-summary.md` for aggregate metrics.

Retained conclusions:

- exact references resolve reliably when the reference is explicit and
  in-scope;
- query-explicit real-record references are not safe semantic ground truth;
- semantic top-1 is diagnostic only;
- clean curated retrieval is acceptable as a small regression signal;
- route ambiguity must preserve multiple plausible legal routes instead of
  forcing one route from `Asyl`/`refugee` wording;
- route-union candidate visibility is diagnostic evidence, not production
  policy.

## Question-Bank Promotion Path

The question-bank/final-candidate path has been mechanically dry-run without
LLM calls or real approvals.

Dry-run command notes:

`tmp/007_question_bank_promotion_dry_run_commands.md`

Observed dry-run result on 2026-06-20:

- 6 synthetic decisions imported, 0 failed;
- 6 question-bank entries built;
- 4 entries had missing reference answers;
- 2 entries were not current-default eligible at question-bank level;
- final candidates: 1 eligible, 1 blocked missing reference answer, 1 blocked
  temporal currentness, 3 rejected because not approved for final evaluation;
- reviewed final dataset emitted 1 synthetic eligible case.

Interpretation:

The mechanics work. Real promotion is still blocked by human cluster review,
temporal-currentness review, and reviewed reference answer material.

## Hermes Experiment State

Hermes/agentic research is currently an experiment, not a permanent project
tool. The experiment tests whether a memory-capable agent can reduce human
review time by learning short route corrections.

Prepared but not permanentized:

- instruction file:
  `tmp/007_hermes_agentic_research_instructions.md`
- request/loop commands:
  `tmp/007_agentic_research_loop_commands.md`
- offline importer, review HTML exporter, and second-pass request builder in
  `tmp/`

Trust boundary:

Hermes output is preliminary research evidence only. It must not approve
question-bank entries, mutate the graph, or become legal truth without human
review.

## Current Blockers

- OpenCode Go quota limits block mass LLM and Hermes experiments for now.
- Temporal currentness is unresolved for all 984 current issue clusters even
  though source dates are now available.
- Question-bank promotion lacks real human cluster decisions and reviewed
  reference answer material.
- Semantic retrieval still needs a candidate-generation/reranking design that
  respects exact references, route ambiguity, temporal state, and multi-law
  support.

## Useful Offline Work Remaining

- Review a bounded subset in the temporal-currentness HTML.
- Use retrieval diagnostics to design a non-LLM candidate-generation/reranking
  baseline.
- Keep future inference questions and prompt lessons updated when manual review
  reveals recurring route ambiguity.
- Keep dry-run promotion artifacts private and separate from real human review
  outputs.
