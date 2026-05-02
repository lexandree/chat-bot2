# Feature Specification: Corpus Boundary And Source Status Hardening

**Feature Branch**: `004-corpus-boundary-status`  
**Created**: 2026-04-30  
**Status**: Draft  
**Input**: User description: "Harden corpus-boundary and source-status semantics after the completed legal relationship foundation. Scope: detect inactive legal sections from German legal XML markers such as '(weggefallen)', 'aufgehoben', and 'außer Kraft'; preserve source document version/build metadata; refine LegalReference resolution evidence with explicit unresolved reasons such as missing_target_in_corpus, out_of_scope_law, ambiguous_target, parse_incomplete, and target_without_law_code; carry inactive existing targets as resolved references with inactive target status; extend relationship-quality artifacts with source status, target status, and unresolved-reason summaries; improve relationship-refresh behavior while preserving idempotency, stale edge cleanup, and the trusted graph boundary. Also produce a P3-readiness artifact that counts active/inactive structural units and classifies future norm-segmentation complexity without creating LegalNorm, Condition, LegalEffect, or Exception nodes. Do not add LLM semantic decomposition, chatbot UX, answer generation, GraphRAG inference, framework sidecars, guidance/case/wiki layers, trusted semantic candidates, or legacy graph comparison."

## Clarifications

### Session 2026-04-30

- Q: Should batched Neo4j writes remain part of `004`? → A: No. Defer batching to a separate research/optimization follow-up and keep `004` focused on source status, unresolved reasons, and structural output.
- Q: What does source structural unit identify? → A: No new graph entity. In `004`, a source structural unit is the existing `LegalSection` identified by `legal_section_id`; `source_legal_section_id` names that same id from `LegalReference` evidence, while `LegalFragment` and `SourceFragment` remain provenance/text anchors.
- Q: How are corpus-readiness structure classes assigned? → A: Deterministically, without LLMs, using a documented priority order and structural/text-marker signals: inactive_skipped first; mixed_content when two or more signals match; then definition_heavy, list_heavy, simple_paragraph, and unknown.
- Q: Which names are canonical for missing and out-of-scope summaries? → A: Keep `resolution_status = out_of_scope` for 003 compatibility, but use `unresolved_reason = out_of_scope_law`, `target_unit_status = out_of_scope_law`, `missing_target_in_corpus`, and `top_missing_targets` as the canonical new 004 names. Preserve `top_unresolved_targets` only as a baseline compatibility field.
- Q: How is a reference to an existing inactive target represented? → A: It is resolved, not unresolved. Store `resolution_status = resolved`, populate `target_legal_section_id`, set `target_unit_status = inactive`, and leave `unresolved_reason` unset.
- Q: Is the 004 relationship-quality artifact a breaking replacement for the existing 003 artifact? → A: No. It is a non-breaking extension that preserves existing baseline fields such as `counts_by_relation_type`, `sample_edges_by_relation_type`, `top_unresolved_targets`, and `deferred_relation_strategy`, while adding source-status, target-status, unresolved-reason, and `top_missing_targets` fields.
- Q: What belongs in `top_missing_targets`? → A: Only deterministic `missing_target_in_corpus` summaries. Each item includes target law/section, `reason = missing_target_in_corpus`, count, and bounded source samples; ambiguous, parse-incomplete, no-law-code, and out-of-scope references are excluded.
- Q: Are target law and section required for every non-resolved reference? → A: No. All non-resolved references must keep raw/normalized text and `unresolved_target_evidence`, but target fields are conditional: missing and out-of-scope references require parsed law and section; `target_without_law_code` requires section with no law; `parse_incomplete` and `ambiguous_target` may leave target fields unset when evidence explains why.
- Q: When does marker text count as structural inactive status instead of ordinary body text? → A: Markers in XML/source status fields, metadata, titles, or headings count. Body markers count only in documented status positions before substantive text; explanatory, historical, quoted, cross-reference, or example body text must remain ordinary text and must be covered by false-positive fixtures.
- Q: How should real-data `missing_target_in_corpus` records be handled after 004? → A: Record them as a post-004 missing-target inventory and treat them as known, potentially temporary corpus-coverage gaps. They are not parser failures, not trusted inferred edges, and not blockers for 005 graph workflows; later corpus expansion may remove or reclassify them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preserve Source Unit Status (Priority: P1)

As a corpus operator, I want inactive legal sections to be detected and stored
as source-grounded structural status so that missing, inactive, and active legal
units are not confused during later retrieval or semantic extraction.

**Why this priority**: Inactive status is a source fact. It must be visible
before any later corpus analysis so that a section marked as unavailable is not
treated as a live source unit.

