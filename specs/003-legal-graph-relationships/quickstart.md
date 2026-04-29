# Quickstart: Legal Graph Relationship Foundation

## 1. Environment

```bash
conda activate chbot
python -m pip install -e ".[dev]"
```

Default unit and smoke checks must not require live Neo4j, live embeddings,
paid APIs, remote notebooks, chatbot UX, answer generation, or GraphRAG
inference.

## 2. Prepare Or Reuse A Loaded Corpus Scope

Generate preview and load a selected legal corpus scope if it is not already
loaded:

```bash
python -m app preview legal-xml \
  --manifest tests/fixtures/legal_xml_import_manifest.json \
  --output data/import_preview/legal_xml_preview.json

python -m app graph load \
  --preview data/import_preview/legal_xml_preview.json \
  --law-code AufenthG
```

Expected result:

- source documents and fragments exist for the selected scope
- legal sections and legal fragments exist
- repeated load remains scoped and idempotent
- trusted `LegalReference` evidence and typed relationship edges are not
  created until relationship refresh runs

## 3. Refresh Relationship Evidence

Run the relationship-refresh workflow for the selected scope:

```bash
python -m app relationships refresh \
  --law-code AufenthG \
  --classifier-policy legal-ref-context-v1
```

Expected result:

- each parsed reference has source and context evidence
- resolved references create at most one primary section-level typed edge
- paragraph, sentence, number, appendix, and range anchors remain evidence
- missing targets are classified as `out_of_scope`, `unresolved`, or
  `ambiguous`
- repeated refresh passes do not duplicate reference records or typed edges

## 4. Verify Relationship Coverage

```bash
python -m app relationships verify --law-code AufenthG
```

Expected result:

- relation counts by type
- resolution-status counts
- bounded sample ids
- classifier-policy version
- visible unresolved and ambiguous evidence

## 5. Generate Relationship Quality Artifact

```bash
python -m app relationships quality \
  --law-code AufenthG \
  --output data/relationship_quality/aufenthg_relationship_quality.json
```

Expected result:

- counts by relation type
- counts by resolution status
- sample edges and sample reference evidence
- top unresolved targets
- source-to-relation coverage
- fanout summary
- temporal metadata completeness
- deferred strategy for `EXCLUDES_IF`, `AMENDS`, and `SUPERSEDED_BY`
- no generated answer fields such as `answer_text`, `answer`, or
  `generated_answer`

Required top-level artifact fields:

- `artifact_id`
- `selected_scope`
- `classifier_policy_version`
- `generated_at`
- `counts_by_relation_type`
- `counts_by_resolution_status`
- `sample_edges_by_relation_type`
- `sample_reference_evidence`
- `top_unresolved_targets`
- `source_to_relation_coverage`
- `fanout_summary`
- `temporal_metadata_completeness`
- `deferred_relation_strategy`

## 6. Framework Boundary Check

Microsoft GraphRAG and Neo4j GraphRAG are design references in `003`.

Acceptance does not require running either framework. Relationship acceptance is
based on deterministic refresh, verification, quality artifacts, and documented
framework boundaries. Framework sidecar output is not a trusted graph writer,
not a legacy migration path, and not part of relationship-quality acceptance.

Future external graph-method research, including Microsoft GraphRAG sidecars or
other framework comparison adapters, belongs in a separate feature after the
`003` deterministic relationship foundation is implemented. Any such output
must remain research evidence until a review-gated feature turns findings into
deterministic fixtures, adjusted parser/classifier rules, documented taxonomy
strategy, or candidate-only semantic workflows.

No chatbot UX, answer generation, GraphRAG inference, old graph migration, or
legacy comparison is part of this feature's implementation or acceptance path.

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
```

Latest validation on 2026-04-29:

- `python -m compileall src tests`: passed.
- `python -m pytest tests/unit`: 67 passed.
- `python -m pytest tests/smoke`: 4 passed.
- `RUN_LIVE_NEO4J_TESTS=true python -m pytest tests/integration -m neo4j`:
  6 passed, 1 skipped, 1 deselected.
- `python -m pytest tests/integration` without live flags: 8 skipped, confirming
  live resources are opt-in.

Default unit and smoke suites were run without live Neo4j, live Jina, paid APIs,
remote notebooks, private corpora, GraphRAG sidecars, chatbot UX, or answer
generation dependencies. Static boundary tests also verified that relationship
source imports no chatbot, LLM extraction, or GraphRAG sidecar runtime modules
and that acceptance docs do not promote legacy comparison or framework output
as a source of truth.

Real data smoke on 2026-04-29 used `data/legal_xml/AufenthG.xml`,
`data/legal_xml/AsylG.xml`, and `data/legal_xml/BeschV.xml` to generate
`data/import_preview/legal_xml_preview_003_smoke.json`. The selected scope
loaded 356 source fragments/legal sections, produced 1804 relationship evidence
records, resolved 1666 references into typed edges, left 138 references
unresolved, and generated
`data/relationship_quality/real_data_003_smoke.json`.

## 8. Completion Evidence

The feature is ready for implementation acceptance when:

- classifier tests cover `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`, and
  `EXCEPTION_TO`
- typed edges target section-level legal nodes
- sub-section anchors remain in reference evidence
- missing targets use `out_of_scope`, `unresolved`, or `ambiguous`
- refresh passes are idempotent
- relationship-quality artifacts are deterministic for unchanged graph state
- no legacy graph comparison is required
- no framework sidecar execution is required
- framework-produced observations, if created outside `003`, remain outside
  trusted graph writes and relationship-quality acceptance
