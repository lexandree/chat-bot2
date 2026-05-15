# Quickstart: Telegram Q/A Evaluation Dataset

## Offline Sample

```bash
conda run -n chbot python -m pytest tests/unit/test_tg_qa_dataset.py tests/smoke/test_cli_offline.py -k "tg_qa or evaluation"
```

## Real Local Export

```bash
PYTHONPATH=src conda run -n chbot python -m app evaluation tg-qa \
  --input data/tg \
  --bot-catalog tmp/tg_wiki_bot_catalog_seed.json \
  --output data/evaluation/tg_qa_candidates/tg_qa_candidates.jsonl \
  --summary-output data/evaluation/tg_qa_dataset/tg_qa_summary.json \
  --embedding-batch-output data/evaluation/tg_qa_embeddings/tg_qa_embedding_batch.jsonl \
  --llm-batch-output data/evaluation/tg_qa_llm_batches/tg_qa_llm_batch.jsonl \
  --max-candidates 500 \
  --candidate-offset 0 \
  --min-attention-score 6
```

Expected result:

- raw Telegram text is not written to tracked source files
- emitted candidate texts are redacted
- wiki bot mentions are retained as weak metadata
- answer candidates are direct replies or trigger-linked wiki-bot replies, not
  trusted legal answers
- trigger messages are kept as `trigger_evidence`, not answer candidates
- answer candidates include link metadata such as `answer_link_type`,
  `link_confidence`, and trigger timing fields when applicable
- known wiki-bot and other bot-like replies are marked with
  `answer_source_type`, `answer_source_markers`, and
  `answer_candidate_priority`
- question and answer texts are emitted separately for optional external
  vectorization
- candidate records include quality tier, cascade route, cluster placeholders,
  and `selection_status`
- answer candidates include `answer_candidate_status` and
  `answer_candidate_usable`
- generated artifacts stay under ignored `data/evaluation/` paths

Use `--candidate-offset` only for repeatable later review rounds. It is applied
after deterministic candidate sorting and before `--max-candidates`, so
`--candidate-offset 50 --max-candidates 50` emits the next non-overlapping
candidate window.

## Local Jina Batch Vectorization

Use the canonical embedding endpoint variable for local or tunneled
Jina-compatible runtimes:

```bash
PYTHONPATH=src EMBEDDING_ENDPOINT_URL=http://127.0.0.1:18080/v1/embeddings \
  conda run -n chbot python -m app evaluation tg-qa-embed-batch \
  --embedding-batch data/evaluation/tg_qa_embeddings/tg_qa_embedding_batch.jsonl \
  --output data/evaluation/tg_qa_embeddings/tg_qa_external_vectors.jsonl \
  --summary-output data/evaluation/tg_qa_embeddings/tg_qa_vectorization_summary.json \
  --model-id jina-q8 \
  --batch-size 16
```

Then import and validate those vectors against the project embedding profile:

```bash
PYTHONPATH=src conda run -n chbot python -m app evaluation tg-qa-embeddings-import \
  --embedding-batch data/evaluation/tg_qa_embeddings/tg_qa_embedding_batch.jsonl \
  --external-vectors data/evaluation/tg_qa_embeddings/tg_qa_external_vectors.jsonl \
  --output data/evaluation/tg_qa_embeddings/tg_qa_embedding_records.jsonl \
  --summary-output data/evaluation/tg_qa_embeddings/tg_qa_embedding_import_summary.json \
  --model-id jina-q8
```

## Processing Policy

006 does not use message date as a global freshness cutoff. The full staged
pipeline is documented in:

- `specs/006-tg-question-answer-evaluation-dataset/pipeline.md`
- `specs/006-tg-question-answer-evaluation-dataset/data-model.md`
- `specs/006-tg-question-answer-evaluation-dataset/contracts/final-dataset.md`

The intended selection policy is:

1. extract redacted Q/A candidates;
2. vectorize question, answer, and optional Q/A-pair text;
3. run similarity search in question, answer, and optional Q/A-pair spaces;
4. cluster questions, answers, and Q/A pairs;
5. sort usable answer variants by date inside each semantic Q/A cluster;
6. select the latest usable answer only when the cluster is stable enough;
7. route medium/uncertain/conflicting clusters to LLM or manual review;
8. build the final dataset only from `auto_selected` and `review_approved`
   records.

