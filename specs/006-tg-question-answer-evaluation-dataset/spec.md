# Feature 006: Telegram Question/Answer Evaluation Dataset

## Purpose

Build a reproducible, reviewable question/answer candidate dataset from local
Telegram exports so later retrieval and answer workflows can be measured against
real user questions.

The dataset is built as a staged quality cascade. High-confidence cases should
exit early as automatically selected evaluation candidates after semantic
question/answer clustering, while ambiguous cases continue to LLM or manual
review. Fully unclear cases remain explicitly uncertain instead of being forced
into the dataset.

## Scope

Inputs:

- `data/tg/**/result.json` Telegram export files
- optional Telegram wiki bot catalog seed

Outputs:

- redacted Q/A candidate JSONL
- extraction summary JSON
- embedding batch JSONL for question, answer, and optional Q/A pair text
- embedding records JSONL
- similarity neighbor JSONL
- semantic cluster JSONL
- cluster selection JSONL
- optional LLM batch JSONL for external cheap/free model processing
- optional LLM result JSONL
- optional LLM run manifest
- manual review queue and decision JSONL
- final evaluation dataset JSONL, manifest JSON, and quality report JSON

## Boundaries

- Raw Telegram exports remain private local inputs and must not be committed.
- Extracted Telegram answers are evaluation material, not legal truth.
- LLM output, when used later, is candidate metadata only.
- LLM analysis is a one-time, operator-managed classifier/reviewer contour for
  006 dataset construction, not a production dependency.
- No graph mutation.
- No chatbot answer generation.
- No default test may require network, paid APIs, LangChain, LangGraph, or a
  live LLM runtime.
- Recency is not a global corpus filter. Date is used only inside semantic
  question/answer clusters to select the latest usable answer variant.

## Staged Processing Model

The authoritative end-to-end workflow is documented in
[`pipeline.md`](pipeline.md). The artifact model is documented in
[`data-model.md`](data-model.md), and the final dataset contract is documented
in [`contracts/final-dataset.md`](contracts/final-dataset.md). Optional LLM
analysis is documented in [`contracts/llm-analysis.md`](contracts/llm-analysis.md).

### Stage 1: Candidate Extraction

Deterministic local extraction reads Telegram exports, normalizes text,
redacts obvious PII, finds question candidates, links direct reply answers,
links admin-triggered wiki-bot answers, and emits candidate metadata. This
stage may assign deterministic quality tiers and routes, but it must not select
final expected answers.

Stage 1 candidate records must include:

- `question_date`
- answer candidate `date`
- `answer_candidate_status`
- `confidence_tier`: `high`, `medium`, `low`, or `unknown`
- `selection_status`: initially `pending_embedding_cluster`,
  `needs_manual_review`, `uncertain`, or `rejected`
- `selection_policy`: `semantic_qa_cluster_latest_usable_answer`
- `embedding_processing_status`
- `clustering_status`
- placeholder cluster fields: `question_cluster_id`, `answer_cluster_id`,
  `qa_cluster_id`
- `answer_drift_status`: initially `not_evaluated`
- answer candidate source markers, including `answer_source_type`,
  `answer_source_markers`, `answer_candidate_priority`, `answer_candidate_status`,
  `answer_candidate_usable`, and `marking_reason`
- answer source counts, including known wiki-bot and other bot-like reply counts
- `bot_answer_marking_policy`
- answer link metadata: `answer_link_type`, `link_confidence`,
  `trigger_message_id`, `trigger_author_hash`, `trigger_date`,
  `question_to_trigger_seconds`, and `trigger_to_bot_seconds`
- trigger evidence records for short non-question messages that caused or likely
  caused known wiki-bot answers

### Stage 2: Question, Answer, And Q/A Pair Embeddings

Both sides of each Q/A candidate are vectorization inputs. The implementation
may also add a combined Q/A-pair embedding item when useful for pair-level
clustering:

- question text is embedded for user-intent grouping;
- answer text is embedded because answers usually contain more stable
  procedural, legal, and administrative signals than short Telegram questions;
- optional Q/A-pair text is embedded to support combined case grouping;
- downstream clustering must combine question similarity, answer similarity,
  optional pair similarity, topic/law overlap, and optional bot/city/source
  hints.

Embedding batch artifacts are external-service inputs and must remain ignored
under `data/evaluation/`. They do not mutate the graph and do not create trusted
legal facts.

006 embeddings must reuse the existing project embedding contract:

