# Agent Instructions

## Project Scope

This repository is a clean database-first legal GraphRAG foundation.

The first-stage product is the legal knowledge base: source import, structural
legal graph, embeddings, reviewable candidates, validation, and repeatable
operations. Chatbot inference, answer synthesis, and UX layers are out of scope
until explicitly requested after the foundation is stable.

## Authoritative Documents

Read these files before making project-shaping changes:

- `PROJECT_CONSTITUTION.md`
- `TECHNICAL_SPEC.md`
- `ARCHITECTURE.md`
- `export/migration_export_plan.md`

`export/source_snapshot/`, `export/notebooks/`, `export/reference_docs/`, and
`export/project_seed/` are reference material only. Do not copy or migrate old
code automatically.

## Non-Negotiable Rules

- Do not implement features, migrate source snapshots, or create runtime code
  until the user gives a separate explicit implementation command.
- Do not import chatbot handlers, answer synthesis, or old orchestration paths
  into the clean foundation.
- Do not introduce secrets, local `.env` values, raw private legal corpora,
  generated run artifacts, or notebook runtime state into tracked source files.
- Do not hide retrieval failure behind demo or fallback answers.
- Do not make default unit tests depend on Neo4j, Jina, paid APIs, network
  services, or remote notebooks.
- Do not treat LLM-generated propositions as trusted support unless the review
  boundary marks them approved, non-flagged, and non-isolated.

## Architecture Rules

- Keep ingestion, graph storage, embeddings, retrieval, enrichment, review,
  evaluation, bulk processing, snapshot/comparison artifacts, and future
  inference as separate concerns.
- Build the database foundation before inference.
- Preserve legal source provenance, structural references, checksums, temporal
  metadata, embedding profile metadata, and review state.
- Prefer exact legal-reference resolution and bounded typed traversal before
  broad semantic expansion.
- Base graph load must write source/legal structure only. Trusted
  `LegalReference` evidence and typed legal relationship edges belong to an
  explicit relationship-refresh workflow.
- Relationship-quality artifacts summarize the new graph only. They must not
  rely on legacy graph comparison, framework sidecar output, chatbot answers,
  or generated answer text.
- Use mature Neo4j/GraphRAG framework patterns when inference is later added,
  unless a documented project-specific exception exists.

## Embedding Rules

- Preserve asymmetric embedding prefixes: `Query: ` for search queries and
  `Document: ` for indexed source text.
- Record provider, model, variant, dimensions, normalization, routing mode, and
  task semantics in embedding profile metadata.
- Graph-write embedding workflows must fail fast if the required local-only
  backend is unavailable.
- Live embedding checks belong to explicit integration or smoke tests.

## Bulk And Notebook Rules

- Treat notebooks as operator-managed reference surfaces, not core application
  architecture.
- Bulk execution must be disabled by default and require explicit opt-in.
- Runtime binaries, model artifacts, project code, input corpora, and run
  outputs must remain separate artifact classes.
- Useful bulk runs must export coherent artifact bundles with manifest, runtime
  profile, result JSON, logs, command metadata, and checkpoint state when
  available.
- A separate model server may be started for bulk work, but the bulk runner and
  state machine belong in project code, not in notebook glue.
- Project-specific legal inputs and outputs are private unless explicitly
  sanitized for publication.

## Change Discipline

- Schema, embedding contract, review promotion, legal retrieval policy, and
  runtime contour changes require an explicit design note or spec update.
- Keep edits narrow and aligned with the existing baseline documents.
- Use source snapshots as implementation evidence only after deciding what the
  clean target design requires.
- Mark integration and smoke tests separately from default unit tests.
- Update documentation when behavior, contracts, or operational assumptions
  change.
- Treat legacy comparison baselines as read-only file artifacts that can be
  removed after cutover.

## Active Technologies
- Python 3.11+ in conda environment `chbot` + Neo4j official Python driver (`neo4j>=5.18`), `pydantic` plus `pydantic-settings` for typed env configuration, pytest, Python stdlib HTTP client for the Jina-compatible local embedding endpoint unless implementation evidence justifies a narrow HTTP dependency (001-legal-graph-foundation)
- Neo4j 5.18+ / Aura-compatible graph of record with stable constraints and vector indexes; local fixture files for unit tests and legal XML preview inputs (001-legal-graph-foundation)
- Python 3.11+ + Neo4j official Python driver, pydantic/pydantic-settings, pytest, stdlib JSON/filesystem tooling (002-real-corpus-graph-artifacts)
- Neo4j for loaded graph state; JSON files for preview, snapshot, and comparison artifacts (002-real-corpus-graph-artifacts)
- Python 3.12 in conda environment `chbot` + Neo4j official Python driver, pydantic/pydantic-settings, pytest, Python stdlib JSON/filesystem tooling (003-legal-graph-relationships)
- Neo4j for loaded source/legal/reference/edge state; JSON files for relationship-quality artifacts and optional design evidence (003-legal-graph-relationships)

## Recent Changes
- 001-legal-graph-foundation: Added Python 3.11+ in conda environment `chbot` + Neo4j official Python driver (`neo4j>=5.18`), `pydantic` plus `pydantic-settings` for typed env configuration, pytest, Python stdlib HTTP client for the Jina-compatible local embedding endpoint unless implementation evidence justifies a narrow HTTP dependency
