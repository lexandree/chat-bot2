# Feature Specification: Legal Graph Relationship Foundation

**Feature Branch**: `003-legal-graph-relationships`  
**Created**: 2026-04-27  
**Status**: Draft  
**Input**: User description: "Build legal graph relationship foundation from real German legal XML corpus. Scope: context-aware legal reference parsing, typed legal relation extraction, source-grounded LegalReference audit records, resolved typed Neo4j edges, unresolved and ambiguous reference evidence, temporal/version relation metadata, new-graph relationship quality artifacts, and tests. Do not compare against a legacy graph. Do not migrate old graph data. Do not add chatbot UX, answer generation, LLM proposition extraction, trusted semantic candidates, or GraphRAG inference. Use Microsoft GraphRAG and Neo4j GraphRAG as methodological references for indexing, relationship extraction, lexical graph design, and future retrieval, while treating German legal XML structure and explicit legal references as authoritative."

## Clarifications

### Session 2026-04-27

- Q: What granularity should typed legal edges target when a reference points to paragraph, sentence, number, appendix, or range detail? -> A: Section-level typed edges, with sub-section anchors stored in reference evidence.
- Q: What role should Microsoft GraphRAG and Neo4j GraphRAG play in `003` acceptance? -> A: Documentation/design reference only; no sidecar execution required in `003`.
- Q: How should multi-signal contexts be represented when one reference has several relation cues? -> A: One primary typed edge; secondary signals stored in reference evidence.
- Q: Which relation types require classifier tests for `003` acceptance? -> A: Mandatory tests for `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO`; other taxonomy relations need documented strategy.
- Q: How should missing target resolution states be classified? -> A: `out_of_scope` for target law outside selected scope, `unresolved` for missing in-scope target, and `ambiguous` for multiple matches. Repeated relationship-refresh passes may improve coverage but must remain idempotent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Parse References With Context (Priority: P1)

As a corpus operator, I want explicit legal references in the real German legal
XML corpus to be parsed together with their surrounding context so that each
reference has auditable source evidence before any typed legal edge is created.

**Why this priority**: Typed legal relationships are only trustworthy when the
source reference, nearby wording, source fragment, and resolution status are
visible. A relation classifier that sees only the matched `§ ...` text is not a
valid legal foundation.

**Independent Test**: Can be tested offline by running selected legal fragments
through the parser and confirming that every parsed reference includes raw text,
normalized text, source fragment identity, context evidence, target law/section
candidate, classifier version, and resolution status.

**Acceptance Scenarios**:

1. **Given** a source fragment that cites another section, **When** reference
   parsing runs, **Then** the resulting reference record includes the raw
   citation, normalized citation, source fragment id, context evidence, target
   law code, target section reference, classifier version, and an initial
   resolution status.
2. **Given** a reference embedded in wording that signals definition,
   requirement, applicability, exception, exclusion, amendment, or supersession,
   **When** relation classification runs, **Then** the classifier uses the
   context window rather than only the matched citation text.
3. **Given** a reference target is absent from the selected corpus, **When**
   parsing and resolution run, **Then** the reference remains stored as
   unresolved or out-of-scope evidence without creating a misleading typed edge.

---

### User Story 2 - Materialize Typed Legal Edges (Priority: P2)

As a graph operator, I want resolved legal references to become distinct typed
legal edges so that structural retrieval can distinguish citations,
definitions, requirements, applicability, exceptions, exclusions, amendments,
and supersession.

**Why this priority**: A legal graph cannot collapse legally different
relationships into generic similarity. Typed edges are the minimum structure
needed for later explainable GraphRAG retrieval.

**Independent Test**: Can be tested by building a structural graph from a
bounded corpus preview as base source/legal structure, then running
relationship refresh and confirming that resolved references produce typed
edges from source legal sections to target legal sections, while unresolved or
ambiguous references remain audit records only.

**Acceptance Scenarios**:

1. **Given** a parsed and resolved `CITES` reference, **When** relationship
   refresh runs after base graph loading, **Then** the graph contains the
   corresponding `LegalReference` record and a typed `CITES` edge with
   traceable source evidence.
2. **Given** parsed references classified as `DEFINES`, `APPLIES_IF`,
   `REQUIRES`, or `EXCEPTION_TO`, **When** relationship refresh runs after
   base graph loading,
   **Then** each resolved reference creates only the corresponding relation
   type and does not also create a generic related edge.
3. **Given** temporal or version evidence indicates amendment or replacement,
   **When** relationship refresh runs after base graph loading, **Then**
   `AMENDS` or `SUPERSEDED_BY` relation strategy and evidence fields are
   documented even if full classifier coverage is not required for `003`
   acceptance.