- profile/service/backend/client code in `src/retrieval/*embedding*`;
- Jina retrieval semantics documented in `TECHNICAL_SPEC.md`,
  `ARCHITECTURE.md`, and `export/reference_docs/jina_embeddings_playbook.md`;
- `Query: ` prefix for question items;
- `Document: ` prefix for answer and Q/A-pair items;
- default `1024` dimensions and normalized vectors;
- default tests use fixtures/fakes and must not require a live Jina endpoint.

### Stage 3: Similarity Search

Similarity search consumes embedding records and emits neighbor evidence for
question, answer, and optional Q/A-pair spaces. It must record top-k,
thresholds, embedding profile id, and index implementation. Similarity search
does not merge or approve records by itself.

Initial fixture thresholds are versioned under
`clustering_policy_version=tg_qa_cluster_policy_v1`: question similarity `0.82`,
answer similarity `0.86`, Q/A-pair similarity `0.84`, top-k `20`, and max
component size `50`. These are starting values for deterministic tests and
must be recorded in every similarity/clustering summary before being tuned.

### Stage 4: Semantic Clustering

Clustering produces:

- `question_cluster_id` for similar user formulations;
- `answer_cluster_id` for similar answer variants;
- `qa_cluster_id` as the combined unit used for dataset selection.

The selection rule is:

1. group candidates into `qa_cluster_id`;
2. filter to usable answer candidates;
3. sort usable answers inside the cluster by `answer_date` descending;
4. choose the latest usable answer as `selected_answer_candidate_id`;
5. retain older answers as `historical_answer_variants`.

An answer candidate is usable for automatic latest-answer selection only when
`answer_candidate_status` is `strong` or `partial`,
`answer_candidate_usable=true`, `link_confidence` is `high` or `medium`, and
`answer_candidate_priority` is not `low`. Manual review may still approve or
reject any candidate as evaluation metadata.

If a question cluster contains divergent answer clusters over time, the cluster
must be marked with `answer_drift_status=changed` or `conflicting` instead of
being silently merged.

### Stage 5: Cluster Selection And Temporal Drift

Cluster selection chooses the latest usable answer only inside a semantic
`qa_cluster_id`. It must preserve historical variants, compute drift/conflict
status, and route stable high-confidence clusters to `auto_selected`.

Drift decisions are deterministic:

- `not_evaluated` before clustering/selection runs;
- `insufficient_history` when usable answers or similarity evidence are missing;
- `stable` when usable variants agree with the selected latest answer cluster;
- `changed` when older usable variants differ from the latest answer in a
  chronologically ordered way;
- `conflicting` when answer variants cannot be reduced to a stable or changed
  history.

### Stage 6: LLM Analysis

LLM analysis is optional and review-gated. It is used for medium-confidence,
underspecified, conflicting, or uncertain clusters. It may propose labels,
normalized questions, answer summaries, and review recommendations, but it
cannot approve final dataset records by itself.

The preferred 006 LLM runtime contour is an operator-managed OpenAI-compatible
`llama-server` endpoint exposed through a temporary tunnel. The first no-paid-token
model candidate is `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`; if classification
quality is insufficient, `Qwen3.6-27B-Q6_K.gguf` or `Qwen3.6-27B-Q8_0.gguf`
may be tried after an operator capacity smoke on the target Kaggle T4 x2
runtime. The selected model and tunnel URL are runtime inputs, not trusted
project configuration.

Small-context runtime variants may use a compact cluster prompt profile with a
recorded character budget. Full redacted cluster tasks that exceed that budget
must be preserved in a separate overflow batch for a later long-context endpoint
instead of being silently dropped.

Minimum LLM smoke evidence is JSON validity, schema-valid result count,
failed/skipped count, and a small manual spot-check of classifier recommendations.
If the primary model fails this smoke, the run is recorded as `failed` or
`skipped` and the items remain manual-review backlog.

Manual spot-check sample size must be deterministic for a run: review at least
`min(20, completed_count)` completed results when available, or all completed
results when fewer than 20 exist. Record the sample size and outcome in the LLM
run manifest.

LLM result import must be idempotent by `(llm_run_id, task_scope, task_id)`.
Partial JSONL imports are valid: importable lines become review evidence, failed
lines are counted, and missing tasks remain backlog. Re-importing the same run
must not create duplicate evidence or promote LLM-only output into final records.

### Stage 7: Manual Review

