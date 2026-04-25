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
```

Required for live embedding writes when you choose to run them:

```bash
export LLAMA_SERVER_URL="http://<embedding-pc>:18080/v1/embeddings"
export EMBEDDING_MODEL="jina-embeddings-v5-text-small-retrieval-GGUF"
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

## 3. Live Neo4j Integration

Run only when Neo4j/Aura is available and credentials are configured.

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
