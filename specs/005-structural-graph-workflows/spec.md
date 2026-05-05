# Feature Specification: Structural Graph Workflows With Coverage Boundaries

**Feature Branch**: `005-structural-graph-workflows`  
**Created**: 2026-05-02  
**Status**: Draft  
**Input**: User description: "Build structural graph workflows with coverage boundaries after 004. Operators should use the resolved legal graph without waiting for full corpus coverage closure. Workflows must operate on trusted resolved typed legal edges, expose deterministic section dependency and neighborhood reports, stop explicitly at missing_target_in_corpus coverage boundaries, report excluded or blocked counts from the post-004 missing-target inventory, and preserve source/reference provenance. Do not infer missing edges, do not add chatbot UX, answer generation, semantic LLM extraction, GraphRAG inference, or corpus expansion automation in this feature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect Resolved Section Neighborhoods (Priority: P1)

As a graph operator, I want to generate deterministic structural workflow views
for selected legal sections or bounded law-code scopes so that I can start using
the trusted resolved graph without waiting for every missing target to be added
to the corpus.

**Why this priority**: The completed `004` smoke has a large resolved graph
surface. Operators need a practical way to inspect resolved dependencies while
keeping missing-target gaps visible and bounded.

**Independent Test**: Can be tested with fixture graph data containing active
sections, law-code scope membership, resolved typed edges, and a small number of
unresolved references. The workflow output is checked for deterministic
ordering, relation metadata, source provenance, explicit workflow mode, and
absence of inferred missing edges.

**Acceptance Scenarios**:

1. **Given** a selected source legal section with resolved typed edges, **When**
   the structural neighborhood workflow runs, **Then** the output lists the
   selected section, resolved neighboring sections, relation types, traversal
   depth, and source reference evidence.
2. **Given** the same graph state and workflow parameters, **When** the
   workflow is repeated, **Then** all deterministic sections of the output match
   the prior output.
3. **Given** a relation exists only as unresolved `missing_target_in_corpus`
   evidence, **When** the neighborhood output is generated, **Then** no trusted
   neighbor or typed edge is inferred for that target.
4. **Given** a selected law-code scope without a seed section, **When** the
   structural workflow runs in `law_scope_overview` mode, **Then** the output
   lists scope sections, resolved typed edges, coverage-boundary stops, and
   quality counts without performing unbounded recursive traversal.

---

### User Story 2 - Expose Coverage Boundary Stops (Priority: P1)

As a graph operator, I want unresolved references to appear as explicit coverage
boundary stops so that structural graph workflows reveal where traversal could
not continue without pretending the corpus is complete.

**Why this priority**: Missing targets are known, potentially temporary corpus
coverage gaps. Hiding them would make graph output look more complete than it
is, while forcing corpus closure first would block useful graph work.

**Independent Test**: Can be tested by running a workflow over fixture
references where some targets resolve and others have
`missing_target_in_corpus`. The output must include boundary-stop counts,
reason values, and bounded source samples for missing targets.

**Acceptance Scenarios**:

1. **Given** a reference with `unresolved_reason = missing_target_in_corpus`,
   **When** a workflow reaches that reference, **Then** traversal stops at that
   boundary and reports the target law, target section, reason, and source
   sample identifiers.
2. **Given** a post-004 missing-target inventory is available, **When** a
   workflow output is assembled, **Then** missing-target boundary counts are
   consistent with the selected scope and inventory semantics.
3. **Given** missing targets are later resolved by corpus expansion, **When**
   the same workflow is run against the updated graph state, **Then** formerly
   blocked paths can appear as resolved paths without requiring trusted edge
   inference from the old inventory.

---

### User Story 3 - Control Traversal Scope And Fanout (Priority: P2)

As an operator, I want structural workflows to have explicit depth, relation,
and fanout boundaries so that graph exploration remains repeatable and does not
turn into uncontrolled recursive expansion.

**Why this priority**: Legal graphs can contain dense citation patterns. The
first usable workflow must make traversal boundaries visible before broader
retrieval or semantic ranking is introduced.

**Independent Test**: Can be tested with fixture graphs that include multiple
relation types, high fanout sections, and cycles. The workflow must respect
configured traversal limits and report truncation or cycle-handling metadata.

**Acceptance Scenarios**:

