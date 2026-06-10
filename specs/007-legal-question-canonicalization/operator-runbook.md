# Operator Runbook: 007 LLM Canonicalization Funnel

This runbook covers the live operator-managed contour for producing
`real_data_007_canonicalization_results.jsonl` from the emitted 007
canonicalization batch. It is not a default test path and does not create
trusted legal answers.

Future answer-planning issues discovered during review are tracked in
`specs/007-legal-question-canonicalization/future-inference-questions.md`.
That backlog is not part of the current 007 execution path, but it preserves
patterns that will matter when retrieval and chatbot inference are designed.

Prompt-level lessons from repeated manual corrections are tracked in
`specs/007-legal-question-canonicalization/prompt-lessons.md`, and human review
conventions are tracked in
`specs/007-legal-question-canonicalization/manual-review-notes.md`.
The cumulative prompt-regression registry is tracked in
`specs/007-legal-question-canonicalization/prompt-regression-cases.json`.
Legal-intent pair review labels are explained in
`specs/007-legal-question-canonicalization/legal-intent-pair-review-guide.ru.md`
and
`specs/007-legal-question-canonicalization/legal-intent-pair-review-guide.en.md`.

## Cumulative Prompt-Regression Gate

A prompt correction is incomplete until it has been checked against every
previously retained regression case for that prompt family. Testing only the
record that motivated the latest correction can hide regressions in rules added
earlier.

The tracked registry stores only task ids, lesson ids, expected semantic focus,
and durable automatic invariants. It does not store raw private Telegram text.
The builder resolves task ids against local ignored batch artifacts and writes a
generated regression batch and manifest under `data/evaluation/`. It also fails
when a real task found in a local historical `*smoke*batch.jsonl` artifact has
not been added to the cumulative registry.

The accepted baseline is model-specific and remains an ignored generated
artifact. It is a comparison aid, not trusted legal evidence. Never compare a
different model or materially different reasoning mode to the same accepted
baseline without an explicit new baseline.

Prepare the complete canonicalizer regression batch without making live calls:

```bash
PREFIX=real_data_007_prompt_regression_v11_positive_qwen36 \
PROMPT_VERSION=tg_question_canonicalizer_v11_positive \
bash tmp/run_007_cumulative_prompt_regression.sh prepare
```

Run and compare a candidate prompt:

```bash
PREFIX=real_data_007_prompt_regression_v11_positive_qwen36 \
PROMPT_VERSION=tg_question_canonicalizer_v11_positive \
bash tmp/run_007_cumulative_prompt_regression.sh full
```

The generated review HTML shows the accepted baseline and current output side
by side. Manual review is required for the first baseline, every automatic
failure, every semantic warning, and only the bounded sample of other semantic
changes defined by the cost and stopping policy below. Quality-flag expectations
are warnings unless the flag itself is part of a stable contract; the same
meaning may be preserved correctly in `hidden_issues`. After the cumulative set
passes the promotion gate, promote it explicitly:

```bash
PREFIX=real_data_007_prompt_regression_v11_positive_qwen36 \
CONFIRM_PROMOTE=1 \
bash tmp/run_007_cumulative_prompt_regression.sh promote-baseline
```

When manual review discovers a new generalizable prompt failure:

1. Add the task id and expected invariant to
   `prompt-regression-cases.json`.
2. Add or update the generalized lesson in `prompt-lessons.md`.
3. Apply the cost and stopping policy below before changing the prompt.
4. Rerun the complete accumulated set only for a candidate that passed its
   bounded smoke tests.
5. Promote a new baseline only after reviewing all automatic failures and the
   bounded semantic-change sample required below.

## Cost And Stopping Policy

The canonicalized dataset is a supporting evaluation artifact, not the primary
product. Optimize for a sufficiently clean, auditable subset under a bounded
operator budget. Completeness and perfect phrasing are explicitly not goals.

Classify defects before spending another prompt iteration:

- **critical**: changes included/excluded routing, selects the wrong central
  legal proposition, invents or drops a material legal object/status/route,
  violates a stable quality flag used for routing, or fails schema validation;
- **non-critical**: awkward wording, harmless mixed-language phrasing,
  evidence ordering, optional authority wording, or a detail that does not
  change routing, legal intent, or downstream filtering.

Use these hard limits:

1. A new prompt rule requires either the same critical defect in at least three
   independent records, at least a 2% critical-error rate in a representative
   sample of 100 or more records, or one deterministic defect with clear
   high-impact downstream routing consequences.
2. A single record may be added to the regression registry, but it does not by
   itself justify changing the prompt. Route isolated defects to residual
   review or exclude them from dataset promotion.
