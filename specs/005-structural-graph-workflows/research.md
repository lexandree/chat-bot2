# Research: Structural Graph Workflows With Coverage Boundaries

## Decision 1: Make 005 Workflows Read-Only Over Trusted Graph State

- **Decision**: Structural workflows read existing `LegalSection`,
  `LegalReference`, and typed legal-edge state and write only generated JSON
  artifacts or command output. They do not mutate trusted graph state.
- **Rationale**: The purpose of 005 is to start using the graph foundation, not
  to alter source or relationship truth. Read-only semantics keep 005 distinct
  from ingestion, relationship refresh, corpus expansion, and review promotion.
- **Alternatives considered**:
  - Persist workflow runs as graph nodes: rejected because the first workflow
    surface needs inspectable output, not additional trusted graph schema.
  - Re-run relationship refresh inside each workflow: rejected because refresh
    is an explicit 003/004 operation and would blur operator boundaries.

## Decision 2: Traverse Only Resolved Typed Legal Edges

- **Decision**: Workflow traversal and scope overview collection use only
  resolved typed legal edges and explicit depth, relation-type, fanout, node,
  and edge limits. `seed_neighborhood` follows bounded paths from exact seed
  sections. `law_scope_overview` collects a deterministic bounded overview for
  selected law-code scopes without recursive traversal from every section.
- **Rationale**: The project constitution prioritizes exact references and
  bounded typed traversal. The current graph already has a useful resolved
  surface, while unresolved references are not safe traversal edges.
- **Alternatives considered**:
  - Traverse unresolved references as candidate edges: rejected because it would
    infer trusted graph structure from missing corpus targets.
  - Use vector or semantic expansion for gaps: rejected because embeddings and
    semantic inference are outside 005.
  - Traverse all relations recursively: rejected because legal citation graphs
    can be dense and cyclic.

## Decision 3: Represent Missing Targets As Coverage Boundary Stops

- **Decision**: `missing_target_in_corpus` references become explicit
  `Coverage Boundary Stop` items in workflow artifacts. They include target law
  and section where available, reason, count or reference id, and bounded source
  samples, but they do not create neighbor nodes or edges.
- **Rationale**: The post-004 smoke has 138 unresolved references, all
  `missing_target_in_corpus`, grouped into 81 unique missing targets. This is a
  selected-corpus coverage boundary, not evidence that parser/resolver quality
  blocks graph use.
- **Temporary nature**: Boundary stops may disappear after later corpus
  expansion. Artifacts should therefore record current graph/inventory context
  without treating the gap as a permanent legal fact.
- **Alternatives considered**:
  - Block 005 until all missing targets are loaded: rejected because it risks
    open-ended corpus chasing before graph workflows can be evaluated.
  - Ignore missing targets in workflow output: rejected because operators need
    to see where traversal stopped.

## Decision 4: Produce Deterministic JSON Artifacts Before User-Facing Output

- **Decision**: The primary output is a deterministic structural workflow JSON
  artifact with explicit `workflow_mode`. CLI presentation can summarize the
  same payload, but the JSON artifact is the contract.
- **Rationale**: JSON artifacts match the existing foundation pattern for
  import previews, relationship-quality reports, and corpus-readiness reports.
  They are easy to test, diff, store as ignored run artifacts, and inspect
  without adding UX or answer-generation scope.
- **Alternatives considered**:
  - Build a UI or report page: rejected as out of scope for the foundation
    stage.
  - Return only terminal text: rejected because deterministic validation and
    follow-on planning need a structured artifact.

## Decision 5: Extend The Existing Traversal Surface Conservatively

- **Decision**: Use the existing `traversal` CLI/repository area as the natural
  operator surface, extending it with artifact output, explicit workflow modes,
  and boundary reporting rather than introducing a separate product surface.
- **Rationale**: `src/retrieval/legal_traversal.py` already contains bounded
  traversal policy, and `src/app/commands.py` already exposes a `traversal run`
  command. Extending this path keeps the implementation small and aligned with
  current code boundaries.
- **Alternatives considered**:
  - Add a new top-level command group such as `workflows`: rejected for the
    initial 005 slice because it would duplicate traversal concepts.
  - Move traversal into GraphRAG or inference packages: rejected because 005 is
    structural and pre-inference.

## Decision 6: Validate With Fixture Unit Tests Plus Gated Neo4j Smoke

- **Decision**: Default validation uses fixture-based unit tests for traversal
  policy, artifact assembly, boundary-stop normalization, and CLI command
  shape. Live Neo4j coverage is optional and gated.
- **Rationale**: This preserves test-boundary discipline and keeps default
  validation fast. Live graph checks are still useful for the real 004 smoke
  scope but must remain deliberate.
- **Alternatives considered**:
  - Require live Neo4j for default validation: rejected because default unit
    tests must not depend on live services.
  - Validate only with unit tests: rejected because the operator workflow should
    have at least one gated live smoke path before being considered ready.
