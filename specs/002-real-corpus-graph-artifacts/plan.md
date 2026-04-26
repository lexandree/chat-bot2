# Implementation Plan: Real Corpus Graph Artifacts

**Branch**: `002-real-corpus-graph-artifacts` | **Date**: 2026-04-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-real-corpus-graph-artifacts/spec.md`

## Summary

Extend the legal graph foundation from fixture-backed validation to real corpus
coverage and file-based comparison artifacts. The implementation will keep
preview data, graph state, snapshot artifacts, and comparison reports as
distinct concepts: preview is a file artifact, the loaded corpus lives in Neo4j,
and snapshots/comparison outputs are file artifacts generated from graph state.
The legacy AufenthG baseline graph snapshot is treated as read-only comparison
evidence, not as a migration source.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Neo4j official Python driver, pydantic/pydantic-settings, pytest, stdlib JSON/filesystem tooling  
**Storage**: Neo4j for loaded graph state; JSON files for preview, snapshot, and comparison artifacts  
**Testing**: pytest unit tests, marked integration tests, marked smoke tests  
**Target Platform**: Linux operator workstation with optional live Neo4j and local/remote embedding endpoints  
**Project Type**: CLI-oriented Python package for graph data operations and artifact generation  
**Performance Goals**: Deterministic artifact generation for bounded corpus slices; repeated preview and snapshot runs must produce stable outputs when inputs and graph state are unchanged  
**Constraints**: No chatbot UX, no LLM extraction, no answer generation, no hidden live-service dependency in unit tests, no migration of old graph data, no trust promotion from baseline comparison  
**Scale/Scope**: Selected German legal corpus slices, plus one legacy AufenthG baseline graph snapshot

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Database Before Inference**: Pass. The feature is about real corpus coverage, snapshot artifacts, and comparison. It does not add inference, answer synthesis, or fallback answers.
- **Structural Legal Graph**: Pass. The feature touches source provenance, legal structure, reference coverage, and temporal/legal scope reporting.
- **Embedding Contract**: Pass. Embedding semantics are unchanged; existing profile metadata is reported when present and unit validation stays offline.
- **Review Boundary**: Pass. No LLM-derived candidates, approval flow, or trusted promotion are introduced.
- **Reproducible Operations**: Pass. Preview, load, verify, delete, snapshot, and comparison workflows are treated as deterministic or explicitly scoped operations.
- **Bulk Runtime Control**: Pass. Notebook or remote-runtime workflows remain out of scope for this feature.
- **Test Boundaries**: Pass. Unit, integration, and smoke validation remain separated; live dependencies are explicit.
- **Minimal Trusted Surface**: Pass. The feature keeps exact legal-reference and bounded comparison workflows centered on the legacy AufenthG baseline graph snapshot.

## Project Structure

### Documentation

```text
specs/002-real-corpus-graph-artifacts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── artifacts.md
```

### Source Code

```text
src/
├── app/
├── graph/
├── ingestion/
├── retrieval/
├── review/
└── evaluation/

tests/
├── unit/
├── integration/
├── smoke/
└── fixtures/
```

**Structure Decision**: Reuse the existing `src/app/`, `src/graph/`,
`src/ingestion/`, `src/retrieval/`, `src/review/`, and `src/evaluation/`
packages together with `tests/unit/`, `tests/integration/`, `tests/smoke/`, and
`tests/fixtures/`. Add only the feature-specific artifact and comparison logic
needed to keep preview, graph state, snapshot, and comparison report
responsibilities separate.

## Complexity Tracking

No constitution violations require justification.
