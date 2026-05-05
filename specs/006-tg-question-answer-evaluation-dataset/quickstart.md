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
- answer candidates are direct replies, not trusted legal answers
- known wiki-bot authored replies are marked in
  `marked_known_bot_answer_candidates`
- other bot-like replies are counted but not treated as useful wiki-bot answers
- question and answer texts are emitted separately for optional external
  vectorization
- candidate records include quality tier, cascade route, cluster placeholders,
  and `selection_status`
- generated artifacts stay under ignored `data/evaluation/` paths

## Processing Policy

006 does not use message date as a global freshness cutoff. The intended
selection policy is:

1. extract redacted Q/A candidates;
2. vectorize both question and answer text;
3. cluster questions, answers, and Q/A pairs;
4. sort usable answer variants by date inside each semantic Q/A cluster;
5. select the latest usable answer only when the cluster is stable enough;
6. route medium/uncertain/conflicting clusters to LLM or manual review.

Only `auto_selected` and `review_approved` records are eligible for the final
evaluation dataset. `uncertain` is a valid terminal status for dirty chat data.