---

### User Story 3 - Report Relationship Quality (Priority: P3)

As an operator, I want relationship-quality artifacts for the new graph so that
I can validate coverage, unresolved references, classifier behavior, and graph
shape without comparing against a legacy graph.

**Why this priority**: The accepted evidence for this stage must be quality of
the new source-grounded relationship foundation, not similarity to old graph
data.

**Independent Test**: Can be tested by generating a relationship-quality
artifact twice for unchanged graph state and confirming deterministic relation
counts, unresolved-reference summaries, sample edges, classifier-version
metadata, source coverage, fanout summaries, and temporal completeness.

**Acceptance Scenarios**:

1. **Given** a loaded selected corpus scope, **When** the relationship-quality
   artifact is generated, **Then** it includes relation counts by type,
   resolution-status counts, top unresolved targets, bounded sample edges,
   source-to-relation coverage, classifier version, and temporal metadata
   completeness.
2. **Given** graph state has not changed, **When** the artifact is regenerated,
   **Then** deterministic sections match the previous artifact.
3. **Given** the selected corpus contains unresolved, ambiguous, or
   out-of-scope references, **When** the artifact is reviewed, **Then** those
   records are visible as graph-quality evidence rather than failures hidden by
   graph loading.

---

### User Story 4 - Preserve Framework-Guided Boundaries (Priority: P4)

As a project maintainer, I want Microsoft GraphRAG and Neo4j GraphRAG methods
to guide indexing, lexical graph design, relationship extraction, and future
retrieval without allowing framework-generated output to override the legal XML
source of truth.

**Why this priority**: Mature GraphRAG patterns reduce bespoke design risk, but
legal source structure and explicit references remain authoritative for this
foundation stage.

**Independent Test**: Can be tested by reviewing design artifacts and operator
outputs to confirm that framework-derived outputs are research artifacts or
candidate evidence only, while trusted graph writes come from source-grounded
legal structure and explicit reference resolution.

**Acceptance Scenarios**:

1. **Given** Microsoft GraphRAG or Neo4j GraphRAG is referenced during design,
   **When** acceptance is reviewed, **Then** `003` requires only documented
   design mapping and does not require sidecar execution.
2. **Given** Neo4j GraphRAG retriever or KG-builder patterns are evaluated,
   **When** the design references them, **Then** the project keeps the current
   Neo4j graph of record and a manually constrained legal schema for trusted
   legal relations.

---

### Edge Cases

- A reference omits the law code and must inherit or infer law scope from the
  source fragment.
- A reference target is outside the selected corpus.
- A reference points to a paragraph, sentence, number, appendix, or range; the
  typed edge still targets the resolved legal section, while the more specific
  anchor remains auditable in reference evidence.
- Context contains multiple relation signals, such as a citation inside an
  exception clause that also defines a term; one primary typed edge is created
  for a resolved reference and secondary relation signals remain in reference
  evidence.
- A selected legal fragment contains many repeated references to the same
  target.
- A heading signals amendment or scope while the body text contains only a
  neutral citation.
- XML structure exposes paragraph or list hierarchy inconsistently across laws.
- A temporal relation is known to exist but the selected corpus lacks the older
  or newer version.
- A repeated relationship-refresh pass discovers additional references or
  relation evidence after parser policy changes; existing records are updated
  idempotently rather than duplicated.
- Framework documentation suggests a broader KG pipeline than this feature
  needs; the feature keeps sidecar execution outside `003` implementation and
  acceptance.
- A future external graph-method research feature may inspect framework output
  from bounded samples, but those observations remain outside trusted
  `LegalReference` and typed-edge writes until a separate review-gated feature
  promotes any finding into deterministic rules, fixtures, or candidate-only
  workflows.
- Default validation runs without live Neo4j, live embeddings, paid APIs,
  remote notebooks, chatbot UX, answer generation, or GraphRAG inference.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory)*

- **Foundation scope**: This feature strengthens the database-first foundation
  by improving source-grounded legal relationships before chatbot inference or
  GraphRAG answer generation. It does not add UX, answer synthesis, semantic
  proposition extraction, or trusted LLM-derived candidates.
- **Source and provenance**: The feature must preserve source document identity,
  source fragment identity, legal section identity, raw reference text,
  normalized reference text, context evidence, checksums or evidence-span
  identifiers, target candidates, resolution state, temporal metadata, and
  classifier version.