3. Spend at most two candidate prompt revisions on one defect class. Each
   candidate gets one targeted smoke of at most ten records. If both revisions
   fail, stop prompt work and use residual routing, deterministic validation,
   or exclusion.
4. Run the full cumulative regression set at most once for a candidate that
   passed targeted smoke. A critical cumulative failure permits one final
   targeted correction cycle; otherwise keep the previous baseline.
5. Review every automatic failure and semantic warning. For other changed
   semantic fields, manually inspect at most 20 records or 2% of the production
   batch, whichever is smaller. Do not manually review every changed record.
6. Unresolved or disputed records do not block the clean dataset. Keep them in
   a separate residual/manual artifact and omit them from promotion.
7. Stop processing additional corpus batches when the current clean subset is
   sufficient for the active retrieval or evaluation experiment. Resume only
   when a measured coverage gap requires more data.
8. New few-shot examples require the same evidence threshold as a new rule.
   Prefer replacing or consolidating an existing example over unbounded prompt
   growth.

Promotion gate for a frozen prompt:

- zero provider or schema-validation failures in the cumulative run;
- zero critical automatic-regression failures;
- no new systematic critical defect in the bounded manual sample;
- non-critical defects are documented or routed to residual review rather than
  repaired through another prompt iteration.

Current freeze decision: `tg_question_canonicalizer_v22_positive` passed its
49-record cumulative regression and bounded manual sample on 2026-06-10. It is
the accepted Qwen3.6 baseline and is frozen for this optimization cycle. Do not
revise it for isolated wording defects; route those records to residual review
or omit them from dataset promotion.

Verifier and adjudicator regressions require stable review-stage inputs, not
only the original source task. Until each such real input is captured, the
field-scope fixtures retained in the registry are exercised with:

```bash
PREFIX=real_data_007_field_scope_<model> JUDGE=<model> \
bash tmp/run_007_field_scope_smoke.sh run-both
```

## Providers And Budget Assumptions

- OpenCode Go is used for Qwen3.6 Plus normalization and DeepSeek V4 Pro
  adjudication.
- MiniMax.io pay-as-you-go credits are used for MiniMax-M2.7 verification.
- MiniMax-M2.7 is preferred over MiniMax-M2.5 because direct MiniMax.io pricing
  is the same for this verifier workload and M2.7 is the newer model.
- MiniMax Anthropic-compatible API is the preferred verifier transport because
  MiniMax documentation recommends it for M2.7 coding/agent work and it supports
  native tool-use blocks. OpenAI-compatible API remains an accepted fallback.
- MiniMax spend is controlled by sending only compact verifier payloads and by
  using DeepSeek only after human triage.

## Environment

Operator secrets stay in `.env` or the shell and are never written to tracked
artifacts. Supported MiniMax verifier environment variables:

```bash
OPENAI_API_KEY=<MiniMax key>
MINIMAX_API_KEY=<same key, optional alias>
OPENAI_BASE_URL=https://api.minimax.io/v1
ANTHROPIC_API_KEY=<MiniMax key, optional alias>
ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
```

If `ANTHROPIC_API_KEY` is unset, the operator runner may use `MINIMAX_API_KEY`
or `OPENAI_API_KEY` for the Anthropic-compatible client.

## Calibration Scope

The first live check is exactly 50 records from:

```text
data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch.jsonl
```

The 50-record slice should include:

- multiple `answer_candidate_status` values: `strong`, `partial`, and
  `no_answer`;
- multiple law-area hints: `migration_status`, `employment`, and `asylum`;
- short, long, borderline, and noisy questions;
- at least a few records with quality flags.

Full 5,000-record processing starts only after the 50-record calibration run
has clean technical validation, readable review cards, and acceptable MiniMax
verification behavior.

## Minimal Payload Rules

Do not send whole 006 candidates, answer candidates, source paths, manifests,
artifact metadata, or existing reviewed answer text to LLMs unless the current
stage explicitly needs it.

Qwen normalization receives only:

- `task_id`;
- `candidate_id`;
- redacted `question_text`;
- compact `topic_labels`;
- compact `law_code_candidates`;
- `answer_candidate_status`;
- compact `quality_flags`;
- canonicalization output schema and enum rules;
- the versioned few-shot example set `tg_question_canonicalizer_examples_v1`.

The prompt must include the active three examples before the current task:

- a standalone residence-permit address update question;
- a standalone Blue Card employer-change question;
- a short dialogue fragment that is excluded as `not_standalone_question`.

