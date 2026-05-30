# Contract: Question Canonicalization Evidence

## Boundary

Canonicalization output is review evidence. It is not a legal authority, not a
trusted answer source, not graph state, and not chatbot inference.

LLM output may propose canonical questions, legal issue frames, fact hints,
authority context, hidden issue hints, exclusions, confidence, and clustering
signals. It must not create trusted legal answers or final evaluation cases by
itself.

## Input Batch Shape

Each JSONL item in a canonicalization batch must include:

```json
{
  "task_id": "tg-question-canonicalization-task:...",
  "task_scope": "question_candidate",
  "candidate_id": "tg-qa-candidate:...",
  "canonicalization_contract_version": "tg_question_canonicalization_v1",
  "prompt_version": "tg_question_canonicalizer_v1",
  "prompt_example_set_id": "tg_question_canonicalizer_examples_v1",
  "runtime_hint": "operator_managed_llm_or_deterministic_fixture",
  "input": {
    "question_text_redacted": "...",
    "topic_labels": ["migration_status"],
    "law_code_candidates": ["AufenthG"],
    "question_date": "2026-01-01T00:00:00",
    "answer_candidate_status": "partial",
    "quality_flags": [],
    "source_candidate_artifact": "data/evaluation/...",
    "source_message_ids": ["..."]
  },
  "expected_output_schema": {
    "canonical_question": "string",
    "canonical_question_language": "string",
    "legal_issue_frame": "string",
    "legal_issue_frame_slug": "string",
    "law_area": "string",
    "facts": "array[string]",
    "desired_outcome": "string",
    "authority_context": "array[string]",
    "hidden_issues": "array[string]",
    "is_legal_answer_required": "boolean",
    "is_standalone_question": "boolean",
    "exclusion_reason": "string",
    "confidence": "low|medium|high",
    "quality_flags": "array[string]"
  }
}
```

The batch must contain redacted Telegram text only.

The LLM prompt profile is versioned separately from each task item so examples
are not duplicated into every JSONL row. The active profile must require the
same structured result object for every input text, including unrelated,
malformed, spam, announcement, resource-list, and dialogue-fragment inputs.
Those cases are represented through `exclusion_reason` and related boolean
fields; the model must not switch to prose or markdown.

The active profile contains:

- a system instruction that forbids answering the legal question or inventing
  legal citations, and treats topic/law hints as non-authoritative;
- five few-shot examples:
  - standalone residence-permit address update;
  - standalone Blue Card employer-change question;
  - short dialogue fragment that must be excluded as not standalone;
  - unrelated non-legal opening-hours question that must be excluded as
    `non_legal_question`;
  - operational asylum-intake question that remains standalone but is marked
    with `quality_flags=["requires_live_operational_data"]`;
- the expected output schema and enum rules.

Operator runners must include these few-shot examples before the current task
payload when calling Qwen normalization.

## Result JSONL Shape

Each imported result line must include:

```json
{
  "task_id": "tg-question-canonicalization-task:...",
  "task_scope": "question_candidate",
  "candidate_id": "tg-qa-candidate:...",
  "canonicalization_run_id": "tg-question-canonicalization-run:...",
  "canonicalization_contract_version": "tg_question_canonicalization_v1",
  "prompt_version": "tg_question_canonicalizer_v1",
  "runtime_contour": "operator_managed_batch",
  "backend": "llm-or-deterministic-fixture",
  "model_id": "operator-resolved-model-id-or-empty",
  "status": "completed",
  "failure_reason": "",
  "canonical_question": "...",
  "canonical_question_language": "ru",
  "legal_issue_frame": "Residence document address update with expired or extended permit",
  "legal_issue_frame_slug": "residence_document_address_update_with_expired_or_extended_permit",
  "law_area": "migration_status",
  "facts": ["moved residence", "plastic residence card appears expired"],
  "desired_outcome": "update address sticker or record after registration change",
  "authority_context": ["Buergeramt", "Auslaenderbehoerde"],
  "hidden_issues": ["continued lawful stay evidence", "Fiktionsbescheinigung"],
  "is_legal_answer_required": true,
  "is_standalone_question": true,
  "exclusion_reason": "none",
  "confidence": "high",
  "quality_flags": [],
  "provenance": {
    "source_candidate_artifact": "data/evaluation/...",
    "source_message_ids": ["..."]
  }
}
```

Allowed `status` values:

- `completed`
- `failed`
- `skipped`

Allowed `confidence` values:

- `low`
- `medium`
- `high`

## Exclusion Reasons

`exclusion_reason` must be `none` for included legal standalone questions.
Otherwise use a bounded value such as:

- `non_legal_question`
- `not_standalone_question`
- `dialogue_fragment`
- `rhetorical_or_complaint_only`
- `spam_or_joke`
- `insufficient_context`
- `privacy_or_redaction_blocker`
- `malformed_input`
- `llm_failed`

## Validation Rules

- Result identity is `(canonicalization_run_id, task_scope, task_id)`.
- Re-importing the same identity must not append duplicate evidence.
- `canonical_question` must be non-empty for included completed records.
- `legal_issue_frame_slug` must be stable and machine-oriented.
- `exclusion_reason=none` requires `is_legal_answer_required=true` and
  `is_standalone_question=true`.
- Failed and skipped records remain backlog and must be counted in the run
  manifest.
- Batch tasks that have no result line may be emitted as `skipped` evidence
  with `missing_result_for_batch_task` so the backlog remains explicit.
- Imported output must not contain raw Telegram text, secrets, tunnel URLs, API
  keys, or local `.env` values.

## Run Manifest

The canonicalization run manifest must record:

- run id
- input artifact path
- batch artifact path
- result artifact path
- evidence output path
- runtime contour
- backend and model id when applicable
- prompt or policy version
- processed, completed, failed, skipped, excluded, and uncertain counts
- started and completed timestamps
- known limitations and operator notes path when present
