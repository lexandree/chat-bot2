# Research: Legal Question Canonicalization And Cluster Coverage

## Decision: Use Canonical Legal Issue Evidence As The Primary Grouping Target

**Rationale**: The prior 006 coverage run showed that raw Telegram question
embeddings are too sensitive to surface wording and noisy keyword prefilters.
A canonical legal issue representation can group repeated legal situations that
mention different words, authorities, documents, or status details.

**Alternatives considered**:

- Raw question embeddings only: rejected because they produced misleading
  coverage signals and poor semantic grouping.
- Broad topic/law keywords only: rejected because they admit non-legal noise and
  miss legal equivalence across wording variants.
- Answer embeddings as the main target: rejected for 007 because many corpus
  candidates lack usable answer support and 007 is specifically about question
  space coverage.

## Decision: Preserve Source-Language Canonical Questions And Use Stable Issue Slugs

**Rationale**: Reviewers need canonical questions in the source user's language
to audit meaning without translation loss. Metrics and clustering need stable,
language-neutral issue identifiers such as
`residence_document_address_update_with_expired_or_extended_permit`.

**Alternatives considered**:

- Translate all canonical questions to English: rejected because it adds review
  friction and risks losing German legal terms or source-user nuance.
- Use free-text canonical questions as cluster ids: rejected because wording
  changes would make coverage metrics unstable.

## Decision: Treat LLM Canonicalization As Review Evidence Only

**Rationale**: LLMs can normalize noisy questions, identify issue frames, and
suggest hidden issue hints, but those outputs are not authoritative legal
facts. They must remain candidate evidence with runtime metadata, confidence,
validation status, and review routing.

**Alternatives considered**:

- Allow LLM canonicalization to approve clusters automatically: rejected because
  cluster approval affects evaluation coverage and must be reviewable.
- Use LLM output to write final legal answers: rejected as out of scope and a
  violation of the project trust boundary.

## Decision: Keep `question_bank` Separate From Reviewed Evaluation Cases

**Rationale**: 007 should produce many useful canonical issue clusters even
when no reviewed reference answer is available. A final evaluation case remains
a stricter artifact that requires reviewed reference answer material from an
accepted Telegram answer or manual override.

**Alternatives considered**:

- Require every canonical cluster to have a final answer: rejected because it
  would recreate the high manual-review cost 007 is meant to reduce.
- Promote answerless clusters into final evaluation: rejected because later
  evaluation would not have a reference answer boundary.

## Decision: Embed Canonical Question And Issue Frame Text With Query Semantics

**Rationale**: Canonical questions and issue frames represent search/query
intent, not source documents. They should use the existing asymmetric embedding
contract with `Query: ` semantics and full embedding profile metadata.

**Alternatives considered**:

- Use `Document: ` semantics for issue frames: rejected because issue frames are
  not source text or answer material.
- Define a separate embedding profile for 007: rejected until evidence shows
  the existing retrieval profile is unsuitable.

## Decision: Start With Bounded Corpus Slices And Record Scope Explicitly

**Rationale**: The full 006 pool contains 295k candidates and a noisy
`law_or_topic` subset of 38,835 candidates. 007 should support bounded,
resume-safe batches first and record scope limitations so operators do not
misread early coverage numbers.

## Decision: Allow Mature Context Helpers, Not Agent Orchestration

**Rationale**: The live Qwen/MiniMax/DeepSeek contour needs reliable prompt
assembly, few-shot placement, token budgeting, message formatting, and
structured-output validation. Reimplementing all context-handling details risks
rediscovering known edge cases. A small, explicit operator dependency such as
`langchain-core` may be justified for prompt/context utilities if it reduces
custom glue.

**Boundary**: This does not authorize LangGraph, LangChain agents/chains,
retrieval agents, chatbot inference, answer synthesis, or default-test
dependencies. Context helpers must remain inside an operator-managed live LLM
runner and must not change the reviewed-evidence trust boundary.

**Alternatives considered**:

- Hand-roll all prompt/context construction: acceptable for the current static
  50-row calibration, but risky once example selection, token budgeting, and
  provider-specific message shapes become more complex.
- Adopt full LangChain/LangGraph orchestration: rejected for 007 because the
  feature is an artifact pipeline, not an agent or inference system.

**Alternatives considered**:

- Full-corpus-only design: rejected because it slows prompt, schema, and review
  calibration.
- Treat the prior 1.52% raw-embedding coverage as an actionable coverage
  estimate: rejected because the start context explicitly identifies it as a
  diagnostic artifact, not reliable coverage evidence.

## Decision: Review Clusters, Not Isolated Messages

**Rationale**: The unit of manual review should be a legal issue cluster with
representative raw questions. This reduces repeated work and makes merge/split
decisions visible at the correct semantic level.

**Alternatives considered**:

- Continue reviewing individual Telegram questions: rejected because duplicate
  legal situations appear with many surface forms.
- Trust transitive embedding clusters: rejected because broad components can
  merge legally different issues.

## Decision: Keep 007 As File Artifacts, Not Graph State

**Rationale**: 007 prepares evaluation and retrieval coverage evidence. It does
not add source-grounded legal facts, trusted propositions, or graph retrieval
features. File artifacts preserve auditability without expanding graph state.

**Alternatives considered**:

- Store canonical issue clusters in Neo4j immediately: rejected because the
  graph of record should remain source/legal/reference state until a later
  design explicitly introduces evaluation or review entities.
- Add chatbot inference around canonical clusters: rejected as out of scope.
