# Legal Graph Relationship Methods

## Purpose

This document guides the next relationship-foundation stage for the German
legal graph.

The goal is not to compare the new graph with a legacy graph. The goal is to
build a source-grounded, retrieval-ready legal relationship foundation from
real German legal XML sources.

Use mature GraphRAG programs and papers as method references, but keep the
project's legal XML structure, provenance, temporal metadata, and typed legal
relations as the graph of record.

## Scope For The Next Stage

Recommended feature name:

`003-legal-graph-relationship-foundation`

Recommended stage goal:

Build context-aware typed legal relationships from real German legal XML corpus
data. Preserve source provenance and unresolved-reference evidence. Produce
relationship-quality artifacts for the new graph only.

In scope:

- legal XML structure as authoritative source input
- multi-resolution legal units: act, section, paragraph/list item when
  recoverable, fragment
- explicit legal reference parsing with surrounding context
- typed legal relation classification
- unresolved, ambiguous, and out-of-scope reference audit records
- temporal and version-aware relation metadata
- relationship-quality report for the new graph
- tests over real-corpus fixtures and selected live graph checks

Out of scope:

- legacy graph comparison
- migration from old graph data
- chatbot UX
- answer generation
- GraphRAG inference
- trusted LLM-derived propositions
- community reports as runtime answer support

## Source Of Truth Order

Use this precedence order when building legal relations:

1. German legal XML structure and metadata.
2. Exact legal references in source text.
3. Deterministic parsing and legal-domain rules.
4. LLM-assisted extraction only as reviewable candidate evidence.
5. Embeddings and vector similarity only as retrieval indexes, never as legal
   meaning.

This means a framework-generated entity or relationship may suggest work to
review, but it must not override the authoritative legal structure.

## Relationship Taxonomy

The first relationship-foundation slice should preserve distinct relation
semantics:

- `CITES`: neutral explicit reference.
- `DEFINES`: source text defines a term or legal concept by reference.
- `APPLIES_IF`: source text describes an applicability condition.
- `REQUIRES`: source text states a required condition, document, status, or
  action.
- `EXCEPTION_TO`: source text creates an exception to a referenced rule.
- `EXCLUDES_IF`: source text excludes applicability under a condition.
- `AMENDS`: source text changes another legal unit.
- `SUPERSEDED_BY`: legal unit is replaced by a later unit or version.

Do not collapse these into `RELATED` or `SEMANTICALLY_RELATED` in the structural
foundation. A semantic-similarity relation can be added later as a separate
retrieval-support signal.

## Methodology

### 1. Build The Lexical Legal Graph First

Map the XML corpus into a lexical graph:

- `SourceDocument`
- `SourceFragment`
- `LegalAct`
- `LegalSection`
- smaller legal fragments when source structure supports them
- sequence links where paragraph/list order matters
- provenance links back to source file, checksum, law code, and section
  reference

Neo4j's GraphRAG material describes this as a lexical graph shape: documents,
chunks, document-to-chunk links, and next-chunk links. For this project, use
legal names and legal anchors instead of generic document/chunk names where the
source structure is known.

### 2. Parse Explicit References With Context Windows

The parser must not classify relation type from the matched `§ ...` text alone.
It should inspect a bounded context window around each reference:

- current sentence
- previous sentence when it introduces a definition or condition
- heading/title when it signals amendment, exception, or scope
- list item marker when relation semantics are distributed across a list

Every `LegalReference` should record:

- raw reference text
- normalized reference text
- source legal fragment id
- source legal section id
- target law code
- target section reference
- resolved target section id when available
- relation type
- relation classifier version
- resolution status: `resolved`, `unresolved`, `ambiguous`, `out_of_scope`
- evidence span or context text checksum

### 3. Resolve Before Classifying Deep Semantics

Resolution and classification should be separate steps:

1. normalize the reference
2. resolve target law and section
3. classify relationship type from context
4. materialize typed edge only if target resolution is reliable
5. store unresolved or ambiguous references as audit records

This keeps the graph inspectable when a reference is valid textually but the
target is absent from the selected corpus.

