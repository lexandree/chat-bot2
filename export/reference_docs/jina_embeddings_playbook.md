# Jina Embeddings Playbook

## Purpose

This file captures the working decisions, tested settings, and operational rules
for Jina retrieval embeddings so they can be reused in a similar project without
re-discovering the same constraints.

## Final Decisions

- Use Jina v5 retrieval embeddings.
- Use the retrieval-specific model, not a generic text embedding model.
- Keep the retrieval contract stable:
  - `Query: ` for user queries
  - `Document: ` for indexed text
- Keep vectors normalized.
- Keep one embedding dimensionality per active index.
- Current validated dimensionality: `1024`
- Allowed local quantization variants:
  - `Q8`
  - `F16`
- Forbidden local variant:
  - `XXS`

## What Was Tested

The detailed comparison artifacts were archived after the final conclusions were
consolidated into this playbook. Keep this file as the canonical summary rather
than depending on raw experiment folders in the project root.

Observed conclusions:

- `Q8` and `F16` are both retrieval-compatible with hosted Jina API on the tested set.
- `Q8` is the preferred local default because it preserved retrieval quality while
  being much faster than `F16`.
- `XXS` is not acceptable for this project. Even when top-1 stayed intact on the
  tiny test set, vector agreement degraded too much.

## Benchmark Results That Matter

From the recorded comparisons:

- `Q8`
  - top-1 agreement with API: `1.0000`
  - average same-text cosine: about `0.9945`
  - score-matrix Pearson: about `0.9997`
- `F16`
  - top-1 agreement with API: `1.0000`
  - average same-text cosine: about `0.9947`
  - score-matrix Pearson: about `0.9996`
- `XXS`
  - average same-text cosine: about `0.7560`
  - score-matrix Pearson: about `0.9849`

Operational interpretation:

- `Q8` is the main local runtime.
- `F16` is a fallback comparison mode, not the default.
- `XXS` must stay disabled.
- hosted Jina and approved local Jina runtimes can be treated as practically
  equivalent only when they preserve the same retrieval contract and continue to
  pass benchmark checks

## Deployment Model

- Daytime / online small-batch embeddings: hosted Jina API
- Nightly / bulk reindex: local `llama-server` on GPU
- CPU or free-tier VM is not a valid primary embedding backend

Current application routing policy:

- user-facing query embeddings: prefer local `llama-server`, fail over to hosted
  Jina API when local is unavailable, then switch new requests back to local
  after confirmed recovery
- graph writes: local-only for ingestion, seed loading, and reindex

For `003` bulk knowledge enrichment:

- the first iterative operator workflow uses the same local Jina-compatible
  embedding path as the operator-managed contour
- hosted Jina remains a compatible managed alternative, not the required first
  debugging path
- Colab-style and Kaggle-style LLM runtimes do not change the embedding
  contract; only the effective run metadata changes

For `004` legal proposition extraction:

- keep the same graph-write embedding contract from `003`
- operator-managed notebook and managed paid contours must preserve the same
  `Document: ` embedding semantics for legal fragments
- contour changes are metadata changes, not embedding-profile changes
- managed smoke runs must stay bounded; do not spend paid tokens on full-corpus
  legal extraction until the notebook contour and proposition contract are
  already stable

Practical rule:

- Do not plan a production embedding pipeline around CPU inference for Jina GGUF.
- CPU can still host orchestration, graph DB, or glue code.

## Equivalence Policy

Embeddings are not treated like free-form LLM generations.

For this project, approved embedding backends may be swapped only when they are
demonstrably compatible with the active retrieval contract:

- same `Query: ` / `Document: ` semantics
- same dimension
- same normalization mode
- acceptable retrieval agreement on the benchmark fixture

If those conditions hold, backend choice is an operational concern rather than a
knowledge-validity concern. If they do not hold, the backend is a different
embedding profile and must be treated as incompatible until revalidated and
reindexed.

## Local Llama-Server Contract

Required runtime properties:

- embeddings mode only
- pooling: `last`
- retrieval-specific GGUF weights
- one active request stream or an external queue
- stable output dimensionality `1024`
- normalized vectors in the client contract

Validated local server endpoint shape:

- base URL: `http://127.0.0.1:18080`
- embeddings endpoint: `http://127.0.0.1:18080/v1/embeddings`

Current dev-environment note:

- do not start `llama-server` on this dev machine
- the runtime is hosted on another machine and forwarded here through reverse
  SSH to `127.0.0.1:18080`

For operator-managed Colab or Kaggle runs that still need the same home-GPU
embedding runtime, use a relay host instead of trying to reach the home machine
directly from the notebook:

