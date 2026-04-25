# Neo4j Playbook

## Purpose

This file captures the working rules and practical lessons for Neo4j usage in
this project so the same setup can be reproduced in a similar project without
repeating trial-and-error.

## Current Architecture

- Neo4j is the graph knowledge and retrieval context store.
- PostgreSQL is reserved for transactional state.
- Neo4j also serves as the vector store.
- A separate vector DB is not required for the current project stage.
- Graph writes use local-only embedding generation in `002`.
- User-query failover does not change the local-only rule for stored graph
  embeddings.
- `003` adds legal-first bulk-enrichment artifacts:
  - `SourceDocument`
  - `SourceFragment`
  - `CandidateEntity`
  - `CandidateClaim`
  - `EnrichmentRun`
  - `ValidationQuestionSet`
  - `ValidationQuestion`
  - `ValidationRunResult`

## Current Embedding Contract In Neo4j

- vector field: `embedding_v1`
- active dimensionality: `1024`
- normalized vectors
- active embedding profile id:
  - `jina_v5_q8_1024_norm_v1`
- profile semantics:
  - provider: `jina_local`
  - variant: `q8`
  - query prefix: `Query: `
  - document prefix: `Document: `
  - query task: `retrieval.query`
  - document task: `retrieval.passage`

## Data Modeling Rule For Embeddings

Use the lightweight model:

- on content nodes:
  - `embedding_v1`
  - `embedding_updated_at`
  - `embedding_profile_id`
- separately:
  - `(:EmbeddingProfile {...})`
- optional relation:
  - `(:AnyEmbeddedNode)-[:EMBEDDED_WITH]->(:EmbeddingProfile)`

Reason:

- full per-node metadata packs are overkill for `001`
- one active profile plus lightweight node fields is enough

## Current Vector Indexes

Active vector indexes:

- `authority_embedding`
- `benefit_embedding`
- `knowledge_source_embedding`
- `legal_norm_embedding`
- `observation_claim_embedding`
- `procedure_embedding`
- `requirement_embedding`
- `user_query_embedding`

All of them should use:

- `vector.dimensions = 1024`
- `vector.similarity_function = cosine`

## Neo4j Aura Free Notes

- Aura Free may be paused automatically.
- If the connection suddenly fails, check whether the instance is paused before
  assuming credentials or code are wrong.
- Once resumed, the instance may need a short delay before fully accepting work.

## Working Connection Patterns

### MCP read/write

Useful for:

- schema inspection
- small Cypher changes
- validation queries
- optional local developer tooling only

Limitation discovered in practice:

- very large parameter payloads can be truncated or become impractical through
  MCP tooling
- large vector writes are risky through MCP alone
- sandboxed agent environments may be unable to reach AuraDB or host-local
  helper services through MCP even when direct host access works

## Important Practical Finding

Writing a full `1024`-dimensional embedding through MCP as one huge parameter was
not reliable enough for bulk seed writes. One attempted write ended up truncated.

Safe rule:

- use MCP only when it is convenient and actually available
- use a direct Neo4j client or Aura HTTP query API for large vector writes
- do not block development or operations on MCP availability

## Preferred Access Paths

Use these access paths in order of importance:

1. official Neo4j driver for application code, ingestion, and operational
   scripts
2. Aura HTTP `query/v2` for large writes and environments where the direct
   driver is not the best fit
3. Neo4j Browser or `cypher-shell` for manual inspection and admin work
4. MCP only as optional inspection tooling

## Aura HTTP Query API

Working endpoint shape for this Aura instance pattern:

```text
https://<aura-host>/db/<database>/query/v2
```

Important finding:

- `/db/<database>/tx/commit` returned `403 Forbidden`
- `/db/<database>/query/v2` worked

So for large writes:

- prefer `query/v2`
- send one statement with parameters
- validate the returned `embedding_size`

## Credentials Handling

Do not hardcode secrets in repository docs.

Working local pattern:

- keep Aura connection details in a local non-committed file
- example fields:
  - `NEO4J_URI`
  - `NEO4J_USERNAME`
  - `NEO4J_PASSWORD`
  - `NEO4J_DATABASE`

Rule:

- document the variable names
- do not commit live passwords or tokens

## Current Seed Status

Seed nodes currently aligned to the active profile:

- `Authority`
- `Benefit`
- `KnowledgeSource`
- `LegalNorm`
- `ObservationClaim`
- `Procedure`
- `Requirement`
- `UserQuery`

Current expected state:

- each has `embedding_v1`
- each has `embedding_updated_at`
- each has `embedding_profile_id = jina_v5_q8_1024_norm_v1`
- each is linked by `[:EMBEDDED_WITH]` to the active `EmbeddingProfile`

## Working Cypher Checks

### Show vector indexes

```cypher
SHOW VECTOR INDEXES
YIELD name, state, options
RETURN name, state, options
ORDER BY name
```

### Check node embedding sizes

```cypher
MATCH (n)
WHERE any(label IN labels(n) WHERE label IN [
  'Authority',
  'Benefit',
  'KnowledgeSource',
  'LegalNorm',
  'ObservationClaim',
  'Procedure',
  'Requirement',
  'UserQuery'
])
RETURN labels(n) AS labels,
       size(n.embedding_v1) AS embedding_size,
       n.embedding_profile_id AS embedding_profile_id
ORDER BY labels
```

### Check active embedding profile

```cypher
MATCH (p:EmbeddingProfile {profile_id: 'jina_v5_q8_1024_norm_v1'})
RETURN p.profile_id,
       p.provider,
       p.variant,
       p.dim,
       p.normalized,
       p.query_prefix,
       p.document_prefix
```

## Safe Migration Rules

- do not mix different dimensions in one active index
- do not mix different `embedding_profile_id` values in one active retrieval path
- if profile changes, reindex under a new profile id
- if dimension changes, rebuild vector indexes before treating the system as
  healthy

## When Reindexing Is Needed

Reindex if any of these change:

- model family
- quantization variant
- dimension
- normalization mode
- query/document prefix contract
- query/document task semantics

## Recommended Write Strategy For Large Embeddings

1. Compute embeddings first.
2. Validate dimension before writing.
3. Ensure matching vector indexes already exist.
4. Write embeddings through official driver or Aura `query/v2`.
5. Read back:
   - `size(n.embedding_v1)`
   - `embedding_profile_id`
6. Only then continue to the next batch.

## Reindex And Graph-Write Policy

- ingestion: local-only
- seed loading: local-only
- reindex: local-only
- user-query embeddings may fail over to hosted API, but those requests must not
  silently redefine the stored graph embedding surface

## Current Project Rules

- Neo4j is both graph DB and vector DB for this project stage.
- No separate vector database is required yet.
- For `003`, treat source documents and source fragments as the provenance
  anchor for all extracted candidate knowledge.
- Keep `CandidateEntity` and `CandidateClaim` reviewable by default.
- Persist `EnrichmentRun` metadata even for incomplete or resumed runs.
- Validation artifacts may stay file-backed for the first slice, but the graph
  schema should remain ready for eventual persistence of validation records.
- Use Neo4j vector indexes as retrieval entry points.
- Keep profile metadata separate from node payloads.

## Things To Check First In A Similar Project

- Is the Aura instance paused?
- What is the active embedding dimensionality?
- Do all vector indexes use the same dimension?
- Are embeddings already present on nodes?
- Does the active profile match the client contract?
- Is MCP sufficient for the intended write size, or should direct API/driver be
  used immediately?
