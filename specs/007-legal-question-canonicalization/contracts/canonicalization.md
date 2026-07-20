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
  "canonicalization_contract_version": "tg_question_canonicalization_v2",
  "prompt_version": "tg_question_canonicalizer_v22_positive",
  "prompt_example_set_id": "tg_question_canonicalizer_examples_v12_positive",
  "canonicalization_identity_policy_version": "tg_question_canonicalization_identity_v1",
  "canonicalization_batch_id": "tg-question-canonicalization-batch:...",
  "canonicalization_batch_hash": "64-hex-sha256",
  "task_input_hash": "64-hex-sha256",
  "prompt_profile_hash": "64-hex-sha256",
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

The active profile contains a system instruction that forbids answers and
invented citations, versioned few-shot examples, and the expected output schema
and enum rules. The example count is profile content, not a contract invariant;
the profile hash identifies the exact instruction/example set used by a batch.

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
  "canonicalization_contract_version": "tg_question_canonicalization_v2",
  "prompt_version": "tg_question_canonicalizer_v22_positive",
  "canonicalization_identity_policy_version": "tg_question_canonicalization_identity_v1",
  "canonicalization_batch_id": "tg-question-canonicalization-batch:...",
  "canonicalization_batch_hash": "64-hex-sha256",
  "task_input_hash": "64-hex-sha256",
  "prompt_profile_hash": "64-hex-sha256",
  "runtime_profile": {"stage": "canonicalization", "model_id": "..."},
  "runtime_profile_hash": "64-hex-sha256",
  "canonicalization_evidence_hash": "64-hex-sha256",
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
  "untrusted_law_code_hints": ["AufenthG"],
  "provenance": {
    "source_candidate_artifact": "data/evaluation/...",
    "source_message_ids": ["..."]
  }
}
```

`untrusted_law_code_hints` is optional audit provenance copied from input
`law_code_candidates`. It is not canonical legal evidence and is not part of
the model-authored candidate. Atomic verification may use it only to detect
verbatim hint reuse in any candidate field outside the source question.

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
- The importer recomputes `task_input_hash`, `prompt_profile_hash`, and batch
  identity from the input batch. A strict result must match all of them, its
  runtime-profile hash, and its evidence hash; unknown top-level result fields
  are rejected rather than ignored.
- A derived retry batch has its own immutable identity and must carry
  `canonicalization_source_identity` for the original task. A retry can replace
  base evidence only when both its own batch and this root identity validate.
- Legacy artifacts can be read only through explicit `--allow-legacy-identity`;
  they are marked unverified and are not valid strict snapshot input.
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

## Review, Routing, And Finalization

- Routing reconciles every task in the batch. Missing, duplicate, unknown, or
  identity-invalid result rows go to backlog rather than being silently merged.
- The default unreviewed policy is `hold`. `first_pass` is an explicit,
  non-promotable diagnostic mode only.
- Verifier and adjudicator records must identify the canonical evidence hash and
  their own prompt/runtime profile. Material adjudicator disagreement routes to
  human review; it does not auto-retry generation.
- A finalization input must be an accepted result supplied through the explicit
  human review-decision import. `reviewer_hash` is optional compatibility
  metadata and is not a trust condition in the single-reviewer workflow.
- Current review cards export `review_payload_version` plus a deterministic
  `review_payload_hash` over the displayed source, candidate, verifier, retry
  context, source question date, and candidate evidence identity. The source
  question date must be visible in the review UI because temporal legal rules
  cannot be reviewed reproducibly against the export date. Import distinguishes missing or
  unsupported versions from a changed payload and rejects all three. Historical
  decisions without the hash remain `legacy_unverified` review history and are
  not reproducible model-qualification labels.
- Finalization preserves the selected source run id and writes
  `finalization_provenance`; it never rewrites a retry result into a synthetic
  merged run.
- A private snapshot accepts only completed, included, strict-identity-valid,
  human-accepted, finalized evidence. Rejected records remain a separate
  backlog artifact.

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
- canonicalization contract, batch, task, prompt-profile, runtime-profile, and
  evidence-hash metadata
- processed, completed, failed, skipped, excluded, and uncertain counts
- started and completed timestamps
- known limitations and operator notes path when present

Operator LLM runs additionally write a checkpoint and run-bundle sidecar. The
bundle records result/summary paths, runtime profile and hash, command metadata,
and an optional log path without storing secrets.

## Atomic Verification Sidecar

The optional atomic verify/repair contour consumes completed imported
canonicalization evidence. It does not change the result JSONL shape above.

Each sidecar record includes:

- `atomic_run_id`, controller policy version, verifier/critic/repair prompt
  versions and output-schema hashes;
- source `canonicalization_evidence_id` and
  `canonicalization_evidence_hash`;
- `initial_claim_ledger`, `initial_verification`, and `initial_controller`;
- optional `initial_critic_verification`, conservative merge diagnostics, and
  explicit verifier/critic disagreements;
- exact-quote span validation plus any deterministic
  `normalized_source_spans` offset corrections;
- `route`: `pass`, `pass_repaired`, or `hold`;
- optional `repair`, controller `deterministic_list_repairs`,
  `repaired_candidate`, changed-field checks, `final_claim_ledger`, final
  verifier/critic evidence, and `final_controller`;
- per-call and aggregate runtime metadata;
- active verifier/critic/repair model-native runtime profiles, structured-output
  adapter versions, their registry hash, operator runtime profile, input hash,
  checkpoint, and run-bundle lineage.
- when a stage uses two calls, its sanitized bounded reasoning memo, raw memo
  SHA-256, reasoning profile, no-reasoning formatter profile, and execution
  mode.

`stage_runtime` contains one entry per provider attempt, not merely one entry
per successful semantic stage. Terminal failures retain their completed
attempt count and retry-exhaustion state even when the provider omits token
usage.

Every attempt identifies the effective component profile. Different model and
transport profiles may be used by verifier, critic, repair, and their optional
formatters. A formatter profile must declare `reasoning_mode=disabled`.
Reasoning and formatter attempts have distinct call-stage names, token usage,
cost attribution, and retry histories; a formatter retry does not repeat a
completed reasoning call. Native request parameters are preserved in
secret-free lineage and unknown parameters must fail rather than being silently
discarded. Provider/transport failures, reasoning-memo failures,
structured-output failures, and semantic `pass|revise|hold` outcomes remain
separate states.

The verifier/critic formatter schema carries `source_quotes`, not offsets.
Offsets are derived only for a unique exact source occurrence. A missing,
non-matching, or ambiguous quote converts an otherwise supported formatter
verdict to `unresolved` before the unchanged controller runs.

The atomic stage checkpoint records `initial_verified`, `repair_completed`, or
`final_primary_verified` plus evidence, run, and runtime-profile identities.
Resume may reuse only an exact identity match. It rebuilds deterministic
initial and final ledgers before trusting saved LLM output and fails on a ledger
mismatch.

Claim-verifier support values are `explicit`, `necessary_inference`,
`unsupported`, and `unresolved`. Exact source quotes are mandatory for
`explicit` and `necessary_inference`; offsets may be normalized only from a
valid start anchor or a unique exact occurrence. Missing/duplicate claim verdicts,
invalid or ambiguous spans, unresolved claims, unauthorized repair edits, incomplete repair
ids, or a non-pass post-repair verification route the record to `hold`.

When critic mode is enabled, structured verdicts are merged conservatively:
`unresolved > unsupported > necessary_inference > explicit`. The sidecar keeps
all disagreements. Unsupported list claims authorize deletion only; the
controller preserves supported list items exactly and records any normalization
of the LLM repair proposal.

`atomic_critic_policy=before_pass` may skip critic execution only when the
primary controller already routes to `revise` or `hold`. The critic still runs
before every potential `pass` and `pass_repaired`. Records state whether the
critic executed and, when skipped, retain the deterministic skip reason.

Atomic `pass` is review evidence only. Neither `pass` nor `pass_repaired`
bypasses review-decision import or finalization.
