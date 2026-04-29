# Implementation Plan: Legal Graph Relationship Foundation

**Branch**: `003-legal-graph-relationships` | **Date**: 2026-04-27 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/003-legal-graph-relationships/spec.md`

## Summary

Build the relationship foundation for the German legal graph by upgrading
explicit legal-reference parsing from regex-only citation extraction to
context-aware, source-grounded relationship evidence. The implementation keeps
German legal XML structure authoritative, materializes section-level typed
legal edges only for reliably resolved references, records unresolved,
ambiguous, and out-of-scope references as audit evidence, and generates
new-graph relationship-quality artifacts. Microsoft GraphRAG and Neo4j GraphRAG
are design references only in this stage; sidecar execution is outside `003`
implementation scope and is not an acceptance requirement. A separate future
research feature may export bounded samples, compare framework proposals, and
review findings as research evidence only after the deterministic relationship
foundation is implemented.

## Technical Context

**Language/Version**: Python 3.12 in conda environment `chbot`  
**Primary Dependencies**: Neo4j official Python driver, pydantic and
pydantic-settings, pytest, Python stdlib JSON/filesystem tooling  
**Storage**: Neo4j for loaded source/legal/reference/edge state; JSON files for
relationship-quality artifacts and optional design evidence  
**Testing**: pytest unit tests for parsing/classification/artifact assembly;
marked Neo4j integration tests for graph writes, idempotent refresh, and scoped
verification; smoke tests for CLI artifact generation  
**Target Platform**: Linux operator workstation with optional live Neo4j and
optional local Jina-compatible embedding endpoint  
**Project Type**: CLI-oriented Python package for legal graph data operations
and artifact generation  
**Performance Goals**: Deterministic refresh and artifact generation for
bounded law-code scopes; repeated relationship-refresh passes must update
coverage without duplicating reference records or typed edges  
**Constraints**: No chatbot UX, no answer generation, no fallback answers, no
LLM proposition extraction, no trusted semantic candidates, no GraphRAG
inference, no legacy graph comparison, no legacy graph migration, no mandatory
framework sidecar execution, and no hidden live-service dependency in default
unit tests  
**Scale/Scope**: Selected German legal XML corpus slices already supported by
preview/load workflows, with mandatory classifier tests for `CITES`, `DEFINES`,
`APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO`; `EXCLUDES_IF`, `AMENDS`, and
`SUPERSEDED_BY` remain in taxonomy with documented source strategy and evidence
fields

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Database Before Inference**: Pass. The plan improves source-grounded graph
  state and relationship validation without adding chatbot inference, answer
  synthesis, or fallback responses.
- **Structural Legal Graph**: Pass. The plan directly touches legal references,
  typed legal edges, temporal/version evidence, section-level target policy,
  provenance, and bounded structural traversal readiness.
- **Embedding Contract**: Pass. Embedding semantics are unchanged. Embeddings
  remain retrieval indexes only, and default tests do not require a live
  embedding service.
- **Review Boundary**: Pass. LLM or framework outputs are not trusted graph
  writes in this feature. If produced outside acceptance, they remain research
  artifacts or candidate evidence.
- **Reproducible Operations**: Pass. Relationship-refresh passes are explicitly
  idempotent, versioned by classifier policy, and validated through
  relationship-quality artifacts.
- **Bulk Runtime Control**: Pass. Notebook, remote runtime, Microsoft GraphRAG,
  and Neo4j KG-builder sidecars remain external research surfaces for a future
  feature, not required core execution paths.
- **Test Boundaries**: Pass. Unit, integration, and smoke tests are separated;
  live Neo4j checks are opt-in and live embeddings are not needed for default
  validation.
- **Minimal Trusted Surface**: Pass. The first slice keeps section-level typed
  edges, rule-based deterministic classification, source evidence, and bounded
  relation coverage before semantic expansion or inference.

## Project Structure

### Documentation (this feature)

```text
specs/003-legal-graph-relationships/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── relationship-evidence.md
│   └── relationship-quality-artifact.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── app/
│   └── commands.py
├── graph/
│   ├── types.py
│   ├── writer.py
│   └── repositories.py
├── ingestion/
│   ├── legal_reference_parser.py
│   └── legal_structure_builder.py
├── retrieval/
│   └── legal_traversal.py
└── evaluation/
    └── load_cases.py

tests/
├── unit/
├── integration/
├── smoke/
└── fixtures/
```

**Structure Decision**: Reuse the existing CLI-oriented foundation packages and
extend only the modules that already own legal reference parsing, structural
graph assembly, Neo4j writes, scoped verification, and artifact generation. Do
not introduce a new service, chatbot path, notebook path, or framework-sidecar
runtime in this feature.

## Phase Plan

### Phase 0: Research and decisions

1. Lock the context-window reference parsing policy.
2. Lock section-level edge target policy and sub-section anchor evidence.
3. Lock primary-edge and secondary-signal representation.
4. Lock classifier coverage for the first acceptance slice.
5. Lock resolution-status taxonomy and idempotent refresh semantics.
6. Lock the boundary for Microsoft GraphRAG and Neo4j GraphRAG as design
   references only, with sidecar execution deferred to a separate future
   research feature.

### Phase 1: Design and contracts

1. Define `LegalReference` evidence fields, including context evidence,
   classifier version, sub-section anchor, secondary signals, and resolution
   status.
2. Define relationship classifier policy and source strategy for deferred
   taxonomy relations.
3. Define idempotent relationship-refresh pass semantics.
4. Define graph write contract for section-level typed edges.
5. Define relationship-quality artifact contract.
6. Define quickstart workflow and validation commands.
7. Update Codex agent context with current feature guidance.

### Phase 2: Implementation sequencing

1. Add offline parser fixtures for mandatory relation types.
2. Extend reference parser to emit context evidence, classifier version,
   primary relation type, secondary signals, sub-section anchors, and target
   candidates.
3. Extend structural graph builder to resolve targets and assign
   `resolved`, `unresolved`, `ambiguous`, or `out_of_scope` status.
4. Extend graph writer/repository behavior to materialize at most one primary
   section-level typed edge per `LegalReference`.
5. Add idempotent relationship-refresh command path.
6. Add relationship-quality artifact assembly and CLI writer.
7. Add unit, smoke, and marked Neo4j integration coverage.

## Complexity Tracking

No constitution violations require justification.
