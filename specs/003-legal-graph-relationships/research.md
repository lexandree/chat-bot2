# Research: Legal Graph Relationship Foundation

## Decision 1: Keep typed edges section-level in `003`

- **Decision**: Resolved typed legal edges target section-level legal nodes.
  More specific paragraph, sentence, number, appendix, and range anchors are
  preserved in `LegalReference` evidence.
- **Rationale**: The existing graph foundation is section-centered, and
  section-level edges keep traversal, idempotency, and verification manageable.
  Preserving sub-section anchors avoids losing precision and keeps a path open
  for later multi-resolution nodes.
- **Alternatives considered**:
  - Create paragraph/list/sentence target nodes now: rejected because it expands
    schema and parser scope before section-level relationships are reliable.
  - Ignore sub-section anchors: rejected because legal references often depend
    on paragraph, sentence, number, or range precision.

## Decision 2: Use one primary typed edge per LegalReference

- **Decision**: A resolved `LegalReference` may materialize at most one primary
  typed edge. Additional relation cues from the same context are stored as
  secondary signals in reference evidence.
- **Rationale**: Multi-signal legal contexts are common. One primary edge keeps
  traversal and quality reports interpretable, while secondary evidence
  preserves ambiguity for review and future classifier improvement.
- **Alternatives considered**:
  - Create multiple typed edges from one reference: rejected because it can
    inflate traversal fanout and make evidence hard to explain.
  - Create no edge for multi-signal contexts: rejected because it would hide
    useful direct relations that can be classified with a primary signal.

## Decision 3: Make five relation classifiers mandatory for first acceptance

- **Decision**: `003` acceptance requires classifier tests for `CITES`,
  `DEFINES`, `APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO`.
  `EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY` remain in the taxonomy with
  documented source strategy and evidence fields.
- **Rationale**: The mandatory set covers direct citation, definition,
  applicability, requirement, and exception behavior without forcing full
  amendment/version extraction before the source strategy is mature.
- **Alternatives considered**:
  - Require all eight relation types immediately: rejected as too broad for the
    first relationship-foundation slice.
  - Require only citation, definition, and exception: rejected because
    requirements and applicability are central to legal retrieval.

## Decision 4: Use explicit missing-target resolution statuses

- **Decision**: Resolution status uses:
  - `resolved` when exactly one target section is found
  - `out_of_scope` when the target law is outside the selected corpus scope
  - `unresolved` when the target law is in scope but the target section is
    missing
  - `ambiguous` when multiple target candidates match
- **Rationale**: These states make quality artifacts actionable. They separate
  normal corpus-boundary limits from parser or corpus-coverage problems.
- **Alternatives considered**:
  - Use only `resolved` and `unresolved`: rejected because it obscures whether
    missing targets are expected scope boundaries or real coverage failures.
  - Treat all missing targets as out of scope: rejected because in-scope missing
    sections should be visible as graph-quality issues.

## Decision 5: Support repeated idempotent relationship-refresh passes

- **Decision**: Operators may repeat relationship-refresh passes over a loaded
  corpus scope. Refreshes may add newly discovered evidence after
  parser-policy changes, but must not duplicate existing reference records or
  typed edges.
- **Rationale**: Microsoft GraphRAG-style indexing workflows often improve
  coverage through repeated passes and tuned extraction. The legal graph should
  support iterative improvement while preserving deterministic graph state.
- **Alternatives considered**:
  - One-shot relationship extraction only: rejected because classifier policies
    will improve as real corpus evidence is reviewed.
  - Delete and reload the whole graph for every parser change: rejected because
    it is operationally heavy and risks unrelated graph state.

## Decision 6: Treat GraphRAG frameworks as design references in `003`

- **Decision**: Microsoft GraphRAG and Neo4j GraphRAG guide methodology,
  terminology, and future retrieval design, but running either framework is not
  required for `003` acceptance.
- **Rationale**: The project needs framework-aware design without turning the
  relationship foundation into a sidecar pipeline integration. Legal XML
  structure and deterministic reference evidence remain authoritative.
- **Alternatives considered**:
  - Require Microsoft GraphRAG and Neo4j KG Builder sidecar runs before
    acceptance: rejected because it would add external runtime and dependency
    work outside the first relationship-foundation goal.
  - Ignore existing GraphRAG frameworks: rejected because framework patterns
    are useful for indexing separation, lexical graph design, prompt tuning,
    retrievers, and later semantic enrichment.

## Decision 7: Relationship-quality artifacts replace legacy comparison

- **Decision**: Acceptance evidence is a new-graph relationship-quality
  artifact with relation counts, resolution-status counts, sample edges,
  context samples, classifier-version metadata, source coverage, fanout
  summary, and temporal completeness.
- **Rationale**: This stage is about quality of the new graph, not similarity
  to old graph data. The artifact makes relationship coverage inspectable
  without reintroducing the legacy graph as a baseline.
- **Alternatives considered**:
  - Compare relationship coverage against the legacy graph: rejected because
    the spec explicitly excludes legacy graph comparison.
  - Rely only on tests: rejected because operators need corpus-level evidence
    after loading real data.

## Decision 8: Defer external graph-method research track

- **Decision**: Do not include Microsoft GraphRAG sidecar export, run-record, or
  proposal-review implementation tasks in `003`. Treat external graph-method
  research as a separate future feature that can compare Microsoft GraphRAG,
  LlamaIndex, Neo4j KG Builder, or schema-validation ideas after deterministic
  relationship refresh and relationship-quality artifacts exist.
- **Rationale**: Framework sidecars can reveal blind spots in deterministic
  relation rules, useful prompt-tuning hints, and future semantic extraction
  opportunities. They are more useful after `003` produces unresolved,
  ambiguous, high-fanout, and multi-signal evidence to sample from. Deferring
  the track preserves the legal XML source-of-truth boundary and keeps sidecar
  runtime availability from becoming a foundation implementation concern.
- **Alternatives considered**:
  - Require Microsoft GraphRAG sidecar execution before acceptance: rejected
    because it would make `003` depend on optional runtime, model, network, and
    framework state.
  - Implement a skipped-status-only sidecar path inside `003`: rejected because
    it still adds CLI, repository, artifact, and test surface to a feature whose
    critical path is deterministic parser, resolver, writer, and quality
    evidence.
  - Ignore Microsoft GraphRAG and related frameworks beyond documentation
    references: rejected because a later research feature can produce useful
    fixture and rule-improvement evidence without trusted graph writes.
  - Write framework-proposed relationships directly to Neo4j: rejected because
    sidecar output is LLM-derived research evidence and not authoritative legal
    structure.
