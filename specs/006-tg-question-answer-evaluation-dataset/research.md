# Research: Telegram Q/A Evaluation Dataset

## Decision: Keep 006 As An Evaluation Dataset Feature

**Rationale**: The immediate system need is a measurable question/answer dataset
for retrieval and later answer workflows. Telegram chat data is noisy,
historical, and partially bot-mediated, so it should become evaluation evidence
rather than trusted legal knowledge. This keeps the foundation focused on
measurable retrieval behavior without adding chatbot inference.

**Alternatives considered**:

- Graph enrichment from Telegram answers: rejected because Telegram answers are
  not authoritative legal sources.
- Immediate answer-generation baseline: rejected because there is not yet a
  measured evaluation dataset or retrieval baseline for those questions.

## Decision: Use A Staged Quality Cascade

**Rationale**: Clean cases should exit early, while ambiguous cases need more
evidence. The cascade separates deterministic extraction, embedding/similarity
evidence, cluster selection, optional LLM review, manual review, and final
dataset build. This avoids all-or-nothing processing and keeps uncertainty
visible.

**Alternatives considered**:

- Single-pass LLM extraction: rejected because it would hide deterministic
  evidence and make quality hard to measure.
- Date-only filtering: rejected because older and newer answers must be compared
  inside semantic clusters, not globally discarded.

## Decision: Cluster Questions And Answers, Then Select By Date Inside Q/A Clusters

**Rationale**: Telegram questions can be short, indirect, or trigger-only, while
answers often contain more stable procedural semantics. Clustering both question
and answer spaces, plus optional Q/A-pair space, lets the pipeline identify
answer drift and choose the latest usable answer only among semantically similar
cases.

**Alternatives considered**:

- Question-only clustering: rejected because short keywords and admin-triggered
  bot calls do not reliably represent the user need.
- Answer-only clustering: rejected because similar answer templates may apply
  to distinct user intents.
- Global newest-answer policy: rejected because it can overwrite unrelated
  topics with merely recent content.

## Decision: Reuse The Existing Jina Embedding Contract

**Rationale**: The project already has a validated asymmetric embedding contract
for Jina-compatible retrieval: `Query: ` for user/search text and `Document: `
for indexed/source text, default 1024 dimensions, normalized vectors, and
fixture/fake vectors in default tests. 006 should not create a parallel
embedding profile.

**Alternatives considered**:

- Separate Telegram embedding profile: rejected because it would complicate
  later retrieval comparisons without a proven need.
- Live embedding calls in unit tests: rejected by the constitution and by the
  need for repeatable local tests.

## Decision: Treat Known Wiki-Bot Answers As Marked Evidence

**Rationale**: Known Telegram wiki bots are high-value sources of community FAQ
answers, but they are not legal authorities. Their messages should be marked
with `known_wiki_bot` metadata and prioritized for review, while other bot-like
messages remain low-priority evidence instead of being silently deleted.

**Alternatives considered**:

- Trust known bot answers automatically: rejected because bot content can be old
  or administratively simplified.
- Drop all bot replies: rejected because many relevant answers are delivered by
  bots after admin-triggered keyword calls.

## Decision: Link Admin-Triggered Bot Answers

**Rationale**: In the observed exports, admins often answer a user question by
sending a short trigger message that causes a wiki bot to reply. The pipeline
must preserve `question -> trigger -> bot answer` evidence and distinguish it
from direct replies.

**Alternatives considered**:

- Only direct Telegram replies: rejected because it misses a common answer
  pattern in the data.
- Unbounded nearby-message matching: rejected because it would create noisy
  links in active group chats.

## Decision: Use Optional One-Time LLM Analysis As Review Evidence

**Rationale**: The LLM role in 006 is mostly classification and review support:
is this a real user question, is it on-topic, does the answer candidate look
usable, is there conflict or drift, and what should be reviewed manually. This
is suitable for cheap/free operator-managed batch processing and does not need
to become a production runtime dependency.

**Alternatives considered**:

- Production LLM service dependency: rejected because 006 should be runnable
  and testable without live LLM services.
- No LLM path at all: rejected because medium/conflicting clusters can be too
  expensive to triage manually at corpus scale.

## Decision: Prefer Operator-Managed `llama-server` For LLM Batch Work

**Rationale**: The project already has notebook and Kaggle runtime references
for `llama-server`, artifact separation, runtime manifests, and temporary tunnel
access. Gemma 4 is the first no-paid-token candidate for 006 classification.
Qwen 27B GGUF variants are fallback candidates only after operator smoke testing
on the target Kaggle T4 x2 memory contour.

**Alternatives considered**:

- Paid API by default: rejected because the task is one-time classification and
  cost control matters.
- Embedding runtime reuse for chat completion: rejected because Jina embeddings
  and LLM classification are different runtime contracts.
- Committing tunnel/model configuration: rejected because tunnel URLs,
  credentials, model files, and runtime binaries are operational artifacts.

## Decision: Keep LangChain/LangGraph Optional

**Rationale**: LangChain or LangGraph may help with batch orchestration,
retries, and structured-output parsing, but the default implementation can emit
JSONL batches and import JSONL results without making those frameworks required.
This keeps the core test path small and deterministic.

**Alternatives considered**:

- Require LangChain/LangGraph for 006: rejected because the current feature is
  an artifact pipeline, not a long-lived agent workflow.
- Forbid framework use entirely: rejected because wrapper tooling may be useful
  for external batch execution when it does not alter project contracts.

## Decision: Generated Artifacts Stay Ignored

**Rationale**: Raw Telegram exports, candidate records, vectors, LLM results,
review decisions, and final datasets can contain private or sensitive text even
after redaction. They must remain local/generated artifacts unless a sanitized
publication path is explicitly created later.

**Alternatives considered**:

- Commit sample real-data outputs: rejected because privacy risk is higher than
  the value of tracking volatile artifacts.
- Store all review evidence in Neo4j: rejected for 006 because the feature is an
  evaluation dataset builder and should not mutate graph state.