1. On the home GPU host, keep `llama-server` bound to `127.0.0.1:18080`.
2. From the home GPU host, open a reverse tunnel to a reachable relay host.
3. Inside the Colab or Kaggle notebook, open a local forward to that relay.
4. Inside the notebook, keep `LLAMA_SERVER_URL=http://127.0.0.1:18080/v1/embeddings`.

That preserves the existing local-only client contract while making the home
runtime reachable from the operator-managed notebook environment.

Validated model alias example:

- `jina-q8`

## Recommended Launch Command

Validated local profile on the dev machine:

```bash
/home/admin3/roentgen-for-docs/llama_cpp_matrix/build_build_cu124/bin/llama-server \
  -m models/v5-small-retrieval-Q8_0.gguf \
  --alias jina-q8 \
  --embedding \
  --pooling last \
  --host 127.0.0.1 \
  --port 18080 \
  --n-gpu-layers all \
  --threads 6 \
  --threads-batch 6 \
  --ctx-size 8192 \
  --batch-size 4096 \
  --ubatch-size 4096 \
  --parallel 1 \
  --no-warmup
```

Notes:

- `ctx-size 8192` is sufficient for this embedding use case.
- `parallel 1` is intentional.
- If memory becomes tight, reduce `batch-size` and `ubatch-size` before touching
  `ctx-size`.

Observed VRAM usage on the validated profile:

- about `4420 / 6144 MB`

## Parameters That Actually Matter

High priority:

- model variant: `Q8`
- `Query: ` / `Document: ` prefixes
- dimension `1024`
- normalized output
- `pooling last`
- embedding-only runtime
- batch size
- no uncontrolled parallel request fan-out

Lower priority:

- increasing context above `8192`
- aggressive experimentation with lower quantization

## API Contract

### Hosted Jina API

Expected behavior:

- endpoint: `https://api.jina.ai/v1/embeddings`
- retrieval semantics:
  - `task = retrieval.query`
  - `task = retrieval.passage`
- normalized float embeddings

### Local Llama-Server

Expected behavior:

- endpoint: `/v1/embeddings`
- input already includes `Query: ` or `Document: `
- local endpoint does not add retrieval semantics automatically, so the caller
  must keep the contract stable

## Example Requests

### Query embedding

```bash
curl -s http://127.0.0.1:18080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "jina-q8",
    "input": ["Query: Какие документы нужны для Jobcenter?"]
  }'
```

### Document embedding

```bash
curl -s http://127.0.0.1:18080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "jina-q8",
    "input": ["Document: Для подачи в Jobcenter обычно нужны удостоверение личности и документы по жилью."]
  }'
```

## Operational Rules

- Never silently fall back from Jina API or local `Q8` to `XXS`.
- Never mix vectors from incompatible dimensions in one active index.
- Never mix incompatible normalization modes in one active index.
- Never mix `Query: ` and `Document: ` semantics incorrectly.
- If local `llama-server` is not running, say so explicitly and stop.
- For interactive traffic, failover between local and hosted backends must be
  policy-driven and observable.
- For graph writes, do not use hosted API as fallback.
- For `003` validation, preserve one embedding contract across baseline and
  enriched runs even when the LLM contour changes.

## Benchmarking Method

Use the small multilingual retrieval fixture already added to the repository:

- [embedding_benchmark_cases.json](/home/admin2/chat_bot/tests/fixtures/embedding_benchmark_cases.json)
- [benchmark runner](/home/admin2/chat_bot/src/evaluation/run_embedding_benchmark.py)
- [benchmark notes](/home/admin2/chat_bot/specs/001-graph-chatbot-mvp/embedding_benchmarking.md)

Run:

```bash
/usr/bin/time -v env PYTHONPATH=src python -m evaluation.run_embedding_benchmark \
  --fixture tests/fixtures/embedding_benchmark_cases.json \
  --top-k 3 \
  --output-json /tmp/jina-benchmark.json
```

Track:

- top-1 accuracy
- top-3 accuracy
- cross-language top-3 accuracy
- average query latency
- peak RSS

## Safe Defaults For A New Project

- online mode: hosted Jina API
- local bulk mode: Jina retrieval `Q8`
- dimension: `1024`
- normalized: `true`
- local pooling: `last`
- prefixes:
  - `Query: `
  - `Document: `
- local parallel requests: `1`

## Things To Ask Before Work Starts

- Is the local `llama-server` running right now?
- What is the model alias?
- Which mode is intended:
  - hosted API
  - local GPU bulk
- Is the target index already populated with a different embedding profile?
