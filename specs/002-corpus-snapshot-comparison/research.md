# Research: Real Corpus Snapshot Comparison

## Decision 1: Keep preview as a file artifact

- **Decision**: Preview output stays a JSON file artifact derived from the real
  corpus manifest and selected law-code scope.
- **Rationale**: The preview is an inspection boundary, not persisted graph
  state. Keeping it file-based makes repeated runs deterministic and keeps graph
  writes separate from source normalization.
- **Alternatives considered**:
  - Persist preview as graph nodes: rejected because it blurs inspection with
    loaded state.
  - Skip preview and load directly: rejected because missing or malformed source
    files would only surface after graph mutation.

## Decision 2: Treat loaded corpus as the only graph state

- **Decision**: The new graph in Neo4j is the persisted source of truth for the
  selected corpus scope after load.
- **Rationale**: Snapshot comparison needs a stable persisted state to compare
  against, and delete/verify semantics must operate on actual graph records.
- **Alternatives considered**:
  - Keep comparison state in files only: rejected because the feature needs a
    real graph load/verify/delete path.
  - Reuse the old `AufenthG` graph as the working graph: rejected because it is
    only a temporary baseline reference.

## Decision 3: Use file-to-file comparison artifacts

- **Decision**: Snapshot artifacts and comparison reports are file artifacts,
  not comparison-only graph nodes.
- **Rationale**: The user explicitly separated file and graph concepts, and
  file artifacts are easier to version, remove, and compare after cutover.
- **Alternatives considered**:
  - Store snapshots in Neo4j: rejected because that would mix reporting with the
    graph being reported on.
  - Query the old graph live on every comparison: rejected because the old graph
    should remain a temporary read-only baseline, not a recurring dependency.

## Decision 4: Capture the legacy baseline once, then compare artifacts

- **Decision**: The legacy AufenthG baseline graph snapshot is represented as a
  read-only structural snapshot artifact that can be captured from the old
  graph once and then compared file-to-file.
- **Rationale**: This keeps the old graph out of the ongoing workflow while
  preserving a reference artifact that can be removed after cutover.
- **Alternatives considered**:
  - Keep querying the old graph live: rejected because it keeps the legacy graph
    in the runtime path.
  - Migrate the old graph into the new schema: rejected because the feature must
    not treat old data as source of truth.

## Decision 5: Preserve embedding metadata only as reporting evidence

- **Decision**: Snapshot and comparison artifacts report embedding profile and
  coverage metadata when present, but the feature does not alter embedding
  semantics.
- **Rationale**: Embedding values are existing indexes, not new truth sources,
  and the comparison stage should not change how embeddings are produced.
- **Alternatives considered**:
  - Recompute embeddings as part of comparison: rejected because it would make
    comparison dependent on live services and not just graph state.

## Decision 6: Keep the surface CLI-oriented and artifact-driven

- **Decision**: The feature stays within the existing CLI operator workflow and
  file artifact contract.
- **Rationale**: The project already uses CLI commands and artifact files for
  foundation operations, which keeps validation and operator workflows explicit.
- **Alternatives considered**:
  - Add a GUI or notebook-first workflow: rejected because the feature is about
    database-first comparison and repeatability.
