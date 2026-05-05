# Implementation Plan: Structural Graph Workflows With Coverage Boundaries

**Branch**: `005-structural-graph-workflows` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/home/admin2/chat_bot2/specs/005-structural-graph-workflows/spec.md`

## Summary

Add read-only structural graph workflows that let operators inspect resolved
legal neighborhoods and bounded law-code scope overviews before full corpus
coverage closure. The workflows use trusted resolved typed legal edges only,
preserve section, reference, and source provenance, and expose
`missing_target_in_corpus` references as explicit coverage-boundary stops.
Generated workflow artifacts are deterministic JSON reports; this feature does
not infer missing edges, expand the corpus, create semantic candidates, or
introduce answer generation.

## Technical Context

**Language/Version**: Python 3.12 in conda environment `chbot`  
**Primary Dependencies**: Neo4j official Python driver, pydantic/pydantic-settings, pytest, Python stdlib JSON/filesystem tooling  
**Storage**: Neo4j graph of record for source/legal/reference/edge state; generated JSON artifacts under `data/structural_workflows/`  
**Testing**: pytest unit, smoke, and gated Neo4j integration tests  
**Target Platform**: Linux workstation/server with local project checkout and configured Neo4j for live checks  
**Project Type**: CLI-backed database foundation for a legal graph system  
**Performance Goals**: Deterministic traversal and overview collection over selected scopes; bounded depth, fanout, node, and edge limits; stable ordering for repeated runs on unchanged graph state  
**Constraints**: Read-only trusted graph workflows; no default unit dependency on live Neo4j, live Jina, paid APIs, remote notebooks, GraphRAG sidecars, or private corpora; no answer generation or semantic extraction  
**Scale/Scope**: Initial real-data smoke scope is `AufenthG`, `AsylG`, and `BeschV` with 1666 resolved typed edges and 138 known `missing_target_in_corpus` boundary references; workflows must remain bounded for larger law-code scopes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Database Before Inference**: PASS. The plan adds structural workflow
  artifacts over the graph of record and does not add chatbot inference,
  answer synthesis, or fallback answers.
- **Structural Legal Graph**: PASS. The plan directly uses legal sections,
  source fragments, legal references, typed legal edges, source/target status,
  unresolved-reason evidence, traversal bounds, and provenance metadata.
- **Embedding Contract**: PASS. Embeddings are not changed and are not required
  for default unit tests or workflow generation.
- **Review Boundary**: PASS. LLM-derived candidates are out of scope; workflow
  outputs must not create or promote generated propositions, claims, summaries,
  or trusted semantic candidates.
- **Framework-First GraphRAG**: PASS. GraphRAG retrieval/inference frameworks are
  not introduced because 005 is a structural workflow slice, not semantic
  GraphRAG inference. Borrowing established Cypher traversal/reporting patterns
  remains allowed inside the project-specific provenance and boundary contract.
- **Reproducible Operations**: PASS. Workflows are read-only with explicit
  artifact outputs, stable ordering, visible boundary stops, truncation
  metadata, and repeatable parameters.
- **Bulk Runtime Control**: PASS. Notebook and remote-runtime workflows are not
  introduced. Generated workflow artifacts remain operator-visible files.
- **Test Boundaries**: PASS. Unit tests use fixtures; live Neo4j checks are
  gated integration tests; embeddings and remote services are not required.
- **Minimal Trusted Surface**: PASS. The workflow surface uses exact resolved
  legal-reference edges and bounded typed traversal, while missing targets are
  explicit boundaries rather than inferred links.

## Project Structure

### Documentation (this feature)

```text
specs/005-structural-graph-workflows/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── structural-neighborhood-artifact.md
│   └── structural-workflow-cli.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── app/
│   └── commands.py
├── graph/
│   ├── repositories.py
│   └── types.py
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

**Structure Decision**: Extend the existing CLI-backed repository layout. Keep
graph reads in `src/graph/repositories.py`, traversal policy in
`src/retrieval/legal_traversal.py`, artifact assembly in
`src/evaluation/load_cases.py`, and command wiring in `src/app/commands.py`.
Do not add a new service layer unless tasks reveal duplication that cannot be
kept local. Implementation tasks must add the generated artifact ignore rule
for `data/structural_workflows/*.json` before live workflow artifacts are
created.

## Complexity Tracking

No constitution violations or justified complexity exceptions.

## Phase 0: Research Summary

Research resolves the following planning choices:

- workflow read/write semantics
- traversal policy and artifact granularity
- coverage-boundary stop semantics
- CLI and artifact contract shape
- validation strategy for default and live tests

See [research.md](./research.md).

## Phase 1: Design Summary

Design artifacts generated for this feature:

- [data-model.md](./data-model.md): workflow request, structural workflow
  artifact, resolved traversal edge, coverage boundary stop, and quality summary
  models
- [contracts/structural-neighborhood-artifact.md](./contracts/structural-neighborhood-artifact.md):
  deterministic JSON artifact contract
- [contracts/structural-workflow-cli.md](./contracts/structural-workflow-cli.md):
  operator command contract
- [quickstart.md](./quickstart.md): validation and smoke workflow

## Post-Design Constitution Check

- **Database Before Inference**: PASS. Contracts describe structural JSON
  artifacts only; answer generation remains forbidden.
- **Structural Legal Graph**: PASS. Data model preserves legal section,
  legal-reference, relation, status, and provenance identifiers.
- **Embedding Contract**: PASS. Design explicitly excludes embeddings from the
  workflow contract.
- **Review Boundary**: PASS. Contracts forbid semantic propositions,
  generated legal conclusions, and trusted LLM candidates.
- **Framework-First GraphRAG**: PASS. The design keeps 005 pre-inference while
  allowing established Neo4j/Cypher traversal and reporting patterns under the
  structural workflow contract.
- **Reproducible Operations**: PASS. Artifact contracts require workflow
  parameters, stable ordering, boundary counts, truncation metadata, and
  provenance completeness.
- **Bulk Runtime Control**: PASS. No notebook or remote runtime dependency is
  introduced.
- **Test Boundaries**: PASS. Quickstart separates unit/smoke checks from live
  Neo4j integration checks.
- **Minimal Trusted Surface**: PASS. Only resolved typed edges are traversed;
  missing targets remain coverage-boundary stops.
