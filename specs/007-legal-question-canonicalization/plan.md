# Implementation Plan: Legal Question Canonicalization And Cluster Coverage

**Branch**: `007-legal-question-canonicalization` | **Date**: 2026-05-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-legal-question-canonicalization/spec.md`

## Summary

Build an evaluation and retrieval-preparation layer on top of the completed 006
Telegram Q/A artifacts. The feature converts redacted raw Telegram question
candidates into reviewable canonical legal issue evidence, embeds and clusters
canonical issue representations instead of raw question text, measures coverage
against the reviewed 006 seed dataset, and separates broad `question_bank`
coverage from promoted reviewed evaluation cases.

This remains an artifact pipeline. It does not mutate Neo4j, create chatbot
answers, produce trusted legal facts, or allow LLM output to approve final
records by itself.

The legal-intent equivalence diagnostic extension remains inside 007 as an
optional evaluation layer, not a new feature branch and not a production
retrieval policy change. It documents and implements how canonical questions
can be transformed into structured legal-intent candidates, pair-review
benchmarks, and review-evidence pair decisions so embeddings can generate
candidates without becoming a legal-equivalence decision boundary.

## Technical Context

**Language/Version**: Python 3.12 in conda environment `chbot`
**Primary Dependencies**: Python stdlib JSON/filesystem/date handling, existing
006 artifact readers and evaluation patterns, existing retrieval embedding
profile/service contracts, pytest for default tests. Operator-managed LLM calls
remain optional batch contours rather than default dependencies. The optional
live operator runner should use provider SDK tool modes and Pydantic models for
structured output validation instead of custom structured output parsing where
the provider supports it. MiniMax-M2.7 verification prefers the
Anthropic-compatible SDK path and keeps OpenAI-compatible tool calls as a tested
fallback. Optional operator dependencies are `openai`, `anthropic`,
`langchain-core`, `langchain-openai`, and `langchain-anthropic`; `instructor`
is not part of the tracked operator dependency set because the current code uses
LangChain structured-output binding plus Pydantic directly.
**Context Tooling Boundary**: Mature prompt/context utilities such as
`langchain-core` prompt templates, example selectors, token counters, or
message-format helpers may be used in an explicit operator-managed LLM runner
when they reduce custom context-packing code. Agent frameworks, LangGraph
orchestration, autonomous chains, retrieval agents, chatbot inference, and
default-test dependencies remain out of scope for 007.
**Storage**: Redacted 006 generated artifacts under ignored `data/evaluation/`;
new generated canonicalization, embedding, cluster, coverage, review, question
bank, promotion, and optional legal-intent equivalence artifacts under ignored
`data/evaluation/` paths; no Neo4j writes.
**Testing**: pytest unit tests and offline CLI smoke tests with fixtures/fakes.
Live Jina, live LLM endpoints, paid APIs, remote notebooks, and Neo4j are
excluded from default tests and must be explicit integration or smoke contours.
**Target Platform**: Linux development/runtime environment with project CLI.
**Project Type**: Internal CLI/evaluation pipeline in `src/evaluation` with
entrypoints in `src/app/commands.py` when implementation is later requested.
**Performance Goals**: Support bounded fixture and operator-selected corpus
slices first; preserve streaming JSONL boundaries and manifest counts so the
current 006 full-corpus scale of 295k question candidates can be processed in
operator-managed batches.
**Constraints**: Preserve Telegram privacy and redaction; keep raw exports,
generated vectors, LLM outputs, review sheets, run logs, tunnel URLs, API keys,
and `.env` values out of tracked source; preserve asymmetric embedding prefix
semantics; do not create trusted answer support; do not hide missing evidence
behind fallback answers; minimize fields sent to external LLMs at each stage so
the operator does not pay for provenance, summaries, answers, or artifact paths
that the current judgment does not need.
**Scale/Scope**: Inputs are the 006 reviewed final dataset of 63 cases, the 006
full candidate pool of 295,303 candidates, and bounded legal-topic subsets such
as the prior 38,835-candidate `law_or_topic` coverage run. 007 treats raw
coverage numbers as diagnostic evidence until canonical issue clustering is
available.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Gate

- **Database Before Inference**: PASS. 007 is an evaluation/retrieval
  preparation feature and introduces no chatbot inference, answer synthesis, or
  fallback answers.
- **Structural Legal Graph**: PASS. 007 does not change legal graph schema,
  source imports, legal references, temporal metadata, checksums, or traversal
  contracts. Law-area and authority-context labels are review evidence only.
- **Embedding Contract**: PASS. Canonical question and issue-frame embeddings
  are query-like evaluation artifacts and preserve `Query: ` semantics plus
  embedding profile metadata. Legal-intent equivalence diagnostics treat
  embeddings as candidate-generation evidence only. Default tests use
  fixtures/fakes.
- **Review Boundary**: PASS. LLM canonicalization output is untrusted
  candidate evidence. It cannot approve clusters, create final evaluation
  cases, or produce legal answer text.
- **Reproducible Operations**: PASS. Planned runs produce manifests, policy or
  prompt versions, processed/skipped/failed counts, checkpoint/resume metadata,
  and explicit limitations.
- **Bulk Runtime Control**: PASS. Full-corpus LLM canonicalization is an
  operator-managed batch contour with explicit opt-in; model files, runtime
  binaries, credentials, and private outputs remain separate artifact classes.
- **Test Boundaries**: PASS. Unit and default smoke tests avoid Neo4j, live
  Jina, live LLMs, paid APIs, network services, and remote notebooks.
- **Minimal Trusted Surface**: PASS. The feature broadens evaluation coverage
  but does not broaden trusted graph support or inference behavior.

### Post-Design Gate

- **Database Before Inference**: PASS. Contracts explicitly keep question-bank
  and coverage artifacts separate from answer generation.
- **Structural Legal Graph**: PASS. Contracts define file artifacts only and no
  graph write path.
- **Embedding Contract**: PASS. Data model and contracts bind canonical
  embedding records to the existing profile metadata and query prefix semantics.
- **Review Boundary**: PASS. Canonicalization evidence, clusters, and coverage
  records are reviewable evidence; legal-intent candidates and pair decisions
  are also reviewable candidates. Promotion requires reviewed reference answer
  material.
- **Reproducible Operations**: PASS. Manifests and summaries record source
  artifact paths, policy versions, runtime contour, counts, failures, and known
  limitations.
- **Bulk Runtime Control**: PASS. Batch shape is project-owned; LLM/model
  runtime remains operator-managed and disabled by default.
- **Test Boundaries**: PASS. Quickstart and contracts mark live embeddings and
  live LLM canonicalization as explicit opt-in paths.
- **Minimal Trusted Surface**: PASS. `question_bank` entries can remain without
  final answers; only reviewed clusters with reviewed answer material can enter
  the reviewed evaluation dataset.

## Project Structure

### Documentation (This Feature)

```text
specs/007-legal-question-canonicalization/
├── plan.md
├── research.md
├── spec.md
├── data-model.md
├── quickstart.md
├── operator-runbook.md
├── contracts/
│   ├── canonicalization.md
│   ├── cluster-coverage.md
│   ├── legal-intent-equivalence.md
│   └── review-promotion.md
└── checklists/
    └── requirements.md
