# Contract: Source Status and Resolution Reason Semantics

## Purpose

Define the minimum structural contract for inactive legal-unit detection and
explicit unresolved reasoning.

## Source Status Rules

Legal XML source markers such as `(weggefallen)`, `aufgehoben`, and
`außer Kraft` must be preserved as explicit source-status evidence.

`004` does not introduce a new graph entity for source structural units. Source
status belongs to the existing `LegalSection` identified by `legal_section_id`.
When the same section is referenced from `LegalReference` evidence, use
`source_legal_section_id`. `LegalFragment` and `SourceFragment` remain the
linked provenance/text anchors.

**Required status fields**:
- `legal_section_id`
- `law_code`
- `section_reference`
- `unit_status`
- `status_marker_text`
- `source_document_id`
- `source_fragment_id`
- `source_version_id`
- `source_revision_marker`
- `build_date`
- `content_checksum`

Allowed `unit_status` values for this feature:
- `active`
- `inactive`

Structural status marker policy:

- Mark a unit inactive when an inactive marker appears in an explicit XML/source
  status field, source metadata field, section title, or section heading.
- Body text markers count only when the marker appears in a documented status
  position: either the XML block is explicitly typed as status/note metadata, or
  the marker appears in the first non-empty body block before substantive text
  and that block consists only of the inactive marker plus punctuation,
  whitespace, dates, or version/build metadata.
- Body text markers do not count when they appear after substantive text, inside
  explanatory or historical prose, quoted text, references to another norm, or
  examples.
- Non-structural body occurrences must leave `unit_status = active` and must
  not populate `status_marker_text` as structural status evidence.
- When a marker is accepted as structural status evidence, preserve the original
  marker text and source provenance through `status_marker_text`,
  `source_fragment_id`, and source version/build fields.

## Resolution Reason Rules

Every non-resolved legal reference must map to one reason bucket. A reference to
an existing inactive target is a resolved reference with inactive target status,
not an unresolved reference.

**Required fields for non-resolved evidence**:
- `legal_reference_id`
- `resolution_status`
- `unresolved_reason`
- `raw_reference_text`
- `normalized_reference_text`
- `unresolved_target_evidence`

Target fields are conditionally required by reason:

| `unresolved_reason` | `target_law_code` | `target_section_reference` | Required evidence |
| --- | --- | --- | --- |
| `missing_target_in_corpus` | required | required | evidence that parsed target belongs to selected corpus family but is absent from loaded XML graph state |
| `out_of_scope_law` | required | required | evidence that parsed target law is outside selected corpus scope |
| `ambiguous_target` | optional | optional | candidate targets or ambiguity notes in `unresolved_target_evidence` |
| `parse_incomplete` | unset unless confidently parsed | unset unless confidently parsed | parse failure details in `unresolved_target_evidence` |
| `target_without_law_code` | unset | required | evidence that the section reference was parsed but law code was absent or unusable |

**Required fields for resolved inactive target evidence**:
- `legal_reference_id`
- `resolution_status`
- `target_legal_section_id`
- `target_unit_status`

Allowed `unresolved_reason` values:
- `missing_target_in_corpus`
- `out_of_scope_law`
- `ambiguous_target`
- `parse_incomplete`
- `target_without_law_code`

Inactive existing target rule:

- If the target `LegalSection` exists and has `unit_status = inactive`, use
  `resolution_status = resolved`.
- Populate `target_legal_section_id`.
- Set `target_unit_status = inactive`.
- Leave `unresolved_reason` unset.

Terminology rule:

- `out_of_scope` remains a `resolution_status` value inherited from `003`.
- `out_of_scope_law` is the `004` unresolved-reason and target-status bucket.
- `missing_target_in_corpus` is the only missing-target bucket name for `004`.
- `inactive_target` is not an allowed `unresolved_reason` in `004`; inactive
  existing targets are represented by `target_unit_status = inactive`.
- Do not introduce `missing_in_corpus` as a synonym in new artifacts.

## Forbidden Behavior

- No `SourceStructuralUnit` node label, canonical graph id, or parallel graph
  entity for the same legal section.
- No collapsing inactive targets into generic missing-target errors.
- No representing existing inactive targets as unresolved references.
- No use of answer text fields in status or resolution artifacts.
- No semantic inference is required to determine source status.