- **Embedding contract**: This feature does not change embedding semantics.
  Embeddings remain retrieval indexes only. Default validation must not require
  a live embedding service.
- **Review boundary**: LLM and framework outputs are out of trusted graph-write
  scope. If produced outside this feature, they are research artifacts or
  reviewable candidate evidence only.
- **Operational contour**: Operators must be able to load or reuse selected
  corpus scopes, build or refresh typed legal relationships, repeat
  relationship-refresh passes idempotently, verify relation evidence, and
  generate new-graph relationship-quality artifacts.
- **Test boundary**: Unit tests cover parsing, classification, resolution-state
  decisions, artifact assembly, and framework-boundary rules without live
  services. Live Neo4j checks are explicit integration tests. Live embeddings,
  paid APIs, remote notebooks, chatbot UX, answer generation, and GraphRAG
  inference are not required for default validation.

### Functional Requirements

- **FR-001**: System MUST parse explicit legal references from real German
  legal XML-derived fragments with a bounded context window around each
  reference.
- **FR-002**: System MUST preserve raw reference text, normalized reference
  text, source fragment identity, source legal section identity, context
  evidence, and classifier version for every parsed legal reference.
- **FR-003**: System MUST separate reference normalization, target resolution,
  relation classification, edge materialization, and quality reporting into
  auditable stages.
- **FR-003a**: Base graph loading MUST create or update source/legal structure
  only. Trusted `LegalReference` evidence and typed legal relationship edges
  MUST be created or updated by the relationship-refresh workflow, not by the
  base graph-load workflow.
- **FR-004**: System MUST classify supported relation types without collapsing
  them into a generic related edge.
- **FR-005**: The supported structural relation taxonomy MUST include `CITES`,
  `DEFINES`, `APPLIES_IF`, `REQUIRES`, `EXCEPTION_TO`, `EXCLUDES_IF`,
  `AMENDS`, and `SUPERSEDED_BY`.
- **FR-005a**: `003` acceptance MUST include classifier tests for `CITES`,
  `DEFINES`, `APPLIES_IF`, `REQUIRES`, and `EXCEPTION_TO`.
- **FR-005b**: `EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY` MUST remain in the
  taxonomy with documented source strategy and evidence fields, but full
  classifier test coverage for those relation types is not required in `003`.
- **FR-006**: System MUST materialize a typed legal edge only when the reference
  target is reliably resolved to a target legal node in the selected graph
  scope.
- **FR-006a**: Typed legal edges MUST target section-level legal nodes in this
  feature. More specific paragraph, sentence, number, appendix, or range
  anchors MUST be preserved in `LegalReference` evidence rather than becoming
  separate target nodes.
- **FR-006b**: Each resolved `LegalReference` MUST create at most one primary
  typed legal edge. Additional relation cues from the same context MUST be
  preserved as secondary signals in reference evidence.
- **FR-007**: System MUST preserve unresolved, ambiguous, and out-of-scope
  references as auditable `LegalReference` evidence without creating misleading
  typed edges.
- **FR-007a**: Resolution status MUST use `out_of_scope` when the target law is
  outside the selected corpus scope, `unresolved` when the target law is in
  scope but the target section is missing, and `ambiguous` when multiple target
  candidates match.
- **FR-007b**: Repeated relationship-refresh passes MUST be idempotent. They MAY
  add newly discovered relationship evidence after parser-policy changes, but
  MUST NOT duplicate existing reference records or typed edges.
- **FR-008**: System MUST record temporal or version metadata for amendment,
  supersession, current-default, and as-of-date relation evidence when that
  evidence is available from source data.
- **FR-008a**: Temporal/version evidence MUST be captured as evidence metadata
  when available from XML metadata, section headings, amendment wording, or
  explicit source references. `003` does not require complete historical law
  version reconstruction. Temporal/version evidence from XML metadata is
  captured from optional parser input metadata fields supplied by the loaded
  source document, source fragment, or legal section record before relationship
  parsing.
- **FR-008b**: Temporal/version evidence MUST distinguish at least
  `effective_from`, `effective_until`, `publication_date`, `source_version_id`,
  `source_revision_marker`, `temporal_context_text`, and
  `temporal_context_checksum` when those values are available.
- **FR-008c**: Missing temporal/version metadata MUST be represented explicitly
  as absent or unknown and MUST NOT block relationship refresh or typed edge
  materialization for otherwise resolved references.
- **FR-009**: System MUST expose relationship verification evidence for a
  selected law-code scope, including relation counts, resolution-status counts,
  and bounded sample ids.
