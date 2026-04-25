# Operations Checklist

## Before Starting Work

1. Check whether Neo4j Aura Free is paused.
2. Check whether local `llama-server` is actually running.
3. Confirm whether `ENABLE_EMBEDDING_ROUTER` is enabled.
4. Confirm which embedding workflow is active:
   - interactive user-query failover
   - local-only graph writes
5. Confirm the local model alias if `llama-server` is used.
6. Confirm the active embedding profile:
   - model
   - variant
   - dimension
   - normalized or not
   - `Query: ` / `Document: ` contract

## Jina Embeddings

1. Use retrieval-specific Jina weights only.
2. Use:
   - `Query: ` for queries
   - `Document: ` for indexed text
3. Keep vectors normalized.
4. Keep dimension fixed per active index.
5. Current validated dimension: `1024`
6. Allowed local variants:
   - `Q8`
   - `F16`
7. Forbidden local variant:
   - `XXS`
8. Do not treat CPU as the main embedding backend.

## Local Llama-Server

1. Run in embeddings mode.
2. Keep `pooling=last`.
3. Keep `parallel=1` unless there is a very good reason to change it.
4. Start with `ctx-size=8192`.
5. Tune `batch-size` and `ubatch-size` before touching `ctx-size`.
6. If the server is not running, say so explicitly before any embedding work.
7. For the current dev setup, do not launch `llama-server` on this machine.
8. Treat `127.0.0.1:18080` as a reverse-SSH forwarded endpoint from another
   host.
9. For Colab or Kaggle operator-managed runs, reach the same home-GPU endpoint
   through a relay-host reverse-SSH pattern and keep the notebook-side
   `LLAMA_SERVER_URL` bound to `127.0.0.1:18080/v1/embeddings`.

## Neo4j

1. Neo4j is the graph DB and vector DB.
2. Keep one active embedding profile per retrieval path.
3. Keep vector indexes aligned with the active dimension.
4. Check index state before writing data.
5. Check node `embedding_size` after writes.
6. Do not mix dimensions or profile ids in one active retrieval path.

## Large Vector Writes

1. Do not assume MCP is safe for large embedding payloads.
2. For large vector writes, prefer:
   - official Neo4j driver
   - Aura HTTP `query/v2`
3. After writing, always read back:
   - `size(n.embedding_v1)`
   - `embedding_profile_id`

## Tooling Expectations

1. Do not treat `neo4j-mcp` as required infrastructure.
2. If MCP is unavailable, continue with:
   - application direct-driver code paths
   - Aura HTTP `query/v2`
   - Neo4j Browser or `cypher-shell`
3. If Codex or another agent runs in a sandbox, assume host-local listeners and
   external DNS may be isolated until proven otherwise.
4. Treat `speckit` setup/init scripts as potentially destructive and inspect
   `git diff` immediately after running them.
5. Use [spec_kit_git_playbook.md](/home/admin2/chat_bot/spec_kit_git_playbook.md)
   for repeat iterations on generated spec artifacts.

## Bulk Enrichment `003`

1. Treat the first `003` slice as legal-first:
   - `law`
   - `official_guidance`
2. Default the first iterative bulk-enrichment loop to `operator_managed`.
3. Treat Colab-style and Kaggle-style remote GPUs as the same operator-managed
   LLM runtime class.
4. Use local Jina-compatible embeddings for the first `003` contour unless
   there is a specific reason to exercise managed-paid embedding infrastructure.
5. Keep the active validation fixture at:
   - `tests/fixtures/legal_enrichment_validation_cases.json`
6. Run baseline-vs-enriched validation against the same fixed question set.
7. Record:
   - runtime contour
   - effective LLM backend
   - effective embedding backend
   - extraction-policy version
   - processed/skipped/failed counts
8. Keep new `003` candidates in `pending` review state until moderator review.
9. Only `approved` `003` candidates may participate in trusted answer support.
10. If review load becomes too high relative to bounded validation benefit,
    treat that as a `no-go` signal for expanding the pipeline.

## Legal Extraction `004`

1. Treat the structural legal graph baseline as the semantic comparison point.
2. Run full-corpus semantic extraction first on the operator-managed notebook
   contour.
3. Keep managed paid validation bounded by:
   - the fixed `004` validation fixture
   - or an explicitly smaller subset
4. Enforce `LEGAL_MANAGED_SMOKE_LIMIT` for managed runs.
5. Record for every semantic extraction run:
   - runtime contour
   - effective LLM backend
   - effective embedding backend
   - LLM model id
   - embedding model id
   - prompt or extraction-policy version
   - processed/skipped/failed counts
6. Persist proposition candidates as untrusted-by-default.
7. Reject invalid outputs instead of silently coercing them.
8. Flag weakly grounded outputs and keep them out of trusted answer support.
9. Isolate ambiguous or duplicate outputs and keep them auditable.
10. Create review tasks for persisted proposition candidates before any trusted
    promotion.

## Model Semantics

1. Treat embeddings as contract-bound artifacts.
2. Treat LLM outputs as non-deterministic candidate interpretations.
3. For embeddings, require profile consistency:
   - dimension
   - normalization
   - `Query: ` / `Document: `
   - benchmark compatibility
4. For LLM pipelines, do not require identical outputs across runs or models.
5. For LLM-derived knowledge, keep source text and review state as the truth
   boundary, not the raw model output alone.
6. Record effective backend, model id, and prompt or extraction-policy version
   for LLM-backed batch jobs when practical.

## If Something Breaks

1. First suspect a paused Aura instance.
2. Then check whether `llama-server` is down.
3. Then check whether interactive failover is behaving as configured.
4. Then check dimension mismatch.
5. Then check profile mismatch.
6. Then check whether someone accidentally changed prefixes or normalization.

## Canonical References

- [jina_embeddings_playbook.md](/home/admin2/chat_bot/jina_embeddings_playbook.md)
- [neo4j_playbook.md](/home/admin2/chat_bot/neo4j_playbook.md)
- [quickstart.md](/home/admin2/chat_bot/specs/003-bulk-knowledge-enrichment/quickstart.md)
