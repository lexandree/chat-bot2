# Feature 007: Legal Question Canonicalization And Cluster Coverage

**Feature Branch**: `007-legal-question-canonicalization`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "Open feature 007 for legal question canonicalization and cluster coverage from the 006 Telegram evaluation artifacts. Convert raw Telegram question candidates into structured legal issue frames, cluster and measure coverage using canonical frames instead of raw question text, preserve embeddings as indexes and LLM canonicalization as reviewable evidence only, and do not implement chatbot answer generation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Canonicalize Telegram Questions (Priority: P1)

An evaluation operator needs to convert noisy redacted Telegram question candidates into consistent legal issue evidence so repeated legal situations can be recognized even when users describe them with different words.

**Why this priority**: Raw question embeddings did not reliably group legally equivalent situations. Canonical issue evidence is the foundation for useful cluster review and coverage measurement.

**Independent Test**: Can be tested with a small redacted candidate fixture containing repeated legal situations, dialogue fragments, and non-legal keyword noise. The result is a schema-valid canonicalization artifact with no trusted answers.

**Acceptance Scenarios**:

1. **Given** redacted Telegram question candidates from 006, **When** canonicalization evidence is produced, **Then** each completed item contains a canonical question, legal issue frame, law area, factual signals, desired outcome, authority context, hidden issue hints, legal-answer-required flag, standalone-question flag, confidence, runtime metadata, and provenance.
2. **Given** a candidate that is a non-legal or non-standalone message admitted by broad topic keywords, **When** it is canonicalized, **Then** the record is excluded from legal issue clustering with an explicit exclusion reason instead of being silently merged.
3. **Given** a question whose wording is in Russian, Ukrainian, or German, **When** the canonical question is emitted, **Then** the canonical question preserves the user's language while the issue-frame identifier remains a stable machine label.

---

### User Story 2 - Cluster Canonical Legal Issues (Priority: P2)

An evaluation operator needs clusters built around canonical legal issue frames, with representative raw questions retained as examples, so review work happens at the repeated legal issue level instead of one message at a time.

**Why this priority**: Reviewing isolated Telegram questions is too expensive and misses repeated legal meaning hidden behind different surface wording.

**Independent Test**: Can be tested by grouping a fixture where multiple surface forms describe the same residence-document address update issue and unrelated messages share only broad keywords.

**Acceptance Scenarios**:

1. **Given** canonicalized question records, **When** clustering is performed, **Then** equivalent legal issue records are grouped into issue clusters with representative examples and cluster quality flags.
2. **Given** similar raw words but different legal obligations or authorities, **When** clusters are formed, **Then** the records remain separate or are flagged for review rather than merged only because embeddings or keywords are close.
3. **Given** a low-confidence canonicalization result, **When** clustering is performed, **Then** the cluster records preserve the uncertainty and route the issue to review.

---

### User Story 3 - Measure Corpus Coverage By Canonical Frame (Priority: P3)

An evaluation operator needs coverage reports that compare the reviewed 006 evaluation dataset against the broader Telegram question corpus using canonical issue clusters instead of raw question similarity.

**Why this priority**: The previous raw-embedding coverage run is useful diagnostic evidence, but it should not be treated as a reliable estimate of legal question-space coverage.

**Independent Test**: Can be tested with a fixture containing reviewed seed cases, uncovered canonical issues, partial overlaps, and known non-legal noise.

**Acceptance Scenarios**:

1. **Given** reviewed 006 final cases and canonicalized corpus candidates, **When** coverage is measured, **Then** the report counts covered, partial, uncovered, excluded, and uncertain issue clusters with clear supporting evidence.
2. **Given** a corpus issue that maps to an existing reviewed evaluation case, **When** coverage is measured, **Then** the report links the issue cluster to that reviewed case without treating the Telegram reference answer as legal truth.
3. **Given** non-legal or dialogue-fragment records, **When** coverage is summarized, **Then** those records are counted as exclusions or backlog rather than uncovered legal questions.

---

### User Story 4 - Review And Promote Issue Clusters (Priority: P4)