1. **Given** a workflow has a selected depth and allowed relation types,
   **When** traversal runs, **Then** only paths matching those bounds are
   included.
2. **Given** a section exceeds the workflow fanout limit, **When** traversal
   reaches that section, **Then** output remains deterministic and reports the
   truncation count.
3. **Given** a graph cycle exists, **When** traversal runs, **Then** the output
   avoids duplicate path expansion and records enough path metadata to audit
   the cycle boundary.

---

### User Story 4 - Produce Workflow-Quality Evidence (Priority: P3)

As a maintainer, I want workflow artifacts to summarize coverage, traversal,
and provenance quality so that the next planning step is based on graph
evidence rather than informal inspection.

**Why this priority**: The workflow surface should expose whether structural
graph usage is useful enough for later retrieval design, without creating
answer text or semantic candidates.

**Independent Test**: Can be tested by generating workflow artifacts twice for
unchanged fixture or live graph state and verifying stable quality summaries
for visited sections, followed edges, boundary stops, truncations, and missing
source evidence.

**Acceptance Scenarios**:

1. **Given** a selected graph workflow completes, **When** the workflow-quality
   summary is reviewed, **Then** it includes visited section counts, followed
   edge counts by relation type, boundary-stop counts by reason, truncation
   counts, and provenance completeness.
2. **Given** source or reference provenance is missing from an output item,
   **When** the artifact is generated, **Then** the issue is visible as quality
   evidence rather than hidden.
3. **Given** a workflow artifact is reviewed, **When** checking for inference
   leakage, **Then** it contains no chatbot answer, generated legal conclusion,
   LLM proposition, or trusted semantic candidate output.

### Edge Cases

- Selected law code or section is absent from the graph.
- Law-code scope is selected without seed sections and must run as
  `law_scope_overview`, not as recursive traversal from every section.
- Selected section exists but is inactive.
- Selected section has no resolved outgoing or incoming typed edges.
- Traversal reaches only boundary stops and no additional resolved sections.
- Missing-target inventory exists but is stale relative to the current graph.
- Multiple references point to the same missing target from the same section.
- High fanout or cycles would exceed workflow bounds without deterministic
  limits.
- Source/reference provenance is incomplete for a relationship output item.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory)*

- **Foundation scope**: This feature supports the database-first legal
  knowledge foundation by making the resolved structural graph usable for
  operator workflows. It does not introduce chatbot inference, answer
  synthesis, semantic LLM extraction, GraphRAG inference, or corpus expansion
  automation.
- **Source and provenance**: Workflow outputs must preserve legal section ids,
  source fragment ids, legal reference ids, relation types, target status,
  unresolved reason where applicable, temporal metadata when available, and
  source evidence checksums where already present in the graph.
- **Embedding contract**: Embeddings are not affected. Structural graph
  workflows must work without embedding vectors or live embedding services.
- **Review boundary**: LLM-derived candidates are not affected. Workflow
  outputs are structural artifacts only and must not promote generated
  propositions, claims, summaries, or semantic candidates into trusted support.
- **Operational contour**: Operators must be able to run deterministic
  structural graph workflows for a selected scope, repeat them idempotently,
  inspect coverage-boundary stops, and generate ignored JSON artifacts or
  equivalent reports. The workflows are read-only with respect to trusted graph
  state.
- **Test boundary**: Default unit tests must use fixture data and must not
  require live Neo4j, live Jina, paid APIs, remote notebooks, GraphRAG sidecars,
  or private corpora. Live Neo4j checks are integration tests and must be gated
  separately.

### Functional Requirements

- **FR-001**: System MUST generate deterministic structural workflow output in
  two explicit modes: `seed_neighborhood` for selected legal sections and
  `law_scope_overview` for bounded law-code scopes, using only resolved typed
  legal edges.
- **FR-002**: System MUST include required identity provenance for every section,
  edge, and boundary item, preserve all source and reference provenance already
  available in graph state, and report missing optional provenance through
  workflow-quality evidence.
- **FR-003**: System MUST represent `missing_target_in_corpus` references as
  explicit coverage-boundary stops rather than inferred trusted edges.
- **FR-004**: System MUST report boundary-stop counts by reason and include
  deterministic bounded source samples for missing-target boundaries. The
  default `source_sample_limit` is 5 per grouped boundary stop.
