# Legal Graph Foundation

Database-first foundation for a German legal graph knowledge base. The current
scope is configuration, Neo4j schema/bootstrap, deterministic legal XML preview,
structural graph load/verify/delete, file-based graph snapshots and comparison
reports, local-only source embeddings, exact reference resolution, bounded
traversal, and tests.

Out of scope for this foundation stage: chatbot UX, inference, LLM proposition
extraction, review workflow, trusted promotion, fallback answers, and GraphRAG
answer generation.

## Offline Validation

```bash
python -m compileall src tests
python -m pytest tests/unit
```

Unit tests use fakes and fixtures only. They must not require live Neo4j, live
embedding services, paid APIs, or remote notebooks.

## Live Checks

Live checks are opt-in:

```bash
export RUN_LIVE_NEO4J_TESTS=true
python -m pytest tests/integration -m neo4j

export RUN_LIVE_EMBEDDING_TESTS=true
python -m pytest tests/integration -m embedding
```

Start the local Jina-compatible embedding endpoint before running embedding
integration checks, and set `EMBEDDING_ENDPOINT_URL`.

Live integration tests write only to the isolated `TestAufenthG` scope and
clean that scope after graph-write checks. Existing live graph data, including a
separate comparison baseline such as `AufenthG`, is not part of automated test
cleanup.

## Operator Flow

```bash
python -m app settings validate
python -m app schema bootstrap
python -m app preview legal-xml --manifest tests/fixtures/legal_xml_import_manifest.json --output data/import_preview/legal_xml_preview.json
python -m app graph load --preview data/import_preview/legal_xml_preview.json --law-code AufenthG
python -m app graph verify --law-code AufenthG
python -m app graph snapshot --law-code AufenthG --output data/snapshots/aufenthg_snapshot.json
python -m app graph snapshot --law-code AufenthG --output data/snapshots/legacy_aufenthg_baseline_snapshot.json --read-only-baseline
python -m app graph compare --new data/snapshots/aufenthg_snapshot.json --baseline data/snapshots/legacy_aufenthg_baseline_snapshot.json --output data/comparisons/aufenthg_comparison.json
python -m app embeddings write --law-code AufenthG
python -m app references resolve --law-code AufenthG --section-reference "§ 1"
python -m app traversal run --legal-section-id legal-section:AufenthG:1:current --relation-type CITES --depth 1 --fanout 25 --node-limit 100
python -m app graph delete --law-code AufenthG --confirm
```

Add a new law to the active corpus only through the guarded corpus-expansion
runner. Offline preflight performs no graph writes:

```bash
NEW_LAW_CODE=VwVfG bash scripts/legal_graph/load_new_law.sh preflight
```

The complete workflow requires explicit graph-write opt-in:

```bash
NEW_LAW_CODE=VwVfG ALLOW_GRAPH_WRITES=1 \
  bash scripts/legal_graph/load_new_law.sh full
```

For the reviewed 007 core-corpus expansion from four to six laws
(`AsylbLG`, `AufenthV`), use the dedicated wrapper. Its preflight allows a
recorded `needs_review` warning for `AsylbLG` without graph writes:

```bash
bash scripts/legal_graph/load_core_six_law_corpus.sh preflight
```

The complete six-law workflow requires both graph-write opt-in and explicit
acknowledgement of the reviewed preflight warning:

```bash
ALLOW_GRAPH_WRITES=1 ALLOW_PREFLIGHT_NEEDS_REVIEW=1 \
  bash scripts/legal_graph/load_core_six_law_corpus.sh full
```

See
[`specs/004-corpus-boundary-status/new-law-operator-workflow.md`](specs/004-corpus-boundary-status/new-law-operator-workflow.md)
for manifest, relationship-refresh, embedding, and artifact requirements.