An evaluation operator needs a review workflow that can approve, reject, merge, split, or hold canonical issue clusters, then promote only reviewed clusters with reviewed reference answer material into the evaluation dataset.

**Why this priority**: Canonicalization and clustering can reduce review effort, but final evaluation cases still require human-reviewed reference answer material.

**Independent Test**: Can be tested with a review fixture where some clusters become question-bank entries only, while a smaller subset is promoted into reviewed evaluation cases.

**Acceptance Scenarios**:

1. **Given** canonical issue clusters, **When** review decisions are recorded, **Then** question-bank entries can be approved without final reference answers.
2. **Given** a cluster selected for the reviewed evaluation dataset, **When** it is promoted, **Then** the promoted case must have a reviewed reference answer source: an explicitly accepted Telegram reference answer or a manual reference answer override.
3. **Given** LLM canonicalization evidence, **When** a final evaluation case is built, **Then** LLM output alone cannot approve the case or create trusted legal answer content.

### Edge Cases

- Broad Telegram keyword filters admit non-legal questions about work, electricity, sport, bikes, plants, heating, or similar everyday topics.
- A message contains several independently answerable legal questions.
- A message is a dialogue fragment, a helper's clarifying question, or a rhetorical complaint rather than a standalone user question.
- Similar surface wording maps to different authorities, legal statuses, deadlines, or desired outcomes.
- Different surface wording maps to one repeated legal issue, such as address updates for an expired or extended residence document.
- Canonicalization output is malformed, incomplete, low-confidence, or internally inconsistent.
- A candidate is missing expected 006 provenance, redaction status, or source artifact metadata.
- A cluster is too broad, has conflicting issue frames, or exceeds the reviewable size expected for one issue.
- Embedding records are unavailable, produced by a different profile, or created through a live service that was not explicitly opted in.
- Two canonical questions have high embedding similarity but differ in a material legal slot, such as status, authority, desired action, legal object, jurisdiction, temporal condition, or third-party role.
- Two questions are wording variants of the same legal issue and should be candidates for answer reuse, but are not exact duplicates.
- A similarity chain contains A-B and B-C close pairs while A-C is not legally equivalent; equivalence-safe clusters must not be inferred from connected components alone.
- A question contains both operational logistics and an independently answerable legal issue; diagnostics must separate legal intent from surrounding context before pair classification.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory)*

- **Foundation scope**: This feature supports the database-first legal knowledge foundation by improving evaluation and retrieval preparation. It does not introduce chatbot UX, answer synthesis, production inference, graph mutation, or trusted LLM legal facts.
- **Source and provenance**: Inputs are redacted 006 Telegram evaluation artifacts and reviewed 006 final dataset artifacts. Outputs must preserve candidate ids, message ids or redacted source references where available, source artifact paths, redaction status, text checksums or stable content identifiers, policy versions, run ids, and generated timestamps.
- **Embedding contract**: Embeddings are affected only as evaluation file artifacts. Canonical question and legal issue frame embedding inputs are query-like and must preserve `Query: ` semantics. Any embedding record must include provider, model, variant when available, dimensions, normalization, routing mode, task semantics, backend, profile id, status, and failure reason. Default tests must not require live embeddings.
- **Review boundary**: LLM canonicalization may create candidate evidence: canonical question text, issue frame labels, fact hints, hidden issue hints, exclusion reasons, confidence, and cluster suggestions. It must not create trusted legal answers, approve final cases, or make LLM-only evidence eligible for trusted retrieval.
- **Operational contour**: Full-corpus canonicalization and embedding runs are operator-managed bulk workflows with explicit opt-in, bounded scope controls, checkpoint or resume evidence, run manifests, failure counts, and coherent output artifact bundles. Useful runs remain private under ignored data paths unless separately sanitized.
- **Context tooling**: Operator-managed LLM runners MAY use mature context-handling helpers for prompt templates, few-shot example selection, token budgeting, provider message formatting, or structured-output binding. This does not permit LangGraph, autonomous agents/chains, chatbot inference, answer synthesis, or default-test live-service dependencies.
- **Test boundary**: Unit tests validate schema, deterministic policies, clustering decisions on fixtures, review-promotion rules, and artifact summaries without live Neo4j, live Jina, paid APIs, or remote notebooks. Integration or smoke tests may validate live embedding or operator-managed LLM contours only when explicitly enabled.

