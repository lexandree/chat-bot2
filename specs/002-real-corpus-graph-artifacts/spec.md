# Feature Specification: Real Corpus Graph Artifacts

**Feature Branch**: `002-real-corpus-graph-artifacts`  
**Created**: 2026-04-26  
**Status**: Draft  
**Input**: User description: "Build real corpus ingestion and graph artifact workflows for the legal graph foundation. Scope: real corpus manifest handling, preview over selected German legal XML sources, load/verify/delete against the new graph schema, snapshot artifacts with counts, labels, relation types, sample ids, source coverage, and embedding profile metadata, plus a legacy AufenthG baseline coverage check. Do not migrate old graph data. Do not treat the old graph as source of truth. Do not add chatbot UX, LLM extraction, answer generation, or GraphRAG inference."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preview Real Corpus (Priority: P1)

As a corpus operator, I want to preview selected real German legal XML sources so
that I can confirm source coverage, missing inputs, stable identifiers, and
checksums before changing graph state. The preview is a file artifact, not
persisted graph state.

**Why this priority**: Real corpus preview is the first validation gate beyond
fixtures. It proves that the foundation can ingest the intended source material
without relying on the legacy AufenthG baseline graph snapshot.

**Independent Test**: Given a real corpus manifest with a selected law-code
scope, preview generation can be run twice and produces the same source
coverage, identifiers, ordering, and checksum summary in the preview file
artifact.

**Acceptance Scenarios**:

1. **Given** a controlled real corpus manifest and selected law codes, **When**
   the operator generates a preview, **Then** the result lists source documents,
   source fragments, source coverage, checksums, and missing optional inputs.
2. **Given** the same unchanged real corpus manifest, **When** preview is run
   again, **Then** the preview summary and sample identifiers are deterministic.
3. **Given** a configured source is missing or malformed, **When** preview runs,
   **Then** required failures stop before graph changes while optional failures
   are reported in the preview evidence.

---

### User Story 2 - Load And Manage Real Corpus Scope (Priority: P2)

As an operator, I want to load, verify, and delete a selected real corpus scope
against the new graph foundation so that the new schema can be validated with
real source data while remaining reversible. Loading writes persisted graph
state; it does not create another preview file.

**Why this priority**: Baseline coverage checks are meaningful only after the new
graph can manage real loaded data with controlled scope and repeatable
verification.

**Independent Test**: Given a real corpus preview, the operator can load a
selected law-code scope twice, verify stable counts, delete only that selected
scope, and verify that unrelated data is not removed.

**Acceptance Scenarios**:

1. **Given** a valid real corpus preview, **When** the operator loads a selected
   scope, **Then** the new graph contains source documents, fragments, legal
   structures, references, and auditable unresolved-reference evidence for that
   scope.
2. **Given** the selected scope has already been loaded, **When** the operator
   repeats the load, **Then** verification reports stable counts rather than
   duplicate records.
3. **Given** the operator deletes the selected real corpus scope, **When**
   verification runs, **Then** records in that scope are absent and unrelated
   graph data remains available.

---

### User Story 3 - Generate Snapshot Artifacts (Priority: P3)

As an operator, I want file-based graph snapshot artifacts for selected scopes
so that I can compare graph shape, source coverage, and embedding metadata
without adding comparison-only nodes to the graph. A snapshot is a file
artifact produced from persisted graph state, not the graph itself.

**Why this priority**: File artifacts create an auditable checkpoint that can be
regenerated, reviewed, versioned, and removed after cutover without mutating
the graph for comparison-only state.

**Independent Test**: Given a loaded selected scope, the operator can generate
a snapshot artifact twice and receive the same counts, labels, relation types,
sample identifiers, source coverage, and embedding profile metadata when graph
state has not changed.

**Acceptance Scenarios**:

1. **Given** a loaded selected scope, **When** the operator creates a snapshot,
   **Then** the artifact records counts by source object, legal object,
   reference status, graph label, relation type, and embedding profile metadata.
2. **Given** the snapshot includes sample identifiers, **When** the artifact is
   reviewed, **Then** samples are bounded, stable, and sufficient to inspect the
   shape of loaded source, legal, reference, and embedding records.