### 4. Use Rule-Based Classifiers Before LLM Assistance

Start with deterministic legal-domain rules:

- citation-only patterns -> `CITES`
- "im Sinne", "Begriff", "Definition" context -> `DEFINES`
- "abweichend", "Ausnahme", "unbeschadet" context -> exception/exclusion
  candidates
- "setzt voraus", "erforderlich", "muss", "nur wenn" context -> `REQUIRES`
  or `APPLIES_IF`
- amendment headings and amendment-law metadata -> `AMENDS` /
  `SUPERSEDED_BY`

LLM extraction can be introduced later for unresolved or low-confidence cases,
but only as candidate evidence with source support and review state.

### 5. Produce Relationship Quality Artifacts

The stage should output artifacts about the new graph:

- relation counts by type
- resolved/unresolved/ambiguous counts
- top unresolved target laws and sections
- sample edges by relation type
- sample context spans by classifier rule
- relation classifier version
- source-to-relation coverage by law code
- fanout distribution for high-degree sections
- temporal metadata completeness

These artifacts replace legacy graph comparison as the acceptance evidence.

## How To Use Microsoft GraphRAG

Microsoft GraphRAG is useful as methodology in `003` and as potential sidecar
tooling in a later external graph-method research feature.

Relevant ideas to adopt:

- indexing pipeline separation: load documents, chunk text, extract graph,
  extract claims, embed chunks, detect communities, generate reports
- prompt tuning for domain-adapted entity and relationship extraction
- LLM caching and idempotent indexing behavior for expensive extraction runs
- local/global/DRIFT search concepts for later retrieval experiments
- claim extraction as a later reviewable semantic layer

Recommended use in this project:

- Use prompt tuning, indexing separation, idempotent extraction, and
  local/global/DRIFT search concepts as design references during `003`.
- Defer running `microsoft/graphrag` on exported corpus samples to a separate
  external graph-method research feature after deterministic relationship
  refresh and relationship-quality artifacts exist.
- Treat GraphRAG outputs as research artifacts or candidate suggestions, not as
  authoritative graph writes.
- Do not let GraphRAG community summaries or entity extraction become
  acceptance criteria for the structural legal graph.

Do not use Microsoft GraphRAG as the primary graph-of-record writer in this
stage. Its default model is LLM-derived KG indexing over text units, while this
project's first reliable layer is source-grounded legal structure.

### Future External Graph-Method Research Track

After `003` implements the deterministic relationship foundation, a separate
research feature may evaluate Microsoft GraphRAG and comparable frameworks:

1. Export a bounded sample of legal text units with law code, section reference,
   source fragment id, source legal section id, and relationship-quality
   findings such as unresolved, ambiguous, high-fanout, or multi-signal cases.
2. Run Microsoft GraphRAG, LlamaIndex schema-guided extraction, Neo4j KG Builder
   sandboxing, or schema-validation experiments when runtime, model, and
   network conditions are available.
3. Record completed, failed, or skipped status for each adapter.
4. Review proposed entities and relationships against the project taxonomy.
5. Map observations to `ignore`, `add_fixture`, `adjust_rule`,
   `taxonomy_gap`, or `future_llm_candidate`.
6. Store results under `data/research/`, not as trusted graph state.

The future research track should find blind spots in fixtures, deterministic
rules, taxonomy design, and prompt-tuning strategy. It must not create trusted
`LegalReference` records, typed edges, relationship-quality acceptance
artifacts, chatbot answers, or GraphRAG inference behavior for `003`.

## How To Use Neo4j GraphRAG

Neo4j GraphRAG is closer to the future runtime shape because Neo4j is the graph
of record.

Relevant modules and patterns:

- `neo4j-graphrag` retrievers:
  - `VectorRetriever`
  - `VectorCypherRetriever`
  - `HybridRetriever`
  - `HybridCypherRetriever`
  - `Text2Cypher`
- Knowledge Graph Builder concepts:
  - data loader
  - text splitter
  - lexical graph builder
  - schema builder
  - entity/relation extractor
  - graph pruner
  - entity resolver
  - KG writer

