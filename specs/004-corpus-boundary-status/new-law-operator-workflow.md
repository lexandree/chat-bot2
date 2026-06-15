# New Law Operator Workflow

## Purpose

Add one official legal XML source to the active graph corpus without silently
leaving stale relationship evidence, missing embeddings, or unreviewed corpus
scope changes.

This workflow changes the graph corpus and runtime contour. It does not create
answers, trusted LLM facts, or semantic retrieval policy.

## Active Corpus Manifest

`config/legal_xml_active_corpus.json` is the publication-safe manifest for the
currently selected law-code scope. It contains paths and source metadata only.
The referenced XML files remain private ignored inputs under `data/legal_xml/`.

Every active input is required. Optional or experimental laws belong in a
different manifest until they are intentionally added to the active scope.

## Safety Model

The runner is fail-fast and split into explicit actions:

- `preflight`: offline only; parses the complete active manifest, writes a
  deterministic preview, and resolves relationship evidence in memory.
- `load`: requires `ALLOW_GRAPH_WRITES=1`; loads only the new law and verifies
  its graph scope.
- `post-load`: requires `ALLOW_GRAPH_WRITES=1`; refreshes and verifies
  relationships across the complete active corpus, writes embeddings for the
  new law, and exports quality/readiness/snapshot artifacts.
- `full`: runs all stages in order.

Relationship refresh covers the complete active corpus because adding one law
can resolve references emitted by laws that were already loaded.

The runner does not rebuild dataset-specific semantic retrieval artifacts.
Those artifacts are explicitly marked stale by the run manifest and must be
rebuilt separately.

## Commands

Offline preflight for VwVfG:

```bash
NEW_LAW_CODE=VwVfG bash scripts/legal_graph/load_new_law.sh preflight
```

Complete guarded load:

```bash
NEW_LAW_CODE=VwVfG ALLOW_GRAPH_WRITES=1 \
  bash scripts/legal_graph/load_new_law.sh full
```

Skip graph-written embeddings only when intentionally completing them later:

```bash
NEW_LAW_CODE=VwVfG ALLOW_GRAPH_WRITES=1 WRITE_EMBEDDINGS=0 \
  bash scripts/legal_graph/load_new_law.sh full
```

Generated artifacts are written under ignored
`data/corpus_expansion/<run-id>/`.

## Preconditions

- official XML exists at the manifest path;
- `.env` or exported environment variables contain live Neo4j settings for
  graph-write stages;
- the configured local-only embedding backend is running when
  `WRITE_EMBEDDINGS=1`;
- the graph embedding writer sends sequential HTTP batches of at most `16`;
  this matches the established four-slot Jina/GTX 1060 operating profile;
- relationship refresh and graph embedding writes emit stage progress, counts,
  rates, and ETA to stderr while preserving the final JSON report on stdout;
- full law names used by existing sources have a tested canonical alias when
  they differ from the graph law code.

## Acceptance

- offline preflight reports `status=ready`;
- the new law has parsed source fragments;
- graph load and repeated load are scoped and idempotent;
- relationship refresh completes over every active law code;
- incoming references to the new law can resolve;
- graph verification, relationship verification, relationship quality, corpus
  readiness, and snapshot artifacts are exported;
- retrieval artifacts remain visibly pending rebuild.

The preflight checks relationship resolution only for references extracted by
the current structural parser. Lists and ranges can still require parser
improvements or later quality review when not every item is extracted.

## VwVfG Run Evidence

The first completed four-law expansion run added `VwVfG` alongside `AufenthG`,
`AsylG`, and `BeschV`:

- 477 source fragments and legal sections in active scope;
- 1,922 relationship references;
- five existing-law incoming references to `VwVfG`, all resolved;
- 122 verified VwVfG embeddings: one source document and 121 fragments;
- a checked structural route from `AsylG §25` to `VwVfG §14`.

An early embedding run exposed a source-fragment identifier mismatch and
reported processed vectors without matching graph nodes. The writer now uses
the entity-specific identifier and requires every embedding write to return
exactly one matched node.
