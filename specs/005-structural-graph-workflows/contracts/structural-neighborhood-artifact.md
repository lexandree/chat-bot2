# Contract: Structural Workflow Artifact

## Purpose

Define the deterministic JSON artifact produced by structural graph workflows.
The artifact lets operators inspect resolved legal neighborhoods or bounded
law-code scope overviews while seeing where traversal stopped at coverage
boundaries.

The filename keeps the earlier neighborhood name for continuity; the artifact
contract is `structural_workflow`.

## Scope

The artifact is read-only evidence generated from persisted graph state for a
selected workflow request. It is not trusted graph state and must not mutate
Neo4j.

## Required Top-Level Fields

- `artifact_id`
- `artifact_type`
- `generated_at`
- `workflow_id`
- `workflow_request`
- `selected_scope`
- `sections`
- `resolved_edges`
- `coverage_boundary_stops`
- `quality_summary`
- `ordering_policy`
- `warnings`

Optional context fields:

- `source_relationship_quality_artifact`
- `missing_target_inventory_reference`

## Artifact Type

`artifact_type` must be `structural_workflow`.

`workflow_id` is a deterministic workflow-content identifier used for repeat
comparison. Repeatability checks may exclude `workflow_id`, `artifact_id`, and
`generated_at` when comparing two generated files.

## Workflow Request

Must include:

- `workflow_mode`
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

Allowed `workflow_mode` values:

- `seed_neighborhood`: requires at least one exact seed legal section and
  follows bounded resolved typed paths from those seeds.
- `law_scope_overview`: requires at least one law code and produces a bounded
  structural overview of scope sections, resolved typed edges, and coverage
  boundary stops without recursive traversal from every section.

Default bounds:

- `direction = outgoing`
- `max_depth = 1`
- `fanout_limit = 25`
- `node_limit = 100`
- `edge_limit = 500`
- `source_sample_limit = 5`

Maximum accepted bounds for 005:

- `max_depth <= 2`
- `fanout_limit <= 100`
- `node_limit <= 1000`
- `edge_limit <= 5000`
- `source_sample_limit <= 20`

## Sections

Each section item must include:

- `legal_section_id`
- `law_code`
- `section_reference`
- `unit_status`
- `depth`
- `role`
- source provenance fields when available

Required identity provenance for section items:

- `legal_section_id`
- `law_code`
- `section_reference`
- `unit_status`
- `depth`
- `role`

Allowed `role` values:

- `seed`
- `resolved_neighbor`
- `scope_member`
- `cross_scope_context`
- `inactive_context`

## Resolved Edges

Each resolved edge item must include:

- `source_legal_section_id`
- `target_legal_section_id`
- `relation_type`
- `depth`
- `legal_reference_ids`
- `source_fragment_ids`

Required identity provenance for resolved edge items:

- `source_legal_section_id`
- `target_legal_section_id`
- `relation_type`
- `depth`
- `legal_reference_ids`

Resolved edge rules:

- Only resolved trusted typed legal edges may appear.
- `target_legal_section_id` must identify an existing section in graph state.
- The artifact must not synthesize a resolved edge from
  `missing_target_in_corpus` evidence.
- In `seed_neighborhood` mode, resolved edges are followed from exact seed
  sections according to workflow bounds.
- In `law_scope_overview` mode, resolved edges are collected for the selected
  law-code scope according to relation, direction, node, and edge limits; this
  mode is not unbounded recursive traversal from every section.

## Coverage Boundary Stops

Each boundary stop item must include:

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

For `missing_target_in_corpus` boundary stops:

- `reason` must be `missing_target_in_corpus`.
- Target law and section must be present.
- The stop must not appear in `resolved_edges`.
- The stop may be grouped with other references to the same target only when
  `count` and bounded `source_samples` remain visible.
- Grouping key is `reason`, `target_law_code`, `target_section_reference`, and
  selected law-code scope.
- `source_samples` must contain at most `source_sample_limit` items sorted by
  `source_legal_section_id`, `source_fragment_id`, and `legal_reference_id`.
- Each source sample must include `legal_reference_id`,
  `source_legal_section_id`, `source_fragment_id`, `raw_reference_text`, and
  `normalized_reference_text`. If normalized text is absent in graph state, the
  field remains present with a null value and the gap is reflected in
  provenance completeness.
- Boundary stop `normalized_reference_text` follows the same rule: the field is
  always present and may be null when graph state lacks normalized text.
- `inventory_match` must be `matched`, `not_found`, `not_checked`, or
  `stale_inventory`.

Other unresolved reasons may be reported as boundary stops when present, but
they must remain separate reason buckets.

## Quality Summary

Must include:

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
- `workflow_mode`

`missing_target_inventory_status` must be `not_provided`, `available`,
`missing_file`, `stale`, or `scope_mismatch`.

`provenance_completeness` must report required identity provenance and optional
source/reference provenance separately. Missing optional provenance must not be
hidden.

## Deterministic Ordering

Artifact arrays must use stable ordering:

- sections by depth, role, law code, section reference, then id
- resolved edges by depth, relation type, source id, target id, then reference id
- boundary stops by reason, target law code, target section reference, source
  id, then legal reference id

When `edge_limit` or `node_limit` affects output, truncation metadata must be
stable and visible in `quality_summary`.

## Forbidden Behavior

- Must not include chatbot answers or generated legal conclusions.
- Must not include LLM propositions, claims, summaries, or trusted semantic
  candidates.
- Must not infer missing target nodes or edges.
- Must not require embeddings or vector indexes.
- Must not require legacy graph comparison input.