- **FR-005**: System MUST support explicit bounds, including maximum depth,
  allowed relation types, fanout limits, node limits, edge limits, and
  deterministic ordering. Default bounds are `direction = outgoing`,
  `max_depth = 1`, `fanout_limit = 25`, `node_limit = 100`,
  `edge_limit = 500`, and `source_sample_limit = 5`; 005 maximums are
  `max_depth <= 2`, `fanout_limit <= 100`, `node_limit <= 1000`,
  `edge_limit <= 5000`, and `source_sample_limit <= 20`.
- **FR-006**: System MUST report traversal truncation, skipped path, and cycle
  boundary metadata when workflow limits affect the output.
- **FR-007**: System MUST treat inactive sections as auditable structural nodes
  and must make their status visible when they appear as selected sections,
  neighbors, or boundary context.
- **FR-008**: System MUST NOT infer, create, or persist trusted typed edges for
  missing targets from the inventory or from unresolved reference text.
- **FR-009**: System MUST NOT create chatbot answers, generated legal
  conclusions, semantic propositions, GraphRAG inference output, or trusted LLM
  candidates.
- **FR-010**: System MUST produce workflow-quality evidence summarizing visited
  sections, followed edges by relation type, boundary stops by reason,
  truncation counts, and provenance completeness.
- **FR-011**: System MUST remain deterministic for unchanged graph state and
  identical workflow parameters, excluding generated timestamps or run ids.

### Key Entities *(include if feature involves data)*

- **Structural Workflow Request**: Operator-selected workflow mode, scope, and
  controls, including law codes, seed legal sections where applicable,
  direction, maximum depth, allowed relation types, fanout limits, node limits,
  edge limits, and source sample limits.
- **Structural Workflow Artifact**: Read-only output describing selected
  sections or law-code scopes, resolved typed-edge neighbors or overview edges,
  traversal paths where applicable, relation evidence, provenance, statuses,
  and deterministic ordering metadata.
- **Coverage Boundary Stop**: A non-inferred traversal stop caused by unresolved
  reference evidence, especially `missing_target_in_corpus`, with target
  law/section where available, reason, count, and bounded source samples.
  Grouped stops keep `count` for all matching references while `source_samples`
  stores a deterministic prefix of representative references.
- **Workflow Quality Summary**: Deterministic summary of visited sections,
  followed edges, boundary stops, truncations, cycles, and provenance
  completeness for a workflow run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can generate a structural workflow artifact for either a
  selected seed section or a selected law-code scope that includes only resolved
  typed edges and auditable provenance.
- **SC-002**: For unchanged graph state and identical parameters, repeated
  workflow runs produce identical deterministic content apart from timestamp or
  run-id fields.
- **SC-003**: Missing-target references are reported as boundary stops with
  reason, target law/section where available, count, and source samples, and no
  trusted edge is inferred for them.
- **SC-004**: Workflow outputs include counts for visited sections, followed
  edges by relation type, boundary stops by reason, truncations, and provenance
  completeness.
- **SC-005**: Default unit validation runs without live Neo4j, live embeddings,
  paid APIs, GraphRAG sidecars, remote notebooks, or private legal corpora.
- **SC-006**: Workflow artifacts contain no answer text, generated legal
  conclusion, LLM proposition, or trusted semantic candidate content.

## Assumptions

- `004-corpus-boundary-status` has produced trusted `LegalReference` evidence,
  typed legal edges, source/target statuses, relationship-quality artifacts,
  corpus-readiness artifacts, and a post-004 missing-target inventory for the
  real-data smoke scope.
- Known missing targets are potentially temporary corpus-coverage gaps. They
  can be resolved or reclassified by later corpus expansion, but this feature
  does not automate that expansion.
- Operators want structural graph usage before full corpus coverage closure.
- Existing resolved typed edges are the only trusted relationship traversal
  surface for this feature.
- Law-code-only workflow requests are bounded structural overview artifacts.
  They are not corpus expansion automation and do not perform recursive
  traversal from every section.
- Trusted relation types come from the typed legal edges produced by the
  relationship-refresh foundation. Unknown relation types are validation errors,
  not empty successful workflows.
- Runtime output artifacts under `data/` remain generated artifacts and are not
  source-controlled unless explicitly sanitized for publication.
