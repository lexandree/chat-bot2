# Feature Specification: German Legal Graph Foundation

**Feature Branch**: `001-legal-graph-foundation`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: User description: "Build the foundation stage for a database-first German legal graph knowledge base. Scope: settings, production graph connection, schema bootstrap, legal XML import preview, structural legal graph build, load/verify/delete workflow, and tests. Inference, chatbot UX, LLM proposition extraction, and GraphRAG answer generation are out of scope."

## Clarifications

### Session 2026-04-25

- Q: What graph database posture should the foundation lock in? -> A: Neo4j 5/Aura-compatible is the graph of record; use a real driver-backed client; no generic graph database abstraction in the foundation.
- Q: How should the project use exported source snapshots from the previous project? -> A: Treat `export/source_snapshot` as reference evidence only; selectively reimplement or adapt contracts, tests, and narrow proven behaviors into clean modules. No wholesale code import.

### Session 2026-04-26

- Q: Should source and fragment embedding generation/write workflows be included in this foundation feature? -> A: Include full source and fragment embedding generation and graph writes using an operator-started local-only Jina-compatible service, with fail-fast behavior when unavailable and live checks marked outside default unit tests.
- Q: Should structural retrieval baseline be included in this foundation feature? -> A: Include exact legal-reference resolution plus bounded typed traversal as a foundation validation workflow, without answer generation.
- Q: What candidate/review schema boundary should the foundation include? -> A: Include candidate/review constraints and metadata placeholders in schema bootstrap, but no LLM extraction, review workflow, or trusted promotion behavior.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prepare The Graph Foundation (Priority: P1)

As an operator, I want to configure the foundation runtime and prepare an empty
Neo4j 5/Aura-compatible graph store so that source and legal graph data can be
loaded into a known, validated database state.

**Why this priority**: Every later workflow depends on repeatable configuration,
connectivity, and schema readiness. Without this story, the project cannot
prove that it has a database-first foundation.

**Independent Test**: Starting from an empty Neo4j 5/Aura-compatible graph store
and a complete configuration profile, an operator can run the preparation
workflow twice and receive a successful readiness report both times, with no
duplicate schema objects or hidden service dependencies.

**Acceptance Scenarios**:

1. **Given** a complete configuration profile and reachable Neo4j 5/Aura-compatible
   graph store, **When** the operator prepares the foundation, **Then** the
   system records the active settings, confirms graph connectivity through the
   real driver-backed client, prepares all required graph schema objects, and
   reports readiness.
2. **Given** the graph schema has already been prepared, **When** the operator
   repeats the preparation workflow, **Then** the workflow completes without
   duplicating schema objects and reports the same stable schema names.
3. **Given** required configuration is missing or invalid, **When** the operator
   requests preparation, **Then** the workflow stops before writing graph data
   and reports the missing or invalid setting.

---

### User Story 2 - Preview German Legal XML Sources (Priority: P2)

As a corpus operator, I want to preview configured German legal XML files before
loading them so that I can inspect normalized legal sections, source metadata,
checksums, and missing inputs without mutating the graph.

**Why this priority**: Source preview is the first auditable data boundary. It
lets operators validate corpus inputs before any persistent graph state is
created.

**Independent Test**: Given a controlled corpus slice with at least two legal
sections and one intentionally missing optional file, an operator can generate a
preview twice and receive identical normalized output plus a structured missing
inputs report.

**Acceptance Scenarios**:

1. **Given** configured legal XML files, **When** the operator runs preview,
   **Then** the system produces normalized source documents and fragments with
   law code, section reference, title, body text, source metadata, and checksum.
2. **Given** an optional configured source file is absent, **When** preview
   runs, **Then** the system records the absent file in a structured missing
   inputs list and continues previewing available files.
3. **Given** the same unchanged corpus input, **When** preview is repeated,
   **Then** the normalized output order, identifiers, and checksums are
   deterministic.

---

### User Story 3 - Load, Verify, And Delete Structural Legal Graph Data (Priority: P3)

As an operator, I want to load a selected previewed legal corpus slice into the
graph, verify the resulting structural legal data, and delete selected loaded
data when needed so that graph state can be managed without a full reset.

**Why this priority**: The foundation is only useful when operators can create,
inspect, and safely remove structural graph state by controlled scope.

