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
- generated artifacts stay under ignored `data/evaluation/` paths

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

Only `auto_selected` and `review_approved` records are eligible for the final
evaluation dataset. `uncertain` is a valid terminal status for dirty chat data.
