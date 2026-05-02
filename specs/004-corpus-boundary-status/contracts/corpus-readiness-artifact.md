# Contract: Corpus Readiness Artifact

## Purpose

Define the file artifact used to summarize active and inactive structural units
for later segmentation work.

## Artifact Scope

The artifact is generated from the selected graph scope and source corpus
state. It is not trusted graph state.

## Required Fields

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

## Counts By Unit Status

Must include:

- `active`
- `inactive`

## Counts By Structure Class

Must include these deterministic structural categories:

- `inactive_skipped`
- `mixed_content`
- `definition_heavy`
- `list_heavy`
- `simple_paragraph`
- `unknown`

## Deterministic Structure Class Rules

Every existing `LegalSection` in the selected scope receives exactly one
structure class. The classifier is structural only: no LLMs, embeddings,
generated propositions, answer text, or semantic norm decomposition are allowed.
The top-level `structure_class_rules_version` is the required stable version
identifier for the classification rule set used to generate the artifact.

Class assignment MUST use this priority order:

1. `inactive_skipped`
2. `mixed_content`
3. `definition_heavy`
4. `list_heavy`
5. `simple_paragraph`
6. `unknown`

The required signals are:

- `inactive_signal`: `unit_status != active`.
- `definition_signal`: heading or body text contains at least one normalized
  definition marker (`begriffsbestimmung`, `definition`, `im sinne`,
  `bedeutet`, `bezeichnet`) OR the section has two or more existing
  `DEFINES` relationship evidence records.
- `list_signal`: XML/source metadata exposes at least one list or definition
  list item OR normalized body text contains three or more list item markers at
  line or clause boundaries. Text marker detection is limited to this explicit
  pattern set for `structure-class-rules-v1`: decimal markers like `1.` or
  `12.`, parenthesized decimal markers like `(1)` or `(12)`, single-letter
  markers like `a)` through `z)`, parenthesized single-letter markers like `(a)`
  through `(z)`, and double-letter markers like `aa)` through `zz)`.
- `long_or_multi_paragraph_signal`: paragraph count is two or more OR body text
  length is greater than 1200 characters.

Classification rules:

- If `inactive_signal` is true, assign `inactive_skipped`.
- Else if two or more of `definition_signal`, `list_signal`, and
  `long_or_multi_paragraph_signal` are true, assign `mixed_content`.
- Else if `definition_signal` is true, assign `definition_heavy`.
- Else if `list_signal` is true, assign `list_heavy`.
- Else if body text length is at most 1200 characters and paragraph count is at
  most one, assign `simple_paragraph`.
- Else assign `unknown`.

`complexity_summary` MUST record enough signal counts to reproduce the
assignment, including body text length, paragraph count, list marker count,
definition marker count, and existing `DEFINES` evidence count when available.
It may repeat `structure_class_rules_version` for convenience, but the top-level
field is authoritative.

## Forbidden Behavior

- Must not create `LegalNorm`, `Condition`, `LegalEffect`, or `Exception`
  nodes.
- Must not include answer text or semantic proposition output.
- Must not require embeddings for generation.