```

### Source Code

```text
src/
├── app/
│   └── commands.py
└── evaluation/
    └── tg_question_canonicalization.py

tests/
├── unit/
│   └── test_tg_question_canonicalization.py
├── smoke/
│   └── test_cli_offline.py
└── fixtures/
    └── tg_question_canonicalization/

data/
└── evaluation/
    ├── tg_qa_canonicalization/
    ├── tg_qa_canonical_embeddings/
    ├── tg_qa_issue_clusters/
    ├── tg_qa_question_bank/
    ├── tg_qa_canonical_coverage/
    ├── tg_qa_retrieval_benchmark/
    └── tg_qa_legal_intent_equivalence/
```

**Structure Decision**: Keep 007 in the evaluation layer and reuse 006
artifact patterns. Do not add graph, chatbot, orchestration, or production
inference packages. A separate `tg_question_canonicalization.py` module is the
planned implementation target because 006's `tg_qa_dataset.py` is already large
and 007 has distinct artifact contracts.

## Phase 0: Research Output

Research decisions are recorded in [research.md](research.md). No unresolved
`NEEDS CLARIFICATION` items remain.

## Phase 1: Design And Contracts

Design outputs:

- [data-model.md](data-model.md)
- [quickstart.md](quickstart.md)
- [operator-runbook.md](operator-runbook.md)
- [contracts/canonicalization.md](contracts/canonicalization.md)
- [contracts/cluster-coverage.md](contracts/cluster-coverage.md)
- [contracts/legal-intent-equivalence.md](contracts/legal-intent-equivalence.md)
- [contracts/private-snapshot-reference-benchmark.md](contracts/private-snapshot-reference-benchmark.md)
- [contracts/review-promotion.md](contracts/review-promotion.md)

## Operator LLM Run Contour

The live canonicalization contour is a separate operator workflow, not a
default test dependency. It uses two paid providers:

- OpenCode Go for Qwen3.6 Plus normalization and DeepSeek V4 Pro adjudication.
- MiniMax.io pay-as-you-go credits for MiniMax-M2.7 verification. MiniMax-M2.7
  is preferred over M2.5 because the direct MiniMax.io price is the same for the
  verifier workload.

The first live run must be a 50-record calibration slice. Full 5,000-record
processing starts only after the calibration slice proves that Qwen output,
local validation, MiniMax-M2.7 verification, and manual triage artifacts are
usable.

The planned operator tools are:

1. A calibration sampler for exactly 50 records from the emitted canonicalization
   batch.
2. A Qwen normalization runner that sends one record per request with only the
   redacted question, compact topic/law hints, answer status, quality flags, and
   the output schema requirements required for canonicalization. The runner must
   include the versioned 2-3 example prompt profile before the current record.
   It may use a mature context assembly library such as `langchain-core` if that
   keeps prompt construction, example selection, and token budgeting simpler and
   more auditable than custom glue.
3. A local validator/router that parses JSON, validates with the same Pydantic
   models used by `with_structured_output`, applies deterministic domain checks,
   and prepares risk queues without LLM calls.
4. A MiniMax-M2.7 verifier runner using Anthropic-compatible tool use first,
   with OpenAI-compatible tool calls or strict JSON as fallback.
5. A lightweight local review UI for human triage and edits. The first version
   is a dependency-light static HTML review-card export that reads generated
   JSONL data and exports explicit decisions; a stdlib-backed local UI can be
   added if browser download/export becomes too limiting.
   Streamlit/Gradio may be considered only if the added dependency clearly
   reduces implementation and review time.
6. A DeepSeek V4 Pro adjudication runner for the manually selected subset only.
7. A decision merger that emits `real_data_007_canonicalization_results.jsonl`
   for the existing import command.
8. A legal-intent pair judge runner for Phase 8 diagnostics. It consumes pair
   benchmark records and optional legal-intent candidates, returns structured
   `PairEquivalenceDecision` records, supports resume/retry/progress behavior,
   and remains review evidence only.

Manual review must be card-based, not raw JSON browsing. Review cards should
show only the source question, Qwen normalized fields, validation flags,
MiniMax verdict, optional DeepSeek verdict, and a compact decision/edit form.

## Implementation Order

1. Add 007 schemas and fixture validation for canonicalization evidence.
2. Emit canonicalization batch artifacts from 006 candidates.
3. Import canonicalization results idempotently with failure/backlog accounting.
4. Emit and import canonical embedding artifacts using existing embedding
   profile semantics.
5. Cluster canonical legal issue evidence with bounded merge rules and quality
   flags.
6. Measure reviewed 006 dataset coverage by canonical issue cluster.
7. Export question-bank review artifacts and import cluster review decisions.
8. Promote only reviewed clusters with reviewed reference answer material into
   evaluation dataset candidates.
9. Add offline unit/smoke coverage and boundary checks.
10. Run optional legal-intent equivalence diagnostics after accepted
    canonicalization artifacts exist: pair benchmark, legal-intent candidates,
    similarity+recos baseline, slot comparator, pair judge, review labels, and
    equivalence evaluation report.
11. Run corpus-bounded retrieval diagnostics over the private dataset: exact
    query-explicit reference resolution first, then file-based semantic
    retrieval metrics using the existing asymmetric embedding contract.

## Complexity Tracking

No constitution violations require justification.
