# Data Model: Corpus Boundary And Source Status Hardening

## Source Structural Unit

A conceptual view of an existing loaded `LegalSection` with provenance and
source-status metadata.

This feature MUST NOT introduce a new graph entity, node label, or canonical id
named `SourceStructuralUnit`. For `004`, the structural unit identity is the
existing `LegalSection.legal_section_id`. When status is referenced from
`LegalReference` evidence, the same value is carried as `source_legal_section_id`.
`LegalFragment` and `SourceFragment` remain provenance and text anchors linked
to that section.

**Fields**:
- `legal_section_id`
- `law_code`
- `section_reference`
- `title_text`
- `unit_status`
- `status_marker_text`
- `source_document_id`
- `source_fragment_id`
- `source_version_id`
- `source_revision_marker`
- `build_date`
- `content_checksum`
- `effective_from`
- `effective_until`
- `publication_date`

**Validation rules**:
- Source-status metadata is written onto or read from the existing legal section
  record and its linked provenance records; no separate source-structural-unit
  node is created.
- `unit_status` must distinguish active from inactive units.
- Inactive markers must be preserved as source evidence, not rewritten as
  inferred semantic labels.
- Inactive marker detection must follow the structural status marker policy in
  `contracts/source-status.md`: title/status-field markers count, while body
  text markers count only in documented status positions.
- Marker words in explanatory body text remain ordinary text and must not set
  `unit_status = inactive` or populate `status_marker_text`.
- Version/build metadata must remain attached to the structural unit.

## Legal Reference Evidence

Source-grounded citation evidence with explicit resolution status, optional
unresolved reason, and target unit status.

**Fields**:
- `legal_reference_id`
- `source_legal_section_id`
- `source_fragment_id`
- `raw_reference_text`
- `normalized_reference_text`
- `target_law_code` (conditional for non-resolved references)
- `target_section_reference` (conditional for non-resolved references)
- `target_legal_section_id`
- `resolution_status`
- `target_unit_status`
- `unresolved_reason` (unset for resolved references)
- `unresolved_target_evidence`
- `subsection_anchor`
- `context_before`
- `context_text`
- `context_after`
- `context_checksum`
- `classifier_policy_version`
- `temporal_context_text`
- `temporal_context_checksum`
- `temporal_evidence_status`

**Validation rules**:
- `source_legal_section_id` identifies the existing source `LegalSection`; it is
  not an alias for a new source-structural-unit entity.
- `resolution_status` must remain explicit and auditable.
- `unresolved_reason` must be one of the feature-defined reason buckets when
  the reference does not resolve.
- Non-resolved references must preserve `raw_reference_text`,
  `normalized_reference_text`, and `unresolved_target_evidence` even when target
  law or section fields are unset.
- `missing_target_in_corpus` and `out_of_scope_law` require both
  `target_law_code` and `target_section_reference`.
- `target_without_law_code` requires `target_law_code` to be unset and
  `target_section_reference` to be present; if the section is not confidently
  parsed, use `parse_incomplete` instead.
- `parse_incomplete` may leave target law and section fields unset when parser
  confidence is insufficient.
- `ambiguous_target` may leave target law or section fields unset when the
  ambiguity is represented in `unresolved_target_evidence`.
- `target_legal_section_id` is present only when the target resolves.
- If the target exists but is inactive, the reference is still resolved:
  `resolution_status = resolved`, `target_legal_section_id` is present,
  `target_unit_status = inactive`, and `unresolved_reason` is unset.

## Relationship Quality Artifact

Deterministic file artifact summarizing source and target status plus
resolution reasons.

**Fields**:
- `artifact_id`
- `selected_scope`
- `classifier_policy_version`
- `generated_at`
- `counts_by_relation_type`
- `counts_by_source_unit_status`
- `counts_by_target_unit_status`
- `counts_by_resolution_status`
- `counts_by_unresolved_reason`
- `sample_edges_by_relation_type`
- `sample_reference_evidence`
- `top_unresolved_targets`
- `top_missing_targets`
- `source_to_relation_coverage`
- `fanout_summary`
- `temporal_metadata_completeness`
- `deferred_relation_strategy`

**Validation rules**:
- Counts must be stable for unchanged graph state.
- No generated answer fields are allowed.
- Existing `003` baseline fields must remain present so `004` extends the
  relationship-quality artifact instead of replacing it.
- Missing targets and inactive targets must be visible separately.
- Inactive existing targets count under `counts_by_target_unit_status.inactive`
  and `counts_by_resolution_status.resolved`, not under
  `counts_by_unresolved_reason`.
- `counts_by_target_unit_status` must use canonical status values `active`,
  `inactive`, `missing_target_in_corpus`, and `out_of_scope_law`.
- `top_missing_targets` is the canonical `004` missing-target summary.
  `top_unresolved_targets` remains a preserved baseline compatibility field and
  must not be used as the canonical missing-target name in new logic.
- Every `top_missing_targets` item must include `target_law_code`,
  `target_section_reference`, `reason = missing_target_in_corpus`, `count`, and
  bounded `source_samples` with `legal_reference_id`,
  `source_legal_section_id`, `source_fragment_id`, and `raw_reference_text`.
- `top_missing_targets` must exclude `ambiguous_target`, `parse_incomplete`,
  `target_without_law_code`, and `out_of_scope_law`; those cases remain visible
  through unresolved-reason counts and bounded reference samples.

## Corpus Readiness Artifact

Deterministic file artifact summarizing active/inactive structural units and
future segmentation complexity.

**Fields**:
- `artifact_id`
- `selected_scope`
- `generated_at`
- `structure_class_rules_version`
- `counts_by_unit_status`
- `counts_by_structure_class`
- `active_unit_samples`
- `inactive_unit_samples`
- `complexity_summary`
- `excluded_semantic_candidates`

**Validation rules**:
- Must not create `LegalNorm`, `Condition`, `LegalEffect`, or `Exception`
  nodes.
- Must remain purely evidential and structural.
- Inactive units must be counted separately from active units.
- `structure_class_rules_version` is required at the artifact top level and is
  the authoritative version for deterministic structure-class rules.
- Structure classes must be assigned by the deterministic rules in
  `contracts/corpus-readiness-artifact.md`, with exactly one class per existing
  `LegalSection`.

## Unresolved Reason Enum

Explicit reason categories for non-resolved references.

**Allowed values**:
- `missing_target_in_corpus`
- `out_of_scope_law`
- `ambiguous_target`
- `parse_incomplete`
- `target_without_law_code`

**Validation rules**:
- Every reference with `resolution_status` of `unresolved`, `out_of_scope`, or
  `ambiguous` must map to one explicit reason bucket.
- References with `resolution_status = resolved` must not carry
  `unresolved_reason`; inactive resolved targets use
  `target_unit_status = inactive`.
- Reason values must be stable enough for deterministic artifact summaries.
