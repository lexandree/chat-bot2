# Legal Graph Foundation Seed

This seed describes the intended clean project shape. It is not a full
implementation.

## Environment

Use the conda environment:

```bash
conda activate chbot
```

Install dependencies inside that environment.

## First Milestone

Build the database foundation before any inference layer:

1. settings and logging
2. Neo4j driver-backed client
3. schema bootstrap
4. legal XML import preview
5. structural legal graph build
6. load, verify, delete
7. embedding profile and local-only graph-write embeddings
8. structural retrieval baseline

## Bulk Runtime Milestone

After the database foundation is stable, add an operator-managed bulk contour:

1. explicit run guard
2. input manifest and bounded scope controls
3. staged runtime artifact
4. checkpointed item processing
5. run manifest, profile report, result JSON, command metadata, and log export

Notebook workflows should call reusable project modules rather than becoming the
only implementation of bulk processing.

## Test Boundaries

Default tests must not require live Neo4j or live Jina.

Live checks should be separate integration or smoke tests.

## Useful Source Material

The sibling `source_snapshot/` directory contains selected code snapshots that
can be adapted into the new project. Do not copy them blindly; align imports and
tests with the clean architecture first.
