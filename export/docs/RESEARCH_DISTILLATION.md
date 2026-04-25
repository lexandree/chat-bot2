# Research Distillation

## Purpose

This note distills useful observations from the external research notes into
requirements and design pressure for the new legal graph foundation.

The source notes contain repeated critiques and speculative options. The points
below are the retained engineering conclusions.

## Stable Conclusions

### 1. Legal Retrieval Must Be Multi-Resolution

The useful target is not "embed long paragraphs better." The target is to
retrieve legal meaning at multiple granularities:

- proposition or atomic rule for recall
- paragraph or section text for local wording
- section, article, or act context for applicability, exceptions, and hierarchy

The graph must preserve parent context when a smaller unit is retrieved.

### 2. Legal-Aware Splitting Comes Before Broad LLM Extraction

German legal text can be semantically dense even when it is not extremely long.

The import/enrichment pipeline should support:

- heuristic splitting by legal markers such as conditions, exceptions, lists,
  references, and modality
- LLM decomposition only for dense, ambiguous, or failed heuristic segments
- structured extraction output with proposition type and source support

This keeps LLM usage targeted and reviewable.

### 3. German Legal Retrieval Needs Concept And Term Normalization

Embeddings alone are not enough for German legal language.

The architecture should leave room for:

- decompounding or component storage for German compounds
- legal term normalization
- aliases, abbreviations, synonyms, and related terms
- `Concept` nodes connected to legal fragments and proposition candidates

This should be treated as a retrieval-support layer, not as source truth.

### 4. Typed Legal Relations Are Required

A generic related edge is unsafe for law.

Relations with different legal semantics must stay separate. Examples:

- `CITES`
- `DEFINES`
- `REQUIRES`
- `APPLIES_IF`
- `EXCEPTION_TO`
- `EXCLUDES_IF`
- `AMENDS`
- `SUPERSEDED_BY`
- `SEMANTICALLY_RELATED`

This matters because similar wording can imply opposite legal effects.

### 5. Temporal Validity Is Core Legal Semantics

Legal graph entities must carry temporal metadata from the beginning.

Required design support:

- `valid_from`
- `valid_to`
- current-default retrieval
- as-of-date retrieval
- amendment and supersession relations
- preserving previous versions rather than overwriting legal history

### 6. Ranking Should Be Two-Stage

A single weighted score can be a baseline, but should not be the core
architecture.

Preferred shape:

1. Candidate generation from several channels:
   - exact legal reference resolution
   - vector search
   - full-text or BM25 search
   - concept match
   - citation and typed graph neighbors
2. Reranking on a smaller candidate set using normalized features:
   - vector similarity
   - lexical relevance
   - concept overlap
   - graph priors
   - temporal validity
   - optional cross-encoder or LLM reranker later

Reciprocal Rank Fusion can be evaluated before hand-tuned weighted sums become
complex.

### 7. GDS Is Offline Enrichment By Default

Graph Data Science can help discover priors and latent similarity, but it should
not be a default online dependency.

Good uses:

- offline PageRank or centrality as a weak prior
- offline node similarity on carefully selected graph projections
- community detection for exploration and corpus diagnostics

Risks:

- unsupervised communities can group legally opposite concepts
- central norms can overwhelm rare but exact rules
- heavy online GDS can make retrieval slow and hard to explain

### 8. Evaluation Is Mandatory

The system needs validation before ranking changes are trusted.

Minimum evaluation assets:

- legal query set
- expected support references
- Recall@k
- MRR
- nDCG@k
- notes for false positives, false negatives, and missing graph edges

Without this, chunking, concept normalization, fusion weights, and reranking
remain intuition rather than engineering.

### 9. Explainability Must Be First-Class

For legal search, results should explain why they were retrieved.

Useful explanation fields:

- retrieval channel
- matched legal reference
- matched concept nodes
- vector score
- lexical score
- graph path or relation
- temporal status
- source citation
- candidate review state

## Scope Guidance

### Foundation Stage

Required now:

- source import
- structural legal graph
- typed references
- temporal metadata
- embedding profile
- load, verify, delete
- exact reference and bounded traversal baseline
- validation fixtures

### Designed For But Deferred

- proposition-level extraction
- concept nodes and decompounding
- full-text/BM25 channel
- two-stage candidate generation and reranking
- offline GDS enrichment
- explanation traces

### Later Unless Evidence Forces It Earlier

- learning-to-rank
- production cross-encoder reranking
- hypothetical question nodes
- online GDS traversal
- chatbot inference

## Target Reframing

The useful project framing is:

`Build a temporal, typed, multi-resolution legal graph foundation that can later
support GraphRAG inference with reviewable semantic enrichment.`

This is narrower and safer than building a generic chatbot or a broad custom
GraphRAG framework from the start.
