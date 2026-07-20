# Atomic Verify And Repair Contour

## Status

Optional operator-managed diagnostic contour. It does not replace the existing
canonicalizer, verifier/adjudicator review inputs, review-decision import, or
finalization workflows.

## Purpose

Detect unsupported relationships inside otherwise schema-valid legal-question
canonicalization evidence. The contour targets errors such as:

- a source fact becoming an eligibility condition;
- an inferred premise becoming an explicit fact;
- a broad request becoming a specific benefit program;
- a tax-liability question becoming an unsupported legal mechanism;
- a missing-context record being forced through a prerequisite gate.

## Workflow

```text
completed canonicalization evidence
  -> deterministic field claim ledger
  -> independent atomic verifier reasoning
  -> optional no-reasoning schema formatter
  -> optional independent critic reasoning
  -> optional no-reasoning schema formatter
  -> deterministic conservative verdict merge
  -> deterministic span and claim-id controller
  -> pass | hold | one minimal repair reasoning
  -> optional no-reasoning repair formatter
  -> deterministic deletion of unsupported list atoms
  -> rebuilt claim ledger
  -> independent atomic re-verification and optional critic
  -> pass_repaired | hold
```

The generator's hidden reasoning and free-text memo are not passed to the
verifier or critic. Inside one verifier, critic, or repair stage, an explicitly
requested bounded plain-text decision memo may pass to a separately configured
no-reasoning formatter. The formatter also receives the original compact stage
payload, treats the memo as untrusted, and emits the strict schema. Native
hidden `reasoning_content` is neither used as the memo nor passed across the
boundary. The critic receives the source, selected claims, and prior structured
verdicts as untrusted hypotheses; it never receives the verifier memo.

Verifier and critic formatters emit exact quote strings rather than character
offsets. Python accepts only a unique exact occurrence and computes its offsets.
A supported verdict without one resolvable quote is conservatively converted to
`unresolved`; the controller therefore routes it to `hold`.

Controller v5 also applies four narrow deterministic relation guards after
model verdicts. A guard can block a potential `pass`, but it cannot create an
acceptance, change model support, or authorize repair:

- foreign activity or registration claims require an actor-action link near
  the foreign-registration mention; a possible FOP account document is not
  activity evidence;
- a normalized child-benefit claim that also contains Jobcenter is held for
  separate review;
- a double-taxation claim requires an explicit treaty, credit, allocation, or
  double-taxation mechanism in the source;
- a missing Steuer-ID becomes a prerequisite only when the source reports a
  blocked process or an authority requirement.

The separate `tg-qa-canonicalization-atomic-risk-split` command applies the
same checks before any LLM call. It writes unchanged risk and low-risk evidence
queues plus a diagnostic sidecar. These are routing hints, not quality verdicts.
Input records must contain non-empty string `task_id`, `candidate_id`,
`canonicalization_evidence_hash`, and `source_question_text_redacted` fields,
and the evidence hash must match the canonical payload. Dataset or clustering
derivatives that stripped source or identity fail before any output queue is
written.

The 985-record legacy diagnostic split selected 18 records (1.83%). A matched
three-record comparison cost $0.21734004 and 584.625 seconds with reasoning,
versus $0.0379372 and 53.305 seconds without reasoning. Claim-support agreement
was only 73.5%, while the deterministic controller blocked the cheap model's
one semantic pass. This supports direct human routing for known-risk records,
not automatic acceptance of the remaining queue.

The no-reasoning contour then completed all 18 selected records for $0.235275,
90,300 tokens, and 383.907 request seconds. Its model routes included ten
passes; controller v5 blocked every pass and emitted 18 holds without a critic
call. Model execution is therefore omitted from the retained known-risk route.

Controller v6 also carries input `law_code_candidates` into evidence as
optional `untrusted_law_code_hints`. The verifier model does not receive these
hints. If a hint absent from the source question appears verbatim in any
candidate field, the deterministic controller emits
`untrusted_input_hint_reused` and routes the record to `hold`. This is a
provenance guard against prompt leakage, not a judgment that the cited law is
substantively inapplicable.

