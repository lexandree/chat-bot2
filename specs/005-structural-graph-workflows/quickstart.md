# Quickstart: Structural Graph Workflows With Coverage Boundaries

## 1. Environment

```bash
conda activate chbot
python -m pip install -e ".[dev]"
```

Default tests must not require live Neo4j, embeddings, paid APIs, remote
notebooks, GraphRAG sidecars, or private corpora.

## 2. Validate Offline Workflow Contracts

```bash
python -m pytest tests/unit -k "traversal or structural_workflow or neighborhood"
python -m pytest tests/smoke -k "traversal or structural_workflow or neighborhood"
```

Expected result:

- traversal bounds are enforced
- artifacts include resolved edges and boundary stops separately
- missing targets do not become inferred trusted edges
- no answer text or semantic candidate output appears

## 3. Generate Structural Workflow Artifacts

Seed-neighborhood example for a live graph after 004 load and relationship
refresh:

```bash
python -m app traversal neighborhood \
  --workflow-mode seed_neighborhood \
  --law-code AufenthG \
  --law-code AsylG \
  --law-code BeschV \
  --seed-section-id legal-section:AufenthG:54:current \
  --relation-type CITES \
  --depth 1 \
  --fanout 25 \
  --node-limit 100 \
  --edge-limit 250 \
  --source-sample-limit 5 \
  --missing-target-inventory data/relationship_quality/real_data_004_missing_targets.json \
  --output data/structural_workflows/aufenthg_54_neighborhood.json
```

Law-scope overview example without a seed section:

```bash
python -m app traversal neighborhood \
  --workflow-mode law_scope_overview \
  --law-code AufenthG \
  --law-code AsylG \
  --law-code BeschV \
  --relation-type CITES \
  --fanout 25 \
  --node-limit 500 \
  --edge-limit 2000 \
  --source-sample-limit 5 \
  --missing-target-inventory data/relationship_quality/real_data_004_missing_targets.json \
  --output data/structural_workflows/real_data_scope_overview.json
```

Expected result:

- output uses resolved typed legal edges only
- `seed_neighborhood` starts from exact seed sections
- `law_scope_overview` produces a bounded structural overview for selected law
  codes without recursive traversal from every section
- CLI response includes `status`, `workflow_mode`,
  `structural_workflow_artifact_path`, `selected_scope`,
  `visited_section_count`, `resolved_edge_count`, `boundary_stop_count`,
  `boundary_stops_by_reason`, `missing_target_inventory_status`, and
  `warnings`
- `missing_target_in_corpus` references appear as coverage-boundary stops
- visited sections, followed edges, boundary stops, and truncations are counted
- source/reference provenance remains visible
- grouped boundary stops include at most five deterministically ordered source
  samples by default
- missing-target inventory status is reported but does not change trusted
  traversal
- generated artifact paths under `data/structural_workflows/` are ignored by
  source control

## 4. Live Neo4j Validation

Live checks remain opt-in:

```bash
export RUN_LIVE_NEO4J_TESTS=true
python -m pytest tests/integration -m neo4j -k "traversal or structural_workflow"
```

Expected result:

- the real 004 smoke graph can produce at least one seed-neighborhood artifact
  and one law-scope overview artifact
- boundary counts are consistent with current `LegalReference` state
- no trusted edge is inferred for missing targets

## 5. Scope Boundary

This feature is a structural graph workflow stage. It does not:

- add corpus expansion automation
- run LLM semantic extraction
- create `LegalNorm`, `Condition`, `LegalEffect`, or `Exception` nodes
- generate chatbot answers or legal advice
- introduce GraphRAG inference
- require embeddings or vector indexes

Known post-004 missing targets may be temporary. They remain auditable
coverage-boundary stops until a later feature chooses to expand the corpus or
define broader retrieval behavior.

## 6. Validation Record

Observed on 2026-05-03:

- `conda run -n chbot python -m pytest tests/unit -k "traversal or structural_workflow or neighborhood"`:
  15 passed
- `conda run -n chbot python -m pytest tests/smoke -k "traversal or structural_workflow or neighborhood"`:
  4 passed
- `conda run -n chbot python -m pytest tests/unit tests/smoke`: 100
  passed
- `RUN_LIVE_NEO4J_TESTS=true conda run -n chbot python -m pytest tests/integration/test_neo4j_structural_workflows.py -m neo4j`:
  1 passed with live Neo4j configuration
