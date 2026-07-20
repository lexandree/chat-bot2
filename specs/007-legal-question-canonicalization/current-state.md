# 007 Current State

Date: 2026-07-20

This document is an operator-facing status snapshot for 007. It records the
current evaluation, review, and retrieval state without including private
Telegram text, generated vectors, LLM outputs, API endpoints, or local secrets.

## Scope Boundary

007 remains an evaluation and canonicalization layer for the database-first
legal GraphRAG foundation. It does not create chatbot inference, production
answer synthesis, or trusted legal answer support.

All generated dataset, review, LLM, embedding, and HTML artifacts under
`data/evaluation/` are private generated artifacts and remain ignored by git.

## Implementation Status

The tracked 007 implementation tasks are complete through Phase 14:

- canonicalization batch/import;
- canonical embeddings and deterministic issue clusters;
- canonical coverage reports;
- cluster review import, question-bank build, final-candidate gating, reviewed
  dataset export;
- legal-intent equivalence diagnostics;
- private snapshot and explicit-reference benchmark;
- semantic retrieval diagnostics;
- human retrieval relevance review;
- clean curated retrieval baseline;
- route-ambiguity diagnostic;
- temporal-currentness promotion gate.

The canonicalization control plane is additionally hardened for strict batch
identity, human review admission, disagreement routing, resumable operator
runs, finalization, and private snapshots. The design note is
`canonicalization-trust-hardening.md`.

Latest recorded verification after Phase 14 and canonicalization control-plane
hardening:

- `python -m pytest -q`: 267 passed, 11 skipped;
- `tg-qa-boundary-check`: passed;
- `tg-qa-canonical-boundary-check`: passed;
- `python -m compileall -q src tests`: passed;
- tracked operator scripts under `scripts/evaluation/`: syntax checks passed;
- `git diff --check`: passed.

## Frozen Prompt State

The accepted Qwen3.6 canonicalizer baseline is:

`tg_question_canonicalizer_v22_positive`

Operator rule: do not revise the canonicalizer prompt for isolated wording
defects. Route isolated defects to residual review or omit them from dataset
promotion. New prompt rules require repeated critical defects or a clear
high-impact deterministic routing defect as defined in `operator-runbook.md`.

## Canonicalization Control Plane

- Canonicalization task, prompt-profile, batch, runtime-profile, and evidence
  hashes are strict by default; historical artifacts require explicit
  `--allow-legacy-identity` and remain unverified.
- Routing reconciles the full batch. Unreviewed output is held in backlog by
  default rather than being passed through as accepted evidence.
- Verifier/adjudicator lineage is tied to the canonical evidence hash. Material
  adjudicator disagreement is a human-review route, not an automatic retry.
- Human acceptance is established by a valid imported review-decision artifact;
  `reviewer_hash` is optional compatibility metadata and is ignored as a trust
  condition in the single-reviewer workflow. Core finalization preserves source
  run ids and validates retry-to-base root identity; snapshots require finalized
  human-reviewed evidence.
- Canonicalizer, verifier, and adjudicator runs write checkpoint and run-bundle
  sidecars with runtime identity and command metadata.
- For a bounded high-value batch of at most 100 records, the active OpenCode
  default is `glm-5.2`. Hermes remains experimental evidence only and is not a
  substitute for direct model quality.

## Atomic Diagnostic State

- Atomic verifier and critic prompt v6 are active; repair remains v3.
- Atomic controller v6 validates exact source spans, blocks four known
  unsupported relation classes before a potential `pass`, and holds output
  that copies an untrusted law-code hint absent from the source.
- The contour contract and promotion boundary are recorded in
  [atomic-verify-repair-contour.md](atomic-verify-repair-contour.md).
- The full GLM-5.2 reasoning verifier+critic contour passed the two reviewed
  activity-gate directions, but remains too slow and incompletely priced for
  bulk use because reasoning usage is not reported by the endpoint.