## Sidecar Contract

The canonicalization result schema remains unchanged. The contour writes a
separate sidecar record containing:

- source canonicalization evidence identity and hash;
- deterministic atomic claims and claim ids;
- initial verifier verdicts and exact source spans;
- optional critic verdicts, merge diagnostics, and claim-level disagreements;
- controller route and reason codes;
- optional repaired canonicalization candidate and deterministic list
  normalizations;
- rebuilt claims and final verifier verdicts;
- per-call runtime metadata;
- optional bounded verifier/critic/repair reasoning memos with raw-text hash;
- prompt, model, backend, and runtime lineage.

Top-level run-summary counts, usage, duration, and cost describe the current
invocation. `cumulative_output_metrics` is recalculated from every record in
the current result JSONL and remains available after a resumed or zero-work
invocation. This prevents a resumed increment from being mistaken for total
run cost.

The sidecar is review evidence only. A repaired candidate is not imported or
accepted automatically.

## Controller Rules

- Every expected claim id must appear exactly once in verifier output.
- Unknown, missing, or duplicate claim ids route to `hold`.
- Every cited quote must match the redacted source exactly. The controller may
  correct offsets only when the supplied start anchors that exact quote or the
  quote occurs exactly once; it records every correction. Missing or ambiguous
  quotes route to `hold`.
- `explicit` and `necessary_inference` verdicts require at least one valid
  source span.
- Any `unsupported` claim routes to `revise` before repair and `hold` after the
  bounded repair is exhausted.
- Any `unresolved` medium- or high-materiality claim routes to `hold`.
- A supported claim that conflicts with a deterministic relation guard blocks
  an otherwise possible `pass` and records the claim and guard ids. Existing
  `revise` and `hold` routes remain non-passing.
- In critic mode, `unresolved` is more conservative than `unsupported`, which
  is more conservative than `necessary_inference`, which is more conservative
  than `explicit`. Structural critic failure routes to `hold`; disagreement is
  retained rather than hidden behind a model vote.
- Only claims identified by controller feedback may drive repair. The repair
  stage must preserve unrelated fields.
- Unsupported list atoms are removed by the deterministic controller and all
  supported list items are preserved byte-for-byte. The LLM cannot replace an
  unsupported hidden issue with a new unverified list item.
- Changed evidence is fully re-ledgered and re-verified. Prior pass verdicts are
  not copied onto changed text.

## Operational Limits

- disabled unless the operator invokes its explicit CLI command;
- one semantic verifier execution per candidate state and, when enabled, one
  independent critic execution per candidate state;
- each semantic execution is either one direct structured call or one
  reasoning call followed by one no-reasoning formatter call;
- zero or one repair execution under the same direct-or-two-step rule;
- no recursive or open-ended loop;
- finite provider retry policy remains separate from semantic repair count;
- every successful or failed provider attempt is retained in per-attempt
  runtime metadata, including its stage, duration, outcome, and available token
  usage;
- completed merged-initial, repair, and final-primary-verifier states are
  written to an identity-bound stage checkpoint before the next expensive
  call, and resume skips those completed stages;
- resume requires identical input evidence and runtime profile identities;
- live calls remain outside default unit tests.

The measured GLM-5.2 operator profile uses native `json_schema`, 32768 verifier
and critic tokens, and 16384 repair tokens. A 16384-token verifier budget
reached a length finish on a 26-claim real record, so it is not the default for
this contour. Critic mode remains an escalation because it materially increases
latency and token use.

The active atomic verifier and critic prompt profiles are v6. They make field
ownership and relation preflight explicit and passed the two reviewed activity-
gate controls with GLM-5.2 reasoning in both roles. This is bounded semantic
evidence, not bulk qualification. The canonicalizer prompt remains v22.

Verifier v7/v8 compact-memo profiles are immutable inactive experiments. They
deduplicate exact quotes before a no-reasoning formatter expands the existing
schema. V8 reduced cost on the two target records, but repeated holdout runs
were over-conservative and one produced a formatter failure after retry. The
compact profiles must be selected explicitly through the prompt-version
environment variable and do not change the v6 default.

