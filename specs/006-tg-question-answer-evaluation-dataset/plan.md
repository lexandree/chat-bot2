# Implementation Plan: Telegram Q/A Evaluation Dataset

**Branch**: `006-tg-question-answer-evaluation-dataset` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-tg-question-answer-evaluation-dataset/spec.md`

## Summary

Build a reproducible evaluation-dataset pipeline from private Telegram exports.
The feature extracts redacted Q/A candidates, preserves direct and
admin-triggered wiki-bot answer evidence, emits embedding batches, imports
external embedding records, runs similarity and semantic clustering, selects the
latest usable answer only inside stable semantic Q/A clusters, and routes dirty
or conflicting cases to optional one-time LLM analysis or manual review.

The implementation remains an evaluation pipeline, not graph enrichment and not
chatbot inference. All durable outputs are JSON/JSONL artifacts under ignored
`data/evaluation/` paths. LLM output is review evidence only.

## Technical Context

**Language/Version**: Python 3.12 in conda environment `chbot`  
**Primary Dependencies**: Python stdlib JSON/filesystem/date handling, existing `src/retrieval/*embedding*` contract types, pydantic only if needed by existing project patterns, pytest for tests; LangChain/LangGraph and live model clients are optional operator tooling, not default dependencies.  
**Storage**: Private Telegram exports under ignored `data/tg/`; generated candidate, embedding, similarity, cluster, LLM, review, and final dataset artifacts under ignored `data/evaluation/`; no Neo4j writes.  
**Testing**: pytest unit and offline smoke tests with fixtures/fakes; live Jina,
live LLM, Kaggle, Cloudflare Tunnel, and Neo4j are excluded from default tests.  
**Target Platform**: Linux development/runtime environment with project CLI.  
**Project Type**: Internal CLI/evaluation pipeline in `src/evaluation` and `src/app/commands.py`.  
**Performance Goals**: Deterministic extraction over the current six-export
Telegram corpus scale observed in smoke testing, approximately 974k processed
messages, with bounded candidate limits for local iteration and streaming JSONL
artifact boundaries for later batch stages.  
**Constraints**: Preserve Telegram privacy by redacting emitted text; never
commit raw chat exports, generated vectors, model output, tunnel URLs, secrets,
or `.env` values; preserve asymmetric embedding prefixes; do not mutate graph
state; do not create trusted legal facts; keep LLM output review-gated.  
**Scale/Scope**: Six large local Telegram exports, known wiki-bot catalog,
candidate extraction already proven on a bounded 500-candidate smoke; follow-on
pipeline must support staged processing through embeddings, clustering, LLM
review evidence, manual review, and final dataset build.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Gate

- **Database Before Inference**: PASS. 006 creates an evaluation dataset and
  does not introduce chatbot inference, answer synthesis, or fallback answers.
- **Structural Legal Graph**: PASS. 006 does not change legal graph schema,
  source import, legal references, temporal contracts, checksums, or typed
  traversal. Legal law-code labels are candidate metadata only.
- **Embedding Contract**: PASS. Embedding batches preserve `Query: ` for
  question text and `Document: ` for answer and Q/A-pair text, reusing the
  existing Jina-compatible embedding contract. Default tests use fixtures/fakes.
- **Review Boundary**: PASS. Telegram answers, wiki-bot answers, clusters, and
  LLM labels are evaluation evidence, not legal truth. LLM output cannot approve
  final records by itself.
- **Reproducible Operations**: PASS. Pipeline outputs run artifacts, summaries,
  manifests, policy versions, prompt versions, and counts; generated artifacts
  remain outside tracked source.
- **Bulk Runtime Control**: PASS. Optional LLM analysis is operator-managed via
  a separately started model server and temporary tunnel. The project owns batch
  schemas, result import, and artifact validation.
- **Test Boundaries**: PASS. Unit/smoke tests are offline by default; live Jina,
  Neo4j, Kaggle, Cloudflare Tunnel, and LLM service checks are separate opt-in
  operator validations.
- **Minimal Trusted Surface**: PASS. The feature creates measurement data for
  later retrieval work and does not expand trusted graph support.

### Post-Design Gate

- **Database Before Inference**: PASS. Contracts explicitly mark final dataset
  records as evaluation artifacts, not trusted answers.
- **Structural Legal Graph**: PASS. No graph mutation contract exists in 006.
- **Embedding Contract**: PASS. `data-model.md`, `pipeline.md`, and
  `quickstart.md` bind 006 to the existing Jina retrieval semantics.
- **Review Boundary**: PASS. `contracts/llm-analysis.md` forbids LLM-only final
  approval and records model/runtime metadata for review.
- **Reproducible Operations**: PASS. The LLM manifest and dataset manifest
  define run-level provenance, counts, versions, and limitations.
- **Bulk Runtime Control**: PASS. Gemma/Qwen model choices are runtime inputs;
  model files, binaries, tunnel URLs, and credentials stay out of source.
- **Test Boundaries**: PASS. `tasks.md` keeps fixture LLM and embedding records
  in the default test path.
- **Minimal Trusted Surface**: PASS. Dirty or unresolved chat data can remain
  `uncertain`; there is no forced promotion into the dataset.

## Project Structure

### Documentation (This Feature)

```text
specs/006-tg-question-answer-evaluation-dataset/
├── plan.md
├── research.md
├── spec.md
├── pipeline.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── final-dataset.md
│   └── llm-analysis.md
└── tasks.md
```

### Source Code

```text
src/
├── app/
│   └── commands.py
└── evaluation/
    └── tg_qa_dataset.py

tests/
├── unit/
│   └── test_tg_qa_dataset.py
├── smoke/
│   └── test_cli_offline.py
└── fixtures/
    ├── tg_sample_export/
    └── tg_wiki_bot_catalog_sample.json

data/
├── tg/                         # ignored private input exports
└── evaluation/                 # ignored generated artifacts
```

**Structure Decision**: Keep 006 in `src/evaluation` with CLI entrypoints in
`src/app/commands.py`. Do not create graph, chatbot, or production inference
packages. Add small focused modules only when the similarity, clustering,
review, or final-dataset stages become too large for `tg_qa_dataset.py`.

## Phase 0: Research Output

Research decisions are recorded in [research.md](research.md). All planning
unknowns are resolved without adding live-service dependencies to the default
path.

## Phase 1: Design And Contracts

Design outputs:

- [data-model.md](data-model.md)
- [pipeline.md](pipeline.md)
- [quickstart.md](quickstart.md)
- [contracts/final-dataset.md](contracts/final-dataset.md)
- [contracts/llm-analysis.md](contracts/llm-analysis.md)

Existing design artifacts were updated rather than replaced because candidate
extraction and initial batch emission already exist.

## Implementation Order

1. Finish embedding-record import and fixture embedding validation.
2. Implement local similarity search over imported/fixture vectors.
3. Implement semantic clustering with bounded components and quality flags.
4. Implement cluster selection and temporal drift classification.
5. Implement LLM result and run-manifest import as review evidence only.
6. Implement manual review queue/import.
7. Build final dataset artifacts and quality report.
8. Run real-data extraction smoke and fixture-based downstream pipeline smoke.

## Complexity Tracking

No constitution violations require justification.
