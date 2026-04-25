# Implementation Plan: German Legal Graph Foundation

**Branch**: `001-legal-graph-foundation` | **Date**: 2026-04-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-legal-graph-foundation/spec.md`

## Summary

Build the database-first foundation for a German legal graph knowledge base:
typed settings, a real Neo4j 5/Aura-compatible driver client, idempotent schema
bootstrap, deterministic legal XML import preview, structural legal graph build,
load/verify/delete workflows, local-only Jina-compatible graph-write embeddings,
exact legal-reference resolution, bounded typed traversal, and tests with
offline unit boundaries. `export/source_snapshot` is reference evidence only;
implementation must be clean and must not import the old recording facade or
chatbot/inference flow.

## Technical Context

**Language/Version**: Python 3.11+ in conda environment `chbot`  
**Primary Dependencies**: Neo4j official Python driver (`neo4j>=5.18`), `pydantic` plus `pydantic-settings` for typed env configuration, pytest, Python stdlib HTTP client for the Jina-compatible local embedding endpoint unless implementation evidence justifies a narrow HTTP dependency  
**Storage**: Neo4j 5.18+ / Aura-compatible graph of record with stable constraints and vector indexes; local fixture files for unit tests and legal XML preview inputs  
**Testing**: pytest; default unit tests offline; marked integration tests for live Neo4j and local-only Jina-compatible embeddings; smoke tests for operator contours  
**Target Platform**: Linux development/runtime under conda `chbot`; Neo4j/Aura and local Jina-compatible embedding service are operator-managed for live checks  
**Project Type**: Python package with operator command surfaces, not a web app, chatbot, or answer-generation service  
**Performance Goals**: Deterministic preview output for unchanged corpus inputs; idempotent schema/load behavior across repeated runs; fail-fast embedding writes before partial graph mutation when local Jina is unavailable or returns invalid vectors; bounded traversal never exceeds configured relation/depth/fanout/node limits  
**Constraints**: No chatbot UX, no GraphRAG answer generation, no LLM proposition extraction, no generic graph database abstraction, no wholesale source snapshot import, no live Neo4j/Jina dependency in default unit tests, no secrets or private runtime artifacts in tracked files  
**Scale/Scope**: Foundation slice for law and official guidance corpora, initially loaded and validated by law-code scope; schema includes future candidate/review placeholders but not extraction/review workflow behavior

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Database Before Inference**: PASS. The plan excludes chatbot UX, answer
  synthesis, fallback answers, and GraphRAG generation. It validates database,
  embedding index, and structural retrieval behavior first.
- **Structural Legal Graph**: PASS. Source documents/fragments, legal acts,
  legal sections, legal fragments, legal references, unresolved references,
  temporal metadata, and bounded traversal are explicit scope.
- **Embedding Contract**: PASS. The plan preserves `Query: ` and `Document: `
  prefixes, 1024-dimensional normalized Jina-compatible profile metadata, and
  local-only graph-write embeddings. Unit tests stay offline.
- **Review Boundary**: PASS. Candidate/review schema placeholders are included
  for future untrusted outputs, but LLM extraction, review task workflow, and
  promotion behavior are out of scope.
- **Reproducible Operations**: PASS. Schema bootstrap, preview, load, embed,
  verify, delete, and traversal workflows must report scope, counts, metadata,
  and visible failures with idempotent or explicit write semantics.
- **Bulk Runtime Control**: PASS. Notebook/bulk execution is not implemented in
  this feature. Exported notebook ideas remain reference only.
- **Test Boundaries**: PASS. Unit tests validate pure policy/parsing/schema
  assembly without live services. Live Neo4j/Jina checks are marked integration
  or smoke tests.
- **Minimal Trusted Surface**: PASS. Initial scope prioritizes law/official
  guidance, exact references, bounded typed traversal, and clean adoption from
  export evidence without speculative abstractions.

## Project Structure

### Documentation (this feature)

```text
specs/001-legal-graph-foundation/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- operator-commands.md
|   `-- artifacts.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
src/
|-- app/
|   |-- __main__.py
|   |-- commands.py
|   |-- settings.py
|   `-- logging.py
|-- graph/
|   |-- client.py
|   |-- schema.py
|   |-- repositories.py
|   |-- writer.py
|   `-- types.py
|-- ingestion/
|   |-- legal_xml_import.py
|   |-- legal_preview_loader.py
|   |-- legal_structure_builder.py
|   |-- legal_reference_parser.py
|   `-- verification.py
|-- retrieval/
|   |-- embedding_profile.py
|   |-- embedding_service.py
|   |-- embedding_backend.py
|   |-- embedding_endpoint_client.py
|   |-- legal_reference_resolver.py
|   `-- legal_traversal.py
|-- review/
|   `-- schema_boundary.py
`-- evaluation/
    |-- load_cases.py
    `-- legal_validation.py

tests/
|-- unit/
|-- integration/
|-- smoke/
`-- fixtures/
```

**Structure Decision**: Use the clean layered package layout from
`ARCHITECTURE.md`. Omit `enrichment/` and `bulk/` implementation packages for
this feature because LLM extraction, review workflow, and operator bulk runs are
out of scope. Keep `review/schema_boundary.py` limited to schema placeholder
contracts. Keep `src/app/commands.py` and `src/app/__main__.py` as thin
operator command dispatch surfaces for the documented foundation workflows, not
as chatbot, answer-generation, or bulk-orchestration entry points. Use snapshot
files only as reference material for contracts and test cases, never as
wholesale imports.

## Phase 0: Research Summary

See [research.md](./research.md). Decisions are resolved with no open
clarification markers.

## Phase 1: Design Summary

See [data-model.md](./data-model.md), [contracts/operator-commands.md](./contracts/operator-commands.md),
[contracts/artifacts.md](./contracts/artifacts.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

- **Database Before Inference**: PASS. Contracts expose operator reports and
  structural retrieval results only; no answer-generation contract exists.
- **Structural Legal Graph**: PASS. Data model covers source, legal, reference,
  traversal, temporal/provenance fields, and unresolved references.
- **Embedding Contract**: PASS. Data model and contracts preserve profile
  metadata, prefixes, vector dimensions, normalization, routing mode, and
  fail-fast local-only graph writes.
- **Review Boundary**: PASS. Candidate/review entities are schema placeholders
  without extraction, task workflow, promotion, or trusted-use behavior.
- **Reproducible Operations**: PASS. Operator contracts require selected scope,
  processed/skipped/failed counts, metadata, and visible failure reporting.
- **Bulk Runtime Control**: PASS. Bulk/notebook execution remains deferred.
- **Test Boundaries**: PASS. Quickstart separates offline unit validation from
  live Neo4j/Jina integration checks.
- **Minimal Trusted Surface**: PASS. The design favors exact references and
  bounded traversal over broad semantic expansion.

## Complexity Tracking

No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
