# Data Model: Legal Graph Relationship Foundation

## Legal Reference Evidence

Parsed source-grounded legal reference record. It remains auditable whether or
not the target resolves.

**Fields**:
- `legal_reference_id`
- `source_legal_section_id`
- `source_legal_fragment_id`
- `source_fragment_id`
- `law_code`
- `raw_reference_text`
- `normalized_reference_text`
- `target_law_code`
- `target_section_reference`
- `target_legal_section_id`
- `subsection_anchor`
- `context_before`
- `context_text`
- `context_after`
- `context_checksum`
- `primary_relation_type`
- `secondary_relation_signals[]`
- `classifier_policy_version`
- `resolution_status`
- `unresolved_target_evidence`
- `effective_from`
- `effective_until`
- `publication_date`
- `source_version_id`
- `source_revision_marker`
- `temporal_context_text`
- `temporal_context_checksum`
- `temporal_evidence_status`

**Relationships**:
- Originates from one source/legal fragment.
- May resolve to one section-level target legal node.
- May materialize one primary typed legal edge.

**Validation rules**:
- `resolution_status` must be one of `resolved`, `out_of_scope`,
  `unresolved`, or `ambiguous`.
- A typed edge may be created only when `resolution_status = resolved`.
- Paragraph, sentence, number, appendix, and range detail belongs in
  `subsection_anchor`, not in a separate target node for this feature.
- Secondary signals must not create additional typed edges in `003`.
- `temporal_evidence_status` must be one of `available`, `partial`,
  `not_available`, or `not_applicable`.
- Temporal/version fields are evidence metadata. Missing temporal metadata must
  not prevent creation of a typed edge when the reference target is otherwise
  resolved.
- `AMENDS` and `SUPERSEDED_BY` evidence should preserve temporal context when
  available, but `003` does not require full historical version reconstruction.

## Typed Legal Edge

Section-level relationship between legal sections, traceable to a
`LegalReference`.

**Fields**:
- edge type: `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`, `EXCEPTION_TO`,
  `EXCLUDES_IF`, `AMENDS`, or `SUPERSEDED_BY`
- `legal_reference_id`
- `classifier_policy_version`
- `source_legal_section_id`
- `target_legal_section_id`
- `effective_from`
- `effective_until`
- `publication_date`
- `source_version_id`
- `temporal_evidence_status`

**Relationships**:
- From `LegalSection` to `LegalSection`.
- Backed by exactly one primary `LegalReference` evidence record.

**Validation rules**:
- One `LegalReference` may create at most one primary typed edge.
- No generic `RELATED` or `SEMANTICALLY_RELATED` edge is created by this
  structural feature.
- Typed edge writes must be idempotent across refresh passes.
- Typed edges may copy temporal/version metadata from the originating
  `LegalReference`, but the `LegalReference` remains the primary evidence
  record.

## Relationship Classifier Policy

Versioned deterministic policy used to classify legal-reference context.

**Fields**:
- `classifier_policy_version`
- mandatory relation set
- taxonomy relation set
- context-window policy
- primary-signal precedence
- secondary-signal rules
- deferred relation strategies

**Relationships**:
- Referenced by `LegalReference` evidence.
- Referenced by relationship-quality artifacts.

**Validation rules**:
- `003` acceptance requires classifier tests for `CITES`, `DEFINES`,
  `APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO`.
- `EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY` must have documented source
  strategy and evidence fields.
- Policy version changes must be visible in refresh outputs and artifacts.

## Relationship Refresh Pass

Repeatable operation that applies the current parser and classifier policy to a
selected loaded corpus scope.

**Fields**:
- `refresh_id`
- `selected_scope`
- `classifier_policy_version`
- `started_at`
- `finished_at`
- `processed_fragment_count`
- `created_reference_count`
- `updated_reference_count`
- `created_edge_count`
- `updated_edge_count`
- `skipped_count`
- `failed_count`
- `status`

**Relationships**:
- Consumes loaded source/legal fragments.
- Produces or updates `LegalReference` evidence and typed edges.
- Feeds relationship-quality artifact generation.

**Validation rules**:
- Repeating the same refresh over unchanged input and policy must not duplicate
  reference records or typed edges.
- A policy change may update reference evidence and add new evidence, but must
  remain scoped to the selected law codes.
- Failures must be visible in refresh summary output.

## Relationship Quality Artifact

File artifact summarizing relationship coverage and quality for the new graph.

**Fields**:
- `artifact_id`
- `selected_scope`
- `classifier_policy_version`
- `counts_by_relation_type`
- `counts_by_resolution_status`
- `sample_edges_by_relation_type`
- `sample_reference_evidence`
- `top_unresolved_targets`
- `source_to_relation_coverage`
- `fanout_summary`
- `temporal_metadata_completeness`
- `deferred_relation_strategy`
- `generated_at`

**Relationships**:
- Derived from the current graph state for a selected scope.
- Used as acceptance evidence for `003`.

**Validation rules**:
- Deterministic sections must match across repeated generation for unchanged
  graph state.
- The artifact must not compare against a legacy graph.
- The artifact must include classifier-policy version metadata.

## Framework Method Reference

Documented method mapping from Microsoft GraphRAG and Neo4j GraphRAG to project
boundaries.

**Fields**:
- `reference_name`
- `source_url`
- `method_area`
- `adopted_principle`
- `project_boundary`
- `excluded_runtime_requirement`

**Relationships**:
- Supports design notes and plan decisions.
- Does not write graph state.

**Validation rules**:
- Framework execution is not required for `003` acceptance.
- Any sidecar output produced outside `003` remains research or candidate
  evidence only.