**Independent Test**: Given a deterministic preview corpus, an operator can load
a selected law-code slice, verify expected source and legal-structure counts,
delete the same slice, and verify that the selected data has been removed while
unrelated data remains untouched.

**Acceptance Scenarios**:

1. **Given** a valid preview corpus and a selected law-code scope, **When** the
   operator loads the corpus, **Then** the graph contains source documents,
   source fragments, legal acts, legal sections, legal fragments, explicit legal
   references, and auditable unresolved references where resolution is not
   possible.
2. **Given** graph data has been loaded, **When** the operator verifies it,
   **Then** the verification report includes source document count, source
   fragment count, legal act count, legal section count, legal fragment count,
   reference count, unresolved reference count, embedding count, embedding
   profile identifiers, vector dimensions, and backend names.
3. **Given** a loaded law-code scope, **When** the operator deletes that scope,
   **Then** the selected source and legal graph data are removed, unrelated
   graph data remains, and a deletion report records what was selected and
   removed.

---

### User Story 4 - Embed Loaded Source Text (Priority: P4)

As an operator, I want to generate and write embeddings for loaded source
documents and fragments using an explicitly started local-only embedding
service so that the graph foundation has searchable vector indexes without
making default tests depend on live services.

**Why this priority**: The foundation completion criteria include embeddable
source documents and fragments, but embedding must remain an explicit operator
workflow rather than a hidden dependency of import or unit testing.

**Independent Test**: Given loaded source documents and fragments plus an
operator-started local-only Jina-compatible embedding service, an operator can
embed the selected law-code scope and verify embedding count, profile identity,
vector dimensions, normalization, and backend metadata. If the service is not
available, the workflow fails before partial graph writes and tells the
operator which service must be started.

**Acceptance Scenarios**:

1. **Given** loaded source documents and fragments and an available local-only
   Jina-compatible embedding service, **When** the operator runs embedding for a
   selected law-code scope, **Then** the graph records document and fragment
   embeddings with the active embedding profile and backend metadata.
2. **Given** the embedding service is unavailable, **When** the operator starts
   the embedding workflow, **Then** the workflow fails before partial graph
   writes and reports that the local-only embedding service must be started.
3. **Given** embeddings have been written, **When** verification runs, **Then**
   the report includes embedding count, embedding profile identifier, vector
   dimensions, normalization status, backend name, and selected corpus scope.

---

### User Story 5 - Validate Structural Retrieval Baseline (Priority: P5)

As an operator, I want to resolve exact legal references and run bounded typed
traversal over loaded legal graph data so that the foundation proves structural
retrieval behavior before any answer-generation layer exists.

**Why this priority**: The foundation must demonstrate that legal references
and graph relationships are usable without relying on LLM extraction, semantic
expansion, or generated answers.

**Independent Test**: Given a loaded law-code scope with explicit references,
an operator can resolve a known law-code plus section reference to the expected
legal section and run bounded traversal that returns source references,
relation types, depth, fanout, and limit metadata without producing an answer.

**Acceptance Scenarios**:

1. **Given** a loaded legal section exists for a law code and section reference,
   **When** the operator resolves that exact reference, **Then** the system
   returns the matching legal section identity, source references, and temporal
   status when available.
2. **Given** a loaded legal section has typed legal neighbors, **When** the
   operator runs bounded traversal, **Then** the system returns only allowed
   relation types within configured depth, fanout, and node limits.
3. **Given** a reference cannot be resolved in the loaded corpus scope, **When**
   the operator runs the baseline workflow, **Then** the unresolved reference is
   reported with auditable target evidence and no generated answer.

### Edge Cases

- Required configuration is absent, malformed, or points to an unreachable
  Neo4j 5/Aura-compatible graph store.
- Schema preparation is run repeatedly against an already prepared graph.
- A configured corpus file is missing, empty, unreadable, or contains malformed
  XML.
- A legal section has a title but no substantive body text.
- A legal section contains multiple paragraphs, nested numbering, footnotes, or
  amendment notes that must not be lost during preview.
- A reference points to a law code or section that is not present in the loaded
  corpus slice.
- A load operation is repeated for the same source documents and must update or
  preserve existing records without duplication.
- Delete is requested for a law code that has no loaded data.
- Verification runs before any data has been loaded.
- Embedding is requested before source documents or fragments are loaded.
- The local-only Jina-compatible embedding service is not reachable when an
  embedding workflow starts.