- Qwen3.7 Plus and MiniMax M3 reasoning did not qualify as replacements. Direct
  DeepSeek V4 Flash and GLM-5.2 without reasoning produced false semantic
  passes before deterministic guards.
- Guarded GLM-5.2 without reasoning is a review-triage candidate only. Its
  12-record canary completed in 302.916 seconds for $0.1767462, with six pass
  and six hold routes; one pass remained manually disputable.
- Compact-memo verifier v7/v8 profiles are inactive diagnostics. V8 reduced
  target-record cost by 29-37%, but repeated holdout execution completed only
  11/12, produced only one pass, and that pass was the same disputable record.
  It does not replace active v6.
- Plain LangChain message usage is now included in token/cost telemetry; older
  mixed-stage runs remain explicitly incomplete because their raw metadata was
  not retained.
- `tg-qa-canonicalization-atomic-risk-split` can partition known relation-risk
  records before LLM execution. Its output is routing evidence, never an
  acceptance or rejection decision. It now fails fast on stripped source,
  missing identity, and mismatched evidence hashes.
- On the 985-record legacy diagnostic dataset, controller v5 selected 18
  known-risk records. A matched three-record probe cost $0.21734004 and 584.625
  seconds with GLM-5.2 reasoning versus $0.0379372 and 53.305 seconds without
  reasoning. The cheap model semantically passed one record, but the controller
  held it; known-risk records should bypass LLM triage and go to human review.
- Across all 18 selected records, no-reasoning GLM-5.2 cost $0.235275 and used
  90,300 tokens. It emitted ten model passes; controller v5 blocked all ten and
  no critic ran. Atomic summaries now separate current-invocation metrics from
  `cumulative_output_metrics` over the complete resumed result file.
- Existing decision ledgers do not qualify a learned router. Across the two
  current 1,000-record ledgers, 1,995 decisions are generator-route-derived and
  only five are human. The 80-record human adjudication set is intentionally
  selected for non-accept/disagreement, while the older 50-record set and the
  80-record set lack exact evidence-hash binding. No router or NLI dependency
  is introduced before an independently sampled, identity-bound benchmark.
- New canonicalization review cards bind the displayed candidate and verifier
  context with versioned `review_payload_hash`; import rejects unsupported
  versions and changed review payloads. Historical hashless decisions keep
  their explicit manual-review status but are marked `legacy_unverified` and
  remain ineligible for model qualification.
- `tg-qa-canonicalization-sample` retains balanced calibration by default and
  adds an explicit seeded `stable_hash` policy for order-independent,
  predeclared qualification samples. Summaries retain the policy, seed, and
  selected task-id hash.
- The first fresh stable-hash 50-record slice completed on 2026-07-17 with no
  prompt-regression or prior-calibration overlap. Cheap triage produced 23
  potential passes and 27 holds; the full GLM-5.2 reasoning contour retained
  21 passes and repaired two. Reasoning escalation was 46%. These are unlabeled
  routes, so no model was promoted and no automatic acceptance is enabled.
- Review-card export now renders atomic routes as the existing compact verifier
  view, including problematic fields and final repaired-field values. The
  review payload hash still binds the complete underlying atomic result rather
  than only the displayed summary.

## Active Private Dataset Snapshot

The current private canonical dataset contour is `last_2000_v1`.

Current high-level artifact identities:

- issue clusters:
  `data/evaluation/tg_qa_issue_clusters/real_data_007_canonical_question_dataset_last_2000_v1_issue_clusters.jsonl`
- temporal queue:
  `data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_temporal_currentness_review_queue.jsonl`
- cluster review seed:
  `data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_cluster_review_seed_120.jsonl`
- agentic research request experiment:
  `data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_agentic_research_requests_30.jsonl`

These paths are private artifact references, not publication material.

Source question dates have been restored from the original canonicalization
batch metadata (`input.question_date`) for this contour:

- canonical dataset records with `question_date`: 985 / 985
- canonicalization evidence records with `question_date`: 994 / 994
- issue clusters with `source_question_dates`: 984 / 984