Do not include source artifact paths, source message ids, answer text, or review
decisions in the LLM payload. The examples are generic and must not contain
private corpus text.

## Context Assembly Tooling

The first calibration can use the static prompt profile emitted by project code.
If the live runner grows beyond static prompt assembly, prefer mature
context-handling utilities over custom glue for:

- prompt templates;
- few-shot example selection;
- token budgeting and truncation rules;
- provider-specific chat message construction;
- structured output model binding where it is supported.

`langchain-core` or an equivalent lightweight context library is acceptable in
the explicit operator-managed runner when it reduces code and failure modes.
Do not introduce LangGraph, agents, autonomous chains, retrieval agents, chatbot
answering, or a default-test dependency for 007.

The current implementation exposes:

- `CanonicalizationResultPayload`: Pydantic schema for Qwen output and local
  import validation;
- `VerifierVerdictPayload`: Pydantic schema for MiniMax/DeepSeek verifier
  output;
- `compact_canonicalization_llm_payload()`: strips source artifacts, message
  ids, selected answer metadata, and other non-current context before LLM calls;
- `build_langchain_canonicalization_chain()`: creates a LangChain
  `ChatPromptTemplate | model.with_structured_output(CanonicalizationResultPayload)`
  chain for operator normalization;
- `build_langchain_verifier_chain()`: creates the equivalent verifier chain.

`instructor` is not used by the tracked implementation. It can be reconsidered
only if it materially simplifies a provider path that LangChain structured
output does not handle.

MiniMax-M2.7 verification receives only:

- redacted source question;
- Qwen normalized JSON;
- a final `field_scope_review` snapshot that repeats the candidate fields under
  review separately from source text and review reasons;
- compact validation flags from code;
- the verifier rubric.

DeepSeek V4 Pro adjudication receives only manually selected records:

- redacted source question;
- Qwen normalized JSON;
- MiniMax verdict and short reason;
- a final `field_scope_review` snapshot for checking claims about candidate
  field contents;
- human triage reason for escalation;
- the adjudication rubric.

## Pipeline

1. Sample 50 records.
2. Run Qwen3.6 Plus normalization one record per request.
3. Validate Qwen output locally with JSON parsing, Pydantic schema checks,
   domain consistency checks, slug normalization, and privacy guards.
4. Export validation failures and suspicious records to review cards.
5. Run MiniMax-M2.7 verification on locally valid records.
6. Export MiniMax fail, uncertain, low-confidence, high-risk, and random pass
   sample records to review cards.
7. Human triage decides `accept`, `reject`, `retry_qwen`, `send_deepseek`, or
   `hold`.
8. Run DeepSeek V4 Pro only on records explicitly marked `send_deepseek`.
9. Human review resolves DeepSeek conflicts or uncertain verdicts.
10. Merge final decisions into import-ready
    `real_data_007_canonicalization_results.jsonl`.
11. Run the existing canonicalization import command.

## Calibration Commands

Create the 50-record slice:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-sample \
  --batch data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch.jsonl \
  --output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_batch.jsonl \
  --summary-output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_summary.json \
  --sample-size 50
```

Create the first review-card UI:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-review-cards \
  --batch data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_batch.jsonl \
  --html-output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_review.html \
  --summary-output data/evaluation/tg_qa_canonicalization/real_data_007_calibration_50_review_summary.json
```

## Review UI Requirement

Manual review must not require browsing raw JSON. The first UI can be simple,
but it must present one record as a review card with:

- source redacted question;
- Qwen canonical question, issue frame, slug, law area, facts, desired outcome,
  authority context, hidden issues, exclusion reason, confidence, and flags;
- local validation status and failure reasons;
- MiniMax verdict, confidence, risk, bad fields, and short reason;
- optional DeepSeek verdict and short reason;
- editable decision fields.

Required human decision fields:

- `decision`: `accept`, `reject`, `retry_qwen`, `send_deepseek`, or `hold`;
- `reviewer_hash`;
- `decision_reason`;
- optional corrected canonicalization fields for cases where the operator
  chooses manual correction rather than retry.

Preferred first implementation:

- generate JSONL/TSV review cards;
- serve a dependency-light local HTML UI or stdlib-backed local page;
- write decision JSONL/TSV that can be merged deterministically.

Streamlit or Gradio may be used only if the dependency cost is clearly lower
than implementing the review-card UI directly.

## Qwen Normalization

Use Qwen3.6 Plus through OpenCode Go.

Operational rules:

