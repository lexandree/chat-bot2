# Data Model: Structural Graph Workflows With Coverage Boundaries

## Structural Workflow Request

Operator-selected scope and traversal controls for a read-only graph workflow.

**Fields**:
- `workflow_id`
- `workflow_mode`
- `selected_scope`
- `seed_legal_section_ids`
- `law_codes`
- `direction`
- `max_depth`
- `allowed_relation_types`
- `fanout_limit`
- `node_limit`
- `edge_limit`
- `source_sample_limit`
- `include_boundary_stops`
- `include_inactive_sections`
- `generated_at`

**Validation rules**:
- `workflow_mode` must be `seed_neighborhood` or `law_scope_overview`.
- `seed_neighborhood` requires at least one exact seed legal section.
- `law_scope_overview` requires at least one law code and does not require seed
  sections.
- Default bounds are `direction = outgoing`, `max_depth = 1`,
  `fanout_limit = 25`, `node_limit = 100`, `edge_limit = 500`, and
  `source_sample_limit = 5`.
- 005 maximum bounds are `max_depth <= 2`, `fanout_limit <= 100`,
  `node_limit <= 1000`, `edge_limit <= 5000`, and
  `source_sample_limit <= 20`.
- `max_depth`, `fanout_limit`, `node_limit`, `edge_limit`, and
  `source_sample_limit` must be positive operator parameters after defaults are
  applied.
- `allowed_relation_types` must be limited to trusted structural relation
  types already supported by the relationship foundation; unknown relation
  types are validation errors.
- Request parameters must be recorded in every generated artifact so repeated
  runs can be compared.
- `law_scope_overview` is a bounded structural overview over selected law-code
  scope sections, resolved typed edges, and boundary stops. It must not be
  implemented as unbounded recursive traversal from every section.

## Structural Workflow Artifact

Deterministic read-only JSON artifact describing resolved structural graph
neighborhoods or law-code scope overviews and coverage boundaries for a
selected workflow request.

**Fields**:
- `artifact_id`
- `artifact_type`
- `generated_at`
- `workflow_request`
- `selected_scope`
- `sections`
- `resolved_edges`
- `coverage_boundary_stops`
- `quality_summary`
- `ordering_policy`
- `source_relationship_quality_artifact`
- `missing_target_inventory_reference`

**Validation rules**:
- `artifact_type` must be `structural_workflow`.
- Artifact content must be deterministic for unchanged graph state and identical
  workflow parameters, excluding timestamp or run-id fields.
- Artifact must not contain answer text, generated legal conclusions, LLM
  propositions, or trusted semantic candidate output.
- Artifact must not create or imply trusted edges for boundary stops.
- Required identity provenance must be present for each section, edge, and
  boundary item. Optional source/reference provenance available in graph state
  must be preserved; missing optional provenance must be reflected in
  `provenance_completeness` and `warnings`.

## Workflow Section Node

Structural representation of a selected or reached legal section.

**Fields**:
- `legal_section_id`
- `law_code`
- `section_reference`
- `title_text`
- `unit_status`
- `depth`
- `role`
- `source_document_id`
- `source_fragment_id`
- `content_checksum`
- `temporal_metadata`

**Validation rules**:
- `legal_section_id`, `law_code`, `section_reference`, `unit_status`, `depth`,
  and `role` are required identity provenance.
- `role` must identify whether the section is a seed, resolved neighbor,
  law-scope member, cross-scope context item, or inactive context item.
- Inactive sections remain auditable but must be marked with
  `unit_status = inactive`.
- Source provenance fields must be preserved when present in graph state.

## Resolved Traversal Edge

Trusted typed legal relationship followed by seed-neighborhood traversal or
collected by law-scope overview.

**Fields**:
- `edge_id`
- `source_legal_section_id`
- `target_legal_section_id`
- `relation_type`
- `depth`
- `legal_reference_ids`
- `raw_reference_texts`
- `source_fragment_ids`
- `classifier_policy_version`
- `target_unit_status`
- `temporal_evidence_status`

**Validation rules**:
- `edge_id`, `source_legal_section_id`, `target_legal_section_id`,
  `relation_type`, `depth`, and `legal_reference_ids` are required identity
  provenance.
- Edge must connect existing legal sections.
- Edge must originate from persisted resolved `LegalReference` evidence or a
  trusted typed legal edge written by relationship refresh.
- `relation_type` must be one of the trusted legal relation types.
- Missing targets must not appear as `target_legal_section_id`.

## Coverage Boundary Stop

Explicit non-inferred stop where workflow traversal could not continue because
the target is not a resolved graph section.

**Fields**:
- `boundary_id`
- `source_legal_section_id`
- `source_fragment_id`
- `legal_reference_id`
- `raw_reference_text`
- `normalized_reference_text`
- `target_law_code`
- `target_section_reference`
- `reason`
- `count`
- `source_samples`
- `inventory_match`

**Validation rules**:
- `reason` must be an unresolved-reason value, with
  `missing_target_in_corpus` as the primary 005 boundary reason.
- For `missing_target_in_corpus`, target law and section must be present.
- Boundary stops are not graph edges and must not be traversed as neighbors.
- `inventory_match` records whether the stop matched the post-004 missing target
  inventory for the selected scope.
- Multiple references to the same missing target may be grouped when count and
  source samples remain visible.
- Grouping key is `reason`, `target_law_code`, `target_section_reference`, and
  selected law-code scope.
- `source_samples` must contain at most `source_sample_limit` entries sorted by
  `source_legal_section_id`, `source_fragment_id`, and `legal_reference_id`.
- Each source sample must include `legal_reference_id`,
  `source_legal_section_id`, `source_fragment_id`, `raw_reference_text`, and
  `normalized_reference_text`. If normalized text is absent in graph state, the
  field remains present with a null value and the gap is reflected in
  provenance completeness.
- `inventory_match` must be one of `matched`, `not_found`, `not_checked`, or
  `stale_inventory`.

## Workflow Quality Summary

Summary evidence for structural workflow completeness and boundary behavior.

**Fields**:
- `visited_section_count`
- `resolved_edge_count`
- `resolved_edges_by_relation_type`
- `boundary_stop_count`
- `boundary_stops_by_reason`
- `truncation_count`
- `cycle_boundary_count`
- `inactive_section_count`
- `provenance_completeness`
- `missing_target_inventory_status`
- `warnings`

**Validation rules**:
- Counts must match the artifact sections, edges, and boundary items.
- `edge_limit` truncation must be reflected in truncation or warning metadata.
- Provenance completeness must separately account for section, edge, reference,
  and source-fragment identifiers.
- `missing_target_inventory_status` must be one of `not_provided`, `available`,
  `missing_file`, `stale`, or `scope_mismatch`.
- Warnings must be visible and must not convert failures into trusted success.