Backfill summary:
`data/evaluation/tg_qa_canonicalization/real_data_007_canonical_question_dataset_last_2000_v1_question_date_backfill_summary.json`

## Legal-Intent Equivalence State

Current balanced benchmark:

`data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_pair_benchmark_v2_balanced.jsonl`

Current imported human labels:

`data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_pair_review_labels_balanced_v2_imported.jsonl`

Status on 2026-06-23:

- benchmark pairs: 118
- random negative controls: 100
- random negative anchor distribution: 100 unique left candidates, 100 unique
  right candidates, max reuse 1
- reviewed labels retained in balanced benchmark: 41
- unreviewed pairs: 77
- reviewed label classes: 23 `different`, 2 `exact_duplicate`, 4
  `related_context`, 5 `same_legal_intent`, 7
  `same_topic_different_issue`

Historical note: the first `pair_benchmark_v1` random-negative contour pinned
all 100 random controls to one left candidate. It is retained only as a
historical artifact. Use `pair_benchmark_v2_balanced` for further review.

Method reports:

- historical qwen37 pair judge on `pair_benchmark_v1`:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_pair_judge_qwen37_report_summary.json`
  - exact pair-class match: 12 / 23
  - answer-reuse safety match: 18 / 23
  - false duplicate risk examples: 2
  - false separation risk examples: 4
- similarity cosine+recos baseline on `pair_benchmark_v2_balanced`:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_balanced_v2_report_summary.json`
  - reviewed labels: 41
  - exact pair-class match: 27 / 41
  - answer-reuse safety match: 35 / 41
  - false duplicate risk examples: 9
  - false separation risk examples: 0

The latest balanced review UIs are:

