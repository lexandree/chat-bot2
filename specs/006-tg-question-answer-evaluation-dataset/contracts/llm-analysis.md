# Contract: Telegram Q/A LLM Analysis

## Boundary

LLM analysis in 006 is a one-time, operator-managed classifier/reviewer path for
dirty Telegram evaluation data. It is not production inference, not chatbot
answer generation, not trusted legal support, and not graph enrichment.

LLM output may only become review evidence. It cannot directly create
`auto_selected`, `review_approved`, final dataset records, Neo4j mutations, or
trusted legal facts.

## Runtime Contour

The preferred runtime is an OpenAI-compatible `llama-server` endpoint started by
the operator on disposable compute, then exposed to the project through a
temporary Cloudflare Tunnel, `trycloudflare`, local forward, or equivalent
short-lived endpoint.

The primary no-paid-token model candidate for the first 006 LLM pass is the
operator-provided GGUF:

- `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`

If that model is not good enough for the classification/review task, the next
operator-managed candidates are:

- `Qwen3.6-27B-Q6_K.gguf`
- `Qwen3.6-27B-Q8_0.gguf`

The Qwen candidates are capacity hypotheses for approximately 30 GB total GPU
memory on Kaggle T4 x2 and require an operator smoke run before use. Model
availability, exact model path, server parameters, and tunnel URL are runtime
inputs, not source-controlled project configuration.

LangChain or LangGraph may wrap the call path if it helps batch orchestration,
retry policy, or structured-output parsing. They must remain optional for the
006 default test path.

Reference operator docs:

- `export/reference_docs/kaggle_workflow_playbook.md`
- `export/docs/BULK_NOTEBOOK_PROCESSING.md`
- `export/docs/NOTEBOOK_EMBEDDING_RELAY_FALLBACK.md`
- `export/notebooks/llama_server_kaggle_simple_run.ipynb`
- `export/notebooks/llama-server_on_kaggle_full_notebook_workflow.ipynb`

## Input Batch Shape

Each LLM batch JSONL item must include:

- `task_id`
- `task_type`
- `task_scope`: `candidate` or `qa_cluster`
- `runtime_hint`: `operator_managed_llama_server_openai_compatible`
- `llm_contract_version`
- `prompt_version`
- optional `prompt_profile`: `full` or `compact`
- optional `input_char_budget`
- `system_instruction`
- redacted `input`
- `expected_output_schema`

The batch must contain redacted Telegram text only.

Two cluster-level prompt profiles are valid:

- `full`: preserves the full redacted cluster evidence for a long-context
  endpoint;
- `compact`: keeps selected/latest evidence first and truncates question,
  answer, and trigger text for a small-context local endpoint.

When a compact batch is emitted with an `input_char_budget`, the operator may
also emit a companion overflow batch. Overflow items are full-profile tasks
whose full redacted input exceeds the local budget. Compact output is review
evidence only; overflow output is for a later long-context review pass and must
use a separate `llm_run_id`.

The optional project runner for OpenAI-compatible chat endpoints sends one
batch item per request, uses a single user message, and extracts the first valid
JSON object from the model response. This supports Gemma 4 `llama-server`
wrappers such as `<|channel>thought...<channel|>` without making that wrapper a
project-wide standard.

Provider-specific request-body extensions are allowed only as runtime
configuration. The runner may record keys such as `thinking`, `options`,
`use_thinking`, `enable_thinking`, or `reasoning` when an operator is testing
hosted model behaviour. Such keys must be documented in the run summary and
must not alter the trust boundary: imported results remain review evidence only.
For the observed OpenCode `kimi-k2.6` route,
`{"reasoning":{"enabled":false}}` disabled slow reasoning output while
`{"options":{"thinking":{"type":"disabled"}}}` did not. This is provider-route
evidence, not a project-wide model standard.
For the observed OpenCode Zen `minimax-m2.5-free` route, the working smoke used
no extra provider body, omitted temperature, and raised `max_tokens` to `2048`.
Provider body workarounds must therefore be recorded per route/model rather
than reused across models.

Hosted providers may reject or ignore generic OpenAI-compatible defaults. In
particular, models such as Kimi K2.6/K2.5 should be smoke-tested without a
custom `temperature` before batch use, because their provider documentation
defines fixed temperature behaviour.

## Result JSONL Shape

Each imported LLM result line must include:

```json
{
  "task_id": "tg-qa-candidate:...",
  "task_scope": "candidate",
  "candidate_id": "tg-qa-candidate:...",
  "qa_cluster_id": "",
  "llm_run_id": "tg-qa-llm-run:...",
  "llm_contract_version": "tg_qa_llm_analysis_v1",
  "prompt_version": "tg_qa_candidate_classifier_v4_1",
  "runtime_contour": "kaggle_llama_server_cloudflared",
  "backend": "llama-server",
  "model_file": "gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf",
  "model_id": "operator-resolved-model-id-or-empty",
  "quantization": "Q8_K_XL",
  "status": "completed",
  "failure_reason": "",
  "is_real_user_question": true,
  "current_topic_relevance": "high",
  "answer_candidate_quality": "strong",
  "normalized_question": "...",
  "short_answer_summary": "...",
  "drift_or_conflict_assessment": "stable",
  "recommended_selection_status": "needs_manual_review",
  "needs_human_review": true,
  "question_intent": "legal_information_request",
  "legal_answer_requirement": "requires_hidden_issue_spotting",
  "graph_db_evaluation_fit": "legal_core",
  "issue_spotting_required": true,
  "issue_spotting_level": "high",
  "issue_spotting_confidence": "medium",
  "issue_spotting_reason": "The surface insurance question also requires self-employment and income-reporting issue spotting.",
  "hidden_legal_issue_categories": ["self_employment", "tax_income_reporting"],
  "answer_must_expand_beyond_user_wording": true,
  "exclusion_reason": "none"
}
```

