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

- vectorize question items with query semantics;
- vectorize answer items with document semantics;
- optionally vectorize combined Q/A text for pair-level grouping;
- record provider, model, dimensions, normalization, prefixes, run id, and
  failure counts;
- keep vectors and provider output outside tracked source.

Default tests must use fixture vectors or deterministic fake vectors, not live
embedding services.

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
  quality checks.

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
- assess answer candidate quality;
- detect conflict/drift signals;
- propose normalized question text;
- propose short answer summary for review;
- recommend `needs_manual_review`, `uncertain`, or `rejected`.

LLM output cannot approve final dataset records by itself. It is review evidence.

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
- allow decisions: `approve`, `reject`, `merge`, `split`, `needs_more_context`,
  `uncertain`;
- record reviewer id/hash, decision time, decision reason, and selected answer
  candidate id.

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
  candidate, answer source markers, topic/law candidates, cluster ids, review
  status, and provenance;
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
- answer source distribution;
- direct vs trigger-linked answer distribution;
- cluster size distribution;
- drift/conflict counts;
- LLM-reviewed vs manually reviewed counts;
- rejection and uncertainty reasons.
