# Quickstart: Legal Question Canonicalization And Cluster Coverage

This quickstart describes the planned operator flow for 007 after implementation
is explicitly requested. It is not a chatbot or answer-generation workflow.

## Offline Fixture Validation

```bash
python -m pytest \
  tests/unit/test_tg_question_canonicalization.py \
  tests/smoke/test_cli_offline.py -k "canonicalization or coverage"
```

Expected result:

- no live Neo4j, Jina, paid API, network service, or remote notebook is used;
- LLM canonicalization fixture output remains review evidence only;
- no final evaluation case is promoted without reviewed reference answer
  material.

## Canonicalization Batch

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-batch \
  --candidates data/evaluation/tg_qa_candidates/real_data_006_full_corpus_candidates.jsonl \
  --output data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch.jsonl \
  --summary-output data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch_summary.json \
  --filter-mode law_or_topic \
  --max-candidates 5000
```

Expected result:

- batch items contain redacted 006 candidate evidence only;
- each item records source artifact references and expected output schema;
- scope limits are recorded in the summary.

## Operator LLM Calibration

Before running the full 5,000-record canonicalization funnel, run the
operator-managed calibration described in [operator-runbook.md](operator-runbook.md)
on exactly 50 records. This calibration uses OpenCode Go for Qwen3.6 Plus,
MiniMax.io pay-as-you-go credits for MiniMax-M2.7 verification, local
validation, and a review-card UI/export so the operator does not inspect raw
JSON manually.

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-sample \
  --batch data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch.jsonl \
  --output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_batch.jsonl \
  --summary-output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_summary.json \
  --sample-size 50

PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-review-cards \
  --batch data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_batch.jsonl \
  --html-output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_review.html \
  --summary-output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_review_summary.json
```

Expected result:

- Qwen, validation, MiniMax, and human triage artifacts exist for 50 records;
- only minimal task fields are sent to each LLM stage;
- Qwen prompts include the versioned three-example canonicalization profile;
- MiniMax-M2.7 Anthropic-compatible tool-use is preferred; OpenAI-compatible
  tool calls are acceptable with enough token budget for reasoning plus tool
  output, otherwise strict JSON fallback is selected;
- the review UI/export is usable before any full-corpus LLM spend.

## Canonicalization Result Import

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-import \
  --batch data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch.jsonl \
  --results data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_results.jsonl \
  --output data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_evidence.jsonl \
  --manifest-output data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_manifest.json \
  --canonicalization-run-id tg-question-canonicalization-run:real-data-007-smoke
```

Expected result:

- malformed, failed, skipped, excluded, and uncertain records remain visible;
- import is idempotent by `(canonicalization_run_id, task_scope, task_id)`;
- LLM output cannot approve clusters or final cases.

## Canonical Embedding Batch And Import

Canonical question and issue-frame embeddings use query semantics:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonical-embedding-batch \
  --canonicalization-evidence data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_evidence.jsonl \
  --output data/evaluation/tg_qa_canonical_embeddings/real_data_007_canonical_embedding_batch.jsonl \
  --summary-output data/evaluation/tg_qa_canonical_embeddings/real_data_007_canonical_embedding_batch_summary.json
```

Live vectorization is an explicit operator step using the existing
`EMBEDDING_ENDPOINT_URL` contract. Imported records must include the full
embedding profile metadata and remain file artifacts.

## Legal Issue Clustering

```bash
PYTHONPATH=src python -m app evaluation tg-qa-issue-clusters \
  --canonicalization-evidence data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_evidence.jsonl \
  --embedding-records data/evaluation/tg_qa_canonical_embeddings/real_data_007_canonical_embedding_records.jsonl \
  --output data/evaluation/tg_qa_issue_clusters/real_data_007_issue_clusters.jsonl \
  --manifest-output data/evaluation/tg_qa_issue_clusters/real_data_007_issue_clusters_manifest.json \
  --summary-output data/evaluation/tg_qa_issue_clusters/real_data_007_issue_clusters_summary.json
```

Expected result:

- representative raw questions remain redacted examples;
- broad or conflicting clusters receive quality flags;
- no cluster is approved only because of raw question similarity.