**Independent Test**: Can be tested offline with XML fixtures containing active
sections, `(weggefallen)` headings, structural `aufgehoben` or `außer Kraft`
markers, and explanatory body text that contains the same words without setting
inactive status. The parsed preview and graph records preserve the status and
the source evidence for that status.

**Acceptance Scenarios**:

1. **Given** a legal XML section with a title `(weggefallen)`, **When** preview
   and graph load run, **Then** the corresponding legal section or structural
   unit is stored with an inactive status and source evidence for that status.
2. **Given** a section whose title, source status field, or documented leading
   body status position contains `aufgehoben` or `außer Kraft` as a
   source-status marker, **When** status detection runs, **Then** the status is
   captured with the original marker text and does not require semantic
   inference.
3. **Given** a section whose explanatory body text mentions `aufgehoben` or
   `außer Kraft` after substantive text, **When** status detection runs, **Then**
   the section remains active and the mention is not stored as structural
   `status_marker_text`.
4. **Given** a structural unit is inactive, **When** relationship refresh or
   future-readiness analysis runs, **Then** the unit remains auditable but is
   counted separately from active units.

---

### User Story 2 - Classify Relationship Resolution Reasons (Priority: P1)

As a graph operator, I want every non-resolved reference to have a specific
reason and every resolved inactive target to carry target status so that quality
artifacts reveal whether the issue is corpus coverage, target inactivity,
parsing ambiguity, or a true out-of-scope target.

**Why this priority**: A single unresolved bucket hides operationally different
problems. `missing_target_in_corpus` calls for corpus inspection, while
inactive target status and `out_of_scope_law` have different implications.

**Independent Test**: Can be tested by running relationship evidence assembly
against fixture sections with known active targets, inactive targets, missing
in-corpus targets, external-law targets, ambiguous targets, and malformed
references; inactive existing targets must resolve with inactive target status.

**Acceptance Scenarios**:

1. **Given** a reference target exists and is marked inactive, **When**
   relationship refresh runs, **Then** the reference records the resolved
   target and `target_unit_status = inactive` without setting
   `unresolved_reason`.
2. **Given** a reference target law is part of the selected corpus family but
   the referenced section is absent from the loaded XML files, **When**
   resolution runs, **Then** the reference uses `missing_target_in_corpus`.
3. **Given** a reference target law is outside the selected corpus scope, **When**
   resolution runs, **Then** the reference uses a distinct out-of-scope state
   or reason and does not get collapsed into `missing_target_in_corpus`.
4. **Given** a parser cannot confidently identify the target law or section,
   **When** evidence is assembled, **Then** the unresolved reason is explicit
   and raw/normalized reference text plus unresolved-target evidence remain
   available for review even when target law or section fields are unset.

---

### User Story 3 - Preserve Idempotency During Relationship Refresh (Priority: P2)

As an operator running real corpus refreshes, I want relationship refresh to be
idempotent so that repeated runs preserve the same graph state, evidence, and
stale-edge cleanup semantics.

**Why this priority**: Real corpus refreshes already work functionally, but
the corpus status and reason model must remain stable across repeated refreshes.
Batching is explicitly deferred to a later research/optimization step.

**Independent Test**: Can be tested by running the same fixture refresh twice
and confirming identical reference counts, edge counts, status counts, and
idempotent repeat behavior.

**Acceptance Scenarios**:

1. **Given** a fixture relationship refresh input, **When** refresh runs, **Then**
   the resulting graph state matches the existing trusted semantics.
2. **Given** the same refresh runs twice, **When** refresh is repeated, **Then**
   no duplicate trusted reference records or typed edges are created.
3. **Given** parser policy changes remove or reclassify a previously written
   edge, **When** refresh runs, **Then** stale primary typed edges are cleaned
   up within the selected scope.
4. **Given** a refresh partially fails, **When** the refresh report is
   generated, **Then** processed, skipped, failed, created, and updated counts
   remain visible and no silent success is reported.

---

### User Story 4 - Produce Corpus Readiness Evidence Without Semantic Extraction (Priority: P3)

As a maintainer planning later norm segmentation, I want an artifact that
summarizes which active structural units are suitable for future segmentation so
that the next semantic stage can start from corpus evidence rather than
assumptions.

**Why this priority**: The next research step needs a clear view of active and
inactive structure, but this feature must not create semantic nodes or answer
content.

**Independent Test**: Can be tested offline by assembling a readiness artifact
from fixture structural units that deterministically trigger
`inactive_skipped`, `definition_heavy`, `list_heavy`, `mixed_content`,
`simple_paragraph`, and `unknown` under the documented thresholds.

**Acceptance Scenarios**:

1. **Given** loaded legal sections, **When** readiness analysis runs, **Then**
   it reports counts by unit status and excludes inactive units from future
   semantic-extraction candidates by default.
