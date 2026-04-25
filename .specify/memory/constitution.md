<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Placeholder Principle 1 -> Database Before Inference
- Placeholder Principle 2 -> Structural Legal Graph First
- Placeholder Principle 3 -> Embeddings Are Indexes, Not Truth
- Placeholder Principle 4 -> LLM Outputs Are Reviewable Candidates
- Placeholder Principle 5 -> Framework-First GraphRAG
Added principles:
- Reproducible Operations
- Operator-Managed Bulk Runs Are Controlled Surfaces
- Test Boundaries Are Explicit
- Minimal Trusted Surface
Added sections:
- Mission
- Operational Constraints
- Development Workflow
Removed sections:
- None
Templates requiring updates:
- ✅ updated .specify/templates/constitution-template.md
- ✅ updated .specify/templates/plan-template.md
- ✅ updated .specify/templates/spec-template.md
- ✅ updated .specify/templates/tasks-template.md
- ✅ reviewed .specify/templates/checklist-template.md
- ✅ reviewed .specify/templates/agent-file-template.md
- ✅ no command templates present under .specify/templates/commands/
Follow-up TODOs:
- None
-->
# Legal GraphRAG Foundation Constitution

## Mission

Build a database-first legal knowledge foundation for GraphRAG systems.

The project exists to create a reliable, auditable legal graph and retrieval
baseline before any conversational inference layer is added. The knowledge base
MUST preserve source provenance, structural legal references, embedding
contracts, review boundaries, and operational repeatability.

## Core Principles

### I. Database Before Inference

The legal knowledge base is the primary product of the first stages.

- Ingestion, schema bootstrap, graph loading, verification, deletion, and
  reindexing MUST work before chatbot inference is introduced.
- No answer-generation path may be treated as complete until the graph and
  retrieval baseline can be validated independently.
- Demo responses MUST NOT mask missing database state.

**Rationale**: A legal answer layer is only defensible when the database and
retrieval evidence can be inspected independently.

### II. Structural Legal Graph First

Legal structure is a source-grounded fact layer, not an LLM interpretation.

- Legal acts, sections, fragments, references, and typed legal edges are
  canonical database objects.
- Exact legal-reference resolution and bounded graph traversal are required
  baselines.
- Structural retrieval MUST work without LLM extraction.
- Temporal metadata MUST support current-default and as-of-date behavior.

**Rationale**: Legal references, hierarchy, and temporal validity are
foundational facts that cannot be delegated to probabilistic extraction.

### III. Embeddings Are Indexes, Not Truth

Embeddings help retrieve source material. They do not define legal meaning.

- Query embeddings and document embeddings MUST preserve asymmetric prefix
  semantics: `Query: ` for search requests and `Document: ` for indexed source
  text.
- The active embedding profile MUST record provider, model, variant,
  dimensions, normalization, and task semantics.
- Unit tests MUST NOT require a live embedding service.
- Live embedding checks MUST be explicit integration or smoke tests.

**Rationale**: Embedding vectors are retrieval indexes. Their contract must be
auditable, repeatable, and separate from legal truth claims.

### IV. LLM Outputs Are Reviewable Candidates

LLMs may propose interpretations, but source texts remain authoritative.

- LLM-derived propositions, entities, claims, summaries, and enrichment outputs
  MUST start untrusted.
- Every persisted candidate MUST retain source support and runtime metadata.
- Weakly grounded, structurally invalid, ambiguous, or duplicate outputs MUST
  be rejected, flagged, or isolated before they can affect trusted retrieval.
- Only approved, non-flagged, non-isolated candidates may be used as trusted
  answer support.

**Rationale**: Generated legal interpretation needs an explicit review boundary
before it can influence trusted retrieval or answers.

### V. Framework-First GraphRAG

GraphRAG retrieval and inference MUST evaluate mature framework patterns unless
there is a documented reason not to.

- Neo4j-native GraphRAG patterns are preferred for Neo4j-backed vector and
  graph retrieval.
- Microsoft GraphRAG, Neo4j GraphRAG, LlamaIndex, and LangChain patterns may be
  evaluated for their relevant layer.
- Custom retrieval orchestration is allowed only when it is small, tested, and
  justified by legal-domain requirements.
- Framework adoption MUST NOT blur the boundary between ingestion, retrieval,
  review, and inference.

**Rationale**: Existing GraphRAG frameworks reduce bespoke infrastructure risk
when they preserve the project's legal-domain boundaries.

### VI. Reproducible Operations

Operators must be able to understand and repeat each stage.

- Load, verify, delete, and reindex operations MUST be idempotent or explicitly
  document their write semantics.
