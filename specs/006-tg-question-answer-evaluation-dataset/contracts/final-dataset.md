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
  "original_question_text_redacted": "...",
  "question_text_source": "selected_telegram_question",
  "selected_answer_text_redacted": "...",
  "reference_answer_text_redacted": "...",
  "original_selected_answer_text_redacted": "...",
  "selected_candidate_id": "tg-qa-candidate:...",
  "selected_answer_candidate_id": "tg-answer-candidate:...",
  "reference_answer_candidate_id": "tg-answer-candidate:...",
  "reference_answer_source": "selected_telegram_answer",
  "reference_answer_action": "keep_selected",
  "reference_answer_role": "community_answer_for_graph_db_comparison_not_legal_truth",
  "reference_answer_status": "auto_selected",
  "question_intent": "legal_information_request",
  "legal_answer_requirement": "requires_legal_rule_or_status_analysis",
  "graph_db_evaluation_fit": "legal_core",
  "issue_spotting_required": false,
  "issue_spotting_level": "none",
  "issue_spotting_confidence": "high",
  "issue_spotting_reason": "",
  "hidden_legal_issue_categories": [],
  "answer_must_expand_beyond_user_wording": false,
  "exclusion_reason": "none",
  "manual_reference_answer_redaction_flags": [],
  "manual_question_redaction_flags": [],
  "question_inclusion_status": "auto_selected",
  "answer_source_type": "human_reply",
  "answer_link_type": "direct_reply_to_question",
  "selected_telegram_answer_source_type": "human_reply",
  "selected_telegram_answer_link_type": "direct_reply_to_question",
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

For manually repaired cases, `reference_answer_source` must be
`manual_review_override`, `reference_answer_action` must be `replace_manual`,
and `reference_answer_text_redacted` must contain the reviewer-supplied redacted
answer. The original selected Telegram answer must remain in
`original_selected_answer_text_redacted` for provenance and later audit.

If a reviewer supplies `manual_question_text`, the final case must use that
redacted text for both `normalized_question` and `question_text_redacted`, set
`question_text_source` to `manual_review_override`, and preserve the originally
selected Telegram fragment in `original_question_text_redacted`.
Current 006 final-dataset build emits at most one final case per
`qa_cluster_id`. Duplicating review-sheet rows for one cluster is invalid and
must not be used to emulate a split into several cases.

Legal-evaluation fields measure whether the case is suitable for graph-backed
evaluation. They must generalize beyond keywords: `issue_spotting_required`
captures cases where the user's surface question is practical but a correct
answer must identify hidden legal risks, duties, status conditions, or reporting
obligations. It must not be used as a blanket marker for all legal questions.
`hidden_legal_issue_categories` must stay broad and bounded so quality metrics
remain comparable across prompt iterations.
`issue_spotting_level`, `issue_spotting_confidence`, and
`issue_spotting_reason` are calibration evidence and must not alter final case
eligibility by themselves.

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
- reference answer counts by source, action, and status;
- legal-evaluation counts by graph fit, answer requirement, question intent,
  hidden legal issue category, issue-spotting requirement, issue-spotting
  level, and issue-spotting confidence;
- drift/conflict counts;
- known limitations and unresolved backlog counts.