3. **Given** graph state is unchanged, **When** the snapshot is regenerated,
   **Then** deterministic sections of the artifact match the previous snapshot.

---

### User Story 4 - Legacy AufenthG Baseline Coverage Check (Priority: P4)

As an operator, I want to check the new graph snapshot against the legacy
AufenthG baseline graph snapshot so that I can identify coverage gaps before
the old artifact is removed.

**Why this priority**: The old graph is useful only as a temporary coverage
reference. Comparison must support cutover confidence without migrating or
trusting old graph data.

**Independent Test**: Given a new snapshot for the selected scope and a
read-only legacy AufenthG baseline graph snapshot, the coverage check produces
a report of missing and extra acts, sections, fragments, references, labels,
relation types, sample ids, and coverage differences without copying old nodes.

**Acceptance Scenarios**:

1. **Given** both new and legacy baseline snapshots, **When** the coverage check runs,
   **Then** the report identifies matching, missing, and extra coverage by acts,
   sections, fragments, references, labels, and relation types.
2. **Given** the legacy baseline has records not represented in the new graph,
   **When** the coverage check runs, **Then** those records are reported as coverage
   gaps and not imported into the new graph.
3. **Given** baseline artifacts are no longer needed after cutover, **When**
   the operator removes the temporary comparison scope and references, **Then**
   the project no longer depends on old baseline artifacts.

### Edge Cases

- The real corpus manifest references no source files for the selected law-code
  scope.
- A selected law code appears in the manifest but yields no substantive legal
  fragments.
- The same source appears through multiple manifest entries with conflicting
  metadata.
- The preview is deterministic but source coverage is lower than expected.
- A load is interrupted after some records are written and then repeated.
- The selected delete scope is empty.
- Snapshot generation runs before the selected scope is loaded.
- Snapshot artifacts are regenerated after graph data changed.
- The legacy AufenthG baseline graph snapshot is unavailable, empty, or has labels and relation
  types not recognized by the new foundation.
- Comparison shows differences caused by intentional new normalization rather
  than missing source coverage.
- Embedding metadata is absent for a selected scope that has not been embedded.
- Default validation runs without live graph, live embedding services, paid
  APIs, or remote notebooks.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory)*

- **Foundation scope**: This feature extends the database-first foundation from
  fixture validation to real corpus coverage and auditable graph snapshots. It
  does not add inference, chatbot UX, LLM proposition extraction, answer
  generation, or GraphRAG inference.
- **Source and provenance**: Real corpus preview and snapshots must preserve
  source document identity, source fragment identity, law code, section
  reference, source coverage, checksums, missing-input evidence, and unresolved
  reference evidence.
- **Embedding contract**: This feature does not change embedding semantics.
  Snapshot artifacts report existing embedding profile metadata, dimensions,
  normalization, backend, and counts when embeddings are present. Default
  validation must not require a live embedding service.
- **Review boundary**: LLM-derived candidates and trusted promotion are out of
  scope. The comparison report is coverage evidence only and must not promote
  old graph records or generated content into trusted support.
- **Operational contour**: Operators must be able to preview a real corpus,
  load, verify, delete a selected scope, generate file-based snapshots, and
  compare snapshots against the legacy AufenthG baseline graph snapshot.
  Comparison-only state must be easy to remove after cutover.
- **Test boundary**: Unit validation covers manifest handling, deterministic
  preview behavior, snapshot artifact assembly, and comparison report assembly
  without live services. Live graph checks are marked separately. Live
  embeddings, paid APIs, chatbot UX, LLM runtimes, and remote notebooks are not
  required for default validation.

### Functional Requirements

- **FR-001**: System MUST accept a controlled real corpus manifest and selected
  law-code scope for preview.
- **FR-002**: System MUST generate deterministic real corpus previews that
  include source coverage, stable sample identifiers, checksums, and structured
  missing-input evidence.
- **FR-003**: System MUST stop before graph changes when required real corpus
  inputs are missing, malformed, or outside the selected scope.
- **FR-004**: Operators MUST be able to load selected real corpus preview data
  into the new graph foundation using explicit law-code scope.
- **FR-005**: Operators MUST be able to verify selected real corpus graph state
  with counts for source documents, source fragments, legal objects,
  references, unresolved references, and embedding metadata.