- all 118 pairs:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_balanced_v2_review.html`
- unreviewed 77 remaining pairs:
  `data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_balanced_v2_unreviewed77_review.html`

Prepared source-hard Qwen3.7 judge contour:

- source-hard batch: 18 pairs
- source-hard labels imported: 18 completed, 0 failed
- structured-output mode: Qwen3.7 thinking disabled; the failed historical
  `real_data_007_last_2000_source_hard_qwen37_v2_positive_*` attempt combined
  thinking with forced tool calling and is not usable.
- two-step mode: Qwen3.7 Max writes plain-text reasoning first; Qwen3.6 Plus
  with thinking disabled converts that rationale and the pair payload into
  `LegalIntentPairDecisionPayload`.
- current two-step source-hard result after schema rerun:
  `real_data_007_last_2000_source_hard_qwen37_reasoning_qwen36_schema_v2_positive_*`
  completed 18/18 with no failed records. Strict `pair_class` match against
  the 18 human labels is 7/18; answer-reuse safety match is 13/18; canonical
  question reuse safety match is 16/18. Treat this as useful reasoning evidence
  and a hard-pair diagnostic, not yet as a reliable automatic equivalence
  classifier.

Note: the full qwen37 run currently recorded under
`real_data_007_last_2000_pair_judge_qwen37_*` used prompt version
`tg_legal_intent_pair_judge_v1`. Future qwen37 pair-judge runs should set
`TG_LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION=tg_legal_intent_pair_judge_v2_positive`
unless intentionally comparing against the historical v1 run.

## Temporal Currentness State

Current temporal queue aggregate:

- queue records: 984
- suggested temporal state: 984 `unresolved_currentness`
- source question date available: 984
- source question date missing: 0

Generated temporal review UI:

`data/evaluation/tg_qa_question_bank/real_data_007_last_2000_v1_temporal_currentness_review.html`

Interpretation:

The current temporal gate blocks current-default promotion unless a reviewer
explicitly sets `current_reusable` or `historical_but_generalizable`. Source
question dates are available for review, but they remain metadata only: age
alone does not prove obsolescence, and recent date alone does not prove current
reusable status.

## Retrieval State

See `retrieval-diagnostics-summary.md` for aggregate metrics.

Retained conclusions:

- exact references resolve reliably when the reference is explicit and
  in-scope;
- query-explicit real-record references are not safe semantic ground truth;
- semantic top-1 is diagnostic only;
- clean curated retrieval is acceptable as a small regression signal;
- route ambiguity must preserve multiple plausible legal routes instead of
  forcing one route from `Asyl`/`refugee` wording;
- route-union candidate visibility is diagnostic evidence, not production
  policy.

## Question-Bank Promotion Path

The question-bank/final-candidate path has been mechanically dry-run without
LLM calls or real approvals.

Observed dry-run result on 2026-06-20:

- 6 synthetic decisions imported, 0 failed;
- 6 question-bank entries built;
- 4 entries had missing reference answers;
- 2 entries were not current-default eligible at question-bank level;
- final candidates: 1 eligible, 1 blocked missing reference answer, 1 blocked
  temporal currentness, 3 rejected because not approved for final evaluation;
- reviewed final dataset emitted 1 synthetic eligible case.

Interpretation:

The mechanics work. Real promotion is still blocked by human cluster review,
temporal-currentness review, and reviewed reference answer material.

## Hermes Experiment State

Hermes/agentic research is currently an experiment, not a permanent project
tool. The experiment tests whether a memory-capable agent can reduce human
review time by learning short route corrections.

The local Hermes scratch loop is closed and is not part of the tracked runtime
or operator interface. Its aggregate conclusion is retained here; disposable
scratch scripts and sample outputs are not retained as project files.

Trust boundary:

Hermes output is preliminary research evidence only. It must not approve
question-bank entries, mutate the graph, or become legal truth without human
review.

For bounded canonicalization and review work, use direct OpenCode `glm-5.2`
before considering a Hermes wrapper. The wrapper does not change the review
trust boundary or compensate for a weaker base model.

## Atomic Critic Experiment State

An optional operator sidecar now supports:

- deterministic field claims and exact-quote validation;
- independent verifier plus opt-in structured critic;
- conservative disagreement merge;
- one repair followed by full re-verification;
- deterministic deletion of unsupported list claims;
- identity-bound resume after merged initial review, repair, and final primary
  verification.

Target live evidence on `tg-question-canonicalization-task:20338f0eb2122742b0ae`
showed why the critic is needed: a single verifier produced a false
`pass_repaired` while retaining a Jobcenter eligibility relationship. Critic
v3 retains the v2 relationship correction and adds an activity-evidence gate.
Controller v4 then normalized
the repaired hidden-issue list to the one supported German
activity-classification issue. A separate v3 final-state verifier+critic smoke
returned two passes with no disagreement in 203.908 seconds and 24,176 total
tokens.

On `tg-question-canonicalization-task:2ec442161386f8e093f5`, verifier/critic v2
incorrectly treated a possible FOP account document as proof of foreign
activity. Verifier/critic v3 independently rejected the registration framing
because the source lacked an actor-action-location link. That two-call run used
51,205 tokens and 403.707 seconds.

This does not promote the repaired record. The contour remains opt-in for small
disputed samples because verifier+critic runs used tens of thousands of tokens
per record and have not passed a cumulative regression batch.

The 2026-07-16 model sweep qualified only direct reasoning-to-JSON deployment.
It did not use the already established reasoning-plus-no-thinking pattern.
Consequently its JSON, span, and timeout failures are not final evidence
against a model used only for the reasoning half; even semantic errors require
comparison of the retained memo with the formatted verdict. The sweep still
shows that no cheaper model was a direct one-call replacement. Registry v1
remains immutable evidence for that result.

On 2026-07-17 the atomic runner gained an optional two-step execution per
verifier, critic, or repair stage. A semantic model writes a bounded plain-text
memo, then an explicitly `reasoning_mode=disabled` profile converts it into the
strict Pydantic schema. Formatter retries reuse the memo. Runtime registry v2,
checkpoint identity, attempt metadata, and cost attribution retain both
profiles. The critic creates an independent memo and never receives verifier
reasoning. DeepSeek V4 Flash, MiMo V2.5, MiniMax M2.7, and MiniMax M3 formatter
profiles are candidates only; no live qualification is implied by registration.

The first end-to-end two-step smoke used MiniMax M3 reasoning followed by
DeepSeek V4 Flash with reasoning disabled on the positive activity-gate record.
It completed without schema failure: M3 produced an 11,243-character memo in
128.838 seconds; DeepSeek formatted all 26 claims in 22.591 seconds using 7,291
input and 3,741 output tokens, estimated at $0.002068 for the priced formatter
call. Deterministic quote resolution left zero invalid spans and conservatively
converted seven claims without one unique quote to `unresolved`; four claims
were unsupported and the final route was `hold`.

This qualifies neither model for bulk. The formatter passed one target-scale
schema smoke, but M3 still treated double-taxation framing and a missing
Steuer-ID prerequisite as supported, contrary to the reviewed target. Keep
the accepted direct GLM-5.2 contour as the comparison baseline while testing
other cheap reasoners. The smoke does confirm that schema failure and semantic
failure are now observable as separate stages.

A follow-up two-target sweep used the same DeepSeek no-reasoning formatter with
GLM-5, MiMo-V2.5, Qwen3.7 Max, and Qwen3.7 Plus reasoning. All eight records
completed without provider or schema failure, but no reasoner passed both
semantic directions. GLM-5, MiMo, and Qwen3.7 Max incorrectly inferred
activity from the possible FOP-account document. Qwen3.7 Plus correctly rejected
that negative gate, but its positive memo retained the reviewed-wrong double-
taxation, Jobcenter, and Steuer-ID-prerequisite claims. Qwen3.7 Plus may be
tested only as diagnostic first-pass evidence; no standalone two-step verifier
is qualified. Full measurements are in `atomic-model-profile-evaluation.md`.

The same-contour v4 GLM-5.2 control exposed field-role and relation failures.
Verifier/critic v6 subsequently passed both reviewed activity-gate directions,
while repeated cheap and mixed-role calls still produced false semantic passes.
Controller v5 now blocks the four known relation classes. Prompt-only success
on two records is no longer treated as the current blocker or as qualification.

The safe cost reduction is critic policy `before_pass`. It challenges every
potential `pass` and `pass_repaired`, but skips critic calls after a primary
`revise` or `hold`. On the negative GLM target this would preserve `hold` while
saving the agreeing critic call. A live run confirmed one call, explicit critic
skip, `hold`, 27,516 tokens, and 193.445 seconds, versus 51,205 tokens and
403.707 seconds in the earlier always-critic run.

## Fresh Qualification V3 (2026-07-19)

The third fresh 50-record qualification run is complete through identity-bound
manual review and finalization. It approves 21 private canonicalization
records; the other 29 records remain visible in the finalization backlog. It
does not approve legal answers or source support.

Observed routing:

- deterministic foreign-activity split: 0 focused, 50 ordinary;
- Qwen 3.6 canonicalization: 49 completed, 1 failed after a reproduced
  semantically inconsistent structured output;
- Qwen outcomes: 23 included candidates, 27 excluded or failed records;
- deterministic known-relation risk split: 0 matched, 50 low risk;
- no-reasoning GLM-5.2 plus DeepSeek V4 Flash formatting on the 23 included
  candidates: 5 potential passes and 18 holds, including one visible
  formatter/retry-exhaustion failure;
- full GLM-5.2 reasoning verifier plus independent reasoning critic and
  no-reasoning formatters on the five potential passes: 5 completed model
  passes, 0 repairs, 0 technical failures.

Runtime evidence:

- cheap screen: 289,934 tokens, 784.916 seconds, estimated uncached cost
  `$0.30741848`;
- strong five-record contour: 197,993 tokens, 1,375.845 seconds, estimated
  uncached cost `$0.38544020`;
- strong reasoning was used for 5/50 records overall and 5/23 Qwen-included
  candidates;
- Qwen generation, one failed resume, and three reviewed correction rounds used
  751,736 input and 14,587 output tokens, estimated at `$0.41962900` using the
  2026-07-16 registry price snapshot;
- the accepted fresh-context GLM-5.2 fallback used 11,881 input and 329 output
  tokens, estimated at `$0.01808100`;
- known metered spend for the complete experiment was at least `$1.13056868`,
  or about `$0.02261` per source record. This includes correction experiments
  and is not a production forecast; one operator-cancelled GLM request has no
  complete usage artifact.

Review artifacts:

- `data/evaluation/tg_qa_canonicalization/real_data_007_fresh_qualification_50_v3_reasoning_review.html`
  contains 5 cards;
- `data/evaluation/tg_qa_canonicalization/real_data_007_fresh_qualification_50_v3_hold_review.html`
  contains 45 cards;
- the two review batches reproduce all 50 source task ids exactly, with no
  overlap or omission;
- `real_data_007_fresh_qualification_50_v3_effective_verifier_results.jsonl`
  contains the five strong results in place of their cheap-screen results and
  retains all cheap holds/failures;
- initial review produced 16 `accept`, 29 record-level `reject`, and 5
  `retry_qwen` decisions. All 27 Qwen-excluded or failed records were rejected;
  among 23 included candidates, 16 were accepted unchanged, five needed a
  material retry, and two were rejected;
- the five strong-model passes produced three unchanged accepts and two
  material retries. The 18 included cheap holds produced 13 unchanged accepts,
  three retries, and two rejects;
- all five retry records were eventually accepted after separate hash-bound
  review: three from the first Qwen retry, one from the second Qwen retry, and
  one from a fresh-context GLM-5.2 fallback;
- `real_data_007_fresh_qualification_50_v3_final_reviewed_results.jsonl`
  contains 21 unique human-accepted records. Its finalization manifest records
  `16 + 3 + 1 + 1` source selections, while
  `real_data_007_fresh_qualification_50_v3_finalization_backlog.jsonl` retains
  the 29 record-level rejects.

Interpretation:

The contour reduced strong-model reasoning to 10% of source records, but two of
five resulting model passes still required material correction. Conversely,
13 of 18 included cheap holds were accepted unchanged. The model routes are
therefore useful for ordering manual work, not for automatic acceptance or
rejection. The operator reported that reviewing this slice was light and
required only about two external lookups, which is useful workflow evidence but
not a statistical quality claim.

The retry path also exposed two operational defects. A Qwen no-reasoning call
configured with a 180-second timeout returned after 551.882 seconds, so the
current client timeout is not a reliable wall-clock deadline. A Qwen3.7 Plus
Anthropic-shaped probe failed after 268.355 seconds because the Go endpoint
required `X-Api-Key`; the generic runner did not provide the endpoint-specific
authentication shape. These failures remain explicit runner-hardening work and
do not change the frozen canonicalization contour.

## Current Blockers

- Mass automatic acceptance is blocked by the two material corrections among
  five strong-model passes and by the absence of a sufficiently large frozen
  human-labeled pass holdout, not by API quota.
- Learned cheap routing is blocked by the absence of independently sampled,
  exact-output-bound human labels. Implicit generator decisions must not be
  treated as ground truth.
- Temporal currentness is unresolved for all 984 current issue clusters even
  though source dates are now available.
- Question-bank promotion lacks real human cluster decisions and reviewed
  reference answer material.
- Semantic retrieval still needs a candidate-generation/reranking design that
  respects exact references, route ambiguity, temporal state, and multi-law
  support.

## Useful Offline Work Remaining

- Review a bounded subset in the temporal-currentness HTML.
- Use retrieval diagnostics to design a non-LLM candidate-generation/reranking
  baseline.
- Keep future inference questions and prompt lessons updated when manual review
  reveals recurring route ambiguity.
- Keep dry-run promotion artifacts private and separate from real human review
  outputs.
