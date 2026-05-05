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
- optional embedding batch JSONL for question and answer text
- optional LLM batch JSONL for external cheap/free model processing
- later cluster/review/final dataset artifacts

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

### Stage 1: Candidate Extraction

Deterministic local extraction reads Telegram exports, normalizes text,
redacts obvious PII, finds question candidates, links direct reply answers, and
emits candidate metadata. This stage may assign deterministic quality tiers and
routes, but it must not select final expected answers.

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
- `parked_bot_answer_candidates` for known wiki-bot authored replies
- `ignored_other_bot_reply_count` for bot-like replies outside the known wiki
  bot catalog
- `bot_answer_parking_policy`

### Stage 2: Question And Answer Embeddings

Both sides of each Q/A candidate are vectorization inputs:

- question text is embedded for user-intent grouping;
- answer text is embedded because answers usually contain more stable
  procedural, legal, and administrative signals than short Telegram questions;
- downstream clustering must combine question similarity, answer similarity,
  topic/law overlap, and optional bot/city/source hints.

Embedding batch artifacts are external-service inputs and must remain ignored
under `data/evaluation/`. They do not mutate the graph and do not create trusted
legal facts.

### Stage 3: Semantic Clustering

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

### Stage 4: Review Cascade

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
- Detect replies authored by known wiki bots from the catalog and park those
  answers separately from ordinary human answer candidates.
- Treat other bot-like replies as low-priority ignored bot noise unless later
  review explicitly promotes them.
- Collect direct reply answers as candidate answer evidence.
- Label current-theme relevance for migration/asylum/employment topics.
- Emit JSONL records with source message ids, quality tier, cascade route,
  placeholder cluster ids, and review status.
- Emit optional embedding batch JSONL for both question and answer text.
- Emit optional LLM batch JSONL that can be processed externally.
- Pass offline unit/smoke tests on a minimal sample export.