2. **Given** sections that match `definition_heavy` or `list_heavy` signals,
   **When** readiness analysis runs, **Then** those sections are counted
   separately from `simple_paragraph` units using deterministic documented
   rules.
3. **Given** readiness analysis completes, **When** artifacts are reviewed,
   **Then** no `LegalNorm`, `Condition`, `LegalEffect`, `Exception`, answer
   text, or LLM-derived proposition is created.

---

### User Story 5 - Report Hardened Relationship Quality (Priority: P3)

As an operator, I want relationship-quality artifacts to include source status,
target status, unresolved reasons, and top missing targets so that graph
quality work is driven by actionable buckets rather than a generic unresolved
count.

**Why this priority**: The next corpus improvement decisions depend on knowing
which references are missing from the corpus, point to inactive existing
targets, are ambiguous, or are parse-incomplete.

**Independent Test**: Can be tested by generating the relationship-quality
artifact twice for unchanged graph state and confirming preserved baseline
fields plus deterministic status and unresolved-reason summaries.

**Acceptance Scenarios**:

1. **Given** a selected graph scope, **When** the quality artifact is
   generated, **Then** it includes counts by legal unit status, target unit
   status, and unresolved reason.
2. **Given** existing consumers read the 003 relationship-quality artifact
   shape, **When** a 004 artifact is generated, **Then** preserved baseline
   fields such as `counts_by_relation_type`, `sample_edges_by_relation_type`,
   `top_unresolved_targets`, and `deferred_relation_strategy` remain present.
3. **Given** missing targets occur repeatedly, **When** the artifact is
   generated, **Then** top missing targets and noisy source sections are
   visible as deterministic bounded summaries with target law, target section,
   count, `reason = missing_target_in_corpus`, and bounded source samples.
4. **Given** graph state is unchanged, **When** the artifact is regenerated,
   **Then** deterministic sections match the prior artifact.

### Edge Cases

- `weggefallen`, `aufgehoben`, or `außer Kraft` appears in explanatory text but
  not as a structural status marker.
- A law section is inactive, but references to it still appear in source text.
- A referenced target is present in the legal family but absent from the loaded
  XML slice.
- A reference omits the law code and must inherit scope from the source unit.
- A reference points to a paragraph, sentence, number, appendix, or range; the
  section-level target is still the primary resolution unit.
- A selected legal fragment contains repeated references to the same target.
- A repeated relationship refresh discovers additional evidence after policy
  changes; existing records are updated idempotently rather than duplicated.
- A readiness summary contains both structurally active and inactive units for
  the same law code, and the artifact must separate them clearly.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory)*

- **Foundation scope**: This feature extends the database-first legal
  foundation by separating active and inactive source units, refining
  resolution reasons, and improving corpus-readiness evidence. It does not add
  chatbot UX, answer synthesis, LLM proposition extraction, or GraphRAG
  inference.
- **Source and provenance**: The feature must preserve source document
  identity, source fragment identity, legal section identity, raw reference
  text, normalized reference text, source status markers, build/version
  metadata, target candidates, resolution state, and evidence-span identifiers.
- **Embedding contract**: This feature does not change embedding semantics.
  Embeddings remain retrieval indexes only. Default validation must not require
  a live embedding service.
- **Review boundary**: LLM and framework outputs remain out of trusted graph
  write scope. If produced outside this feature, they are research artifacts or
  reviewable candidate evidence only.
- **Operational contour**: Operators must be able to load or reuse selected
  corpus scopes, classify source unit status, refresh relationship evidence,
  repeat refresh passes idempotently, verify relation evidence, and generate
  corpus-quality and corpus-readiness artifacts.
- **Test boundary**: Unit tests cover status parsing, resolution-reason
  decisions, artifact assembly, and boundary rules without live services. Live
  Neo4j checks are explicit integration tests. Live embeddings, paid APIs,
  remote notebooks, chatbot UX, answer generation, and GraphRAG inference are
  not required for default validation.

### Functional Requirements

- **FR-001**: System MUST classify legal source units as active or inactive
  when the XML source marks them with status indicators such as `(weggefallen)`,
  `aufgehoben`, or `außer Kraft`.
- **FR-001a**: Inactive marker detection MUST follow the structural status
  marker policy: markers in source status fields, metadata, titles, or headings
  count; body markers count only in documented leading status positions; body
  markers in explanatory, historical, quoted, cross-reference, or example text
  MUST NOT mark a unit inactive.
- **FR-002**: System MUST preserve source document version and build metadata
  for loaded source units and relationship evidence.
- **FR-003**: System MUST store explicit unresolved reasons for non-resolved
  relationship evidence, including `missing_target_in_corpus`,
  `out_of_scope_law`, `ambiguous_target`, `parse_incomplete`, and
  `target_without_law_code`.
