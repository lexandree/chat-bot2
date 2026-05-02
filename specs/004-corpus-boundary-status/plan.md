# Implementation Plan: Corpus Boundary And Source Status Hardening

**Branch**: `004-corpus-boundary-status` | **Date**: 2026-04-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-corpus-boundary-status/spec.md`

## Summary

Harden the legal graph foundation so the corpus distinguishes active and
inactive source units, assigns explicit unresolved reasons to legal references,
separates resolved inactive target status from unresolved reasons, and produces
deterministic corpus-quality and corpus-readiness artifacts for structural
output. The relationship-quality artifact remains a non-breaking extension of
the existing baseline shape. Keep the feature database-first, keep batching out
of scope, and do not introduce semantic extraction, answer generation, or
embedding requirements for this stage.

## Technical Context

**Language/Version**: Python 3.12 in conda environment `chbot`  
**Primary Dependencies**: Neo4j official Python driver, `pydantic`,
`pydantic-settings`, `pytest`, Python stdlib filesystem/HTTP tooling  
**Storage**: Neo4j graph of record plus JSON file artifacts under `data/` and
`specs/` documentation outputs  
**Testing**: `pytest` unit, integration, and smoke suites; live Neo4j marked
separately  
**Target Platform**: Linux workstation/server with local Neo4j and local file
system access  
**Project Type**: CLI-backed database foundation for a legal graph system  
**Performance Goals**: Deterministic artifact generation and repeatable
idempotent refresh behavior on selected corpus slices  
**Constraints**: Offline default unit tests; no chatbot inference; no answer
synthesis; no live Jina dependency for unit tests; structural output only  
**Scale/Scope**: Selected German legal XML corpus slices such as `AufenthG`,
`AsylG`, and `BeschV`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Database Before Inference**: Pass. This feature stays in the structural
  database layer and does not add chatbot inference, answer synthesis, or demo
  fallback behavior.
- **Structural Legal Graph**: Pass. The feature touches source status,
  legal-reference resolution reasons, provenance/version metadata, and
  structural output artifacts.
- **Embedding Contract**: Pass. The feature does not change embedding
  semantics and does not require live embeddings in default unit tests.
- **Review Boundary**: Pass. No LLM-derived candidates are promoted to trusted
  graph state here.
- **Reproducible Operations**: Pass. The feature preserves idempotent refresh
  semantics and deterministic artifact output.
- **Bulk Runtime Control**: Pass. Batching is explicitly deferred to a later
  research/optimization follow-up.
- **Test Boundaries**: Pass. Unit tests stay offline; live Neo4j remains an
  explicit integration path.
- **Minimal Trusted Surface**: Pass. The scope is exact reference resolution,
  inactive-source detection, and bounded structural artifacts.

## Project Structure

### Documentation (this feature)

```text
specs/004-corpus-boundary-status/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── app/
├── graph/
├── ingestion/
├── retrieval/
├── enrichment/
├── review/
└── evaluation/

tests/
├── unit/
├── integration/
├── smoke/
└── fixtures/
```

**Structure Decision**: Reuse the existing CLI, ingestion, graph, evaluation,
and tests layout. This feature is documentation-led at planning time and will
extend the current structural foundation modules rather than introduce a new
subsystem.

## Post-Design Constitution Check

*GATE: Re-checked after Phase 1 design artifacts.*

- **Database Before Inference**: Pass. Design artifacts remain structural and do
  not introduce chatbot inference, answer synthesis, GraphRAG generation, or demo
  fallback behavior.
- **Structural Legal Graph**: Pass. Contracts and data model extend source
  status, reference evidence, and corpus-readiness artifacts without adding
  semantic nodes.
- **Embedding Contract**: Pass. The feature keeps embeddings and vector indexes
  out of scope and does not require live embedding services for unit tests.
- **Review Boundary**: Pass. No LLM-derived candidates or trusted semantic
  propositions are introduced.
- **Reproducible Operations**: Pass. Planned refresh and artifact workflows keep
  idempotency, visible failure, and deterministic JSON output.
- **Bulk Runtime Control**: Pass. Batched refresh optimization remains deferred
  to a later research/optimization follow-up.
- **Test Boundaries**: Pass. Unit tests remain offline; live Neo4j checks are
  integration/smoke-only.
- **Minimal Trusted Surface**: Pass. The trusted surface remains source/legal
  structure, exact reference evidence, typed relationships, and structural
  artifacts.
