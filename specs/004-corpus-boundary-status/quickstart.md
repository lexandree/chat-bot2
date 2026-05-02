# Quickstart: Corpus Boundary And Source Status Hardening

## 1. Environment

```bash
conda activate chbot
python -m pip install -e ".[dev]"
```

Default unit checks must not require live Neo4j, live embeddings, paid APIs,
remote notebooks, or chatbot inference.

## 2. Validate Source Status Detection

Run the offline tests for inactive-source detection and explicit unresolved
reasons:

```bash
python -m pytest tests/unit -k "status or unresolved or corpus_readiness"
```

Expected result:

- inactive XML markers are classified as structural status
- unresolved references map to explicit reason buckets
- no answer text fields appear in any artifact output

## 3. Generate Structural Output Evidence

Generate or refresh the selected preview file artifact, then load that explicit
artifact and run structural refresh/verification:

```bash
python -m app preview legal-xml \
  --manifest tests/fixtures/legal_xml_import_manifest.json \
  --law-code AufenthG \
  --output data/import_preview/legal_xml_preview.json

python -m app graph load --preview data/import_preview/legal_xml_preview.json --law-code AufenthG
python -m app relationships refresh --law-code AufenthG
python -m app relationships verify --law-code AufenthG
python -m app relationships quality --law-code AufenthG --output data/relationship_quality/aufenthg_relationship_quality.json
```

Expected result:

- source units are categorized as active or inactive
- unresolved references have explicit reason buckets
- existing relationship-quality baseline fields remain present
- `top_missing_targets` contains only `missing_target_in_corpus` summaries with
  bounded source samples
- relationship-quality output is deterministic for unchanged graph state

## 4. Generate Corpus Readiness Evidence

```bash
python -m app corpus readiness \
  --law-code AufenthG \
  --output data/corpus_readiness/aufenthg_corpus_readiness.json
```

Expected result:

- active and inactive units are counted separately
- structural complexity classes are summarized with deterministic threshold and
  priority rules
- no `LegalNorm`, `Condition`, `LegalEffect`, or `Exception` nodes are created

## 5. Validation

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

Observed validation on 2026-04-30:

- `python -m compileall src tests` passed
- `python -m pytest tests/unit` passed: 79 passed
- `python -m pytest tests/smoke` passed: 5 passed
- `python -m pytest tests/integration -m neo4j` without live env skipped gated checks as expected
- `RUN_LIVE_NEO4J_TESTS=true python -m pytest tests/integration -m neo4j` passed: 8 passed, 1 skipped, 1 deselected

## 6. Structural Output Scope

This feature is about structural output, not semantic output. Embeddings and
vector indexes are not required for this stage.

Structural output is considered ready when:

- inactive source units are visible
- unresolved reasons are explicit
- relationship-quality artifacts extend the existing baseline shape without
  removing preserved fields
- corpus-readiness summaries are deterministic
- repeated refreshes remain idempotent
- no semantic answer generation appears in the artifact surface

## 7. Post-004 Missing Target Inventory

For the real-data smoke scope `AufenthG`, `AsylG`, and `BeschV`, unresolved
references are currently known corpus-coverage gaps rather than parser failures:

- relationship references: 1804
- resolved typed edges: 1666
- unresolved references: 138
- unresolved reason: all `missing_target_in_corpus`
- unique missing targets in the post-004 inventory: 81
- `out_of_scope_law`, `ambiguous_target`, `parse_incomplete`,
  `target_without_law_code`, and inactive-target cases: 0

The full inventory is written as an ignored run artifact:

```text
data/relationship_quality/real_data_004_missing_targets.json
```

This inventory is intentionally a boundary artifact, not trusted graph state.
The inconsistency may be temporary: later corpus expansion can make some or all
targets resolvable. Until a later feature defines traversal behavior, downstream
graph workflows should use resolved typed edges only, avoid inferring trusted
edges for these missing targets, and treat references in this inventory as
coverage-boundary stops rather than blockers for starting 005.
