# Quickstart: German Legal Graph Foundation

This quickstart describes the planned validation flow for the foundation. It is
not an implementation command list until `/speckit.tasks` creates concrete
tasks and the code exists.

## 1. Environment

```bash
conda activate chbot
python -m pip install -e ".[dev]"
```

Configuration is loaded from environment variables or a local `.env` copied from
`.env.example`. Do not commit secrets.

Required for live graph operations:

```bash
export NEO4J_URI="neo4j+s://example.databases.neo4j.io"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="..."
# Optional. Leave unset/empty to use the server default database.
export NEO4J_DATABASE=""
```

Required for live embedding writes when you choose to run them:

```bash
export EMBEDDING_ENDPOINT_URL="http://<embedding-pc>:18080/v1/embeddings"
export EMBEDDING_MODEL_ID="jina-embeddings-v5-text-small-retrieval-GGUF"
export EMBEDDING_VECTOR_DIMENSIONS="1024"
export EMBEDDING_NORMALIZED="true"
```

Start the local-only Jina-compatible service on the embedding PC before running
live embedding write checks. Unit tests do not need it.

## 2. Offline Validation

Default validation must not require Neo4j, Jina, paid APIs, or notebooks.

```bash
python -m compileall src tests
python -m pytest tests/unit
python -m pytest tests/smoke
```

Expected unit coverage:

- settings validation
- schema definition assembly
- legal XML preview normalization
- stable id/checksum policy
- legal reference parsing
- structural graph mapping
- embedding prefix/profile validation
- load/delete/verify report assembly
- traversal limit policy

Latest offline validation recorded during implementation:

- `python -m compileall src tests`: PASS
- `python -m pytest tests/unit`: PASS, 42 tests
- `python -m pytest tests/smoke`: PASS, 2 tests

## 3. Live Neo4j Integration

Run only when Neo4j/Aura is available and credentials are configured.
The live integration suite rewrites fixture data to the isolated
`TestAufenthG` law-code scope and cleans that scope before/after graph writes.
Existing live graph data outside `TestAufenthG` can be preserved as a separate
comparison baseline and is not touched by the integration cleanup helper.

```bash
export RUN_LIVE_NEO4J_TESTS=true
python -m pytest tests/integration -m neo4j
```

Expected checks:

- real driver connectivity
- idempotent schema bootstrap
- stable constraint/index names
- load/verify/delete by law-code scope
- exact reference resolution and bounded traversal

Latest live Neo4j validation recorded during implementation:

- `RUN_LIVE_NEO4J_TESTS=true python -m pytest tests/integration -m neo4j`:
  PASS, 4 selected tests with embedding-only checks deselected/skipped

## 4. Live Embedding Integration

Run only after the operator starts the local-only Jina-compatible embedding
service.

```bash
export RUN_LIVE_EMBEDDING_TESTS=true
python -m pytest tests/integration -m embedding
```

Expected checks:

- endpoint health/preflight
- `Document: ` prefix for indexed source text
- `Query: ` prefix for search requests
- 1024-dimensional normalized vectors
- fail-fast behavior when endpoint/profile validation fails
- persisted embedding profile and backend metadata

Latest live embedding validation recorded during implementation:

- `RUN_LIVE_NEO4J_TESTS=true RUN_LIVE_EMBEDDING_TESTS=true python -m pytest tests/integration`:
  PASS, 5 tests
- `python -m app graph verify --law-code TestAufenthG`: PASS, zero records
  after live-test cleanup

## 5. Planned Operator Flow

The planned operator command contracts are documented in
[contracts/operator-commands.md](./contracts/operator-commands.md).

Foundation validation order:

1. Validate settings.
2. Bootstrap Neo4j schema.
3. Generate legal XML preview.
4. Load selected law-code scope.
5. Write source/fragment embeddings after starting local Jina.
6. Verify graph state.
7. Resolve exact legal references.
8. Run bounded typed traversal.
9. Delete selected law-code scope when needed.
10. Verify deletion.

No step generates chatbot responses, legal answers, LLM propositions, review
tasks, or GraphRAG output.

## 6. US1 Operator Commands

Validate settings without writing graph data:

```bash
python -m app settings validate
```

Bootstrap the Neo4j schema only after live Neo4j settings are configured:

```bash
python -m app schema bootstrap
```

The schema bootstrap command uses the official Neo4j driver, stable schema
object names, idempotent `IF NOT EXISTS` statements, and candidate/review
placeholder constraints. It does not fall back to a recording facade.

## 7. US2 Preview Command

Generate a deterministic legal XML preview from the offline fixture manifest:

```bash
python -m app preview legal-xml \
  --manifest tests/fixtures/legal_xml_import_manifest.json \
  --output data/import_preview/legal_xml_preview.json
```

The command writes a preview artifact with `source_documents`,
`source_fragments`, stable identifiers, checksums, deterministic ordering, and a
structured `missing_inputs` list for optional files that are absent.

## 8. US3 Load, Verify, And Delete Commands

Load a selected law-code scope from a preview artifact:

```bash
python -m app graph load \
  --preview data/import_preview/legal_xml_preview.json \
  --law-code AufenthG
```

Verify the selected scope:

```bash
python -m app graph verify --law-code AufenthG
```

Delete the selected scope only with explicit confirmation:

```bash
python -m app graph delete --law-code AufenthG --confirm
```

Load uses idempotent upsert semantics for source, legal, fragment, and reference
records. Delete is scoped by law code and does not require a full database reset.

## 9. US4 Embedding Command

Start the local-only Jina-compatible embedding endpoint on the embedding PC
before running graph-write embeddings, then configure its endpoint URL:

```bash
export EMBEDDING_ENDPOINT_URL="http://<embedding-pc>:18080/v1/embeddings"
python -m app embeddings write --law-code AufenthG
```

The workflow performs endpoint/profile preflight before graph mutation and then
writes `embedding_v1` plus profile, model, backend, routing, dimensions, and
normalization metadata to source documents and fragments. Default unit tests use
fakes and never require the endpoint.

## 10. US5 Structural Retrieval Commands

Resolve an exact legal reference:

```bash
python -m app references resolve \
  --law-code AufenthG \
  --section-reference "§ 1"
```

Run bounded typed traversal from a resolved section:

```bash
python -m app traversal run \
  --legal-section-id legal-section:AufenthG:1:current \
  --relation-type CITES \
  --depth 1 \
  --fanout 25 \
  --node-limit 100
```

Structural retrieval outputs source references, relation types, depth/fanout/node
limit metadata, and unresolved-target evidence when applicable. Result artifacts
must not include `answer_text`, `answer`, or `generated_answer` fields.
