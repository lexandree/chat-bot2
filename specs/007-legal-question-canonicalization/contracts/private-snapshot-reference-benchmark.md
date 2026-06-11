# Contract: Private Dataset Snapshot And Explicit-Reference Benchmark

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