## Canonical Coverage Report

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonical-coverage \
  --issue-clusters data/evaluation/tg_qa_issue_clusters/real_data_007_issue_clusters.jsonl \
  --reviewed-final-cases data/evaluation/tg_qa_dataset/real_data_006_canonical_final_cases_reviewed.jsonl \
  --output data/evaluation/tg_qa_canonical_coverage/real_data_007_canonical_coverage_report.jsonl \
  --summary-output data/evaluation/tg_qa_canonical_coverage/real_data_007_canonical_coverage_summary.json
```

Expected result:

- coverage is measured by canonical issue cluster, not raw question text;
- excluded and uncertain clusters are not counted as uncovered legal questions;
- summaries include known limitations.

## Review And Promotion

Import reviewed cluster decisions before building the question bank:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-cluster-review-import \
  --issue-clusters data/evaluation/tg_qa_issue_clusters/real_data_007_issue_clusters.jsonl \
  --decisions data/evaluation/tg_qa_question_bank/real_data_007_cluster_review_decisions_input.jsonl \
  --output data/evaluation/tg_qa_question_bank/real_data_007_cluster_review_decisions.jsonl \
  --summary-output data/evaluation/tg_qa_question_bank/real_data_007_cluster_review_decisions_summary.json
```

Question-bank review can approve useful issue clusters without final reference
answers:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-question-bank-build \
  --issue-clusters data/evaluation/tg_qa_issue_clusters/real_data_007_issue_clusters.jsonl \
  --review-decisions data/evaluation/tg_qa_question_bank/real_data_007_cluster_review_decisions.jsonl \
  --output data/evaluation/tg_qa_question_bank/real_data_007_question_bank.jsonl \
  --manifest-output data/evaluation/tg_qa_question_bank/real_data_007_question_bank_manifest.json \
  --summary-output data/evaluation/tg_qa_question_bank/real_data_007_question_bank_summary.json
```

Final evaluation promotion requires reviewed reference answer material:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-issue-final-candidates \
  --question-bank data/evaluation/tg_qa_question_bank/real_data_007_question_bank.jsonl \
  --review-decisions data/evaluation/tg_qa_question_bank/real_data_007_cluster_review_decisions.jsonl \
  --output data/evaluation/tg_qa_question_bank/real_data_007_final_case_candidates.jsonl \
  --manifest-output data/evaluation/tg_qa_question_bank/real_data_007_final_case_candidates_manifest.json \
  --summary-output data/evaluation/tg_qa_question_bank/real_data_007_final_case_candidates_summary.json
```

Build the reviewed evaluation dataset from eligible promotion candidates:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-reviewed-evaluation-dataset-build \
  --final-case-candidates data/evaluation/tg_qa_question_bank/real_data_007_final_case_candidates.jsonl \
  --output data/evaluation/tg_qa_dataset/real_data_007_reviewed_final_cases.jsonl \
  --manifest-output data/evaluation/tg_qa_dataset/real_data_007_reviewed_final_manifest.json \
  --quality-output data/evaluation/tg_qa_dataset/real_data_007_reviewed_final_quality.json
```

Expected result:

- answerless approved clusters remain in `question_bank`;
- final case candidates without reviewed reference answers are blocked;
- reviewed final cases include only eligible promoted cases with reviewed
  reference answer material;
- Telegram answers remain evaluation material, not legal truth.

## Private Snapshot And Corpus-Bounded Retrieval Baselines

Use the commands in
[contracts/private-snapshot-reference-benchmark.md](contracts/private-snapshot-reference-benchmark.md)
to freeze a content-free private snapshot identity and run the first
corpus-bounded exact-reference and semantic retrieval benchmarks.

Expected result:

- all dataset rows and benchmark cases remain under ignored `data/evaluation/`;
- the snapshot manifest contains hashes and counts but no record content;
- the benchmark evaluates only explicit law-code references against the
  selected legal preview;
- semantic retrieval uses the current asymmetric query/document embedding
  contract and reports Recall@k, MRR, and nDCG@k;
- silver query-explicit targets and any separately reviewed accepted targets
  remain distinct;
- a bounded static HTML review can label multiple actually relevant shown
  sections or record that no relevant candidate was shown;
- reviewed relevance metrics use only completed positive human relevance
  labels;
- neither summary claims legal-reference correctness, reranking quality,
  answer quality, or trusted support.
