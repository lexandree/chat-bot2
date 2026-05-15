# Pipeline: Telegram Q/A Evaluation Dataset

## Principle

006 builds an evaluation dataset, not trusted legal knowledge. Telegram answers,
wiki-bot answers, LLM labels, embedding clusters, and manual review decisions are
dataset-construction evidence only. They must not mutate Neo4j graph state and
must not become legal truth.

## End-To-End Stages

### Stage 0: Private Input Inventory

Input artifacts:

- `data/tg/**/result.json`
- `tmp/tg_wiki_bot_catalog_seed.json`

Output artifacts:

- export inventory summary
- bot catalog validation summary

Purpose:

- confirm which exports are available;
- count messages without exposing raw private text;
- validate known wiki-bot names/usernames.

### Stage 1: Q/A Candidate Extraction

Input artifacts:

- Telegram exports
- bot catalog

Output artifacts:

- `data/evaluation/tg_qa_candidates/*.jsonl`
- `data/evaluation/tg_qa_dataset/*_extraction_summary.json`
- `data/evaluation/tg_qa_embeddings/*_embedding_batch.jsonl`
- `data/evaluation/tg_qa_llm_batches/*_llm_batch.jsonl`

Responsibilities:

- normalize Telegram text shapes;
- redact obvious PII;
- detect question candidates;
- link direct replies;
- link admin-triggered known wiki-bot answers;
- mark human, known wiki-bot, and other bot-like answer sources;
- emit deterministic quality tier and route metadata.

### Stage 2: Embedding Execution And Import

Input artifacts:

- embedding batch JSONL from Stage 1

Output artifacts:

- `data/evaluation/tg_qa_embeddings/*_embedding_records.jsonl`
- embedding run manifest

Responsibilities:

- optionally call the local or tunneled Jina-compatible endpoint from
  `EMBEDDING_ENDPOINT_URL` to convert `*_embedding_batch.jsonl` into
  `*_external_vectors.jsonl`;
- vectorize question items with query semantics;
- vectorize answer items with document semantics;
- optionally vectorize combined Q/A text for pair-level grouping;
- reuse the existing project embedding contract instead of defining a parallel
  one:
  - `src/retrieval/embedding_profile.py`
  - `src/retrieval/embedding_endpoint_client.py`
  - `src/retrieval/embedding_backend.py`
  - `src/retrieval/embedding_service.py`
- preserve the validated Jina retrieval contract:
  - `Query: ` for question items;
  - `Document: ` for answer and Q/A-pair items;
  - `1024` dimensions by default;
  - normalized vectors;
  - local Jina-compatible endpoint shape `/v1/embeddings`;
- record provider, model, dimensions, normalization, prefixes, run id, and
  failure counts;
- keep vectors and provider output outside tracked source.

Supported call modes:

- local/tunneled `llama-server` embedding endpoint, default shape
  `/v1/embeddings`, model alias such as `jina-q8`;
- hosted Jina API as a future explicit adapter, not the default 006 path;
- offline fixture/fake vectors for default tests.

Default tests must use fixture vectors or deterministic fake vectors, not live
embedding services.

Reference documentation:

- `TECHNICAL_SPEC.md`, section `Embedding Index`
- `ARCHITECTURE.md`, section `Embedding Runtime`
- `export/reference_docs/jina_embeddings_playbook.md`

### Stage 3: Similarity Search

Input artifacts:

- candidate JSONL
- embedding records

Output artifacts:

- `data/evaluation/tg_qa_similarity/*_neighbors.jsonl`
- similarity run summary

Responsibilities:

- build local searchable indexes for question, answer, and optional Q/A pair
  embeddings;
- emit top-k neighbors per candidate/item;
- compute separate similarity scores:
  `question_similarity`, `answer_similarity`, `qa_pair_similarity`;
- record thresholds, top-k, embedding profile id, and index implementation.

Similarity output is candidate evidence only. It does not merge records by
itself.

Initial deterministic thresholds for fixture tests:

- `clustering_policy_version`: `tg_qa_cluster_policy_v1`
- `question_similarity_threshold`: `0.82`
- `answer_similarity_threshold`: `0.86`
- `qa_pair_similarity_threshold`: `0.84`
- `top_k`: `20`
- `max_component_size`: `50`

### Stage 4: Semantic Clustering

Input artifacts:

- candidates
- similarity neighbors
- topic/law/bot/source metadata

Output artifacts:

- `data/evaluation/tg_qa_clusters/*_question_clusters.jsonl`
- `data/evaluation/tg_qa_clusters/*_answer_clusters.jsonl`
- `data/evaluation/tg_qa_clusters/*_qa_clusters.jsonl`
- clustering summary

