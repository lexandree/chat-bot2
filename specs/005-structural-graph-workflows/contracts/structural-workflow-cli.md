# Contract: Structural Workflow CLI

## Purpose

Define the operator-facing command contract for generating structural graph
workflow artifacts. The command is a foundation workflow, not a chatbot or
answer-generation interface.

## Command

Seed-neighborhood mode:

```bash
python -m app traversal neighborhood \
  --workflow-mode seed_neighborhood \
  --law-code AufenthG \
  --seed-section-id legal-section:AufenthG:54:current \
  --relation-type CITES \
  --depth 1 \
  --fanout 25 \
  --node-limit 100 \
  --edge-limit 250 \
  --source-sample-limit 5 \
  --output data/structural_workflows/aufenthg_54_neighborhood.json
```

Law-scope overview mode:

```bash
python -m app traversal neighborhood \
  --workflow-mode law_scope_overview \
  --law-code AufenthG \
  --law-code AsylG \
  --law-code BeschV \
  --relation-type CITES \
  --fanout 25 \
  --node-limit 500 \
  --edge-limit 2000 \
  --source-sample-limit 5 \
  --output data/structural_workflows/real_data_scope_overview.json
```

The final command name may reuse the existing traversal command group, but the
contract requires a structural workflow action with JSON artifact output.

## Required Arguments

Workflow mode is required:

- `--workflow-mode`: `seed_neighborhood` or `law_scope_overview`

Selector requirements:

- `seed_neighborhood` requires `--seed-section-id` or a future equivalent exact
  section selector such as law code plus section reference.
- `law_scope_overview` requires at least one `--law-code` and does not require a
  seed section.

Scope and bounds:

- `--law-code`: repeatable law-code scope
- `--relation-type`: repeatable allowed trusted relation type
- `--output`: JSON artifact path

## Optional Arguments

- `--depth`: maximum traversal depth; default `1`, maximum `2`
- `--fanout`: maximum followed edges per section; default `25`, maximum `100`
- `--node-limit`: maximum visited section count; default `100`, maximum `1000`
- `--edge-limit`: maximum emitted resolved edge count; default `500`, maximum
  `5000`
- `--source-sample-limit`: maximum source samples per grouped boundary stop;
  default `5`, maximum `20`
- `--direction`: `outgoing`, `incoming`, or `both`; default `outgoing`
- `--include-boundary-stops`: default true
- `--include-inactive-sections`: default true when reached as selected or
  provenance context
- `--missing-target-inventory`: optional path to the post-004 inventory used
  for stale/coverage checks

## Output Payload

The command returns a machine-readable payload containing:

- `status`
- `workflow_mode`
- `structural_workflow_artifact_path`
- `selected_scope`
- `visited_section_count`
- `resolved_edge_count`
- `boundary_stop_count`
- `boundary_stops_by_reason`
- `missing_target_inventory_status`
- `warnings`

The artifact at `--output` must follow
[structural-neighborhood-artifact.md](./structural-neighborhood-artifact.md).

## Exit Behavior

- Exit success when the workflow completes and writes the artifact, even if
  coverage boundary stops are present.
- Exit non-zero when required selector input for the selected workflow mode is
  absent, bounds are invalid, the selected seed cannot be resolved, the selected
  law-code scope cannot be resolved, the artifact cannot be written, or graph
  access fails.
- Missing targets are not command failures; they are boundary evidence.
- Law-code overview mode must remain bounded by `--node-limit` and
  `--edge-limit`; it must not expand recursively from every section.
- Unknown `--relation-type` values are validation errors.
- Missing-target inventory affects reporting fields only. It must not affect
  trusted edge traversal or create inferred edges.

## Forbidden Behavior

- The command must not write trusted graph nodes or edges.
- The command must not infer missing target edges from inventory data.
- The command must not generate answer text, legal advice, or LLM-derived
  semantic output.
- The command must not require embeddings, GraphRAG sidecars, paid APIs, or
  remote notebooks.
