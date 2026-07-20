# Manual Review Notes

This file records operator review conventions discovered during 007. It is a
human workflow note, not a prompt profile and not trusted legal content.

Do not copy raw Telegram corpus text into this tracked file. Use task ids and
generalized summaries.

## Decision Semantics

- `accept`: The record/candidate is good enough for the current 007 dataset
  purpose. It does not mean a future chatbot can answer without clarification.
- `reject`: The record should not enter the legal canonical question dataset in
  its current form, usually because it is non-legal, lacks standalone context,
  is stale/live operational only, or belongs outside the project scope.
- `retry_generator`: The record is worth keeping, but the current canonical
  candidate should be regenerated with review feedback.
- `send_deepseek` or other escalation routes are review-evidence routes, not
  approval.

When a review UI exports only changed decisions, unchanged cards remain governed
by the pipeline default for that review stage. Do not infer a manual decision
from absence unless the specific import step documents such a default.

## MRN-001: Accepted Can Still Require Future Clarification

Evidence:

- `tg-question-canonicalization-task:095e4b46476f1ae97e13`

Review convention: A question can be accepted for the canonical dataset even
when a real answer would require a clarification. Current 007 is not answering
the person. It records a reusable legal-question artifact. Future inference
must decide whether to answer directly or ask a clarifying question.

Example pattern: ambiguous `Asyl` versus section 24 temporary protection in a
Ukrainian refugee context. The dataset can retain the legal issue, while future
answer planning must ask which legal route the user means.

## MRN-002: Unknown Context Means Reject Or Hold, Not Creative Recovery

Evidence:

- `tg-question-canonicalization-task:4990253d308d11c99ae4`
- `tg-question-canonicalization-task:3bacf1d9153a8cccbe3b`
- `tg-question-canonicalization-task:dab3fe5d290e113d837e`
- `tg-question-canonicalization-task:046f1d13a8085b0e08a3`

Review convention: If the source depends on missing dialogue, unclear pronouns,
or unknown context, do not infer a hidden legal question for dataset purposes.
Reject or hold unless the source contains a standalone legal request.

## MRN-003: Wrong Accept Often Means Exclusion Should Have Won

Evidence:

- `tg-question-canonicalization-task:9aaf29ea3faa7c5e35ae`
- `tg-question-canonicalization-task:9cbb9682eed04fea7bb7`
- `tg-question-canonicalization-task:b448e2852227903a3ea3`
- `tg-question-canonicalization-task:b66a3211941e9dcd7116`
- `tg-question-canonicalization-task:d896fbbe808a22dc0510`

Review convention: Several random accepted samples were manually marked as
wrong accepts because they should have remained `non_legal_question`. The
operator should not spend time repairing a canonical question when the real
issue is that no legal question should have been included.

## MRN-004: Manual Reason May Contain Retry Context

Evidence:

- `tg-question-canonicalization-task:a4c7963852779cb306db`
- `tg-question-canonicalization-task:9128be47d294c4c1f450`
- `tg-question-canonicalization-task:a763836dd3425c7b2c56`

Review convention: If the manual reason explains a hidden legal frame, pass it
to retry as corrective context. It can be more valuable than the verifier's
short reason because it may contain domain knowledge unavailable from the source
text alone.

Do not convert every manual note into a prompt rule. First decide whether the
lesson is:

- a one-off correction for that record;
- a prompt lesson for recurring canonicalizer errors;
- a future inference/retrieval behavior;
- an operator review convention.

## MRN-005: Harvest Manual Reasons Into The Right Memory File

Review convention: Manual reasons are not just local explanations for one
export. During cleanup or after a dense review session, skim non-empty manual
reasons and move durable lessons into the correct tracked memory file:

- future answer-planning or retrieval ambiguity:
  `future-inference-questions.md`;
- recurring canonicalizer, verifier, or judge behavior:
  `prompt-lessons.md`;
- human review semantics and operator workflow:
  `manual-review-notes.md`.

Keep raw corpus text out of tracked notes. Use task ids plus generalized
summaries.

## MRN-007: Dataset Acceptance Does Not Mean Current Retrieval Eligibility

Review convention: A historically meaningful legal question may remain accepted
as canonicalization evidence while being unsuitable for the current-default
question bank or retrieval path. Do not reject useful historical evidence
solely because it is old, and do not promote it as current solely because its
canonicalization is coherent.

Route questions involving transitional rules, temporary extensions, expired
deadlines, or superseded procedures to temporal-currentness review. Preserve
the source question date and distinguish current reuse from historical
evaluation.

## MRN-008: Review Cards Must Show The Source Question Date

Evidence:

- `tg-question-canonicalization-task:700115861f464091317b`
- `real_data_007_fresh_qualification_50_v1`

Review convention: Display `question_date` beside the candidate identity in
every canonicalization review card. Do not require the operator to infer it
from legal history or confuse it with the review/export date.

The first fresh 50-record qualification review was operationally light: the
operator needed external research only a few times. This is evidence that the
contour is useful as review support, not evidence that its outputs can bypass
manual acceptance. One rejection in that run cited a missing question date even
though the batch contained it; retain the decision as supplied, but exclude it
from model-error conclusions unless it is reviewed again with the date visible.