- **FR-003a**: Non-resolved relationship evidence MUST always preserve
  `raw_reference_text`, `normalized_reference_text`, and
  `unresolved_target_evidence`. `target_law_code` and
  `target_section_reference` MUST be conditionally required by reason:
  required for `missing_target_in_corpus` and `out_of_scope_law`; law unset and
  section required for `target_without_law_code`; optional when
  `parse_incomplete` or `ambiguous_target` evidence explains the missing target
  parts.
- **FR-004**: System MUST distinguish inactive targets from missing targets
  when relationship evidence is refreshed.
- **FR-004a**: When a reference target exists but is inactive, the reference
  MUST use `resolution_status = resolved`, MUST populate
  `target_legal_section_id`, MUST set `target_unit_status = inactive`, and MUST
  leave `unresolved_reason` unset.
- **FR-005**: Relationship-quality artifacts MUST include counts by source
  unit status, target status, unresolved reason, and top missing targets.
- **FR-005a**: Relationship-quality artifacts MUST use canonical `004`
  terminology: `missing_target_in_corpus`, `out_of_scope_law`, and
  `top_missing_targets`. The legacy `003` resolution status value
  `out_of_scope` remains valid only in `counts_by_resolution_status`.
- **FR-005b**: `top_missing_targets` MUST contain only
  `missing_target_in_corpus` entries with target law, target section, reason,
  count, and bounded source samples. It MUST exclude `ambiguous_target`,
  `parse_incomplete`, `target_without_law_code`, and `out_of_scope_law`.
- **FR-005c**: Relationship-quality artifacts MUST be non-breaking extensions
  of the existing `003` artifact shape by preserving `counts_by_relation_type`,
  `counts_by_resolution_status`, `sample_edges_by_relation_type`,
  `sample_reference_evidence`, `top_unresolved_targets`,
  `source_to_relation_coverage`, `fanout_summary`,
  `temporal_metadata_completeness`, and `deferred_relation_strategy`.
- **FR-006**: Relationship refresh MUST remain idempotent when run repeatedly
  against the same selected corpus scope.
- **FR-007**: Corpus-readiness artifacts MUST summarize active and inactive
  structural units and must not create `LegalNorm`, `Condition`,
  `LegalEffect`, or `Exception` nodes.
- **FR-007a**: Corpus-readiness structure classes MUST be assigned by
  deterministic rules with a stable priority order and thresholds. Required
  classes are `inactive_skipped`, `mixed_content`, `definition_heavy`,
  `list_heavy`, `simple_paragraph`, and `unknown`.
- **FR-008**: Default unit tests MUST run without live Neo4j, live Jina, paid
  APIs, remote notebooks, or private corpora.

### Key Entities *(include if feature involves data)*

- **Source Structural Unit**: A conceptual view of the existing `LegalSection`
  identified by `legal_section_id`, enriched with source provenance,
  version/build metadata, and active/inactive status. It is not a new graph
  entity.
- **Legal Reference Evidence**: A source-grounded record of a legal citation,
  including raw text, normalized text, context, target candidates, resolution
  reason, and status metadata.
- **Relationship-Quality Artifact**: A deterministic file artifact that
  summarizes reference status, unresolved reasons, and corpus coverage.
- **Corpus-Readiness Artifact**: A deterministic file artifact that summarizes
  active/inactive structural units and segmentation complexity for later
  research.
- **Corpus Readiness Structure Classifier**: A deterministic, non-semantic
  classifier that assigns one structure class per existing `LegalSection` using
  source status, marker counts, list signals, text length, and paragraph counts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can generate a deterministic status summary for a
  selected corpus slice that separates active and inactive structural units.
- **SC-002**: Every unresolved reference in the selected corpus is assigned one
  explicit reason bucket instead of a generic unresolved label.
- **SC-003**: Re-running relationship refresh on unchanged source data does not
  create duplicate trusted records or typed edges.
- **SC-004**: Relationship-quality and corpus-readiness artifacts can be
  regenerated with stable counts and stable bounded summaries for unchanged
  inputs.
- **SC-004a**: Fixture units covering `inactive_skipped`,
  `definition_heavy`, `list_heavy`, `mixed_content`, `simple_paragraph`, and
  `unknown` cases produce stable structure class assignments under the
  documented thresholds.
- **SC-005**: Default unit test runs complete without requiring live Neo4j,
  live Jina, paid APIs, remote notebooks, or chatbot inference.

## Assumptions

- Operators have access to the controlled legal XML corpus used by the
  foundation project.
- The inactive-source markers in the current corpus are sufficient to support
  deterministic status detection without adding semantic interpretation.
- Chatbot UX, answer generation, and GraphRAG inference remain out of scope
  until a later feature explicitly requests them.
- Live Neo4j and live embedding checks remain opt-in validation paths rather
  than default unit-test dependencies.
