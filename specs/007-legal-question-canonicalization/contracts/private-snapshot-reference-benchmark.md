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
as query-explicit silver labels and also accepts separately curated checked
targets. It has three explicit steps:

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

Metrics are separated by target evidence:

- `all_expected_targets` covers every supplied expected target;
- `query_explicit_silver_targets` covers references copied from canonical
  questions and therefore remains a weak silver diagnostic;
- `silver_all_query_explicit_targets` remains as a deprecated compatibility
  alias for `query_explicit_silver_targets`;
- `curated_checked_targets` covers independently selected primary relevant
  sections for coherent clean questions;
- `reviewed_accepted_targets` covers targets accepted through a separate review
  file.

An optional private JSONL review file may provide
`benchmark_case_id`, `reference_correctness_decision` (`accept`, `exclude`, or
`uncertain`), and `decision_reason`.

Missing query or document vectors remain visible and count as retrieval
failures. Semantic metrics do not establish legal-reference correctness,
answer correctness, completeness, or trusted support. They measure
query-explicit citation recovery, not general legal relevance: an explicit
reference may describe the user's status or premise rather than the section
that answers the question.

## Human-Reviewed Retrieval Relevance Diagnostic

Query-explicit citation recovery is not a reliable proxy for legal relevance.
This bounded relevance-review contour is a later stress/backlog diagnostic over
real canonicalization output. It is not the clean initial retrieval benchmark:
real records may contain ambiguous premises, contradictions, inferred
references, multiple issues, or canonicalization defects. Findings from this
contour should improve general retrieval, reference-resolution, reranking, and
quality-gating methods. They must not trigger one-off canonicalizer prompt rules
for each difficult record.

The clean initial retrieval benchmark is a separate curated artifact. Its
questions must be coherent, single-issue, free of known factual or legal
contradictions, and of moderate difficulty. Its expected relevant sections must
be independently checked before metrics are calculated.

Retrieval evaluation proceeds in three distinct stages:

1. The clean curated benchmark isolates basic retrieval behavior. Failures at
   this stage justify changes to general retrieval methods, not prompt examples
   for individual questions.
2. The real-record stress/backlog diagnostic groups failures by recurring
   mechanism, such as reference-role confusion, missing legal terminology,
   mixed issues, or absent corpus coverage.
3. Later improvements may add general exact-reference features, legal-keyword
   expansion, reranking, typed traversal, and quality gates. A change is kept
   only when it improves a cumulative benchmark rather than one isolated
   record.

The bounded relevance-review contour samples eligible semantic cases
deterministically across expected sections and presents:

- the canonical question;
- the redacted source question when the private dataset is supplied;
- the semantic top candidates with legal source text;
- the query-explicit target, added separately when absent from the top
  candidates;
- other section references in the same canonical question when their omitted
  law code can be inherited unambiguously from exactly one explicitly named law
  in that question.

Same-question inherited references are review candidates, not automatic silver
targets. The global graph reference parser remains unchanged because implicit
law-code inheritance is too risky for graph relationship creation.

When source text is available, the review card flags a query-explicit target
law code that was introduced during canonicalization rather than named in the
source. This is a review warning, not an automatic error: inferred law codes may
be correct, but they require scrutiny before citation-based evaluation.

The reviewer may mark multiple shown sections as relevant, mark that no
relevant candidate is shown, add known relevant sections from the selected
corpus that were absent from the shown candidates, and classify the
query-explicit reference as `answer_support`, `status_context`, `incorrect`, or
`uncertain`. Completed review labels require either at least one relevant shown
section or `no_relevant_candidate_shown`, but not both. Reviewer-added relevant
sections may coexist with `no_relevant_candidate_shown`; they record the
sections that retrieval failed to show.

The reviewer may also set `rerun_after_corpus_expansion` to a list of law
codes, for example `["VwVfG"]`. This is an independent routing marker: it does
not alter the current relevance decision or metrics, and it identifies the
question for a later repeat after the named corpus scope is available. The
review UI provides a `VwVfG` shortcut, a generic comma-separated law-code
input, and a `corpus rerun` filter.

The reviewed relevance report evaluates only completed labels with at least one
positive relevance section. This intentionally excludes no-relevant-shown
labels from positive-label ranking metrics while reporting their separate
bounded-candidate failure rate. Review labels and metrics remain private
evaluation artifacts and do not create trusted legal answer support.
Reviewer-added sections outside the recorded ranking count as retrieval misses;
the report does not invent their unknown rank.

## Clean Curated Retrieval Baseline

The tracked, publication-safe clean baseline input is:

