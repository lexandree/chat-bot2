# Project Constitution

## Mission

Build a database-first legal knowledge foundation for GraphRAG systems.

The project exists to create a reliable, auditable legal graph and retrieval
baseline before any conversational inference layer is added. The knowledge base
must preserve source provenance, structural legal references, embedding
contracts, review boundaries, and operational repeatability.

## Principle 1: Database Before Inference

The legal knowledge base is the primary product of the first stages.

- Ingestion, schema bootstrap, graph loading, verification, deletion, and
  reindexing must work before chatbot inference is introduced.
- No answer-generation path may be treated as complete until the graph and
  retrieval baseline can be validated independently.
- Demo responses must not mask missing database state.

## Principle 2: Structural Legal Graph First

Legal structure is a source-grounded fact layer, not an LLM interpretation.

- Legal acts, sections, fragments, references, and typed legal edges are
  canonical database objects.
- Exact legal-reference resolution and bounded graph traversal are required
  baselines.
- Structural retrieval must work without LLM extraction.
- Temporal metadata must be explicit enough to support current-default and
  as-of-date behavior.

## Principle 3: Embeddings Are Indexes, Not Truth

Embeddings help retrieve source material. They do not define legal meaning.

- Query embeddings and document embeddings must preserve asymmetric prefix
  semantics: `Query: ` for search requests and `Document: ` for indexed source
  text.
- The active embedding profile must record provider, model, variant,
  dimensions, normalization, and task semantics.
- Unit tests must not require a live embedding service.
- Live embedding checks belong to explicit integration or smoke tests.

## Principle 4: LLM Outputs Are Reviewable Candidates

LLMs may propose interpretations, but source texts remain authoritative.

- LLM-derived propositions, entities, claims, summaries, and enrichment outputs
  start untrusted.
- Every persisted candidate must retain source support and runtime metadata.
- Weakly grounded, structurally invalid, ambiguous, or duplicate outputs must
  be rejected, flagged, or isolated before they can affect trusted retrieval.
- Only approved, non-flagged, non-isolated candidates may be used as trusted
  answer support.

## Principle 5: Framework-First GraphRAG

GraphRAG retrieval and inference should follow mature framework patterns unless
there is a documented reason not to.

- Neo4j-native GraphRAG patterns are preferred for Neo4j-backed vector and
  graph retrieval.
- Microsoft GraphRAG, Neo4j GraphRAG, LlamaIndex, and LangChain patterns may be
  evaluated for their relevant layer.
- Custom retrieval orchestration is allowed only when it is small, tested, and
  justified by legal-domain requirements.
- Framework adoption must not blur the boundary between ingestion, retrieval,
  review, and inference.

## Principle 6: Reproducible Operations

Operators must be able to understand and repeat each stage.

- Load, verify, delete, and reindex operations must be idempotent or explicitly
  document their write semantics.
- Bulk runs must record effective runtime contour, model identifiers, embedding
  backend, policy or prompt version, processed count, skipped count, and failed
  count.
- Long-running operator-managed jobs must support resume-safe execution.
- Failure modes must be visible and must not silently produce trusted state.

## Principle 7: Operator-Managed Bulk Runs Are Controlled Surfaces

Notebook and remote-runtime workflows are valid for bulk extraction,
validation, and profiling, but they are operator surfaces rather than the core
application architecture.

- Bulk notebooks must be disabled by default and require explicit operator
  opt-in.
- Runtime binaries, model artifacts, project code, input corpora, and run
  outputs must remain separate artifact classes.
- Every useful bulk run must export a coherent artifact bundle with run
  manifest, runtime profile, result JSON, logs, and command metadata.
- Project-specific legal inputs, outputs, and environment snapshots are private
  unless explicitly sanitized for publication.
- Bulk jobs may rely on a separately started model server, but the job runner
  itself must live in project code and own orchestration, checkpointing, and
  artifact export.
- Reusable notebook logic should move into project modules once it becomes part
  of the system contract.

## Principle 8: Test Boundaries Are Explicit

Tests must match the layer they validate.

- Unit tests validate pure parsing, schema assembly, state transitions, and
  deterministic policies without live services.
- Integration tests validate Neo4j, embedding service, and filesystem behavior.
- Smoke tests validate operator-managed and managed runtime contours.
- A test that depends on live Neo4j, live Jina, paid APIs, or remote notebooks
  must be marked and runnable separately.

## Principle 9: Minimal Trusted Surface

The project should start with a narrow, high-confidence scope.

- The first legal corpus slice should prioritize law and official guidance.
- The first retrieval baseline should prefer exact references and bounded
  traversal over broad semantic expansion.
- Inference is a later stage and must be measured against the structural
  baseline.
- The system should avoid speculative abstractions until the database and
  retrieval evidence justify them.

## Governance

Changes that affect schema, embedding contract, review promotion, legal
retrieval policy, or runtime contours require an explicit design note or spec
update.

No module may introduce a hidden live-service dependency into default unit
tests.

No user-facing answer path may claim grounded support unless it cites persisted,
verifiable source material or approved candidate support.