Responsibilities:

- create `question_cluster_id` for similar user formulations;
- create `answer_cluster_id` for similar answer variants;
- create `qa_cluster_id` from combined evidence;
- combine question similarity, answer similarity, Q/A similarity, topic/law
  overlap, answer source markers, bot/city hints, and time ordering;
- avoid broad transitive merges by enforcing bounded components and cluster
  quality checks;
- mark broad or low-cohesion components with quality flags instead of merging
  them into auto-selected clusters.

### Stage 5: Cluster Selection And Temporal Drift

Input artifacts:

- Q/A clusters
- candidate answer variants

Output artifacts:

- `data/evaluation/tg_qa_selection/*_cluster_selection.jsonl`
- selection summary

Responsibilities:

- sort usable answers inside each `qa_cluster_id` by answer date descending;
- select the latest usable answer candidate only inside a semantic cluster;
- retain older answers as `historical_answer_variants`;
- compute `answer_drift_status`: `stable`, `changed`, `conflicting`,
  `insufficient_history`, or `not_evaluated`;
- route high-confidence stable clusters to `auto_selected`;
- route ambiguous clusters to LLM or manual review.

Date must not be used as a global corpus cutoff.

Usable answer predicate for automatic selection:

- `answer_candidate_status` is `strong` or `partial`;
- `answer_candidate_usable=true`;
- `link_confidence` is `high` or `medium`;
- `answer_candidate_priority` is not `low`;
- no cluster or review evidence marks the answer as conflicting or rejected.

Drift decision table:

- `not_evaluated`: Stage 5 has not run.
- `insufficient_history`: usable answers or required similarity evidence are
  missing.
- `stable`: one or more usable answers exist and retained variants agree with
  the selected answer cluster at or above `answer_similarity_threshold`.
- `changed`: older usable variants differ from the selected latest answer, are
  chronologically ordered, and selected-vs-older answer similarity is between
  `answer_changed_similarity_floor` and `answer_similarity_threshold`.
- `conflicting`: usable variants are incompatible by topic/law/source evidence,
  cannot be ordered as historical change, or fall below
  `answer_conflict_similarity_ceiling`.

### Stage 6: LLM Analysis

Input artifacts:

- medium-confidence cluster selections
- conflicting or underspecified clusters
- LLM batch JSONL

Output artifacts:

- `data/evaluation/tg_qa_llm_results/*_llm_results.jsonl`
- LLM run manifest

Responsibilities:

- classify whether the item is a real user question;
- classify topic relevance;
- classify legal-evaluation fit by required answer reasoning, not by topic
  keywords alone;
- detect hidden legal issue spotting cases where the user's practical wording
  implies legal duties, risks, status conditions, or reporting obligations;
- assign calibration-only `issue_spotting_level`, confidence, and reason so the
  boolean flag is not the only signal;
- assess answer candidate quality;
- detect conflict/drift signals;
- propose normalized question text;
- propose short answer summary for review;
- recommend `needs_manual_review`, `uncertain`, or `rejected`.

LLM batches may be `candidate` scope before clustering or `qa_cluster` scope
after semantic clustering. Candidate-scope results attach to candidate ids;
cluster-scope results attach to `qa_cluster_id`.

LLM output cannot approve final dataset records by itself. It is review evidence.

Cluster-level LLM batches may use either:

- `full` prompt profile for long-context endpoints;
- `compact` prompt profile for temporary small-context endpoints.

The compact profile keeps the selected/latest evidence first, truncates long
redacted text, records the input character budget, and can emit a companion
overflow JSONL containing full-profile items for a later long-context endpoint.
Running both compact and full passes is allowed only as separate review-evidence
runs with distinct `llm_run_id` values.

Runtime contour:

- use an operator-managed OpenAI-compatible `llama-server` endpoint;
- prefer the already exercised Gemma 4 Kaggle path with
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- try `Qwen3.6-27B-Q6_K.gguf` or `Qwen3.6-27B-Q8_0.gguf` only if Gemma 4 is
  insufficient and the operator smoke confirms the model fits the target
  Kaggle T4 x2 memory contour;
- expose the endpoint through a temporary Cloudflare Tunnel, `trycloudflare`,
  local forward, or equivalent short-lived endpoint;
- keep model files, runtime binaries, tunnel URLs, credentials, and raw provider
  output outside tracked source;
- store only redacted result JSONL and a redacted run manifest under ignored
  `data/evaluation/tg_qa_llm_results/` paths.
- record JSON validity count, schema-valid count, failed/skipped count, and
  manual spot-check notes in the LLM run manifest.
