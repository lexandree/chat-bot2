# Meta-analysis of `external_research2` critiques

## Scope

This note synthesizes:

- [external_research2.md](/home/admin2/chat_bot/external_research2.md)
- [external_research2-1.md](/home/admin2/chat_bot/external_research2-1.md)
- [external_research2-2.md](/home/admin2/chat_bot/external_research2-2.md)
- [external_research2-3.md](/home/admin2/chat_bot/external_research2-3.md)
- [external_research2-4.md](/home/admin2/chat_bot/external_research2-4.md)

The goal is not to average opinions mechanically, but to identify:

- stable consensus
- high-value corrections
- speculative additions
- concrete implications for stage `004`

## Stable consensus

The critics strongly agree on the following points.

### 1. LLM-backed decomposition should target legal propositions, not only raw paragraphs

This is the strongest consensus across all four critiques.

The common thesis is:

- one embedding over a whole legal paragraph is often too semantically blurry
- retrieval should operate on smaller, legally meaningful units
- parent legal context still matters and must be returned together with the hit

The original `Paragraph -> AtomicRule` idea is therefore confirmed, not weakened.

### 2. Splitting should not be limited to only extreme outliers

All critiques converge on the same refinement:

- long paragraphs are an obvious problem
- but medium-length paragraphs with exceptions, conditions, and cross-references
  are also semantically dense

The practical implication is:

- use heuristic legal-aware splitting first
- use LLM decomposition as a second-stage tool for dense or ambiguous segments

### 3. German legal retrieval needs more than embeddings

All critiques reinforce the same linguistic point:

- NER and lemmatization help
- but German legal compounds and terminology require stronger normalization

The shared recommendation is to add:

- concept nodes
- term normalization
- compound-aware handling
- term-based retrieval alongside vectors

### 4. Evaluation is mandatory

This is the second strongest consensus after proposition extraction.

Every critique, explicitly or implicitly, points to the same risk:

- without a gold or semi-gold validation set, tuning remains intuition

The project therefore needs:

- a legal query set
- expected supporting norms or rule hits
- retrieval metrics such as Recall@k, MRR, nDCG@k

### 5. Temporal validity is core legal semantics

Three critiques make this explicit and the fourth is fully compatible with it.

The consensus is:

- legal retrieval without versioning is structurally unsafe
- `valid_from`, `valid_to`, and relation types like `supersedes` or `amends`
  are not optional polish

For legal systems this belongs in the core model, not in later cleanup.

## High-value corrections to the original proposal

These are the most important upgrades to the original research note.

### 1. Move from two layers to multi-resolution retrieval

The original design focused on:

- parent paragraph
- child atomic rule

The critiques make a convincing case for at least one more level:

- section/article

This leads to the following retrieval stack:

- `AtomicRule` for recall
- `Paragraph` for local legal wording
- `Section/Article` for broader applicability and exceptions

This is a meaningful upgrade and should be reflected in `004`.

### 2. Replace one linear score formula with a two-stage retrieval design

The original weighted formula is acceptable as a baseline, but the critiques are
right that it should not be the main architecture.

The convergent recommendation is:

1. candidate generation from multiple channels
2. reranking on a smaller candidate set

Candidate generation channels consistently proposed:

- vector search
- full-text or BM25 search
- concept match
- citation neighbors or graph expansion

Reranking can then combine:

- vector similarity
- lexical relevance
- graph priors
- later, an LLM or cross-encoder reranker

### 3. Type legal relations explicitly

This is not just graph neatness. It changes retrieval correctness.

The critiques correctly point out that these relations should not collapse into
one generic “related” edge:

- `CITES`
- `AMENDS`
- `DEFINES`
- `EXCEPTION_TO`
- `REQUIRES`
- `APPLIES_IF`
- `EXCLUDES_IF`
- `SEMANTICALLY_RELATED`

This is especially important because similar wording can imply opposite legal
effects.

### 4. Treat GDS as offline enrichment, not default query-time logic

This is another strong point of agreement:

- GDS can be useful
- but it should mostly be precomputed
- its outputs should be treated as priors or graph features, not as the main
  online engine

This is aligned with the current project direction and should stay so.

## Good ideas, but not all of them belong in the first `004` slice

Some recommendations are valuable but should not all be pulled into the first
LLM-backed implementation.

### 1. Hypothetical question nodes

This is interesting and potentially useful, but it is a second-order retrieval
enhancement, not the minimal LLM extraction slice.

Recommendation:

- keep as later optional enrichment
- do not make it part of first `004` scope

### 2. Full learning-to-rank

This is probably useful once there is relevance data, but it is premature for
the first LLM extraction phase.

Recommendation:

- keep as future evaluation/ranking extension
- do not block `004` on it

### 3. Cross-encoder reranking

This may help quality, but on constrained local and operator-managed runtimes it
adds another heavy component.

Recommendation:

- keep as an optional reranking layer
- not required for the first proposition-extraction milestone

### 4. Community detection as a central signal

The critiques are right that it may help exploration, but it is not yet
essential to the initial LLM extraction stage.

Recommendation:

- treat as offline exploratory enrichment
- avoid making it a mandatory ranking pillar in the first slice

## Recommended shape of stage `004`

Based on the combined critiques, stage `004` should be framed as:

`LLM-backed legal proposition extraction with multi-resolution provenance and reviewable graph insertion`

That wording is narrower and more actionable than a generic “better legal
search”.

### Core functional responsibilities for `004`

1. Parse legal text into candidate proposition units using:
   - heuristic legal-aware splitting
   - LLM decomposition for dense or difficult fragments
2. Persist proposition candidates as reviewable graph entities.
3. Preserve provenance across:
   - law
   - section/article
   - paragraph
   - fragment
   - extraction run
4. Store relation candidates with explicit legal semantics when possible.
5. Track effective LLM backend, prompt version, and extraction policy.
6. Support temporal metadata on legal units and extracted candidates.
7. Produce evaluation-ready outputs against a fixed legal validation set.

### What `004` should not try to finish immediately

The first implementation slice should avoid turning into a full legal reasoning
platform all at once.

It should not require from day one:

- learning-to-rank
- full GDS semantic enrichment
- community detection in ranking
- hypothetical question nodes
- production-grade cross-encoder reranking

## Proposed priority order

### Priority A: must enter the first `004` scope

- legal-aware splitting before or alongside LLM extraction
- proposition-level extraction
- multi-resolution provenance
- temporal validity fields
- typed legal relation candidates where confidently extractable
- evaluation harness for retrieval and extraction quality

### Priority B: should be designed for, but can be partially deferred

- concept normalization and decompounding
- concept nodes as a retrieval and linking layer
- offline GDS enrichment
- explicit explanation traces for why a candidate was found

### Priority C: keep for later unless evidence forces it earlier

- learning-to-rank
- cross-encoder reranking
- hypothetical question nodes
- heavy online GDS logic

## Final conclusion

The critics do not undermine the original idea. They sharpen it.

The strongest combined conclusion is:

- the project should not be framed as “embed long paragraphs better”
- it should be framed as “extract, normalize, and retrieve legal propositions
  with preserved legal structure, time validity, and reviewability”

That is the real bridge from `003` to `004`.
