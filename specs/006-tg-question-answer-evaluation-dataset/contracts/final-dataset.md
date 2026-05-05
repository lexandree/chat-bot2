# Contract: Final Telegram Q/A Evaluation Dataset

## Boundary

The final dataset is an evaluation artifact. It is not a legal authority, not a
trusted answer source, and not graph state. It may be used to measure retrieval,
coverage, answer generation, and review workflows later.

## Eligible Inputs

Final cases may come only from:

- `auto_selected` stable cluster selections; or
- `review_approved` manual review decisions.

LLM output alone cannot create a final case.

## JSONL Record Shape

Each line in `*_final_cases.jsonl` must contain:

```json
{
  "case_id": "tg-eval-case:...",
  "qa_cluster_id": "tg-qa-cluster:...",
  "status": "auto_selected",
  "normalized_question": "...",
  "question_text_redacted": "...",
  "selected_answer_text_redacted": "...",
  "selected_candidate_id": "tg-qa-candidate:...",
  "selected_answer_candidate_id": "tg-answer-candidate:...",
  "answer_source_type": "human_reply",
  "answer_link_type": "direct_reply_to_question",
  "topic_labels": ["migration_status"],
  "law_code_candidates": ["AufenthG"],
  "answer_drift_status": "stable",
  "historical_answer_variant_count": 0,
  "review_status": "auto_selected",
  "provenance": {
    "export_id": "...",
    "question_message_id": "...",
    "answer_message_id": "...",
    "trigger_message_id": "",
    "source_candidate_artifact": "...",
    "source_cluster_artifact": "..."
  }
}
```

## Exclusions

The final dataset must not contain:

- raw unredacted Telegram text;
- emails, phone numbers, URLs, or usernames unless redacted;
- `.env` values, secrets, or local credentials;
- graph mutation commands;
- LLM-only approvals;
- rejected or uncertain cases.

## Manifest Requirements

The dataset manifest must include:

- source artifact paths;
- run ids for extraction, embedding, similarity, clustering, LLM, and review
  stages when present;
- case counts by status, topic, law candidate, answer source, and link type;
- drift/conflict counts;
- known limitations and unresolved backlog counts.