### Functional Requirements

- **FR-001**: The system MUST accept redacted Telegram question candidate artifacts from 006 as canonicalization inputs and MUST reject or flag inputs that require raw unredacted Telegram text.
- **FR-002**: The system MUST define a canonicalization evidence record containing at minimum `canonical_question`, `legal_issue_frame`, `law_area`, `facts`, `desired_outcome`, `authority_context`, `hidden_issues`, `is_legal_answer_required`, `is_standalone_question`, `exclusion_reason`, `confidence`, provenance, and runtime metadata.
- **FR-003**: The system MUST preserve the source language in `canonical_question` while using stable, language-neutral `legal_issue_frame` identifiers suitable for grouping and metrics.
- **FR-004**: The system MUST treat every LLM-produced canonicalization field as review evidence only and MUST mark it with run id, prompt or policy version, model or backend metadata when applicable, status, and failure reason.
- **FR-005**: The system MUST validate imported canonicalization results and keep malformed, missing, low-confidence, or contradictory records visible as failed, skipped, uncertain, or needs-review items.
- **FR-006**: The system MUST provide explicit exclusion routing for non-legal messages, non-standalone dialogue fragments, unanswerable fragments, spam, jokes, and records whose privacy or redaction state is unsuitable for downstream artifacts.
- **FR-007**: The system MUST create embedding inputs for canonical question and issue-frame fields using query semantics and MUST record embedding profile metadata for every imported vector record.
- **FR-008**: The system MUST cluster by canonical legal issue evidence and MUST retain representative redacted raw question examples, source candidate ids, cluster size, confidence, quality flags, and policy version.
- **FR-009**: The system MUST prevent raw question embedding similarity, broad keyword overlap, or LLM confidence from being the sole basis for automatic cluster approval.
- **FR-010**: The system MUST compare canonical issue clusters against the reviewed 006 evaluation dataset and report covered, partial, uncovered, excluded, and uncertain coverage categories with counts and supporting record references.
- **FR-011**: The system MUST clearly distinguish a `question_bank` of reviewed or reviewable canonical issue clusters from a `reviewed_evaluation_dataset` that contains only cases with reviewed reference answer material.
- **FR-012**: The system MUST require a reviewed reference answer source before promoting a cluster into the reviewed evaluation dataset: either an explicitly accepted Telegram reference answer or a manual reference answer override.
- **FR-013**: The system MUST preserve that Telegram answers are evaluation material only and are not legal authority or trusted graph support.
- **FR-014**: The system MUST support cluster-level review decisions including approve for question bank, approve for final evaluation, reject, merge, split, needs more context, and uncertain.
- **FR-015**: The system MUST emit run summaries and manifests with input artifact paths, output artifact paths, processed counts, completed counts, excluded counts, uncertain counts, failed counts, policy versions, runtime contour, known limitations, and unresolved backlog counts.
- **FR-016**: The system MUST keep generated data, vectors, LLM batches, LLM results, review sheets, and coverage reports under ignored data paths unless a later explicit publication step sanitizes them.
- **FR-017**: The system MUST NOT mutate Neo4j graph state, import chatbot handlers, generate user-facing answers, or hide missing evidence behind fallback answers in this feature.

### Optional Diagnostic Extension Requirements

The following requirements document Phase 8. They are part of the 007 design
record and were activated after the operator explicitly requested legal intent
equivalence diagnostics. Phase 8 remains an optional diagnostic layer: it does
not replace canonicalization review, does not change production retrieval
policy, and does not approve automatic answer reuse.