- **FR-006**: Operators MUST be able to delete selected real corpus graph data
  by explicit scope without resetting the whole graph.
- **FR-007**: System MUST create file-based snapshot artifacts for selected
  graph scopes.
- **FR-008**: Snapshot artifacts MUST include counts, graph labels, relation
  types, bounded sample identifiers, source coverage, unresolved-reference
  counts, and embedding profile metadata when present.
- **FR-009**: Snapshot artifacts MUST be reproducible for unchanged selected
  graph state.
- **FR-010**: System MUST create a comparison report between a new graph
  snapshot and the legacy AufenthG baseline graph snapshot.
- **FR-011**: Comparison reports MUST identify missing, extra, and matching
  acts, sections, fragments, references, labels, relation types, sample ids,
  source coverage, and embedding metadata differences.
- **FR-012**: Comparison MUST treat the legacy AufenthG baseline graph snapshot as read-only
  coverage evidence, not as source of truth.
- **FR-013**: System MUST NOT copy old graph nodes, relationships, properties,
  or embedding vectors into the new graph during comparison.
- **FR-014**: System MUST NOT create permanent comparison-only graph nodes in
  the first comparison stage; snapshot and comparison outputs are file
  artifacts.
- **FR-015**: Comparison reports MUST be clearly removable after cutover and
  must not become required runtime inputs for foundation workflows.
- **FR-016**: System MUST NOT add chatbot UX, LLM extraction, answer generation,
  GraphRAG inference, fallback answer behavior, or trust promotion behavior.

### Key Entities *(include if feature involves data)*

- **Real Corpus Manifest**: Operator-controlled description of selected source
  files, law codes, jurisdiction, language, required/optional status, and source
  metadata needed for preview.
- **Real Corpus Preview**: Deterministic file artifact describing normalized
  source documents, source fragments, coverage, checksums, and missing inputs
  before graph mutation.
- **Loaded Scope**: Explicit law-code selection represented as persisted graph
  state in the new graph foundation through load, verify, and delete workflows.
- **Graph Snapshot Artifact**: File artifact for a selected graph scope,
  containing counts, labels, relation types, sample ids, source coverage,
  unresolved-reference evidence, and embedding metadata.
- **Legacy AufenthG Baseline Graph Snapshot**: Read-only snapshot of the
  legacy AufenthG graph scope used only for coverage comparison.
- **Comparison Report**: File artifact describing missing, extra, and matching
  coverage between a new graph snapshot and the legacy AufenthG baseline graph snapshot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can generate a deterministic preview for at least one
  selected real law-code scope, with repeated runs producing identical source
  coverage, sample ids, and checksum summary in the preview artifact when
  inputs are unchanged.
- **SC-002**: Operators can load, verify, delete, and re-verify a selected real
  corpus scope without removing unrelated graph data.
- **SC-003**: Snapshot artifacts can be regenerated for unchanged graph state
  with matching counts, labels, relation types, bounded sample ids, and
  embedding metadata sections.
- **SC-004**: Comparison reports identify missing and extra acts, sections,
  fragments, references, labels, and relation types between the new snapshot and
  the legacy AufenthG baseline graph snapshot.
- **SC-005**: Review of the comparison workflow confirms that no old graph data
  is copied into the new graph and the old baseline is not treated as source of
  truth.
- **SC-006**: Default validation completes without live graph, live embedding,
  paid API, remote notebook, chatbot, LLM extraction, answer generation, or
  GraphRAG inference dependencies.
- **SC-007**: Temporary comparison artifacts and documentation references are
  easy to identify for removal after cutover.

## Assumptions

- Operators have access to a controlled real German legal XML corpus manifest
  and can choose a bounded law-code scope for the first real-corpus run.
- The first comparison target is the legacy AufenthG baseline graph snapshot.
- The legacy AufenthG baseline graph snapshot is read-only coverage evidence and may be deleted after the
  new graph has enough coverage.
- Snapshot and comparison outputs are file artifacts in this feature; persistent
  graph nodes for comparison history are deferred unless separately specified.
- Existing foundation workflows for settings, schema readiness, preview, load,
  verify, delete, embeddings, and structural retrieval remain available.
- Live graph validation is opt-in; default tests use fixtures and file
  artifacts only.
