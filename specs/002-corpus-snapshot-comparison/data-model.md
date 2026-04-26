# Data Model: Real Corpus Snapshot Comparison

## Real Corpus Manifest

Describes which real legal XML sources are included in a run.

**Fields**:
- `name`
- `inputs[]`
- `path`
- `law_code`
- `jurisdiction`
- `language`
- `required`

**Relationships**:
- References one or more source files.
- Defines the selected corpus scope for preview.

**Validation rules**:
- Required inputs must exist before load.
- Optional missing inputs must be reported, not hidden.

## Real Corpus Preview

Deterministic file artifact produced from a manifest and selected scope.

**Fields**:
- `preview_id`
- `created_at`
- `source_scope`
- `missing_inputs[]`
- `source_documents[]`
- `source_fragments[]`

**Relationships**:
- Derives from `Real Corpus Manifest`.
- Feeds graph load workflows.

**Validation rules**:
- The same unchanged manifest and scope must produce stable identifiers and
  ordering.
- Preview is a file artifact, not persisted graph state.

## Loaded Scope

Persisted graph state for the selected corpus slice.

**Fields**:
- `law_codes`
- `source_document_count`
- `source_fragment_count`
- `legal_act_count`
- `legal_section_count`
- `legal_fragment_count`
- `legal_reference_count`
- `unresolved_reference_count`
- `embedding_count`
- `embedding_profile_ids[]`
- `vector_dimensions[]`
- `backend_names[]`

**Relationships**:
- Populated by loading a `Real Corpus Preview` into Neo4j.
- Consumed by snapshot generation and verification.

**Validation rules**:
- Load must be scoped and reversible.
- Verify must report stable counts for unchanged loaded state.

## Graph Snapshot Artifact

File artifact describing the shape of a loaded graph scope.

**Fields**:
- `snapshot_id`
- `source_scope`
- `selected_scope`
- `counts`
- `labels`
- `relation_types`
- `sample_ids`
- `source_coverage`
- `embedding_profile_metadata`
- `unresolved_reference_evidence`

**Relationships**:
- Derived from a loaded graph scope.
- Used as the comparison input for baseline analysis.

**Validation rules**:
- Snapshot must be reproducible for unchanged graph state.
- Snapshot is a file artifact, not graph state.

## Legacy AufenthG Baseline Graph Snapshot

Read-only structural artifact derived from the temporary `AufenthG` graph scope.

**Fields**:
- same shape as `Graph Snapshot Artifact`
- `baseline_scope`
- `baseline_origin`

**Relationships**:
- Represents the legacy AufenthG baseline graph comparison baseline.

**Validation rules**:
- Baseline snapshot is read-only.
- It must not be rewritten from the new graph.

## Comparison Report

File artifact describing differences between a new snapshot and a baseline snapshot.

**Fields**:
- `comparison_id`
- `new_snapshot_id`
- `baseline_snapshot_id`
- `matching[]`
- `missing[]`
- `extra[]`
- `summary_counts`
- `notes`

**Relationships**:
- Consumes `Graph Snapshot Artifact` and `Legacy AufenthG Baseline Graph Snapshot`.
- Does not mutate the graph.

**Validation rules**:
- Comparison must report missing, extra, and matching coverage.
- Comparison must not promote baseline content into trusted state.
