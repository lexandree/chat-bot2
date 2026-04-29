# Contract: Relationship Evidence

## Purpose

Define the minimum evidence contract for context-aware legal reference parsing,
relation classification, target resolution, and typed edge materialization.

## Parser Input

The parser consumes loaded or preview-derived legal fragments.

**Required input fields**:
- `source_fragment_id`
- `source_legal_fragment_id` or equivalent legal fragment id
- `source_legal_section_id`
- `law_code`
- `section_reference`
- `body_text`
- optional title or heading text
- selected corpus scope

**Optional temporal/source metadata input fields**:
- `effective_from`
- `effective_until`
- `publication_date`
- `source_version_id`
- `source_revision_marker`
- `source_metadata_checksum`

These fields are supplied from the loaded `SourceDocument`, `SourceFragment`,
`LegalSection`, or XML preview metadata when available. Relationship parsing
must preserve provided temporal/source metadata as evidence, may add
context-derived temporal evidence from headings or amendment wording, and must
mark missing values through `temporal_evidence_status` rather than inferring
them.

## Parsed Reference Candidate Output

The parser emits reference candidate evidence. Parser output is pre-resolution:
it may identify target law and section text, relation cues, temporal evidence,
and subsection anchors, but it must not claim a resolved graph target.

Every parsed reference candidate must be carried into relationship evidence
assembly. Assembly produces a `LegalReference` evidence record with explicit
resolution status.

**Required parser candidate fields**:
- `parsed_reference_id`
- `source_legal_section_id`
- `source_legal_fragment_id`
- `source_fragment_id`
- `law_code`
- `raw_reference_text`
- `normalized_reference_text`
- `target_law_code`
- `target_section_reference`
- `subsection_anchor`
- `context_before`
- `context_text`
- `context_after`
- `context_checksum`
- `primary_relation_type`
- `secondary_relation_signals`
- `classifier_policy_version`
- `effective_from`
- `effective_until`
- `publication_date`
- `source_version_id`
- `source_revision_marker`
- `temporal_context_text`
- `temporal_context_checksum`
- `temporal_evidence_status`

`context_before`, `context_text`, and `context_after` together represent the
bounded context window around the matched legal reference. `context_text`
contains the matched reference sentence or minimal evidence span used for
classification. `context_before` and `context_after` contain deterministic
bounded surrounding text from the same source fragment. `context_checksum` is
computed over the normalized concatenation of `context_before`, `context_text`,
and `context_after`.

## Resolved LegalReference Evidence

Relationship evidence assembly consumes parsed reference candidates, applies
selected-scope-aware target resolution, and emits `LegalReference` evidence
records for relationship refresh.

**Additional required resolved evidence fields**:
- `legal_reference_id`
- `target_legal_section_id`
- `resolution_status`
- `unresolved_target_evidence`

`target_legal_section_id` is populated only when `resolution_status` is
`resolved`. For `unresolved`, `ambiguous`, and `out_of_scope`, the target
candidate remains audit evidence and no typed legal edge may be materialized.

## Temporal/Version Evidence

Every `LegalReference` evidence record must include temporal/version evidence
keys, even when values are absent.

**Required keys**:
- `effective_from`
- `effective_until`
- `publication_date`
- `source_version_id`
- `source_revision_marker`
- `temporal_context_text`
- `temporal_context_checksum`
- `temporal_evidence_status`

Allowed `temporal_evidence_status` values:

- `available`
- `partial`
- `not_available`
- `not_applicable`

Missing temporal data must not be inferred from model output or embeddings.
If temporal evidence is unclear, preserve available context as evidence and
mark the status as `partial` or `not_available`.

## Relation Types

The full taxonomy is:

- `CITES`
- `DEFINES`
- `APPLIES_IF`
- `REQUIRES`
- `EXCEPTION_TO`
- `EXCLUDES_IF`
- `AMENDS`
- `SUPERSEDED_BY`

`003` acceptance requires classifier tests for:

- `CITES`
- `DEFINES`
- `APPLIES_IF`
- `REQUIRES`
- `EXCEPTION_TO`

`EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY` require documented source strategy
and evidence fields in this feature.

## Resolution Status

Allowed values:

- `resolved`: exactly one section-level target node is found
- `out_of_scope`: target law is outside the selected corpus scope
- `unresolved`: target law is in scope but target section is missing
- `ambiguous`: multiple target candidates match

## Edge Materialization Rules

- Typed edges target section-level legal nodes.
- Sub-section anchors remain evidence fields, not target nodes.
- A `LegalReference` may materialize at most one primary typed legal edge.
- Secondary relation signals do not create extra typed edges in `003`.
- No typed edge is created unless resolution status is `resolved`.
- Edge writes must be idempotent across relationship-refresh passes.

## Forbidden Behavior

- No legacy graph comparison.
- No migration from old graph data.
- No generic `RELATED` edge for structural legal meaning.
- No chatbot UX, answer generation, LLM proposition extraction, trusted
  semantic candidates, or GraphRAG inference.
- No mandatory Microsoft GraphRAG or Neo4j GraphRAG sidecar execution.
