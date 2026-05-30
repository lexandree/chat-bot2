# Contract: Question Bank Review And Evaluation Promotion

## Boundary

Review in 007 decides whether a canonical legal issue cluster belongs in the
question bank or should be promoted into a reviewed evaluation dataset. It does
not approve Telegram answers as legal truth and does not make LLM-generated
content trusted legal support.

## Cluster Review Decision Shape

Each review decision must include:

```json
{
  "cluster_review_decision_id": "tg-legal-issue-review:...",
  "legal_issue_cluster_id": "tg-legal-issue-cluster:...",
  "decision": "approve_question_bank",
  "decision_scope": "legal_issue_cluster_review",
  "reviewed_canonical_question": "...",
  "reviewed_legal_issue_frame_slug": "residence_document_address_update_with_expired_or_extended_permit",
  "reference_answer_action": "none",
  "reference_answer_source": "none",
  "manual_reference_answer_text_redacted": "",
  "reviewer_hash": "reviewer:...",
  "reviewed_at": "2026-05-15T00:00:00Z",
  "decision_reason": "repeated issue cluster without reviewed reference answer yet"
}
```

Allowed `decision` values:

- `approve_question_bank`
- `approve_final_evaluation`
- `reject`
- `merge`
- `split`
- `needs_more_context`
- `uncertain`

Allowed `reference_answer_action` values:

- `none`
- `keep_selected_telegram_answer`
- `replace_manual`
- `needs_manual_answer`

## Question Bank Entry Shape

Each question-bank JSONL record must include:

```json
{
  "question_bank_entry_id": "tg-question-bank-entry:...",
  "legal_issue_cluster_id": "tg-legal-issue-cluster:...",
  "canonical_question": "...",
  "legal_issue_frame_slug": "residence_document_address_update_with_expired_or_extended_permit",
  "law_area": "migration_status",
  "authority_context": ["Buergeramt", "Auslaenderbehoerde"],
  "representative_raw_questions": [],
  "coverage_status": "uncovered",
  "review_status": "approved_question_bank",
  "reference_answer_status": "missing_reference_answer",
  "provenance": {
    "source_cluster_artifact": "data/evaluation/..."
  }
}
```

Question-bank entries may exist without final reference answer material.

## Question Bank Summary And Manifest Requirements

The question-bank build command must write:

- question-bank JSONL
- question-bank summary JSON
- question-bank manifest JSON

The summary JSON must include:

- source issue cluster artifact path
- source review decision artifact path
- processed cluster count
- completed entry count
- excluded count
- failed decision count
- approved entry count
- rejected entry count
- needs-more-context count
- uncertain count
- missing reference answer count
- counts by law area
- counts by authority context
- counts by coverage status
- counts by reference answer status
- review policy version
- question-bank policy version
- runtime contour
- generated timestamp

The manifest JSON must include:

- input artifact paths
- output artifact paths
- review policy version
- question-bank policy version
- known limitations
- unresolved backlog counts

## Evaluation Promotion Shape

Each promoted case candidate must include:

```json
{
  "case_candidate_id": "tg-eval-case-candidate:...",
  "legal_issue_cluster_id": "tg-legal-issue-cluster:...",
  "source_006_case_id": "tg-eval-case:...",
  "canonical_question": "...",
  "question_text_redacted": "...",
  "reference_answer_text_redacted": "...",
  "reference_answer_source": "manual_review_override",
  "reference_answer_role": "community_answer_for_graph_db_comparison_not_legal_truth",
  "review_status": "approved_final_evaluation",
  "promotion_status": "eligible",
  "provenance": {
    "source_review_decision_artifact": "data/evaluation/..."
  }
}
```

Allowed `promotion_status` values:

- `eligible`
- `blocked_missing_reference_answer`
- `rejected`

## Final Case Candidate Summary And Manifest Requirements

The final case candidate promotion command must write:

- final case candidate JSONL
- final case candidate summary JSON
- final case candidate manifest JSON

The summary JSON must include:

- source question-bank artifact path
- source review decision artifact path
- processed question-bank entry count
- completed candidate count
- excluded count
- uncertain count
- failed count
- emitted candidate count
- eligible count
- blocked missing reference answer count
- rejected count
- LLM-only rejection count
- manual reference answer count
- accepted Telegram reference answer count
- counts by law area
- counts by authority context
- promotion policy version
- reference answer policy version
- runtime contour
- generated timestamp

The manifest JSON must include:

- input artifact paths
- output artifact paths
- promotion policy version
- reference answer policy version
- known limitations
- unresolved backlog counts

## Reviewed Dataset Export

The reviewed evaluation dataset is a separate export built after promotion.
`ReviewedEvaluationCaseCandidate` records are not themselves the final dataset.

The export must:

- include only `promotion_status=eligible` records;
- reject or count duplicate `case_candidate_id` and `legal_issue_cluster_id`
  collisions;
- preserve canonical issue cluster provenance;
- write reviewed final cases JSONL, manifest JSON, and quality summary JSON;
- count excluded `blocked_missing_reference_answer`, `rejected`, and LLM-only
  records in the quality summary;
- preserve that reference answers are evaluation material only.

## Promotion Rules

- `approve_question_bank` creates or updates a question-bank entry only.
- `approve_final_evaluation` requires a reviewed reference answer source.
- `keep_selected_telegram_answer` is allowed only when the selected Telegram
  reference answer was explicitly accepted for evaluation.
- `replace_manual` requires redacted manual reference answer text.
- `needs_manual_answer` blocks final evaluation promotion.
- LLM canonicalization evidence alone cannot set `promotion_status=eligible`.
- Telegram reference answers remain evaluation material, not legal authority.
