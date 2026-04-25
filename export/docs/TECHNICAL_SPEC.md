# Technical Specification

## Goal

Create a clean database-first legal knowledge base for a future GraphRAG
application. The first implementation stages focus on source import, structural
legal graph creation, embedding indexes, reviewable semantic candidates, and
validation. Chatbot inference is out of scope until those stages are stable.

## Runtime Assumptions

- Development environment: conda environment `chbot`.
- Python: 3.11 or newer.
- Graph database: Neo4j 5.18 or newer, including Aura-compatible deployment.
- Embeddings: Jina-compatible embedding runtime with 1024-dimensional normalized
  vectors.
- Local embedding service may be exposed as
  `http://127.0.0.1:18080/v1/embeddings`.
- The embedding service is not assumed to be running during default unit tests.

## Non-Goals

- Telegram bot or chat UX.
- General-purpose agent framework.
- Production answer generation.
- Hidden fallback answers when retrieval is empty.
- A custom replacement for mature GraphRAG libraries without explicit
  justification.
- Notebook-based bulk extraction as a substitute for a tested project bulk-run
  contract.

## Data Sources

Initial legal source families:

- law
- official guidance

Initial legal XML imports should support `gesetze-im-internet` style XML files.
The import layer must tolerate missing optional corpus files and report them as
missing inputs instead of failing the whole preview.

## Core Domain Model

### Source Layer

- `SourceDocument`
- `SourceFragment`
- source type
- jurisdiction
- language
- source URI or local reference
- publication, effective, retrieved, and freshness metadata
- checksum

### Structural Legal Layer

- `LegalAct`
- optional hierarchy nodes such as `LegalChapter`, `LegalSectionGroup`, or
  `LegalArticle` when the source corpus exposes them cleanly
- `LegalSection`
- `LegalFragment`
- `LegalReference`
- typed legal edges such as `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`,
  `EXCEPTION_TO`, `EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY`
- temporal metadata, including `valid_from`, `valid_to`, version identity, and
  current-version flags

### Retrieval Support Layer

- `Concept`
- aliases, abbreviations, and synonyms
- optional German compound components
- concept-to-source and concept-to-candidate links
- full-text index support where the target Neo4j version and analyzer setup make
  it appropriate

### Embedding Layer

- `EmbeddingProfile`
- `embedding_v1`
- `embedding_profile_id`
- `embedding_backend_used`
- `embedding_routing_mode`
- `embedding_model_id`

### Candidate Semantic Layer

- `PropositionCandidate`
- `PropositionSupport`
- `ExtractionRun`
- bulk item state or checkpoint state
- review state
- grounding flags
- isolation state
- runtime contour metadata

### Validation Layer

- validation case set
- validation case
- validation result
- baseline mode
- semantic enrichment mode

## Required Workflows

### 1. Schema Bootstrap

The system must create unique constraints and vector indexes for source,
legal, candidate, validation, and embedding-profile entities.

Acceptance criteria:

- Schema creation is idempotent.
- Vector dimensions are parameterized.
- Constraint and index names are stable.
- Schema bootstrap can run before any data is loaded.

### 2. Legal XML Import Preview

The system must parse legal XML files into normalized source documents.

Acceptance criteria:

- Substantive sections are extracted with law code, section reference, title,
  body text, source metadata, and checksum.
- Missing configured files are reported in a structured `missing_inputs` list.
- Generated preview output is deterministic for the same input corpus.

### 3. Structural Graph Build

The system must build legal acts, sections, fragments, references, and typed
edges from normalized source documents.

Acceptance criteria:

- Every imported legal section has a stable section id.
- Every legal section has at least one legal fragment.
- Explicit legal references are parsed and resolved where possible.
- Unresolved references remain auditable.
- Graph traversal can be executed without LLM support.
- Legal hierarchy and temporal fields are preserved when available.

### 4. Load, Verify, Delete

The system must support controlled graph load, verification, and deletion for
the normalized legal corpus.

Acceptance criteria:

- Load uses idempotent upsert semantics.
- Verify reports source document count, source fragment count, embedding count,
  embedding profile ids, vector dimensions, and backend names.
- Delete removes selected source documents and fragments without requiring a
  full database reset.
- Law-code filtering is supported.

### 5. Embedding Index

The system must embed source documents and fragments using the active embedding
contract.

Acceptance criteria:

- Query embeddings use `Query: ` prefix.
- Document embeddings use `Document: ` prefix.
- Vector length matches `EMBEDDING_VECTOR_DIMENSIONS`, default `1024`.
- Embeddings are normalized when `EMBEDDING_NORMALIZED=true`.
- Graph-write embedding workflows fail fast if the local-only backend is
  unavailable.
