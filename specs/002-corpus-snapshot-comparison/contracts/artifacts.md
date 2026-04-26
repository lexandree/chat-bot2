# Artifact Contracts: Real Corpus Snapshot Comparison

## Real Corpus Preview Artifact

Preview artifacts are JSON files produced from a real corpus manifest and a
selected law-code scope.

**Required fields**:
- `preview_id`
- `created_at`
- `source_scope`
- `missing_inputs`
- `source_documents`
- `source_fragments`

**Preview rules**:
- Preview is a file artifact, not persisted graph state.
- Deterministic repeated runs must keep identifiers, ordering, and checksums
  stable when inputs are unchanged.
- Missing optional inputs must be recorded in `missing_inputs`.

## Graph Snapshot Artifact

Snapshot artifacts are JSON files produced from a loaded graph scope.

**Required fields**:
- `snapshot_id`
- `selected_scope`
- `source_scope`
- `counts`
- `labels`
- `relation_types`
- `sample_ids`
- `source_coverage`
- `embedding_profile_metadata`
- `unresolved_reference_evidence`

**Snapshot rules**:
- Snapshot is a file artifact, not graph state.
- Snapshot reports on persisted loaded scope only.
- Snapshot artifacts must be reproducible for unchanged graph state.

## Legacy AufenthG Baseline Graph Snapshot Artifact

The legacy AufenthG comparison baseline is represented as a read-only JSON file
artifact with the same shape as the graph snapshot artifact plus:

- `baseline_scope`
- `baseline_origin`

**Baseline rules**:
- The baseline artifact may be captured from the old graph once.
- The baseline artifact is comparison evidence only.
- The baseline artifact must not be treated as a migration source.

## Comparison Report Artifact

Comparison reports are JSON files describing the differences between a new
graph snapshot and the baseline snapshot.

**Required fields**:
- `comparison_id`
- `new_snapshot_id`
- `baseline_snapshot_id`
- `matching`
- `missing`
- `extra`
- `summary_counts`

**Comparison rules**:
- Comparison must not create permanent graph nodes.
- Comparison must not copy old graph data into the new graph.
- Comparison must keep the baseline read-only.