`normalized_question` must preserve the source user's language. Russian,
Ukrainian, or German questions must not be translated into English; German legal
terms and section references may remain as terms inside the preserved-language
question.

The classifier must not approve cases by topic words alone. It must decide
whether a legally precise answer is required: applying a legal rule, status,
entitlement, obligation, procedure, authority competence, statutory condition,
or spotting hidden legal issues the user did not name. Rhetorical,
conversational, emotional, purely logistical, and general discussion questions
must be rejected even when they mention refugees, visas, Jobcenter, BAMF, ABH,
or Aufenthaltstitel.

Prompt v4 narrows `issue_spotting_required`: it is true only when an answer
limited to the user's surface wording would be materially incomplete,
misleading, or legally risky without identifying hidden duties, risks, status
conditions, or reporting obligations. Ordinary legal questions that only need
the explicit rule/status/procedure analysis must not be marked as issue
spotting.

Prompt v4.1 keeps the v4 approve/reject boundary and adds calibration-only issue
spotting fields:

- `issue_spotting_level`: `none`, `low`, `medium`, `high`, or `unclassified`;
- `issue_spotting_confidence`: `low`, `medium`, `high`, or `unclassified`;
- `issue_spotting_reason`: short factual reason for the level.

`issue_spotting_level` scale:

- `none`: no hidden expansion is needed;
- `low`: surrounding legal context is useful, but a direct answer still works;
- `medium`: hidden issues noticeably change answer completeness;
- `high`: omitting hidden issues would be materially misleading or legally
  risky.

These fields are evidence for prompt calibration and later analysis. They must
not change approve/reject by themselves.

`hidden_legal_issue_categories` are broad taxonomy labels for reporting and
comparison, not decision keywords. Emit at most five labels from:

- `residence_status`
- `asylum_or_temporary_protection`
- `work_authorization`
- `self_employment`
- `tax_income_reporting`
- `social_benefits`
- `health_insurance`
- `family_or_children`
- `housing_registration`
- `education_language`
- `authority_procedure`
- `deadline_or_proof`
- `travel_cross_border`
- `criminal_or_fraud_risk`
- `other`

Issue-spotting examples are intentionally generalized, not keyword triggers: a
question about health insurance plus foreign income may require spotting
self-employment, tax, income-reporting, and benefit-reporting issues; a
complaint asking why an authority behaves a certain way is rhetorical unless it
asks for a concrete entitlement, deadline, remedy, or procedure; a question
only asking where to pick up a card is practical logistics.

For prompt A/B tests against a human-reviewed baseline, a batch item may include
`input.review_overlay`. The overlay contains reviewer-corrected question and/or
reference-answer text and must be used as the primary text evidence for that
test. It must not include or leak the prior human decision label into the model
input.

Allowed `status` values:

- `completed`
- `failed`
- `skipped`

Allowed `task_scope` values:

- `candidate`: initial candidate-level classification before clustering;
- `qa_cluster`: cluster-level review after semantic clustering.

Identifier rules:

- `candidate` scope requires `candidate_id` and may leave `qa_cluster_id` empty;
- `qa_cluster` scope requires `qa_cluster_id` and may include candidate ids only
  as supporting input evidence.

Allowed `recommended_selection_status` values:

- `needs_llm_review`
- `needs_manual_review`
- `uncertain`
- `rejected`

## Run Manifest

The LLM run manifest must record:

- `llm_run_id`
- input batch path
- result output path
- runtime contour
- backend
- model file name
- model id when available
- quantization when available
- prompt version
- contract version
- server parameters relevant to reproducibility
- endpoint form with secrets and tunnel host redacted when needed
- JSON-valid result count
- schema-valid result count
- manual spot-check sample size and outcome
- processed, completed, failed, skipped, and unprocessed counts
- started and completed timestamps
- operator notes path when present

Temporary tunnel URLs, API keys, Kaggle credentials, and local `.env` values must
not be written to tracked files.

## Validation

Import must reject or mark as failed any result that:

- is not valid JSON;
- is missing the required task id, task scope, run id, status, contract
  version, or prompt version;
- uses a disallowed enum value;
- recommends direct approval into final dataset status;
- contains unredacted secrets or obvious private identifiers;
- cannot be matched to a known 006 candidate or cluster for its task scope.

Failed or skipped LLM items remain review backlog. They do not block the 006
pipeline if manual review can continue.

## Idempotent Import And Resume

LLM import must use `(llm_run_id, task_scope, task_id)` as the stable result
identity.

Rules:

- importing the same result key twice must not append duplicate review evidence;
- if the same key appears with a later corrected payload, the importer may
  replace the prior review evidence while preserving an audit count in the run
  manifest;
- partial JSONL imports are valid and must record processed, completed, failed,
  skipped, and unprocessed counts;
- failed lines must keep their raw provider text out of tracked source and may
  be summarized only as redacted failure metadata;
- re-running import for the same manifest must be safe after interruption;
- LLM import must never set `auto_selected`, `review_approved`, or final dataset
  eligibility by itself.

Model escalation from Gemma 4 to Qwen requires a failed or insufficient smoke
record for the prior model. Minimum smoke evidence is JSON validity,
schema-valid result count, failed/skipped count, and a short operator note from
manual spot-checking classifier recommendations.

Manual spot-checking must sample `min(20, completed_count)` completed results
when completed results exist. If fewer than 20 results completed, all completed
results are reviewed. The manifest must record both sample size and outcome.
