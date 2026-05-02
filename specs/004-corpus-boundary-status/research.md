# Research: Corpus Boundary And Source Status Hardening

## Decision 1: Treat inactive legal units as source status, not semantic output

- **Decision**: Detect inactive units from XML markers such as `(weggefallen)`,
  `aufgehoben`, and `außer Kraft`, and store them as source-grounded structural
  status.
- **Rationale**: These markers are source facts. They should be visible in
  preview, load, verification, and readiness artifacts before any semantic layer
  is introduced.
- **Alternatives considered**:
  - Infer inactivity from absence alone: rejected because absence in a selected
    corpus slice is different from an explicit inactive marker.
  - Ignore inactive markers until semantic extraction: rejected because the
    corpus boundary must be auditable at the structural layer.

## Decision 2: Split unresolved reasons from inactive target status

- **Decision**: Store explicit unresolved reasons such as
  `missing_target_in_corpus`, `out_of_scope_law`, `ambiguous_target`,
  `parse_incomplete`, and `target_without_law_code`. When the referenced target
  exists but is inactive, keep the reference resolved and store
  `target_unit_status = inactive` instead of an unresolved reason.
- **Rationale**: The current generic unresolved bucket conflates coverage gaps,
  parser limits, and corpus-boundary conditions. Separate buckets make quality
  work actionable, while resolved inactive targets remain distinguishable from
  missing targets without weakening resolution semantics.
- **Alternatives considered**:
  - Keep a single unresolved bucket: rejected because it hides the difference
    between expected corpus boundaries and genuine coverage problems.
  - Promote every unresolved item to a resolved candidate: rejected because it
    would weaken the trusted graph boundary.

## Decision 3: Keep structural output separate from embeddings

- **Decision**: The next stage is structural output. It does not require
  embeddings or vector indexes.
- **Rationale**: Structural output only needs source/legal structure,
  reference evidence, typed relations, and status metadata. Semantic retrieval
  and ranking can come later if needed.
- **Alternatives considered**:
  - Add embeddings now: rejected because this stage does not need semantic
    retrieval.
  - Require vector indexes for all graph output: rejected because it would
    incorrectly couple structural output to semantic infrastructure.

## Decision 4: Defer batched refresh optimization

- **Decision**: Relationship-refresh batching is not part of `004`.
- **Rationale**: It is a separate optimization concern and should be evaluated
  against the actual Neo4j batching patterns before any implementation decision
  is made.
- **Alternatives considered**:
  - Keep batching in scope: rejected after clarification because it would
    broaden the feature into optimization work.
  - Freeze the current per-record approach forever: rejected because batching
    may still be a useful later optimization.

## Decision 5: Preserve structural output as the next planned stage

- **Decision**: The next feature should be framed as structural output over the
  graph, not semantic output.
- **Rationale**: That keeps the next scope grounded in exact references,
  statuses, and bounded traversal without requiring embeddings or answer
  generation.
- **Alternatives considered**:
  - Jump directly to semantic retrieval: rejected because the structure/status
    layer is still being hardened.
  - Skip output artifacts altogether: rejected because operators need inspectable
    corpus evidence.

## Decision 6: Extend relationship-quality artifacts without breaking baseline fields

- **Decision**: The `004` relationship-quality artifact extends the existing
  `003` artifact shape. It preserves baseline fields such as
  `counts_by_relation_type`, `sample_edges_by_relation_type`,
  `top_unresolved_targets`, and `deferred_relation_strategy`, and adds the new
  source-status, target-status, unresolved-reason, and `top_missing_targets`
  fields.
- **Rationale**: The feature language says to extend relationship-quality
  artifacts. Preserving baseline fields avoids forcing existing checks and
  consumers to treat `004` as a breaking artifact version.
- **Alternatives considered**:
  - Replace the artifact with a new shape: rejected because no deliberate
    breaking artifact version was requested.
  - Keep only the old fields: rejected because `004` needs actionable source
    status, target status, and reason summaries.

## Decision 7: Carry missing targets forward as temporary coverage boundaries

- **Decision**: Real-data `missing_target_in_corpus` records are carried forward
  as an explicit post-004 inventory rather than blocking the next graph-workflow
  stage. The current smoke inventory is
  `data/relationship_quality/real_data_004_missing_targets.json`.
- **Rationale**: The smoke scope has 1666 resolved typed edges and 138
  unresolved references, all classified as `missing_target_in_corpus`. There
  are no out-of-scope, ambiguous, parse-incomplete, no-law-code, or inactive
  target cases. That makes the issue a selected-corpus coverage boundary, not a
  parser/resolver correctness failure.
- **Temporary nature**: A missing target means the referenced target section is
  absent from the selected loaded XML graph state. It does not assert that the
  section is permanently unavailable or absent from German law. Later corpus
  expansion may resolve or reclassify these references.
- **Operational boundary**: Do not infer trusted edges for missing targets.
  Until a later feature defines traversal policy, downstream graph workflows
  should operate on resolved typed edges and treat these references as explicit
  coverage-boundary stops.
- **Alternatives considered**:
  - Close all missing corpus coverage before graph workflows: rejected because
    it risks turning structural graph work into open-ended corpus chasing.
  - Ignore missing targets completely: rejected because downstream workflows
    need an auditable boundary artifact.