- use deterministic manual spot-check size: `min(20, completed_count)` completed
  results when available, or all completed results when fewer than 20 exist.
- for Gemma 4 through `llama-server`, tolerate model/template wrappers by
  extracting the first valid JSON object from the response; do not treat this as
  a generic provider contract.

LLM result import is resumable and idempotent:

- use `(llm_run_id, task_scope, task_id)` as the import key;
- allow partial JSONL imports and keep failed/unprocessed items as backlog;
- re-importing the same run de-duplicates or updates review evidence;
- never promote LLM-only output into `auto_selected` or final dataset records.

The LLM analysis contract is
[`contracts/llm-analysis.md`](contracts/llm-analysis.md). Default tests must
use fixture LLM results and must not require Kaggle, `cloudflared`, network
access, LangChain, LangGraph, or a live model server.

### Stage 7: Manual Review Queue

Input artifacts:

- cluster selections
- LLM results
- uncertain/conflicting/rejected candidates

Output artifacts:

- `data/evaluation/tg_qa_review/*_review_queue.jsonl`
- `data/evaluation/tg_qa_review/*_review_decisions.jsonl`

Responsibilities:

- present redacted question, answer variants, source markers, cluster evidence,
  drift evidence, and LLM notes;
- show both the LLM-normalized question and the original redacted Telegram
  question, because LLM normalization can turn a dialogue fragment into a
  misleading standalone-looking question;
- flag dialogue fragments separately from bad answers:
  `dialogue_clarification_question` and `dialogue_context_fragment` are normally
  rejected as standalone cases, while
  `standalone_question_with_clarifying_answer` keeps the question eligible but
  routes the reference answer to manual replacement;
- allow decisions: `approve`, `reject`, `merge`, `split`, `needs_more_context`,
  `uncertain`;
- treat `approve`/`reject` as question-inclusion decisions for the evaluation
  dataset, not as approval or rejection of legal answer truth;
- treat one review row as one `qa_cluster_id` decision boundary: a reviewer may
  normalize a multi-part message into one main evaluable question with
  `manual_question_text` when the parts belong to one scenario and one answer
  obligation, but must not duplicate rows to create multiple final cases from
  the same cluster;
- treat `split` as a reviewer outcome/backlog signal, not as an automatic
  fan-out mechanism in the current 006 builder;
- record reviewer id/hash, decision time, decision reason, selected question
  candidate id, selected answer candidate id, answer-side status, and the
  reference-answer role
  `community_answer_for_graph_db_comparison_not_legal_truth`.
- allow a reviewer to approve the question while replacing the selected Telegram
  answer with `reference_answer_action=replace_manual` and a redacted
  `manual_reference_answer_text`; this is required when the question is valuable
  but the chat answer is irrelevant, stale, or low quality.
- treat a non-empty `manual_reference_answer_text` as an explicit replacement
  even when the sheet still says `reference_answer_action=keep_selected`.

### Stage 8: Final Dataset Build

Input artifacts:

- `auto_selected` stable clusters;
- `review_approved` decisions;
- selected latest usable answers;
- historical variants.

Output artifacts:

- `data/evaluation/tg_qa_dataset/*_final_cases.jsonl`
- `data/evaluation/tg_qa_dataset/*_dataset_manifest.json`
- `data/evaluation/tg_qa_dataset/*_dataset_quality_report.json`

Responsibilities:

- emit a compact dataset suitable for retrieval/evaluation work;
- include normalized question, redacted original question, selected answer
  candidate, redacted reference answer text, answer source markers, topic/law
  candidates, cluster ids, question-inclusion status, review status, and
  provenance;
- preserve the reference answer as comparison material for graph DB output, not
  as trusted legal authority;
- when manual review supplies `replace_manual`, use the manual redacted answer
  as `reference_answer_text_redacted`, keep the original selected Telegram answer
  separately, and mark `reference_answer_source=manual_review_override`;
- exclude raw private text, secrets, and graph mutations;
- keep rejected and uncertain evidence in separate artifacts.

### Stage 9: Dataset Quality Metrics

Input artifacts:

- final dataset cases
- rejected/uncertain/backlog artifacts

Output artifacts:

- quality report JSON

Metrics:

- case count by status;
- topic/law coverage;
- legal-evaluation fit distribution;
- issue-spotting required count;
- issue-spotting level and confidence distribution;
- hidden legal issue category distribution;
- answer source distribution;
- direct vs trigger-linked answer distribution;
- cluster size distribution;
- drift/conflict counts;
- LLM-reviewed vs manually reviewed counts;
- rejection and uncertainty reasons.
