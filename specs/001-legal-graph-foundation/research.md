# Research: German Legal Graph Foundation

## Decision: Use Python 3.11+ in conda `chbot`

**Rationale**: The seed project, exported technical spec, and user direction all
standardize on Python 3.11+ and conda environment `chbot`. This keeps the first
foundation slice aligned with existing fixtures and operator expectations.

**Alternatives considered**:
- Different Python version: rejected because it would add environment churn.
- Non-Python stack: rejected because export evidence and project seed are Python.

## Decision: Use the official Neo4j Python driver directly

**Rationale**: The clarified spec locks Neo4j 5/Aura-compatible storage as the
graph of record. The foundation must expose parameterized reads/writes,
connectivity checks, database selection where needed, vector index queries, and
driver cleanup. A real driver-backed client avoids repeating the old
recording-only facade mistake.

**Alternatives considered**:
- Generic graph database abstraction: rejected by clarification and because it
  would obscure Neo4j schema/vector capabilities.
- Recording facade as production client: rejected; recording/fake behavior is
  allowed only as explicit unit-test doubles.

## Decision: Use pydantic settings for typed configuration

**Rationale**: The foundation has many environment-driven settings: Neo4j
connection values, embedding profile metadata, embedding endpoint, vector dimensions,
normalization, routing mode, and test flags. `pydantic-settings` provides
typed validation without custom env parsing and fits Python 3.11+.

**Alternatives considered**:
- Dataclass plus manual env parsing: rejected because the export snapshot shows
  this becomes verbose and easy to mix with old app concerns.
- Untyped environment lookups at call sites: rejected because failures must be
  visible before graph writes.

## Decision: Keep `export/source_snapshot` as reference evidence only

**Rationale**: The current project must stay clean. Snapshot code can inform
contracts, fixture expectations, and narrow implementation behavior, but modules
must be reimplemented/adapted into the new package layout with new tests.

**Alternatives considered**:
- Wholesale import of snapshot modules: rejected by clarification and adoption
  notes.
- Ignore source snapshots entirely: rejected because useful contracts and tested
  behaviors exist there.

## Decision: Use deterministic legal XML preview before graph writes

**Rationale**: Preview is the first auditable boundary. It must normalize
`gesetze-im-internet` style German legal XML into source documents/fragments,
stable identifiers, law code, section reference, title, body text, metadata, and
checksums without mutating the graph.

**Alternatives considered**:
- Parse and load in one step: rejected because it prevents operator inspection.
- Fail whole preview on missing optional files: rejected by the spec and export
  docs; missing optional inputs must be reported structurally.

## Decision: Create idempotent Neo4j schema bootstrap with stable names

**Rationale**: The schema must be safe to run before data load and repeatedly in
the same database. It includes source/legal/reference uniqueness constraints,
embedding-profile constraints, validation constraints, candidate/review schema
placeholders, and vector indexes over `embedding_v1` with parameterized
dimensions.

**Alternatives considered**:
- Create schema lazily during load: rejected because graph readiness must be
  independently verifiable.
- Omit candidate/review placeholders: rejected by clarification; placeholders
  preserve future review boundaries without implementing extraction.

## Decision: Implement local-only graph-write embeddings in this feature

**Rationale**: Foundation completion requires source and fragment embeddings.
The graph-write path uses operator-started local-only Jina-compatible service,
`Document: ` prefixes for indexed source text, `Query: ` prefixes for search
requests, 1024-dimensional normalized vectors by default, and persisted runtime
metadata. Workflow fails before partial writes if the service is unavailable or
profile validation fails.

**Alternatives considered**:
- Defer embedding generation: rejected after clarification; the local service
  already exists operationally.
- Allow API failover for graph writes: rejected by constitution; graph writes
  must be local-only.
- Require Jina for unit tests: rejected; live embedding checks are integration
  or smoke tests only.

## Decision: Include exact legal-reference resolution and bounded traversal

**Rationale**: Structural retrieval is the first retrieval baseline. It resolves
law code plus section reference against loaded sections and traverses only
allowed typed relations with depth, fanout, and node limits. It returns source
refs and traversal metadata, not generated answers.

**Alternatives considered**:
- Defer traversal to a later retrieval feature: rejected by clarification and
  export docs.
- Broad semantic expansion or ranking now: rejected as post-foundation work.

## Decision: Use pytest with explicit unit/integration/smoke boundaries

**Rationale**: Default validation must run offline. Unit tests cover pure
configuration validation, schema assembly, XML normalization, identifier
creation, reference parsing, embedding prefix/profile policy, load/delete
policy, and report assembly. Live Neo4j and local Jina checks are opt-in
integration/smoke tests.

**Alternatives considered**:
- Require live Neo4j/Jina in default tests: rejected by constitution.
- Skip integration tests: rejected because the real driver and local embedding
  path need explicit validation.

## Decision: Do not implement inference, chatbot UX, LLM extraction, review workflow, or GraphRAG answers

**Rationale**: The feature scope is the database foundation. Candidate/review
schema placeholders are allowed, but extraction, review tasks, trusted
promotion, answer synthesis, and fallback responses are future features.

**Alternatives considered**:
- Add proposition extraction now: rejected by feature scope.
- Add GraphRAG framework integration now: rejected until foundation validation
  passes.
