# Contract: Relationship Quality Artifact

## Purpose

Define the file artifact used to validate relationship coverage, source status,
and unresolved-reason breakdowns for the hardened corpus boundary stage.

## Artifact Scope

The artifact is generated from persisted graph state for a selected scope. It
is deterministic for unchanged inputs and does not compare against a legacy
graph. The `004` artifact is a non-breaking extension of the existing `003`
relationship-quality artifact shape, not a replacement.

## Required Fields

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

## Preserved Baseline Fields

The following fields are preserved from the existing `003` artifact contract so
`004` remains an extension:

- `counts_by_relation_type`
- `counts_by_resolution_status`
- `sample_edges_by_relation_type`
- `sample_reference_evidence`
- `top_unresolved_targets`
- `source_to_relation_coverage`
- `fanout_summary`
- `temporal_metadata_completeness`
- `deferred_relation_strategy`

New `004` consumers should use `top_missing_targets` for the refined
missing-target summary. `top_unresolved_targets` remains a compatibility field
with the broader baseline unresolved-target summary semantics.

## Top Missing Targets

`top_missing_targets` is a bounded deterministic list containing only
references with `unresolved_reason = missing_target_in_corpus`.

Each item MUST include:

- `target_law_code`
- `target_section_reference`
- `reason` with the constant value `missing_target_in_corpus`
- `count`
- `source_samples`

Each `source_samples` item MUST include enough source identifiers to inspect
the evidence:

- `legal_reference_id`
- `source_legal_section_id`
- `source_fragment_id`
- `raw_reference_text`

Membership rules:

- Include only references where the target law and section were parsed
  confidently, the target law belongs to the selected corpus family, and the
  target section is absent from the loaded XML graph state.
- Exclude `ambiguous_target`, `parse_incomplete`, `target_without_law_code`, and
  `out_of_scope_law` references from `top_missing_targets`.
- Ambiguous and parse-incomplete references remain visible through
  `counts_by_unresolved_reason` and bounded `sample_reference_evidence`, not
  through `top_missing_targets`.
- Ordering MUST be deterministic, primarily by descending `count`, then by
  `target_law_code`, then by `target_section_reference`.

## Canonical Terminology

This feature keeps `resolution_status` compatible with `003`, adds a more
specific `unresolved_reason` breakdown for non-resolved references, and uses
`target_unit_status` for resolved inactive targets.

Canonical values:

- `resolution_status`: `resolved`, `out_of_scope`, `unresolved`, `ambiguous`
- `unresolved_reason`: `missing_target_in_corpus`, `out_of_scope_law`,
  `ambiguous_target`, `parse_incomplete`, `target_without_law_code`
- `target_unit_status`: `active`, `inactive`, `missing_target_in_corpus`,
  `out_of_scope_law`
- missing-target summary field: `top_missing_targets`
- baseline unresolved-target summary field: `top_unresolved_targets`

If a target exists and is inactive, the sample and counts must represent it as
`resolution_status = resolved` with `target_unit_status = inactive`; it must not
emit `unresolved_reason`.

Deprecated, compatibility, or forbidden names in new `004` artifacts:

- `missing_in_corpus` -> use `missing_target_in_corpus`
- `inactive_target` -> use `target_unit_status = inactive` on a resolved
  reference when the target exists
- `out_of_scope` as target-unit status -> use `out_of_scope_law`
- Do not use `top_unresolved_targets` as the canonical missing-target summary
  name in new code; use `top_missing_targets`. Preserve `top_unresolved_targets`
  as a baseline compatibility field.

## Counts By Source Unit Status

Must include:

- `active`
- `inactive`

## Counts By Target Unit Status

Must include:

- `active`
- `inactive`
- `missing_target_in_corpus`
- `out_of_scope_law`

## Counts By Resolution Status

Must include:

- `resolved`
- `out_of_scope`
- `unresolved`
- `ambiguous`

## Counts By Unresolved Reason

Must include the feature-defined reason buckets:

- `missing_target_in_corpus`
- `out_of_scope_law`
- `ambiguous_target`
- `parse_incomplete`
- `target_without_law_code`

Must not include `inactive_target`. Inactive existing targets are counted under
`counts_by_target_unit_status.inactive` and
`counts_by_resolution_status.resolved`.

## Sample Rules

- Samples must be bounded and deterministic.
- Samples must include enough identifiers to inspect the source evidence.
- Samples must not include answer text fields.

## Forbidden Behavior

- Must not require legacy graph input.
- Must not include chatbot answers or generated propositions.
- Must not require embeddings for artifact generation.
- Must not count existing inactive targets as unresolved reasons.