Embedding stages must reuse the existing Jina-compatible project contract:
`Query: ` for question items, `Document: ` for answer and Q/A-pair items,
normalized `1024`-dimensional vectors by default, and fixture/fake vectors for
default tests. Live Jina checks remain explicit opt-in validation only.

Initial fixture clustering uses `tg_qa_cluster_policy_v1`: question threshold
`0.82`, answer threshold `0.86`, Q/A-pair threshold `0.84`, top-k `20`, and max
component size `50`. These values are deterministic defaults for tests, not
final quality tuning.

LLM analysis is optional and one-time for this feature. The intended contour is
an operator-managed OpenAI-compatible `llama-server` endpoint exposed through a
temporary tunnel. Use Gemma 4
`gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` first; try
`Qwen3.6-27B-Q6_K.gguf` or `Qwen3.6-27B-Q8_0.gguf` only if Gemma 4 is
insufficient and a Kaggle T4 x2 smoke confirms the model fits. The full
contract is in `contracts/llm-analysis.md`.

For a temporary small-context Gemma endpoint, emit a compact cluster batch and a
full overflow batch:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-cluster-llm-batch \
  --candidates data/evaluation/tg_qa_candidates/real_data_006_bounded_candidates.jsonl \
  --selection data/evaluation/tg_qa_selection/real_data_006_bounded_selection.jsonl \
  --output data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_compact_gemma3k.jsonl \
  --prompt-profile compact \
  --input-char-budget 2500 \
  --overflow-output data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_full_overflow.jsonl
```

For prompt A/B tests against a manually reviewed TSV, pass the TSV as a manual
review overlay. This lets the model see reviewer-corrected question/answer text
without seeing the manual decision label:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-cluster-llm-batch \
  --candidates data/evaluation/tg_qa_candidates/real_data_006_bounded_candidates.jsonl \
  --selection data/evaluation/tg_qa_selection/real_data_006_bounded_selection.jsonl \
  --manual-review-overlay data/evaluation/tg_qa_review/real_data_006_bounded_human_review_kimi_k26.tsv \
  --output data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_v4_overlay_full.jsonl
```

The current v4.1 prompt keeps the v4 approve/reject boundary and adds
calibration-only `issue_spotting_level`, `issue_spotting_confidence`, and
`issue_spotting_reason` fields. Use these fields for analysis, not as automatic
case eligibility rules.

## Manual Review Policy For Multi-Question Messages

Treat one review row as one potential final evaluation case.

- If one Telegram message contains several surface questions but they belong to
  one scenario and require one answer obligation, keep one row and rewrite the
  main evaluable question in `manual_question_text`.
- If one message contains several independently answerable questions, do not
  duplicate TSV rows for the same `qa_cluster_id`. The current 006 builder
  emits at most one final case per cluster.
- Use `split` only as a reviewer outcome/backlog marker. It does not yet create
  multiple final dataset rows automatically.
- If the question is worth keeping but the selected Telegram answer is weak,
  keep one approved row and provide `manual_reference_answer_text` instead of
  trying to split by copying rows.

Run the compact batch through an operator-approved OpenAI-compatible endpoint:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-llm-run \
  --batch data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_compact_gemma3k.jsonl \
  --output data/evaluation/tg_qa_llm_results/real_data_006_bounded_gemma_q6_compact_results.jsonl \
  --summary-output data/evaluation/tg_qa_llm_results/real_data_006_bounded_gemma_q6_compact_summary.json \
  --endpoint-url https://operator-managed-endpoint.example \
  --model-id gemma-4-26B-A4B-it-UD-Q6_K.gguf \
  --llm-run-id tg-qa-llm-run:gemma-q6-compact-YYYYMMDD \
  --max-tokens 384 \
  --model-file gemma-4-26B-A4B-it-UD-Q6_K.gguf \
  --quantization Q6_K