- **FR-010**: System MUST generate deterministic relationship-quality artifacts
  for the new graph that include relation counts, unresolved-reference
  summaries, sample edges, context samples, classifier-version metadata,
  source-to-relation coverage, fanout summaries, and temporal completeness.
- **FR-011**: System MUST treat Microsoft GraphRAG and Neo4j GraphRAG as
  design references in this feature. Sidecar execution is outside `003`
  implementation scope and MUST NOT be required for `003` acceptance.
- **FR-011a**: If framework sidecar outputs are produced outside `003`
  acceptance, they MUST remain research artifacts or candidates unless a
  separate review-gated feature promotes them.
- **FR-012**: System MUST NOT compare against a legacy graph, migrate old graph
  data, or use legacy graph coverage as an acceptance criterion for this
  feature.
- **FR-013**: System MUST NOT add chatbot UX, answer generation, fallback answer
  behavior, LLM proposition extraction, trusted semantic candidates, or GraphRAG
  inference in this feature.

### Key Entities *(include if feature involves data)*

- **Legal Reference Evidence**: Parsed source-grounded reference record with raw
  text, normalized target, source fragment, context evidence, relation type,
  classifier version, target section candidate, optional sub-section anchor,
  secondary relation signals, and resolution status.
- **Typed Legal Edge**: Resolved structural relation between legal nodes,
  preserving relation type and traceability back to the originating legal
  reference evidence. In this feature, typed edges target section-level legal
  nodes, with at most one primary typed edge per `LegalReference`.
- **Relationship Classifier Policy**: Versioned deterministic policy that maps
  context evidence to supported legal relation types.
- **Relationship Refresh Pass**: Repeatable operation that applies the current
  parser and classifier policy to an existing selected corpus scope to improve
  relationship coverage without duplicating existing evidence.
- **Relationship Quality Artifact**: File artifact summarizing new-graph
  relation counts, resolution status, sample edges, unresolved target
  summaries, classifier metadata, coverage, fanout, and temporal completeness.
- **Framework Method Reference**: Microsoft GraphRAG or Neo4j GraphRAG
  documentation, methods, or patterns used to guide design without requiring
  framework execution in this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For selected fixture fragments covering direct cites,
  definitions, requirements, applicability, and exceptions, parser output
  includes source evidence, context evidence, relation type, classifier version,
  and resolution status.
- **SC-001a**: Strategy notes define how `EXCLUDES_IF`, `AMENDS`, and
  `SUPERSEDED_BY` will be recognized or deferred without removing them from the
  relation taxonomy.
- **SC-002**: Resolved references create only the intended typed relation, while
  unresolved, ambiguous, and out-of-scope references remain audit records
  without typed target edges.
- **SC-002a**: References with paragraph, sentence, number, appendix, or range
  detail preserve that detail as reference evidence while the typed edge targets
  the resolved section-level legal node.
- **SC-002b**: Multi-signal references create at most one primary typed edge and
  preserve any additional relation cues as secondary evidence.
- **SC-002c**: Missing target outcomes are distinguishable as `out_of_scope`,
  `unresolved`, or `ambiguous`, and repeated refresh passes do not duplicate
  existing reference records or typed edges.
- **SC-003**: Relationship-quality artifacts can be regenerated for unchanged
  selected graph state with matching deterministic sections.
- **SC-004**: The relationship-quality artifact reports at least relation counts
  by type, resolution-status counts, sample edges, unresolved-reference
  summaries, classifier version, source coverage, fanout summary, and temporal
  completeness.
- **SC-005**: Default validation completes without live graph, live embedding,
  paid API, remote notebook, chatbot, answer generation, LLM proposition
  extraction, or GraphRAG inference dependencies.
- **SC-006**: Review of the feature confirms that no legacy graph comparison,
  legacy graph migration, or legacy graph coverage criterion remains in the
  feature scope.
- **SC-007**: Design notes explicitly map useful Microsoft GraphRAG and Neo4j
  GraphRAG methods to project boundaries, and `003` acceptance does not require
  running those frameworks.

## Assumptions

- Operators have access to the controlled German legal XML corpus and can choose
  bounded law-code scopes for initial validation.
- Existing preview, load, verify, delete, schema, embedding, and structural
  retrieval workflows from prior stages remain available.
- The first relation classifier is deterministic and rule-based; LLM-assisted
  extraction remains a later candidate-only workflow.
- The graph remains Neo4j-backed, and the project schema remains the graph of
  record for trusted legal relations.
- Relationship-quality artifacts are new-graph evidence only and replace
  legacy comparison as the acceptance mechanism.