- Unit tests can run without a live embedding backend.

### 6. Structural Retrieval Baseline

The system must resolve exact legal references and perform bounded traversal.

Acceptance criteria:

- Exact references such as law code plus section reference resolve to a
  `LegalSection`.
- Default traversal depth is shallow and typed.
- Depth two is allowed only for selected relations.
- High-priority direct relations do not cause uncontrolled recursive traversal.
- Fanout and node limits are enforced.

### 7. Multi-Resolution Retrieval Design

The system must be designed so later retrieval can use multiple granularities:

- legal act, article, or section for broad context
- paragraph or section text for local wording
- proposition or atomic rule for precise recall

The foundation stage does not need final GraphRAG inference, but graph identity
and provenance should not prevent multi-resolution retrieval later.

### 8. LLM Semantic Candidate Extraction

The system may extract legal proposition candidates from legal fragments.

Acceptance criteria:

- The extractor emits a stable JSON contract.
- Structurally invalid outputs are rejected.
- Candidates default to `pending`.
- Missing support or parent references are flagged as weak grounding.
- Duplicate or ambiguous candidates are isolated.
- Review tasks are created for persisted candidates.
- Only approved, non-flagged, non-isolated candidates can be trusted later.

### 9. Operator-Managed Bulk Runs

The system must support notebook- or remote-runtime-driven bulk work without
mixing that workflow into interactive inference.

Acceptance criteria:

- Bulk runs are disabled by default until the operator explicitly opts in.
- Runs record runtime contour, effective backend, model id, prompt or policy
  version, input scope, validation fixture, and runtime parameters.
- Runs can limit scope by law code and maximum document or fragment count.
- Runs export a coherent artifact bundle with manifest, profile report, result
  JSON, command metadata, logs, and checkpoint state when available.
- Runs can be resumed from stable per-item or cursor state.
- Project-specific legal inputs and outputs are private artifacts unless
  explicitly sanitized.

### 10. Two-Stage Retrieval And Ranking

The architecture should prepare for two-stage retrieval:

1. candidate generation from exact reference resolution, vector search,
   full-text or BM25, concept matching, and typed graph expansion
2. reranking over a smaller candidate set using normalized scores and optional
   later rerankers

This is a design requirement, not a foundation-stage inference requirement.

### 11. Validation

The system must compare structural baseline behavior with semantic-enriched
behavior.

Acceptance criteria:

- Validation fixtures are versioned.
- Results record observed support refs and outcome labels.
- Semantic enrichment must be measurable against the structural baseline.
- Validation must distinguish retrieval quality from proposition quality.
- Ranking experiments must report Recall@k, MRR, and nDCG@k when enough labeled
  data exists.

## Configuration

Required environment variables:

- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `EMBEDDING_MODEL`
- `EMBEDDING_VECTOR_DIMENSIONS`
- `EMBEDDING_NORMALIZED`
- `LLAMA_SERVER_URL`

Optional bulk/notebook variables:

- `LEGAL_RUNTIME_CONTOUR`
- `LEGAL_EXTRACTION_POLICY_VERSION`
- `LEGAL_MANAGED_SMOKE_LIMIT`
- `RUN_LIVE_NEO4J_TESTS`
- `RUN_LIVE_EMBEDDING_TESTS`

Recommended defaults:

- `EMBEDDING_MODEL=jina-embeddings-v5-text-small-retrieval-GGUF`
- `EMBEDDING_VECTOR_DIMENSIONS=1024`
- `EMBEDDING_NORMALIZED=true`
- `LLAMA_SERVER_URL=http://127.0.0.1:18080/v1/embeddings`
- `ENABLE_EMBEDDING_ROUTER=false` for default local tests

## Test Strategy

Default test command:

```bash
python -m compileall src tests
python -m pytest
```

If pytest is not installed in `chbot`, install project development
dependencies in that environment before running tests.

Test categories:

- Unit: no live Neo4j, no live Jina, no paid APIs.
- Integration: live Neo4j and/or local Jina.
- Smoke: operator-managed or paid managed contour.

## Completion Criteria For The Foundation Stage

- Clean schema bootstrap works against Neo4j.
- Legal XML import preview works on the selected corpus.
- Load, verify, and delete work by law code.
- Source documents and fragments can be embedded through the local-only path.
- Structural retrieval baseline passes fixed validation cases.
- No inference layer is required to validate the database foundation.
- Bulk notebook execution is documented as a later operator-managed contour,
  with clear artifact and metadata contracts.
