# Export Manifest

## Export Root

`export/`

## Contents

### Planning

- `migration_export_plan.md`: source-side export plan and allowlist.

### New Project Documents

- `docs/PROJECT_CONSTITUTION.md`: target project principles.
- `docs/TECHNICAL_SPEC.md`: target technical specification.
- `docs/ARCHITECTURE.md`: target architecture and package boundaries.
- `docs/RESEARCH_DISTILLATION.md`: retained conclusions from external
  research and critique notes.
- `docs/BULK_NOTEBOOK_PROCESSING.md`: retained notebook and operator-managed
  bulk execution lessons.
- `docs/EXPORT_MANIFEST.md`: this manifest.

### Project Seed

- `project_seed/README.md`: bootstrap notes for the new project.
- `project_seed/pyproject.toml`: minimal dependency skeleton.
- `project_seed/.env.example`: safe configuration template.
- `project_seed/.env`: private runtime configuration snapshot added for local
  handoff; do not publish publicly without review.
- `jina/.jina.env`: private Jina runtime configuration snapshot added for local
  handoff; do not publish publicly without review.

### Notebook References

- `notebooks/legal_extraction_on_kaggle.ipynb`: project-facing operator-managed
  legal extraction and semantic validation notebook.
- `notebooks/llama-server_on_kaggle_full_notebook_workflow.ipynb`: full
  `llama-server` runtime, packaging, health, and artifact-export workflow.
- `notebooks/llama_server_kaggle_simple_run.ipynb`: minimal runtime launcher
  for quick Kaggle server runs.

### Source Snapshot

`source_snapshot/` contains selected implementation files copied from the
current repository. They are reference snapshots, not a ready-to-run package.

Primary retained ideas:

- legal XML import
- normalized legal source preview
- structural legal graph builder
- Neo4j schema and profile-aware graph writes
- Jina embedding contract
- local-only graph-write embedding route
- exact legal reference resolver
- bounded legal traversal
- review-gated LLM proposition candidates
- validation fixture loading and baseline comparison helpers

Known adaptation points:

- `graph.neo4j_client.py` is intentionally not exported. Replace it with a
  real Neo4j driver-backed client in the new project.
- `evaluation/run_benchmark.py` contains useful legal validation helpers but
  also imports the old chat handler. Split legal validation into a clean module
  before adopting it.
- Source snapshots preserve old package imports. Treat import cleanup as part of
  adoption, not as a reason to preserve the old layout.

### Reference Documents

`reference_docs/` contains project-local operational and research notes that are
useful for rebuilding decisions in the new project.

Additional exported research notes:

- `external_research.md`
- `external_research2.md`
- `external_research2-1.md`
- `external_research2-2.md`
- `external_research2-3.md`
- `external_research2-4.md`
- `external_research2_meta.md`

## Exclusions

The export intentionally excludes:

- `.env` and any secret-bearing files
- local SSH keys
- generated load reports
- raw legal XML source files
- old chatbot handlers
- generic answer synthesis
- current fake Neo4j production facade as a recommended design

## Import Guidance

When creating the new project, start from `project_seed/` and the documents in
`docs/`. Pull source snapshots into the new `src/` only after adapting imports,
tests, and service boundaries to the new architecture.