- The embedding service returns vectors with unexpected dimensions or
  normalization status.
- Exact reference resolution is requested for a law code or section reference
  outside the loaded corpus scope.
- Traversal encounters high-fanout neighbors or relation cycles.
- Default test execution occurs without live graph, embedding, paid API, or
  remote notebook services.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory)*

- **Foundation scope**: This feature establishes the database-first foundation
  through configuration, graph readiness, source preview, structural graph
  loading, verification, deletion, and validation tests. It excludes inference,
  chatbot UX, LLM proposition extraction, and GraphRAG answer generation.
- **Graph database posture**: Neo4j 5/Aura-compatible storage is the graph of
  record. The foundation must use a real driver-backed client for production
  graph access and must not introduce a broad graph-database abstraction for
  hypothetical replacement.
- **Source and provenance**: Source documents and fragments must retain legal
  source family, law code, section reference, title, body text, source URI or
  local reference, jurisdiction, language, retrieval or freshness metadata when
  available, and checksum.
- **Embedding contract**: The feature includes source and fragment embedding
  generation and graph writes through an operator-started local-only
  Jina-compatible embedding service. Query embeddings must use the `Query: `
  prefix, indexed source text must use the `Document: ` prefix, and graph writes
  must record embedding profile identifier, backend, vector dimensions,
  normalization status, routing mode, and model identifier. Default unit tests
  must not require a live embedding service.
- **Review boundary**: LLM-derived proposition candidates are out of scope.
  The feature must not promote generated claims, summaries, or propositions into
  trusted retrieval support.
- **Candidate/review schema boundary**: Schema bootstrap must include
  candidate/review constraints and metadata placeholders for future untrusted
  outputs, but this feature must not implement LLM extraction, review task
  workflow, or trusted promotion behavior.
- **Structural retrieval boundary**: Exact legal-reference resolution and
  bounded typed traversal are in scope as validation workflows. Semantic
  expansion, ranking experiments, and answer generation remain out of scope.
- **Operational contour**: Operators must be able to prepare schema, preview
  legal XML, load a bounded corpus scope, embed source documents and fragments
  through the local-only path, validate exact legal-reference resolution and
  bounded typed traversal, verify graph state, and delete a selected loaded
  scope. Load, embedding write, traversal, and delete operations must be
  repeatable or must report their write semantics explicitly.
- **Test boundary**: Unit validation covers deterministic parsing, identifier
  creation, schema definitions, embedding prefix/profile policy, reference
  parsing, and operation policy without live services. Graph-store and live
  embedding behavior are covered by marked integration tests. Operator smoke
  checks are separate from default unit tests.
- **Export reference policy**: Exported source snapshots are reference evidence
  only. The foundation must selectively reimplement or adapt proven contracts,
  tests, and narrow behaviors into clean modules, and must not import the
  snapshot wholesale.

### Functional Requirements

- **FR-001**: System MUST load a complete foundation configuration profile and
  fail before writing graph data when required settings are missing or invalid.
- **FR-002**: System MUST provide a real driver-backed Neo4j 5/Aura-compatible
  production graph connection surface that supports parameterized reads,
  parameterized writes, connectivity checks, database selection where needed,
  and resource cleanup.
- **FR-002a**: System MUST NOT introduce a generic graph database abstraction in
  the foundation stage; any adapter boundary must be limited to the real
  Neo4j-compatible client and explicit unit-test doubles.
- **FR-003**: System MUST prepare graph schema objects for source, legal,
  reference, embedding-profile, and validation entities using stable names.
- **FR-003a**: Schema bootstrap MUST include candidate/review constraints and
  metadata placeholders sufficient for future untrusted candidate identifiers,
  support references, review state, grounding flags, isolation state, and
  runtime metadata.
- **FR-003b**: Candidate/review schema support MUST NOT introduce LLM extraction,
  review task workflow, candidate promotion, or trusted-use behavior in this
  feature.
- **FR-004**: Schema preparation MUST be idempotent and safe to run against an
  already prepared graph.
- **FR-005**: System MUST generate a deterministic legal XML import preview from
  configured German legal XML inputs without writing graph data.
- **FR-006**: Preview output MUST include normalized source documents and source
  fragments with stable identifiers, law code, section reference, title, body
  text, source metadata, and checksum.