- **FR-018**: Phase 8 MUST treat legal intent equivalence diagnostics as a separate optional layer over completed canonicalization artifacts, not as a replacement for 007 canonicalization or human review.
- **FR-019**: Phase 8 MUST define legal intent candidates that capture material legal distinctions, explicit unknowns, ambiguities, evidence references, validation flags, provenance, and review state.
- **FR-020**: Phase 8 MUST define a pair benchmark contract for canonical question pairs with stable pair ids, pair source reasons, left/right provenance, similarity evidence when available, and review status.
- **FR-021**: Phase 8 MUST classify legal-intent pairs using the bounded classes `exact_duplicate`, `same_legal_intent`, `same_topic_different_issue`, `related_context`, `different`, and `uncertain`.
- **FR-022**: Phase 8 MUST record downstream safety decisions separately from pair class, including duplicate removal, canonical-question sharing, reference-answer sharing, FAQ-pattern grouping, retrieval-cluster grouping, and human-review routing.
- **FR-023**: Phase 8 MUST preserve high-similarity hard negatives for evaluation instead of silently deduplicating or discarding them.
- **FR-024**: Phase 8 MUST prevent embedding similarity, lexical similarity, reranker scores, clustering scores, or LLM confidence from directly creating trusted duplicate, answer-equivalence, or question-bank decisions.
- **FR-025**: Phase 8 MUST report legal-intent equivalence method quality against reviewed pair labels and must state insufficient-label limitations when labels are too few or imbalanced.
- **FR-026**: Phase 8 MUST provide review-evidence decision producers for method comparison, including a cosine+recos similarity baseline, a deterministic legal-slot comparator over imported legal-intent candidates, and an operator-managed structured-output LLM pair judge.

### Private Snapshot And Retrieval Baseline Extension Requirements

- **FR-027**: The system MUST treat all generated files under `data/evaluation/` as private regardless of file extension unless an explicit sanitization and publication step approves a specific artifact.
- **FR-028**: The system MUST support a content-free private snapshot manifest with stable artifact hashes, counts, privacy classification, and no copied dataset rows.
- **FR-029**: The first corpus-bounded retrieval benchmark MUST use only explicit law-code references as expected targets and MUST report its selected legal corpus boundary.
- **FR-030**: The explicit-reference benchmark MUST state that it does not measure semantic retrieval, reranking, answer quality, or GraphRAG inference.
- **FR-031**: The corpus-bounded semantic retrieval benchmark MUST preserve asymmetric `Query: ` and `Document: ` embedding semantics and MUST use the current graph-write source-fragment text contract.
- **FR-032**: Semantic retrieval evaluation MUST report Recall@k, MRR, and nDCG@k while keeping missing vectors visible as failures.
- **FR-033**: Query-explicit silver targets MUST remain separate from independently reviewed accepted reference targets.
- **FR-034**: Semantic retrieval metrics MUST NOT create trusted legal-reference, answer, or graph-support decisions.

### Key Entities *(include if feature involves data)*

