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
  --llm-batch-output data/evaluation/tg_qa_llm_batches/tg_qa_llm_batch.jsonl \
  --max-candidates 500 \
  --min-attention-score 6
```

Expected result:

- raw Telegram text is not written to tracked source files
- emitted candidate texts are redacted
- wiki bot mentions are retained as weak metadata
- answer candidates are direct replies, not trusted legal answers
- generated artifacts stay under ignored `data/evaluation/` paths