```text
specs/007-legal-question-canonicalization/clean-retrieval-reference-cases.jsonl
```

Version `v1` contains 24 synthetic/curated Russian questions: eight each for
`AufenthG`, `AsylG`, and `BeschV`. Every question:

- contains one legal question and no explicit section number;
- is coherent and free of a known contradictory premise;
- has one independently checked primary relevant section;
- is derived from the selected legal preview, not from private Telegram text;
- uses `target_evidence_type=curated_checked`.

The initial local Jina retrieval result was:

- Recall@1: `0.666667`;
- Recall@5: `0.875`;
- Recall@10: `0.916667`;
- MRR: `0.745068`.

These metrics establish a clean retrieval baseline. They do not prove answer
correctness or that the selected primary section is the only relevant section.
Changes should be retained only when they improve cumulative clean and
stress/backlog evidence rather than one question.

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

Build and open a bounded real-record stress/backlog relevance-review sample:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-batch \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_cases.jsonl \
  --embedding-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_embedding_batch.jsonl \
  --dataset data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1.jsonl \
  --max-cases 30 \
  --top-k 10 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-html \
  --review-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30.html \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30_html_summary.json
```

Build the clean curated review with the local helper:

```bash
bash scripts/evaluation/run_007_clean_curated_retrieval.sh full
```

The helper reuses existing document vectors only when their run completed
without failures, used the requested embedding model, and contains every
document item required by the current legal-preview batch. It always generates
fresh query vectors for the clean questions.

After exporting labels from the HTML, validate them and build reviewed
relevance metrics:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-labels-import \
  --review-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30.jsonl \
  --labels data/evaluation/tg_qa_retrieval_benchmark/tg_qa_retrieval_relevance_review_decisions.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30_labels.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30_labels_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-reviewed-relevance-report \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_semantic_cases.jsonl \
  --review-labels data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_relevance_stress_backlog_30_labels.jsonl \
  --k 1 \
  --k 5 \
  --k 10 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_reviewed_relevance_cases.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_reviewed_relevance_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-retrieval-mechanism-report \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_semantic_cases.jsonl \
  --review-labels data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30_labels.jsonl \
  --sample-limit 5 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_mechanisms.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_mechanisms_summary.json
```

The mechanism report is offline and deterministic. It groups only completed
human-reviewed labels into observable retrieval signals such as wrong-law
top-1, relevant evidence below top-1/top-5, missing bounded candidates,
multi-section or multi-law support, explicit-reference role mismatch, and
required corpus expansion. These groups are diagnostic evidence for deciding
which general retrieval change to test; they are not trusted legal conclusions.

### Cumulative Retrieval Evidence Gate

Any retained general retrieval-method change, including exact-reference
expansion, legal-keyword expansion, reranking, typed traversal, route hints, or
quality gates, must report both:

- the clean curated 24-case reviewed baseline; and
- the latest human-reviewed real-record stress/backlog report.

Single-record improvements are allowed as diagnostic experiments only. A change
is not retained as a general method unless the cumulative evidence shows that it
does not trade clean-case behavior for stress-case behavior, or vice versa.

The current four-law stress review is based on
`tg_007_retrieval_relevance_review_labels4.jsonl`. It imported 30/30 labels
with zero validation failures, containing 28 reviewed records and 2 skipped
records. The reviewed positive-label report evaluated 18 records with
Hit@10 `0.777778`, Recall@10 `0.759259`, and MRR `0.491425`. The mechanism
report found 21 records with retrieval-failure signals, including 11 records
with no relevant candidate shown and 10 records where relevant evidence was
below top-1. Ten records also carry corpus-expansion markers for missing laws:
`AsylbLG`, `AufenthV`, `BGB`, `FeV`, `SGB_5`, and `SGB_12`.

For the current four-law stress review, open
`data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30.html`.
After exporting its labels, run:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-retrieval-relevance-review-labels-import \
  --review-batch data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30.jsonl \
  --labels data/evaluation/tg_qa_retrieval_benchmark/tg_007_retrieval_relevance_review_labels.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30_labels.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30_labels_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-reviewed-relevance-report \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_semantic_cases.jsonl \
  --review-labels data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30_labels.jsonl \
  --k 1 --k 5 --k 10 \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_reviewed_cases.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_reviewed_summary.json

PYTHONPATH=src python -m app evaluation tg-qa-retrieval-mechanism-report \
  --semantic-cases data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_semantic_cases.jsonl \
  --review-labels data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_review_30_labels.jsonl \
  --output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_mechanisms.jsonl \
  --summary-output data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_mechanisms_summary.json
```
