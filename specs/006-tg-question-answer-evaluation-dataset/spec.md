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
- manual review queue and decision JSONL
- final evaluation dataset JSONL, manifest JSON, and quality report JSON

## Boundaries

- Raw Telegram exports remain private local inputs and must not be committed.
- Extracted Telegram answers are evaluation material, not legal truth.
- LLM output, when used later, is candidate metadata only.
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
in [`contracts/final-dataset.md`](contracts/final-dataset.md).

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
  `answer_source_markers`, `answer_candidate_priority`, and `marking_reason`
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

If a question cluster contains divergent answer clusters over time, the cluster
must be marked with `answer_drift_status=changed` or `conflicting` instead of
being silently merged.

### Stage 5: Cluster Selection And Temporal Drift

Cluster selection chooses the latest usable answer only inside a semantic
`qa_cluster_id`. It must preserve historical variants, compute drift/conflict
status, and route stable high-confidence clusters to `auto_selected`.

### Stage 6: LLM Analysis

LLM analysis is optional and review-gated. It is used for medium-confidence,
underspecified, conflicting, or uncertain clusters. It may propose labels,
normalized questions, answer summaries, and review recommendations, but it
cannot approve final dataset records by itself.

### Stage 7: Manual Review

Manual review consumes cluster selections and LLM evidence. It may approve,
reject, merge, split, request more context, or mark a cluster uncertain.

### Stage 8: Final Dataset Build

The final dataset contains only `auto_selected` and `review_approved` records.
It must emit compact cases suitable for retrieval/evaluation work plus a
manifest and quality report.

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
- Emit optional embedding batch JSONL for both question and answer text.
- Import embedding records without requiring a live embedding service in default
  tests.
- Emit similarity neighbor artifacts for question, answer, and optional Q/A-pair
  spaces.
- Emit semantic cluster artifacts for question, answer, and Q/A pair clusters.
- Emit cluster selection artifacts with latest usable answer and drift status.
- Emit optional LLM batch JSONL that can be processed externally.
- Emit optional LLM results as review evidence only.
- Emit manual review queue/decision artifacts.
- Emit final dataset JSONL, manifest, and quality report.
- Pass offline unit/smoke tests on a minimal sample export.