Recommended use in this project:

- Keep our current Neo4j schema and writer as canonical for source-grounded
  legal nodes and relations.
- Use Neo4j GraphRAG retriever patterns later when retrieval needs vector plus
  typed graph expansion.
- Evaluate KG Builder experimentally on legal fragments only after structural
  relations are working.
- Use a manually constrained legal schema if KG Builder is tested; avoid
  automatic broad schema discovery for trusted legal relations.

## Existing Project Modules To Extend

Current modules already provide a starting point:

- `src/ingestion/legal_reference_parser.py`: upgrade from regex-only parsing to
  context-aware reference extraction and relation classification.
- `src/ingestion/legal_structure_builder.py`: keep base structural graph
  assembly separate from relationship evidence assembly. Base graph load writes
  source/legal structure only; relationship refresh emits `LegalReference`
  records with context evidence and classifier metadata.
- `src/graph/writer.py`: keep the typed edge allowlist; add properties such as
  classifier version, resolution status, and evidence reference where useful.
- `src/retrieval/legal_traversal.py`: keep bounded traversal; later validate
  per-relation traversal policy against real graph fanout.
- `src/evaluation/load_cases.py`: move from legacy comparison emphasis to
  new-graph relationship quality artifacts.

## Acceptance Criteria For 003

The next stage should be accepted only when:

- each loaded legal section has stable structural identity
- each parsed reference has auditable source evidence
- resolved references materialize typed legal edges
- unresolved and ambiguous references are preserved without graph-write failure
- at least `CITES`, `DEFINES`, `EXCEPTION_TO`, `REQUIRES`, and `APPLIES_IF`
  have explicit classifier tests
- amendment/version relations have a documented source strategy, even if full
  historic version support remains partial
- relationship-quality artifacts can be regenerated deterministically
- default tests run without live Neo4j, live embeddings, paid APIs, remote
  notebooks, chatbot UX, or answer generation
- no task depends on legacy graph comparison
- base graph load creates no trusted `LegalReference` records or typed legal
  relationship edges before explicit relationship refresh
- framework sidecar output is never an acceptance dependency or trusted graph
  writer in `003`

## Suggested Speckit Prompt

```text
Build legal graph relationship foundation from real German legal XML corpus.
Scope: context-aware legal reference parsing, typed legal relation extraction,
source-grounded LegalReference audit records, resolved typed Neo4j edges,
unresolved and ambiguous reference evidence, temporal/version relation metadata,
new-graph relationship quality artifacts, and tests. Do not compare against a
legacy graph. Do not migrate old graph data. Do not add chatbot UX, answer
generation, LLM proposition extraction, trusted semantic candidates, or GraphRAG
inference. Use Microsoft GraphRAG and Neo4j GraphRAG as methodological references
for indexing, relationship extraction, lexical graph design, and future
retrieval, while treating German legal XML structure and explicit legal
references as authoritative.
```

## References

- Microsoft GraphRAG documentation, indexing overview:
  https://microsoft.github.io/graphrag/index/overview/
- Microsoft GraphRAG documentation, indexing architecture:
  https://microsoft.github.io/graphrag/index/architecture/
- Microsoft GraphRAG documentation, dataflow:
  https://microsoft.github.io/graphrag/index/default_dataflow/
- Microsoft GraphRAG documentation, prompt tuning:
  https://microsoft.github.io/graphrag/prompt_tuning/overview/
- Microsoft GraphRAG GitHub repository:
  https://github.com/microsoft/graphrag
- Microsoft Research GraphRAG paper:
  https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/
- Neo4j GraphRAG overview:
  https://neo4j.com/labs/genai-ecosystem/graphrag/
- Neo4j GraphRAG for Python documentation:
  https://neo4j.com/docs/neo4j-graphrag-python/current/
- Neo4j GraphRAG RAG user guide:
  https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html
- Neo4j GraphRAG Knowledge Graph Builder user guide:
  https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html

Source review date: 2026-04-27.