```

Long-running network batch commands print an updating progress line to stderr
and keep the final JSON summary on stdout. Use `--no-progress` when stderr must
remain quiet.

For provider-hosted OpenAI-compatible endpoints, keep provider-specific request
settings explicit in the run command. Kimi K2.6/K2.5 should be run without a
custom temperature. Kimi's official API documents `{"thinking":{"type":"disabled"}}`
as the direct request-body control, but the observed OpenCode route for
`kimi-k2.6` required `{"reasoning":{"enabled":false}}` to avoid slow
reasoning-token output:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-llm-run \
  --batch data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_full_overflow.jsonl \
  --output data/evaluation/tg_qa_llm_results/real_data_006_bounded_kimi_k26_results.jsonl \
  --summary-output data/evaluation/tg_qa_llm_results/real_data_006_bounded_kimi_k26_summary.json \
  --endpoint-url "$OPENCODE_CHAT_COMPLETIONS_URL" \
  --model-id "$OPENCODE_MODEL_ID" \
  --llm-run-id tg-qa-llm-run:opencode-kimi-k2.6-YYYYMMDD \
  --max-tokens 4096 \
  --thinking-type disabled \
  --omit-temperature \
  --extra-body-json '{"reasoning":{"enabled":false}}' \
  --backend opencode \
  --model-file "$OPENCODE_MODEL_ID" \
  --api-key-env OPENCODE_API_KEY
```

The same mechanism can test alternative provider body shapes, such as
`{"thinking":{"type":"disabled"}}`,
`{"options":{"thinking":{"type":"disabled"}}}`, `{"use_thinking":false}`, or
`{"enable_thinking":false}`, without changing the project contract. These
settings are runtime evidence and do not make provider output trusted.

For the free Zen `minimax-m2.5-free` route, the observed working smoke used no
extra provider body. The important settings were omitting temperature and
allowing enough output budget:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-llm-run \
  --batch data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_full_overflow.jsonl \
  --output data/evaluation/tg_qa_llm_results/real_data_006_bounded_minimax_m2.5_free_smoke_results.jsonl \
  --summary-output data/evaluation/tg_qa_llm_results/real_data_006_bounded_minimax_m2.5_free_smoke_summary.json \
  --endpoint-url "$OPENCODE_ZEN_CHAT_COMPLETIONS_URL" \
  --model-id minimax-m2.5-free \
  --llm-run-id tg-qa-llm-run:opencode-zen-minimax-m2.5-free-smoke-YYYYMMDD \
  --max-items 1 \
  --timeout-seconds 120 \
  --max-tokens 2048 \
  --omit-temperature \
  --runtime-contour opencode_zen_openai_compatible_chat_completion \
  --backend opencode-zen \
  --model-file minimax-m2.5-free \
  --api-key-env OPENCODE_API_KEY
```

Do not apply the Kimi `{"reasoning":{"enabled":false}}` workaround to MiniMax
unless a fresh smoke proves it is needed for that route.

Import the results as review evidence:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-llm-import \
  --batch data/evaluation/tg_qa_llm_batches/real_data_006_bounded_cluster_llm_batch_compact_gemma3k.jsonl \
  --results data/evaluation/tg_qa_llm_results/real_data_006_bounded_gemma_q6_compact_results.jsonl \
  --evidence-output data/evaluation/tg_qa_llm_results/real_data_006_bounded_gemma_q6_compact_evidence.jsonl \
  --manifest-output data/evaluation/tg_qa_llm_results/real_data_006_bounded_gemma_q6_compact_manifest.json \
  --llm-run-id tg-qa-llm-run:gemma-q6-compact-YYYYMMDD \
  --runtime-summary data/evaluation/tg_qa_llm_results/real_data_006_bounded_gemma_q6_compact_summary.json
```

Only `auto_selected` and `review_approved` records are eligible for the final
evaluation dataset. `uncertain` is a valid terminal status for dirty chat data.

## Optional Post-Build Coverage Analysis

After the reviewed final dataset exists, you can measure how well it covers the
full Telegram candidate corpus without mutating the dataset itself.

The intended contour is:

1. extract a full-corpus candidate artifact with `tg-qa`;
2. emit a dedicated coverage embedding batch from:
   - reviewed final dataset questions and reference answers;
   - corpus candidate questions and one representative answer per candidate;
   - if the embedding runtime is slow, use `--corpus-filter law_or_topic` or
     `--corpus-filter legalish` together with `--skip-corpus-answers` for a
     practical question-side first pass;
3. vectorize that batch with the same local Jina-compatible embedding runtime;
4. import coverage embedding records;
5. build a coverage report that measures:
   - question-side nearest dataset match for every corpus candidate;
   - answer-side support only as diagnostics;
   - corpus coverage bands such as `covered`, `partial`, and `uncovered`.

This is a separate evaluation-analysis artifact. It does not create new final
cases and does not promote corpus candidates into the reviewed dataset.