## Model-Native Runtime Profiles

The tracked atomic runtime registry defines transport and request semantics per
model deployment. A profile binds provider, endpoint shape, model id,
structured-output method, stage token and timeout limits, temperature, and the
native request parameter object. OpenAI-compatible request parameters are sent
through `extra_body`; Anthropic-compatible parameters use an explicit
constructor allowlist. Unknown Anthropic parameters fail before a live call
instead of being ignored.

Some deployments reject an explicit temperature or all native structured-
output controls. A profile may therefore omit temperature and may select
`prompt_json`. That method requests one JSON object in the prompt, extracts only
the final text blocks, requires their complete content to be either one JSON
object or one JSON fence, and applies the same strict Pydantic schema locally.
It does not scan prose for an embedded object, strip unknown fields, or convert
malformed output into a pass. The structured-output adapter version is part of
stage runtime identity and checkpoint compatibility.

Verifier, critic, and repair may select different profile ids. Omitted critic
or repair profile ids inherit the verifier profile id. Each stage may also
select an explicit formatter profile, which must declare
`reasoning_mode=disabled`; formatter ids do not inherit because a direct
no-reasoning repair must not accidentally become a redundant two-call stage.
The reasoning and formatter profiles, execution mode, and registry hash are
part of runtime identity and checkpoint/resume compatibility. Inactive stage
profiles do not affect run identity. Formatter retries reuse the completed
memo and do not repeat the reasoning call. LangChain SDK retries remain zero so
the operator retry loop records every provider attempt.

Critic policy `always` preserves the original contour. Policy `before_pass`
runs the critic only when the deterministic primary controller would otherwise
return `pass`; it applies the same rule after repair before `pass_repaired`.
Primary `revise` and `hold` routes remain non-passing and therefore skip an
unnecessary critic call. The policy is part of runtime and resume identity.

Price fields are dated snapshots used only for an uncached cost estimate. They
do not claim billing authority, and generated usage artifacts remain the
operational source for observed tokens. Missing rates produce `null`, not zero.
Mixed-stage estimates retain priced and unpriced call counts and are marked
incomplete if any stage lacks a rate or token usage.

Usage extraction accepts both structured LangChain `{raw, parsed}` wrappers
and plain `AIMessage` results from a semantic memo call. This keeps future
two-step cost estimates complete when the provider supplies usage. Historical
runs without captured plain-message usage remain incomplete and are not
backfilled from memo length.

A registry file is immutable once a generated artifact records its content
hash. Qualification outcomes are written to the dated evaluation report; a
configuration change requires a new registry version.

The isolated no-reasoning and mixed-escalation registries are experiment
lineage only. No-reasoning GLM-5.2 is permitted for guarded triage canaries;
reasoning escalation remains bounded. Neither registry enables automatic
acceptance.

The 2026-07-16 direct-structured model gate is recorded in
`atomic-model-profile-evaluation.md`. It did not test the new two-step contour;
JSON and timeout failures from that sweep therefore require a two-step retest
before they can disqualify a reasoning profile. Registry v2 adds explicit
no-reasoning formatter candidates without assigning them qualification status.

## Promotion Boundary

`pass` means only that this verifier contour found no blocking claim-level
issue. Existing human review is still required before finalization. `hold`
records remain backlog evidence and cannot be converted to accepted
canonicalization by this contour.

The guarded no-reasoning canary is not an automatic-pass boundary. On a
12-record v22 holdout it completed every call, routed six records to `pass` and
six to `hold`, and one of the six passes remained manually disputable on central
question selection. Broader reviewed holdout evidence is required before this
profile can be used for anything beyond prioritizing human review.

The selected mass architecture therefore remains deterministic validation and
risk routing followed by human review, with strong reasoning reserved for
specific disputed claims. A cheap model, critic panel, or compact memo may add
review evidence but cannot promote records. A learned router or local NLI
negative filter requires a separate claim-level labeled benchmark and may emit
only escalation/hold signals until qualified.
