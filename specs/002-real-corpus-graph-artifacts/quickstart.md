# Quickstart: Real Corpus Graph Artifacts

## 1. Environment

```bash
conda activate chbot
python -m pip install -e ".[dev]"
```

Use the configured live Neo4j and local embedding endpoint only for marked
integration checks. Default unit and smoke checks must not require them.

## 2. Preview Real Corpus

Generate a preview file artifact from a real corpus manifest:

```bash
python -m app preview legal-xml \
  --manifest path/to/real_corpus_manifest.json \
  --output data/import_preview/real_corpus_preview.json
```

Expected result:

- source documents and fragments for the selected scope
- deterministic ordering and identifiers
- missing optional inputs recorded in the file artifact

## 3. Load And Verify

Load the previewed scope into Neo4j and verify counts:

```bash
python -m app graph load \
  --preview data/import_preview/real_corpus_preview.json \
  --law-code AufenthG

python -m app graph verify --law-code AufenthG
```

Expected result:

- loaded scope counts stay stable across repeated loads
- verify reports source, legal, reference, unresolved, and embedding counts

## 4. Create Graph Snapshot

Generate a snapshot artifact from the loaded scope:

```bash
python -m app graph snapshot \
  --law-code AufenthG \
  --output data/snapshots/aufenthg_snapshot.json
```

Expected result:

- counts by graph object type
- labels and relation types
- bounded sample identifiers
- source coverage and embedding metadata

## 5. Capture Baseline Snapshot

Capture the legacy AufenthG baseline graph snapshot as a read-only snapshot
artifact once, then use it for the baseline check:

```bash
python -m app graph snapshot \
  --law-code AufenthG \
  --output data/snapshots/legacy_aufenthg_baseline_snapshot.json \
  --read-only-baseline
```

## 6. Baseline Check

Check the new snapshot against the baseline snapshot:

```bash
python -m app graph compare \
  --new data/snapshots/aufenthg_snapshot.json \
  --baseline data/snapshots/legacy_aufenthg_baseline_snapshot.json \
  --output data/snapshots/aufenthg_baseline_report.json
```

Expected result:

- matching, missing, and extra acts, sections, fragments, references, labels,
  and relation types
- read-only baseline treated as coverage evidence only
- no migration of old graph data

## 7. Validation

```bash
python -m compileall src tests
python -m pytest tests/unit
python -m pytest tests/smoke
```

Live checks remain opt-in:

```bash
export RUN_LIVE_NEO4J_TESTS=true
python -m pytest tests/integration -m neo4j

export RUN_LIVE_EMBEDDING_TESTS=true
python -m pytest tests/integration -m embedding
```

## 8. Validation Results

- `python -m compileall src tests`: PASS
- `python -m pytest tests/unit tests/smoke`: `49 passed`
- `RUN_LIVE_NEO4J_TESTS=true python -m pytest tests/integration -m neo4j`: `4 passed, 1 skipped, 1 deselected`
