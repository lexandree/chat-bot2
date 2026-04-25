# Migration Export Plan

## Purpose

Prepare a clean export package for a new database-first legal GraphRAG project.
The export is not a refactor target and not a runnable clone of the current
repository. It is a curated source bundle plus target-system documents.

The current repository remains the source of useful implementation evidence.
The new project should treat these files as reference material and selectively
adopt them into a clean architecture.

## Export Principles

- Export only database-foundation work, not chatbot inference.
- Preserve useful legal corpus, Neo4j schema, embedding-contract, review, and
  validation ideas.
- Do not export `.env`, secrets, local runtime keys, generated load reports, or
  notebook runtime state.
- Keep ingestion, graph storage, embeddings, semantic enrichment, and inference
  as separate target-system concerns.
- Prefer official framework patterns for future GraphRAG retrieval/inference
  unless a project-specific exception is documented.

## Included Files

### Target documents

- `docs/PROJECT_CONSTITUTION.md`
- `docs/TECHNICAL_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/EXPORT_MANIFEST.md`
- `docs/ADOPTION_NOTES.md`
- `docs/RESEARCH_DISTILLATION.md`
- `docs/BULK_NOTEBOOK_PROCESSING.md`
- `project_seed/README.md`
- `project_seed/pyproject.toml`
- `project_seed/.env.example`
- `project_seed/.env` when intentionally added for private handoff
- `jina/.jina.env` when intentionally added for private handoff
- `source_snapshot/README.md`

### Notebook references

- `notebooks/legal_extraction_on_kaggle.ipynb`
- `notebooks/llama-server_on_kaggle_full_notebook_workflow.ipynb`
- `notebooks/llama_server_kaggle_simple_run.ipynb`

### Source snapshots

Application configuration:

- `source_snapshot/src/app/settings.py`

Graph foundation:

- `source_snapshot/src/graph/schema.py`
- `source_snapshot/src/graph/types.py`
- `source_snapshot/src/graph/repositories.py`
- `source_snapshot/src/graph/direct_writer.py`
- `source_snapshot/src/graph/profile_validation.py`
- `source_snapshot/src/graph/reindex_queries.py`

Legal corpus and structural graph:

- `source_snapshot/src/ingestion/legal_xml_import.py`
- `source_snapshot/src/ingestion/load_legal_preview.py`
- `source_snapshot/src/ingestion/legal_structure_builder.py`
- `source_snapshot/src/ingestion/legal_reference_parser.py`
- `source_snapshot/src/ingestion/verification.py`

Embedding contract:

- `source_snapshot/src/retrieval/embedding_profile.py`
- `source_snapshot/src/retrieval/embedding_service.py`
- `source_snapshot/src/retrieval/embedding_backend.py`
- `source_snapshot/src/retrieval/backend_health.py`
- `source_snapshot/src/retrieval/llama_server_client.py`
- `source_snapshot/src/retrieval/jina_api_client.py`

Legal retrieval baseline:

- `source_snapshot/src/retrieval/legal_reference_resolver.py`
- `source_snapshot/src/retrieval/legal_traversal.py`

Review and validation boundary:

- `source_snapshot/src/ingestion/legal_proposition_extractor.py`
- `source_snapshot/src/ingestion/legal_extraction_service.py`
- `source_snapshot/src/ingestion/reindex_state.py`
- `source_snapshot/src/ingestion/reindex_state_store.py`
- `source_snapshot/src/review/claim_repository.py`
- `source_snapshot/src/review/review_task_repository.py`
- `source_snapshot/src/review/review_service.py`
- `source_snapshot/src/evaluation/load_cases.py`
- `source_snapshot/src/evaluation/run_benchmark.py`

Fixtures:

- `source_snapshot/tests/fixtures/legal_xml_import_manifest.json`
- `source_snapshot/tests/fixtures/legal_extraction_validation_cases.json`
- `source_snapshot/tests/fixtures/legal_enrichment_validation_cases.json`
- `source_snapshot/tests/fixtures/embedding_benchmark_cases.json`

Reference documents:

- `reference_docs/jina_embeddings_playbook.md`
- `reference_docs/neo4j_playbook.md`
- `reference_docs/operations_checklist.md`
- `reference_docs/kaggle_workflow_playbook.md`
- `reference_docs/research_multihop_reasoning.md`
- `reference_docs/external_research.md`
- `reference_docs/external_research2.md`
- `reference_docs/external_research2-1.md`
- `reference_docs/external_research2-2.md`
- `reference_docs/external_research2-3.md`
- `reference_docs/external_research2-4.md`
- `reference_docs/external_research2_meta.md`

## Explicitly Excluded

- Root `.env`, SSH keys, and all local secret material not intentionally added
  under `export/` for private handoff.
- Current chatbot/inference modules under `src/bot`, `src/orchestration`, and
  chat handlers.
- The fake runtime behavior of the current `Neo4jClient` facade as a production
  access pattern.
- Generated import reports under `data/import_preview/load_reports`.
- Raw local legal XML inputs by default. The manifest and importer contract are
  exported; the new project should obtain source XML through its own controlled
  data path.
- Notebook files are exported only as references for operator-managed bulk
  runtime design. Reusable logic should move into project modules in the new
  project.

## Followed Steps

1. Create the `export/` directory with documentation, source snapshot,
   reference-doc, fixture, and project-seed subdirectories.
2. Copy only files listed in the allowlist above.
3. Write target-system documents that describe the clean project, not the old
   repository history.
4. Verify the final export tree and report any known caveats.

## Known Caveats For The New Project

- Source snapshots preserve current imports and may require namespace cleanup
  after import into a new repository.
- Unit tests in the current repository include some fixture path assumptions;
  the new project should recreate tests around the new layout.
- Jina and Neo4j live checks must be explicit integration/smoke tests, not
  default unit-test dependencies.