- **FR-007**: Preview MUST report missing optional configured files in a
  structured missing inputs list without failing the entire preview.
- **FR-008**: System MUST reject or report malformed required corpus inputs with
  enough context for an operator to identify the affected file and source item.
- **FR-009**: System MUST build structural legal graph records from previewed
  source data, including legal acts, legal sections, legal fragments, and
  explicit legal references.
- **FR-010**: System MUST preserve unresolved legal references as auditable
  records instead of dropping them silently.
- **FR-010a**: System MUST resolve exact legal references from law code plus
  section reference to loaded current legal sections where possible.
- **FR-010b**: System MUST provide bounded typed traversal from resolved legal
  sections using explicit allowed relation types, depth limits, fanout limits,
  and node limits.
- **FR-010c**: Structural retrieval baseline output MUST include source
  references, relation types, traversal depth, limit metadata, unresolved-target
  evidence when applicable, and no generated answer text.
- **FR-011**: System MUST support load by selected corpus scope, including at
  least law-code filtering.
- **FR-012**: Load MUST use repeatable write behavior that avoids duplicate
  source, legal, and reference records when the same corpus scope is loaded
  more than once.
- **FR-013**: System MUST provide a verification report for loaded graph state
  covering source counts, legal-structure counts, reference counts, unresolved
  reference counts, embedding counts, embedding profile identifiers, vector
  dimensions, backend names, and selected corpus scope.
- **FR-013a**: System MUST generate and write embeddings for selected source
  documents and source fragments using an operator-started local-only
  Jina-compatible embedding service.
- **FR-013b**: System MUST apply asymmetric embedding prefixes: `Document: ` for
  indexed source text and `Query: ` for search requests.
- **FR-013c**: System MUST record active embedding profile identifier, model
  identifier, backend name, routing mode, vector dimensions, and normalization
  status for graph-written embeddings.
- **FR-013d**: Graph-write embedding workflows MUST fail before partial graph
  writes when the configured local-only embedding service is unavailable or
  returns vectors that violate the active embedding profile.
- **FR-014**: System MUST support deletion by selected loaded scope without
  requiring a full database reset.
- **FR-015**: Delete MUST report selected scope, matched records, removed
  records, skipped records, and any remaining related records that were not
  removed.
- **FR-016**: System MUST ensure no inference, chatbot UX, LLM proposition
  extraction, generated answer path, or fallback answer behavior is introduced
  by this feature.
- **FR-017**: System MUST include deterministic unit tests for configuration
  validation, schema definition assembly, legal XML preview normalization,
  embedding prefix/profile policy, reference parsing, structural graph mapping,
  load policy, verify report assembly, and delete scope policy.
- **FR-018**: Tests that require a live graph store, live embedding service,
  paid API, filesystem integration outside unit fixtures, or remote notebook
  runtime MUST be marked separately and excluded from default unit-test runs.
- **FR-019**: System design and implementation work MUST treat
  `export/source_snapshot` as reference evidence only; direct wholesale import
  of snapshot modules is out of scope.
- **FR-020**: Any behavior adopted from exported references MUST be expressed as
  clean project contracts, tests, or narrow module behavior before it becomes
  part of the foundation.

### Key Entities *(include if feature involves data)*

- **Configuration Profile**: The effective foundation settings used by an
  operator run, including Neo4j 5/Aura-compatible graph connection values,
  corpus locations, embedding metadata expectations, and test boundary flags.
- **Graph Readiness Report**: The operator-facing result of configuration,
  connectivity, and schema preparation checks.
- **Source Document**: A normalized legal source unit with source family,
  jurisdiction, language, law code, source reference, metadata, and checksum.
- **Source Fragment**: A smaller source text unit derived from a source document,
  preserving section identity, text, ordering, and checksum.
- **Embedding Profile**: The active embedding contract for indexed source text,
  including profile identifier, model identifier, backend name, routing mode,
  vector dimensions, normalization status, provider, and task semantics.
- **Embedding Run**: A record of an embedding write attempt for a selected
  corpus scope, including processed count, skipped count, failed count, active
  profile, backend, and failure reason when applicable.
- **Candidate/Review Schema Placeholder**: Future-ready schema identity for
  untrusted semantic candidates and review metadata, including candidate
  identifier, support references, review state, grounding flags, isolation
  state, and runtime metadata, without extraction or promotion behavior.