- Bulk runs MUST record effective runtime contour, model identifiers, embedding
  backend, policy or prompt version, processed count, skipped count, and failed
  count.
- Long-running operator-managed jobs MUST support resume-safe execution.
- Failure modes MUST be visible and MUST NOT silently produce trusted state.

**Rationale**: Legal graph state must be explainable after the fact, including
how it was produced and what failed.

### VII. Operator-Managed Bulk Runs Are Controlled Surfaces

Notebook and remote-runtime workflows are valid for bulk extraction,
validation, and profiling, but they are operator surfaces rather than the core
application architecture.

- Bulk notebooks MUST be disabled by default and require explicit operator
  opt-in.
- Runtime binaries, model artifacts, project code, input corpora, and run
  outputs MUST remain separate artifact classes.
- Every useful bulk run MUST export a coherent artifact bundle with run
  manifest, runtime profile, result JSON, logs, and command metadata.
- Project-specific legal inputs, outputs, and environment snapshots MUST remain
  private unless explicitly sanitized for publication.
- Reusable notebook logic MUST move into project modules once it becomes part
  of the system contract.

**Rationale**: Bulk runtime environments are useful but fragile. The durable
project contract must be explicit artifacts, metadata, and review boundaries.

### VIII. Test Boundaries Are Explicit

Tests must match the layer they validate.

- Unit tests MUST validate pure parsing, schema assembly, state transitions,
  and deterministic policies without live services.
- Integration tests MUST validate Neo4j, embedding service, and filesystem
  behavior.
- Smoke tests MUST validate operator-managed and managed runtime contours.
- Any test that depends on live Neo4j, live Jina, paid APIs, or remote
  notebooks MUST be marked and runnable separately.

**Rationale**: Fast deterministic tests protect core contracts, while live
service checks remain deliberate and separately runnable.

### IX. Minimal Trusted Surface

The project must start with a narrow, high-confidence scope.

- The first legal corpus slice MUST prioritize law and official guidance.
- The first retrieval baseline MUST prefer exact references and bounded
  traversal over broad semantic expansion.
- Inference is a later stage and MUST be measured against the structural
  baseline.
- Speculative abstractions MUST be deferred until database and retrieval
  evidence justify them.

**Rationale**: A small trusted surface makes provenance, validation, and review
practical before expanding retrieval or inference behavior.

## Operational Constraints

- The foundation stage MUST focus on source import, schema bootstrap,
  structural graph build, embedding indexes, retrieval baselines, reviewable
  semantic candidates, validation, and repeatable operations.
- Chat UX, production answer generation, and general-purpose agent behavior are
  out of scope until the database foundation is stable and separately
  validated.
- The graph of record MUST preserve source documents, source fragments, legal
  structure, provenance, checksums, temporal metadata, embedding profile
  metadata, review state, and validation evidence.
- Graph-write embedding workflows MUST fail fast when the required local-only
  embedding backend is unavailable.
- Notebook outputs MUST NOT become trusted graph state without validation and
  review.

## Development Workflow

- Feature specs MUST identify whether they affect schema, embedding contracts,
  review promotion, legal retrieval policy, runtime contours, or test
  boundaries.
- Implementation plans MUST pass the constitution check before design work and
  again after design work.
- Tasks MUST separate unit, integration, and smoke coverage according to the
  layer under test.
- Any live-service dependency MUST be explicit, marked, and excluded from
  default unit-test execution.
- Documentation MUST be updated when behavior, data contracts, operational
  contours, or governance-relevant assumptions change.

## Governance

This constitution supersedes conflicting project practices for the legal
knowledge foundation.

Changes that affect schema, embedding contract, review promotion, legal
retrieval policy, or runtime contours require an explicit design note or spec
update before implementation.

Amendments require:

- A documented rationale and affected principle or section.
- A semantic version decision using the policy below.
- A review of dependent spec-kit templates and runtime guidance.
- Updated validation expectations when the change affects tests or operational
  evidence.

Versioning policy:

- MAJOR: Backward-incompatible governance changes, principle removals, or
  redefinitions that alter project trust boundaries.
- MINOR: New principles, new mandatory sections, or materially expanded
  governance requirements.
- PATCH: Clarifications, wording fixes, or non-semantic refinements.

Compliance review:

- Every implementation plan MUST document the constitution check result.
- Any violation MUST be justified in the plan's complexity tracking section
  with the rejected simpler alternative.
- No module may introduce a hidden live-service dependency into default unit
  tests.
- No user-facing answer path may claim grounded support unless it cites
  persisted, verifiable source material or approved candidate support.

**Version**: 1.0.0 | **Ratified**: 2026-04-25 | **Last Amended**: 2026-04-25