Manual review consumes cluster selections and LLM evidence. It may approve,
reject, merge, split, request more context, or mark a cluster uncertain.
The manual decision scope is question inclusion in the evaluation dataset:
`approve` means the question/case is worth testing against the graph DB, not
that the Telegram answer is a trusted legal answer. The selected Telegram answer
must remain visible and exportable as a reference/community answer for later
graph-output comparison.
Manual review must also distinguish standalone user questions from dialogue
fragments. A clarifying question asked by a helper to the original author is not
a standalone evaluation case and should normally be rejected or merged into a
larger case. A standalone question whose selected Telegram answer is itself a
clarifying question may still be approved, but its reference answer must be
replaced manually.
One evaluation case may still cover several surface-form questions when they
belong to one factual scenario and require one answer obligation from the
system. In that situation the reviewer should keep one row and use
`manual_question_text` to normalize the main evaluable question. If the source
message contains several independently answerable questions that could be split
without sharing one answer obligation, the reviewer must not duplicate TSV rows
for the same `qa_cluster_id`. The current 006 pipeline emits at most one final
case per `qa_cluster_id`; independent sub-questions must be handled as
`split`/backlog or rejected for this round rather than being expanded by manual
row copies.
If the question is useful but the selected Telegram answer is missing, stale,
irrelevant, or otherwise unusable, manual review may still approve the question
with `reference_answer_action=replace_manual` and a redacted
`manual_reference_answer_text`. The final dataset must then use the manual
reference answer while preserving the original selected Telegram answer as
provenance/evidence.
When `manual_reference_answer_text` is non-empty, it overrides
`reference_answer_action=keep_selected`; the operator should not have to adjust
two columns when writing a concise reference answer.

### Stage 8: Final Dataset Build

The final dataset contains only `auto_selected` and `review_approved` records.
It must emit compact cases suitable for retrieval/evaluation work plus a
manifest and quality report. Each case must include both the redacted question
and a redacted reference answer while marking that answer as evaluation material,
not legal authority. The reference answer may be either the selected Telegram
answer or a manual review override.

### Stage 9: Quality Metrics

Quality metrics summarize coverage, answer-source distribution,
trigger-linked-answer distribution, cluster sizes, drift/conflict counts, LLM
review counts, manual-review counts, and rejection/uncertainty reasons.

### Review Cascade

Final cluster statuses:

- `auto_selected`: high confidence, stable cluster, latest usable answer exists,
  no material conflict;
- `needs_llm_review`: medium confidence, short/underspecified question,
  multiple plausible answer variants, or possible temporal drift;
- `needs_manual_review`: legal topic is important or answer variants conflict;
- `review_approved`: manually approved item eligible for final dataset;
- `uncertain`: insufficient evidence to determine question, answer, topic, or
  current usability;
- `rejected`: spam, jokes, non-question, no usable answer, personal data too
  specific, or unrelated discussion.

The final evaluation dataset may include only `auto_selected` and
`review_approved` records. Other statuses remain measurable backlog or rejection
evidence.

## Minimal Acceptance

- Parse Telegram `result.json` exports deterministically.
- Normalize text from Telegram string/list text shapes.
- Redact obvious PII from emitted text.
- Detect question candidates with deterministic heuristics.
- Use wiki bot mentions as weak prioritization signals.
- Detect replies authored by known wiki bots from the catalog and mark answer
  candidates with source metadata.
- Treat other bot-like replies as marked low-priority answer candidates rather
  than deleting or silently ignoring them.
- Collect direct reply answers as candidate answer evidence.
- Link known wiki-bot answers that are invoked by short trigger messages:
  direct `question -> trigger -> bot reply` chains are high confidence; nearby
  `question ... trigger ... bot answer` chains are medium confidence.
- Keep trigger messages as link evidence, not answer candidates.
- Label current-theme relevance for migration/asylum/employment topics.
- Emit JSONL records with source message ids, quality tier, cascade route,
  placeholder cluster ids, and review status.
- Emit answer candidate status and usable-answer flags needed by latest-answer
  selection.
- Emit optional embedding batch JSONL for both question and answer text.
- Import embedding records without requiring a live embedding service in default
  tests.
- Emit similarity neighbor artifacts for question, answer, and optional Q/A-pair
  spaces.
- Emit semantic cluster artifacts for question, answer, and Q/A pair clusters.
- Emit cluster selection artifacts with latest usable answer and drift status.
- Emit optional LLM batch JSONL that can be processed externally.
- Emit optional LLM results as review evidence only.
- Record optional LLM run metadata without committing tunnel URLs, credentials,
  raw provider output, or local `.env` values.
- Emit manual review queue/decision artifacts.
- Emit final dataset JSONL, manifest, and quality report.
- Pass offline unit/smoke tests on a minimal sample export.