- **Legal Act**: The graph identity for a law or official legal source family
  that groups legal sections.
- **Legal Section**: A canonical structural legal unit with law code, section
  reference, title, temporal metadata when available, and current-version
  indicators when available.
- **Legal Fragment**: A structural text fragment attached to a legal section,
  preserving source wording and order.
- **Legal Reference**: A parsed reference from one legal unit to another,
  including resolution status and unresolved-target evidence when resolution is
  not possible.
- **Structural Retrieval Result**: The output of exact reference resolution and
  bounded typed traversal, including matched legal section identity, source
  references, relation types, depth, fanout, limit metadata, and unresolved
  reference evidence.
- **Load Run**: A record of a graph load attempt, including selected scope,
  processed count, skipped count, failed count, and write semantics.
- **Verification Report**: A report describing graph state after load, embedding,
  or delete, including counts, embedding metadata, backend metadata, and
  warnings.
- **Deletion Report**: A report describing selected deletion scope, matched
  records, removed records, skipped records, and retained related records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can prepare an empty Neo4j 5/Aura-compatible graph
  foundation twice in sequence, and both runs complete with a readiness report
  that names the same schema objects, includes candidate/review schema
  placeholders, and confirms real driver-backed connectivity.
- **SC-002**: A preview run over an unchanged controlled corpus slice produces
  identical source identifiers, fragment identifiers, ordering, and checksums
  across two consecutive runs.
- **SC-003**: Preview reports all intentionally missing optional corpus inputs
  in a structured list while still producing preview output for available
  inputs.
- **SC-004**: Loading the same selected law-code scope twice does not increase
  the number of source documents, legal sections, legal fragments, or legal
  references beyond the expected unique count.
- **SC-005**: Verification after load reports all required source,
  legal-structure, reference, unresolved-reference, embedding, profile,
  dimension, backend, and selected-scope fields.
- **SC-005a**: With the local-only Jina-compatible embedding service running,
  operators can embed a selected loaded law-code scope and verification reports
  embeddings for the expected source documents and fragments with the expected
  profile, dimensions, normalization status, and backend.
- **SC-005b**: With the local-only embedding service unavailable, embedding a
  selected scope fails before partial graph writes and reports that the operator
  must start the configured service.
- **SC-005c**: Given validation references for the selected corpus scope, exact
  reference resolution returns the expected legal section identities and source
  references without invoking LLM extraction or answer generation.
- **SC-005d**: Bounded traversal never exceeds configured relation, depth,
  fanout, or node limits and reports those limits in the structural retrieval
  result.
- **SC-006**: Deleting a selected law-code scope removes that scope and leaves an
  unrelated loaded scope verifiably present.
- **SC-007**: Default unit validation completes without requiring live graph
  services, live embedding services, paid APIs, or remote notebook runtimes,
  while marked integration checks can validate the live local-only embedding
  workflow when the operator starts the service.
- **SC-008**: Review of the delivered foundation finds no chatbot UX, inference,
  LLM proposition extraction, GraphRAG answer generation, or fallback answer
  behavior.

## Assumptions

- Operators have access to a controlled German legal XML corpus slice for
  preview, load, verify, and delete validation.
- Initial corpus scope prioritizes law and official guidance sources.
- Missing optional corpus files are expected during preview and are reported as
  structured missing inputs.
- Temporal metadata is preserved when available in source inputs; absence of
  temporal metadata does not block preview or load for otherwise valid sections.
- Embedding creation and graph writes are part of this feature for source
  documents and fragments, but only through an operator-started local-only
  Jina-compatible service.
- Operators are responsible for starting the configured local-only embedding
  service before running live embedding workflows.
- Structural retrieval baseline validation uses exact references and bounded
  typed traversal only; semantic expansion, reranking, and generated answers are
  separate future work.
- Candidate/review schema placeholders are included to preserve future review
  boundaries, but no semantic candidate extraction, review task workflow, or
  promotion behavior is implemented in this feature.
- Live Neo4j 5/Aura-compatible graph-store checks are integration tests, not
  default unit tests.
- Inference, chatbot UX, LLM proposition extraction, and GraphRAG answer
  generation require separate future specifications.
- Exported source snapshots are used to recover proven contracts and lessons,
  not to carry forward the old project structure.
