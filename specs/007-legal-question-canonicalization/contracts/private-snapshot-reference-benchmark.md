# Contract: Private Dataset Snapshot And Corpus-Bounded Retrieval Benchmarks

## Publication Boundary

The canonical question dataset and every generated artifact derived from it are
private unless a separate explicit sanitization and publication step approves a
specific artifact.

The public Git repository may contain implementation code, schemas, prompt
profiles, operator documentation, synthetic fixtures, and aggregate findings
that contain no private record text.

The public Git repository must not contain canonical dataset rows, source
Telegram text, vectors, review files, LLM results, benchmark cases derived from
the private dataset, or private snapshot manifests unless separately approved
for publication.

`data/evaluation/` is ignored as a complete directory regardless of file
extension. This prevents a new output format such as CSV, Parquet, or binary
vectors from bypassing extension-specific ignore rules.

## Private Snapshot Manifest

`tg-qa-private-snapshot-manifest` identifies a fixed local artifact bundle
without copying record content into the manifest.

The manifest includes stable `snapshot_id`, operator-selected `snapshot_name`,
SHA-256, byte count, line count, suffix and path for each artifact, aggregate
counts, `privacy_classification=private_project_artifact`,
`publication_status=private_not_for_publication`, and
`contains_record_content=false`.

The manifest remains under ignored `data/evaluation/` paths. Reproduction
requires separate access to the private artifacts.

## Corpus-Bounded Explicit-Reference Benchmark

`tg-qa-corpus-bounded-reference-benchmark` is the first retrieval baseline that
uses the private canonical dataset against the legal corpus.

The benchmark:

- reads only `canonical_question` from dataset records;
- accepts only explicit section references that include a law code;
- limits targets to law codes present in the selected legal preview;
- uses the query-explicit reference as expected mechanical target evidence;
- evaluates the existing exact-reference resolver;
- records Recall@1, outcomes, excluded-reference reasons, selected law codes,
  preview identity, and private dataset snapshot identity.

This baseline does not validate whether an LLM-produced reference is legally
correct and does not measure semantic retrieval, reranking, answer quality, or
GraphRAG inference. A later semantic benchmark requires independently reviewed
expected legal source references.

`mechanically_resolved` means only that the query-explicit law and section
identify a section in the selected preview. It is not a judgment that the
reference is legally correct for the question.

## Corpus-Bounded Semantic Retrieval Benchmark

The semantic benchmark reuses mechanically resolved explicit-reference cases
as query-explicit silver labels. It has three explicit steps:

1. `tg-qa-corpus-bounded-semantic-embedding-batch` emits each canonical
   question with `Query: ` semantics and each selected legal source fragment
   body with `Document: ` semantics.
2. The existing operator-managed `tg-qa-embed-batch` command produces vectors.
3. `tg-qa-corpus-bounded-semantic-benchmark` ranks every selected legal section
   for each query and reports Recall@k, MRR, and nDCG@k.

Document inputs use only `source_fragment.body_text`, matching the current
graph-write embedding contract. The benchmark does not improve scores by
injecting section numbers or titles that are absent from graph-written source
fragment vectors.

All mechanically resolved cases remain in the `silver_all_query_explicit_targets`
metric scope. An optional private JSONL review file may provide
`benchmark_case_id`, `reference_correctness_decision` (`accept`, `exclude`, or
`uncertain`), and `decision_reason`. Only `accept` records enter the separate
`reviewed_accepted_targets` metric scope.

Missing query or document vectors remain visible and count as retrieval
failures. Semantic metrics do not establish legal-reference correctness,
answer correctness, completeness, or trusted support. They measure
query-explicit citation recovery, not general legal relevance: an explicit
reference may describe the user's status or premise rather than the section
that answers the question.

## Human-Reviewed Retrieval Relevance Diagnostic

Query-explicit citation recovery is not a reliable proxy for legal relevance.
The bounded relevance-review contour samples semantic cases deterministically
across expected sections and presents:

- the canonical question;
- the semantic top candidates with legal source text;
- the query-explicit target, added separately when absent from the top
  candidates.

The reviewer may mark multiple shown sections as relevant, mark that no
relevant candidate is shown, and classify the query-explicit reference as
`answer_support`, `status_context`, `incorrect`, or `uncertain`. Completed
review labels require either at least one relevant shown section or
`no_relevant_candidate_shown`, but not both.

The reviewed relevance report evaluates only completed labels with at least one
positive relevance section. This intentionally excludes no-relevant-shown
labels from positive-label ranking metrics while reporting their separate
bounded-candidate failure rate. Review labels and metrics remain private
evaluation artifacts and do not create trusted legal answer support.

## Operator Commands

Freeze a private snapshot:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-private-snapshot-manifest \
  --snapshot-name real_data_007_canonical_question_dataset_last_2000_v1 \
  --artifact data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1.jsonl \
  --artifact data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_manifest.json \
  --artifact data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_quality.json \
  --artifact data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_review_backlog.jsonl \
  --output data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_private_snapshot.json
```

Run the exact-reference benchmark against the current three-law preview:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-corpus-bounded-reference-benchmark \
  --dataset data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1.jsonl \
  --dataset-snapshot-manifest data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_private_snapshot.json \
  --legal-preview data/import_preview/legal_xml_preview_003_smoke.json \
  --law-code AufenthG \
  --law-code AsylG \
  --law-code BeschV \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_explicit_reference_cases.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_explicit_reference_summary.json
```

Emit semantic query/document embedding inputs:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-corpus-bounded-semantic-embedding-batch \
  --reference-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_explicit_reference_cases.jsonl \
  --legal-preview data/import_preview/legal_xml_preview_003_smoke.json \
  --law-code AufenthG \
  --law-code AsylG \
  --law-code BeschV \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_embedding_batch.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_embedding_batch_summary.json
```

Vectorize with the existing explicit live-service contour:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-embed-batch \
  --embedding-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_embedding_batch.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_external_vectors.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_vectorization_summary.json \
  --endpoint-url "${EMBEDDING_ENDPOINT_URL}" \
  --model-id "${EMBEDDING_MODEL_ID}" \
  --batch-size 16 \
  --timeout-seconds 240
```

The validated GTX 1060 operator profile currently exposes four effective
`5376`-token slots. Use HTTP batches of `16` for mixed-length legal fragments:
larger requests can exceed the client timeout even when every individual
fragment fits an effective server slot.

Evaluate the file vectors:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-corpus-bounded-semantic-benchmark \
  --reference-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_explicit_reference_cases.jsonl \
  --embedding-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_embedding_batch.jsonl \
  --external-vectors data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_external_vectors.jsonl \
  --vectorization-summary data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_vectorization_summary.json \
  --k 1 \
  --k 5 \
  --k 10 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_cases.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_summary.json
```

Build and open a bounded relevance-review sample:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-batch \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_cases.jsonl \
  --embedding-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_embedding_batch.jsonl \
  --max-cases 30 \
  --top-k 10 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-html \
  --review-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30.html \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30_html_summary.json
```

After exporting labels from the HTML, validate them and build reviewed
relevance metrics:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-labels-import \
  --review-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30.jsonl \
  --labels data/evaluation/tg_qa_retrieval_benchmark/tg_qa_retrieval_relevance_review_decisions.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30_labels.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30_labels_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-reviewed-relevance-report \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_cases.jsonl \
  --review-labels data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_review_30_labels.jsonl \
  --k 1 \
  --k 5 \
  --k 10 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_reviewed_relevance_cases.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_reviewed_relevance_summary.json
```