- **CanonicalQuestionCandidate**: A redacted Telegram question candidate from 006 plus canonicalization status, provenance, and exclusion state.
- **CanonicalizationRun**: Run-level metadata for a deterministic or LLM-assisted canonicalization pass, including input scope, policy or prompt version, runtime contour, processed counts, failures, and output paths.
- **CanonicalizationEvidence**: Reviewable evidence attached to one candidate, including canonical question, legal issue frame, law area, facts, desired outcome, authority context, hidden issues, standalone/legal-answer flags, confidence, and failure or exclusion reason.
- **CanonicalEmbeddingRecord**: Imported vector evidence for canonical question or issue-frame text with embedding profile metadata and status.
- **LegalIssueCluster**: A cluster of canonicalized candidates representing one reviewable legal issue frame, with representative examples, source ids, quality flags, confidence, and review route.
- **ClusterCoverageRecord**: Coverage evidence linking a legal issue cluster to reviewed 006 final cases, question-bank entries, uncovered corpus records, exclusions, or uncertain backlog.
- **ClusterReviewDecision**: Human decision for one issue cluster, covering question-bank inclusion, final-evaluation promotion, merge, split, rejection, or uncertainty.
- **QuestionBankEntry**: Reviewed or reviewable canonical issue entry that may not yet have final reference answer material.
- **ReviewedEvaluationCaseCandidate**: A promotion candidate that can become a final evaluation case only when reviewed reference answer material is present.
- **LegalIntentCandidate**: Reviewable structured interpretation of one canonical question, including material slots, unknowns, ambiguities, evidence references, validation flags, confidence, and provenance.
- **QuestionPairBenchmarkRecord**: Stable diagnostic pair artifact comparing two canonical questions, including pair source reasons, similarity evidence, left/right provenance, and current review status.
- **PairEquivalenceDecision**: Reviewable candidate judgment for a pair, including pair class, answer-equivalence status, canonical-question-equivalence status, material differences, allowed downstream actions, confidence, risk, and validation flags.
- **PairReviewLabel**: Human label for one benchmark pair, used to evaluate automatic equivalence methods and hard negatives.
- **EquivalenceEvaluationReport**: Diagnostic summary comparing candidate methods against reviewed pair labels and recording risks, limitations, and method suitability.
- **PrivateArtifactSnapshotManifest**: Content-free identity manifest for a fixed private dataset artifact bundle.
- **CorpusBoundedExplicitReferenceCase**: Private retrieval-evaluation case derived from an explicit law-code reference in a canonical question.
- **CorpusBoundedSemanticEmbeddingItem**: Private query or legal-section document embedding input preserving the active asymmetric embedding contract.
- **CorpusBoundedSemanticRetrievalCase**: Private ranked retrieval result for one query-explicit target with silver-label and optional reference-review status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fixture containing at least five different surface forms of the same legal situation groups them under one legal issue frame while preserving each source candidate as an example.
- **SC-002**: A fixture containing broad-keyword non-legal noise produces explicit exclusion reasons for every excluded item and does not count those items as uncovered legal issue clusters.
- **SC-003**: Coverage summaries report reviewed-case coverage at the canonical issue-cluster level and include a limitation note that raw question embedding coverage is diagnostic evidence, not a legal question-space estimate.
- **SC-004**: No promoted reviewed evaluation case can be emitted unless it has a reviewed reference answer source and a recorded answer trust boundary.
- **SC-005**: Every output artifact type includes provenance, policy or prompt version, generated timestamp, and run or source artifact references sufficient for audit.
- **SC-006**: Default unit tests for canonicalization schemas, clustering fixtures, review promotion rules, and coverage summary generation run without live Neo4j, live Jina, paid APIs, network services, or remote notebooks.
- **SC-007**: After Phase 8 implementation, pair benchmark review artifacts allow an operator to classify at least 100 canonical-question pairs without editing raw JSON.
- **SC-008**: After Phase 8 implementation, evaluation reports identify high-similarity hard negatives separately from true duplicates and same-legal-intent pairs.
- **SC-009**: After Phase 8 implementation, no pair receives trusted duplicate-removal or answer-reuse status solely from embedding, lexical, reranker, clustering, or LLM-confidence scores.
- **SC-010**: After Phase 8 implementation, equivalence reports state the limitation instead of recommending an automatic threshold when reviewed pair labels are insufficient.
- **SC-011**: After Phase 8 implementation, offline tests exercise all three legal-intent decision producer contours without live LLMs, live embedding services, paid APIs, Neo4j, or network dependencies.
- **SC-012**: A private snapshot manifest changes identity when an input artifact changes and never contains private record text.
- **SC-013**: The corpus-bounded explicit-reference benchmark runs offline against a legal preview and reports exact-reference Recall@1 without claiming semantic retrieval quality.
- **SC-014**: Offline fixture tests exercise semantic embedding-batch emission and Recall@k, MRR, and nDCG@k evaluation without a live embedding service or Neo4j.

## Assumptions

- The reviewed 006 canonical final dataset is a seed evaluation baseline and coverage reference, not a trusted legal answer source.
- The first useful 007 corpus run may use a bounded legal-topic subset before full-corpus processing, provided the manifest records scope and limitations.
- `canonical_question` preserves the user's source language; `legal_issue_frame` is a stable machine-oriented label for grouping and metrics.
- LLM canonicalization, when used, is an operator-managed batch contour and not a production dependency.
- 007 outputs are file artifacts for evaluation and retrieval preparation. Graph persistence, answer synthesis, and chatbot UX remain out of scope until explicitly requested.
- Legal intent equivalence diagnostics are initially a benchmark and evaluation layer. Production retrieval policy changes require a later explicit design update.
