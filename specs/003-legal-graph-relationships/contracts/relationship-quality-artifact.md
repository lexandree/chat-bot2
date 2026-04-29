# Contract: Relationship Quality Artifact

## Purpose

Define the file artifact that operators use to validate relationship coverage
and graph quality for the new graph.

## Artifact Scope

The artifact is generated from persisted new-graph state for a selected
law-code scope. It is not graph state and does not compare against a legacy
graph.

## Required Fields

- `artifact_id`
- `selected_scope`
- `classifier_policy_version`
- `generated_at`
- `counts_by_relation_type`
- `counts_by_resolution_status`
- `sample_edges_by_relation_type`
- `sample_reference_evidence`
- `top_unresolved_targets`
- `source_to_relation_coverage`
- `fanout_summary`
- `temporal_metadata_completeness`
- `deferred_relation_strategy`

## Counts By Relation Type

Must include all taxonomy relation keys, even when count is zero:

- `CITES`
- `DEFINES`
- `APPLIES_IF`
- `REQUIRES`
- `EXCEPTION_TO`
- `EXCLUDES_IF`
- `AMENDS`
- `SUPERSEDED_BY`

## Counts By Resolution Status

Must include:

- `resolved`
- `out_of_scope`
- `unresolved`
- `ambiguous`

## Temporal Metadata Completeness

`temporal_metadata_completeness` must include the selected scope and minimum
summary fields needed to audit temporal evidence availability without requiring
complete historical reconstruction.

Required keys:

- `selected_scope`
- `counts_by_temporal_evidence_status`
- `counts_by_relation_type`
- `missing_field_summary`
- `total_reference_evidence_count`

`counts_by_temporal_evidence_status` must include all allowed temporal evidence
statuses, even when count is zero:

- `available`
- `partial`
- `not_available`
- `not_applicable`

`counts_by_relation_type` must include all supported relation types. Each
relation-type entry must include:

- `total`
- `with_any_temporal_metadata`
- `missing_required_temporal_fields`

`missing_field_summary` must count missing values for these evidence fields:

- `effective_from`
- `effective_until`
- `publication_date`
- `source_version_id`
- `source_revision_marker`
- `temporal_context_text`
- `temporal_context_checksum`

## Sample Rules

- Samples must be bounded and deterministic.
- Samples must include enough identifiers to inspect the source evidence and
  typed edge.
- Samples must not include generated answer text.

## Idempotency Rules

Regenerating the artifact for unchanged graph state and unchanged classifier
policy must keep deterministic sections stable.

Repeated relationship-refresh passes must not duplicate existing reference
records or typed edges.

## Deferred Relation Strategy

The artifact must report how `EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY` are
handled in this stage:

- recognized and counted
- stored only as evidence
- deferred because source metadata is insufficient
- not observed in the selected scope

## Forbidden Behavior

- Must not require legacy graph input.
- Must not require Microsoft GraphRAG or Neo4j GraphRAG sidecar execution.
- Must not include chatbot answers or trusted semantic candidate promotion.
