# Notebook Embedding Relay Fallback

## Purpose

This topology is a fallback for notebook-driven jobs that must create
embeddings from inside the notebook runtime.

It is not the default embedding architecture for the main project.

## Default Contours

### Local/dev embeddings

The main project treats embeddings as coming from a logical local endpoint:

```text
LLAMA_SERVER_URL=http://127.0.0.1:18080/v1/embeddings
```

The endpoint may be a local process or a tunnel already exposed on the
development machine. Project code should not depend on the physical source.

The graph-write embedding contract is the important boundary:

- OpenAI-compatible `/v1/embeddings` endpoint
- validated Jina retrieval model family
- normalized 1024-dimensional vectors
- `Query: ` prefix for query embeddings
- `Document: ` prefix for document embeddings
- stable embedding profile metadata

### Hosted Jina API

Hosted Jina API is a first-class managed contour, not a relay and not merely a
fallback. It can become the main commercial contour when the effective
embedding profile remains compatible with the validated local runtime.

Local Jina and hosted Jina are contract-equivalent when they preserve:

- the same retrieval model family
- the same `Query: ` / `Document: ` semantics
- the same dimensionality
- normalization
- compatible embedding profile identity and metadata

When the backend changes, graph writes must record effective backend metadata.
If the embedding profile is preserved, the graph embedding semantics remain the
same.

### Preferred operator-managed LLM contour

Kaggle, Colab, or another notebook runtime should normally run only the LLM
runtime, such as `vLLM` or `llama-server`, and expose a temporary LLM endpoint
through `trycloudflare`, Cloudflare Tunnel, or an equivalent tunnel.

The main project calls that temporary LLM endpoint. Neo4j, Jina embeddings,
ingestion, checkpoints, validation, and review remain in the main project.

Tunnel URLs are temporary operational parameters. They are not project
artifacts.

## Fallback Notebook Embedding Relay

Use an Oracle relay or similar reverse tunnel only when the notebook itself
must call a private/home Jina embedding runtime.

```text
notebook runtime
  local embedding client
      |
      | temporary notebook-accessible URL or forward
      v
relay host
  127.0.0.1:<relay_port>
      ^
      | reverse SSH tunnel
      |
private GPU host
  llama-server bound to 127.0.0.1:18080
```

This fallback must not move project state into the notebook. The notebook can
consume inputs and export artifacts, but durable state stays in the main
project.

## Command Pattern

Use placeholders and fill them from private `.env`, SSH config, or operator
notes.

### 1. On the private GPU host

Start `llama-server` bound to loopback:

```bash
llama-server \
  -m /path/to/jina-embeddings-v5-text-small-retrieval-Q8_0.gguf \
  --alias jina-q8 \
  --embedding \
  --pooling last \
  --host 127.0.0.1 \
  --port 18080
```

### 2. From the private GPU host to the relay

Open the reverse tunnel:

```bash
ssh -N -T \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 127.0.0.1:<relay_port>:127.0.0.1:18080 \
  <relay_user>@<relay_host>
```

### 3. From the notebook runtime or dev machine

Open the local forward only for the current operator run:

```bash
ssh -N -T \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:18080:127.0.0.1:<relay_port> \
  <relay_user>@<relay_host>
```

After this, the caller can use:

```bash
LLAMA_SERVER_URL=http://127.0.0.1:18080/v1/embeddings
```

## Health Checks

On the private GPU host:

```bash
curl -s http://127.0.0.1:18080/health
```

On the relay:

```bash
curl -s http://127.0.0.1:<relay_port>/health
```

On the caller:

```bash
curl -s http://127.0.0.1:18080/health
```

## Principle

Notebook, Colab, and Kaggle runtimes are disposable compute.

The main project owns Neo4j, embeddings, ingestion, validation, review, and
checkpoints.
