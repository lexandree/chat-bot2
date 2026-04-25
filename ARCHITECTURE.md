# Architecture

## Layered Design

The system is organized as a staged legal knowledge platform.

```text
source files
  -> import preview
  -> source document/fragment layer
  -> structural legal graph
  -> retrieval support layers
  -> embedding indexes
  -> retrieval baseline
  -> operator-managed bulk enrichment
  -> reviewable semantic candidates
  -> future GraphRAG inference
```

Inference is deliberately last. Earlier layers must be independently testable.

## Package Boundaries

Recommended package layout:

```text
src/
  app/
    __main__.py
    commands.py
    settings.py
    logging.py
  graph/
    schema.py
    client.py
    repositories.py
    writer.py
    types.py
  ingestion/
    legal_xml_import.py
    legal_preview_loader.py
    legal_structure_builder.py
    legal_reference_parser.py
  retrieval/
    embedding_profile.py
    embedding_service.py
    embedding_router.py
    concept_normalization.py
    legal_reference_resolver.py
    legal_traversal.py
    candidate_generation.py
    reranking.py
  enrichment/
    legal_proposition_extractor.py
    legal_extraction_service.py
    review_boundary.py
  bulk/
    run_contract.py
    checkpoint_store.py
    artifact_export.py
    notebook_runtime.md
  review/
    claim_repository.py
    review_task_repository.py
    review_service.py
  evaluation/
    load_cases.py
    legal_validation.py
tests/
  unit/
  integration/
  smoke/
  fixtures/
```

The new project should not keep chatbot handlers, answer synthesis, and
database-import logic in the same orchestration path.

## Graph Access

Neo4j access should use a real driver-backed client.

Required client capabilities:

- execute write queries with parameters
- execute read queries with parameters
- run vector index queries
- expose database name support where needed
- close driver resources
- surface connectivity failures clearly

An in-memory or recording fake is useful for unit tests, but must not be the
production graph client.

## Schema

Schema bootstrap creates:

- uniqueness constraints for source, legal, candidate, validation, and
  embedding-profile ids
- Neo4j vector indexes over `embedding_v1`
- stable names for all constraints and indexes

Vector dimensions are a setting, not a hardcoded global.

## Embedding Runtime

The embedding layer has three concepts:

- profile: immutable contract for model, dimensions, normalization, task
  semantics, and provider metadata
- service: applies prefixes, calls backend, normalizes vectors, records runtime
  metadata
- router: controls local-only and interactive failover behavior

Graph-write workflows use local-only embedding. Interactive query workflows may
prefer local with API failover, but only after that mode is explicitly enabled.

## Structural Legal Retrieval

The first retrieval baseline is deterministic:

1. parse explicit legal references from the query
2. resolve law code and section reference against current or as-of-date sections
3. traverse allowed typed edges with bounded depth and fanout
4. return source refs and traversal metadata

This baseline is the comparison point for later semantic enrichment.

## Retrieval Support Layers

The graph should be able to support retrieval beyond direct vectors:

- concept nodes for legal terms, aliases, abbreviations, and German compound
  components
- full-text or BM25 indexes for lexical recall
- typed citation and legal-effect neighbors
- temporal filters for current-default and as-of-date queries

These layers are retrieval aids. They do not override source text or review
state.

## Candidate Generation And Reranking

Future GraphRAG retrieval should be two-stage:

1. candidate generation from exact references, vector indexes, full-text search,
   concept matches, and bounded graph expansion
2. reranking over a smaller candidate set using normalized vector, lexical,
   concept, graph, and temporal features

RRF and simple normalized feature fusion are acceptable first baselines.
Cross-encoder, LLM, or learning-to-rank rerankers are later additions that need
evaluation evidence.

## Offline Graph Analytics

Neo4j Graph Data Science can be useful for offline enrichment:

- PageRank or centrality as a weak prior
- node similarity on deliberate projections such as rule-to-concept or
  rule-to-citation-target
- community detection for diagnostics and exploration

GDS outputs should be stored as auditable graph features. They should not become
mandatory query-time dependencies in the foundation stage.

## Semantic Enrichment

LLM-backed enrichment is an offline or operator-managed workflow, not a hidden
side effect of query-time retrieval.

The extractor receives legal fragments and structural parent metadata. It emits
candidate propositions with source citations and parent references. The service
persists candidates, supports, extraction-run metadata, and review tasks.

Promotion to trusted support is a separate review action.

## Bulk And Notebook Runtime

Bulk processing is a controlled execution contour for source enrichment and
validation.

The runtime may be a local machine, a remote notebook, Kaggle, Colab, or a
managed API. Regardless of location, the project-facing contract is the same:

- explicit run guard
- explicit input manifest
- bounded scope controls
- stable item order
- checkpoint or resume state
- runtime metadata
- coherent artifact export
- review-gated outputs

Notebook code should be treated as an operator surface, not as the core domain
implementation. Reusable logic belongs in project modules; notebooks should
wire artifacts, runtime startup, and reporting.

## Future GraphRAG Inference

Future inference should be added only after the database foundation is stable.

Candidate approaches:

- Neo4j GraphRAG `VectorRetriever` and `VectorCypherRetriever` for vector plus
  graph expansion.
- Microsoft GraphRAG indexing/query pipelines for broader document-level
  entity, relationship, community, and report workflows.
- LlamaIndex property graph tooling where it cleanly maps to the legal graph.
- LangChain Neo4j integrations where chain-level orchestration is needed.

Selection criteria:

- fits Neo4j as the graph of record
- preserves legal structural retrieval
- exposes citations and provenance
- supports deterministic tests for non-live layers
- avoids hiding retrieval failure behind generic fallback answers
- supports multi-resolution retrieval and explicit explanation traces

## Operational Profiles

### Local development

- conda environment `chbot`
- unit tests do not require Neo4j or Jina
- integration tests can be enabled when Neo4j and local Jina are available

### Graph-write integration

- Neo4j or AuraDB reachable
- local Jina-compatible endpoint reachable
- graph writes fail fast if embeddings cannot be created

### Operator-managed enrichment

- open-weights LLM may run on a remote notebook runtime
- embeddings remain on the validated Jina-compatible path
- runs record contour, backend, model, and policy metadata
- resume state is persisted
- useful runs export manifest, profile report, result JSON, command metadata,
  and logs

## Anti-Patterns

- treating empty retrieval as grounded support
- putting chatbot inference into database import commands
- allowing LLM-generated propositions directly into trusted answers
- making unit tests depend on network services
- implementing a large custom GraphRAG framework before evaluating existing
  Neo4j/Microsoft/LlamaIndex/LangChain patterns
- collapsing legally different relations into one generic related edge
- ignoring temporal validity during legal retrieval
- letting notebook state become the only source of truth for bulk results