- one record per request;
- include 2-3 versioned few-shot examples before the current record;
- no automatic semantic retry;
- JSON-only output;
- non-thinking mode when supported by the endpoint;
- low temperature;
- raw response and normalized parsed result are both preserved as ignored
  artifacts.

The output must match the canonicalization result contract and remain review
evidence only.

## Local Validation

The local validator owns technical correctness. It must classify failures into:

- `invalid_json`;
- `schema_invalid`;
- `contract_invalid`;
- `privacy_blocked`;
- `import_incompatible`;
- `suspicious_but_valid`.

MiniMax and DeepSeek must never be used to decide whether a JSON object parses
or whether enum values are legal.

## MiniMax-M2.7 Verification

Use MiniMax.io direct pay-as-you-go credits.

Preferred mode:

- Anthropic-compatible SDK tool-use with local Pydantic validation of the
  returned `tool_use.input`.

Fallback mode:

- OpenAI-compatible SDK tool calls with `reasoning_split=True` and enough
  `max_tokens` for M2.7 to finish reasoning and emit the tool call.
- Strict JSON response with the same Pydantic verifier model and local
  validation if tool mode degrades.

Observed calibration smoke:

- OpenAI-compatible MiniMax-M2.7 returned valid `tool_calls` with
  `max_tokens=1024`. A too-small `max_tokens=256` run ended with
  `finish_reason=length` before a tool call.
- Anthropic-compatible MiniMax-M2.7 returned `stop_reason=tool_use` and a valid
  `tool_use` block.

Verifier output:

```json
{
  "verdict": "pass|fail|uncertain",
  "confidence": 0,
  "risk": "none|low|medium|high",
  "bad_fields": [],
  "short_reason": "",
  "suggested_action": "accept|reject|retry_qwen|send_deepseek|human_review"
}
```

MiniMax must not rewrite Qwen canonicalization records.

## Human Triage Before DeepSeek

The operator reviews:

- all MiniMax `fail`;
- all MiniMax `uncertain`;
- all MiniMax `confidence < 80`;
- all `risk=medium` or `risk=high`;
- all local validation failures;
- a random 5% sample of MiniMax `pass`;
- new or rare `legal_issue_frame_slug` values.

DeepSeek is used only for records explicitly marked `send_deepseek` by the
operator.

## DeepSeek V4 Pro Adjudication

Use DeepSeek V4 Pro through OpenCode Go.

The model acts as an adjudicator, not a rewriter. It returns:

```json
{
  "verdict": "pass|fail|uncertain",
  "confidence": 0,
  "risk": "none|low|medium|high",
  "bad_fields": [],
  "short_reason": "",
  "final_recommendation": "accept|reject|retry_qwen|human_review"
}
```

Human review resolves all DeepSeek `uncertain` records and all conflicts between
MiniMax and DeepSeek.

When human review selects `retry_generator`, the human decision controls the
route. The retry task must still preserve every available completed judge
result, verifier vote, the previous candidate, and the human reason as
corrective context. An empty human reason is acceptable when the retained judge
reasons already explain the retry.

## Strict Verifier Consensus Queues

After a retry candidate is verified by two or more models, split the completed
records by exact verifier consensus:

- `unanimous_pass`: every completed verifier returns `pass`; retain as accepted
  review evidence;
- `unanimous_nonpass`: every completed verifier returns `fail` or `uncertain`;
  retry the generator with all verifier reasons;
- `non_unanimous`: at least one verifier returns `pass` and at least one returns
  `fail` or `uncertain`; send to adjudication;
- `incomplete`: any candidate or verifier result is missing or failed; keep in
  the operational backlog.

Use `tmp/split_007_verifier_consensus_queues.py` with repeated
`--verifier name=path` arguments. The generated unanimous-nonpass retry batch
preserves the previous candidate and every verifier vote as corrective context.
The splitter supports a variable verifier count and does not assume a specific
model ensemble.

## Final Merge

Only records with final decision `accept` enter:

```text
data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_results.jsonl
```

Records marked `reject`, `retry_qwen`, or `hold` remain visible in decision and
backlog artifacts. The final merge must preserve provenance, model ids,
provider names, prompt/tool versions, validation status, verifier verdicts, and
human decisions.

## Existing Import Command

After final merge:

```bash
PYTHONPATH=src python -m app evaluation tg-qa-canonicalization-import \
  --batch data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_batch.jsonl \
  --results data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_results.jsonl \
  --output data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_evidence.jsonl \
  --manifest-output data/evaluation/tg_qa_canonicalization/real_data_007_canonicalization_manifest.json \
  --canonicalization-run-id tg-question-canonicalization-run:real-data-007
```
