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
- `BULK_NOTEBOOK_PROCESSING.md`
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
  evaluation, bulk processing, and future inference as separate concerns.
- Build the database foundation before inference.
- Preserve legal source provenance, structural references, checksums, temporal
  metadata, embedding profile metadata, and review state.
- Prefer exact legal-reference resolution and bounded typed traversal before
  broad semantic expansion.
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
