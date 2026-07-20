# Atomic Model Profile Evaluation

## Status

Bounded operator evidence from 2026-07-16. Generated inputs and outputs remain
private ignored artifacts. No model result promotes canonicalization evidence.
This report evaluates direct structured-output calls, not the two-step atomic
runtime added on 2026-07-17.

## Method

Each deployment used its native tracked runtime profile. Transport/schema
conformance was checked first on one three-claim excluded record. Models that
passed conformance were tested on the two activity-gate targets used to qualify
verifier/critic v3:

- `tg-question-canonicalization-task:20338f0eb2122742b0ae` must preserve the
  source-grounded German activity-registration gate;
- `tg-question-canonicalization-task:2ec442161386f8e093f5` must reject that gate
  because an FOP account is mentioned only as a possible document.

The strict Pydantic schema, controller, prompts, and acceptance criteria stayed
fixed. Provider failures, structured-output failures, structural controller
holds, and semantic errors were counted separately. Cost is an uncached
estimate from the dated OpenCode price snapshot, not a billing record. An
unpublished price is reported as `n/a`, never as zero.

## Inventory Boundary

The Go models endpoint returned 20 ids on 2026-07-16. All are accounted for:

- 16 deployments have tracked profiles and live evidence in this report;
- `glm-5.1` was deliberately excluded because its published price equals
  GLM-5.2, so it cannot satisfy the cost-reduction objective;
- `mimo-v2-pro` and `mimo-v2-omni` returned repeatable upstream `400`
  responses on both advertised transports;
- `hy3-preview` returned `model_not_supported`; the alternate endpoint named
  in that error returned an HTML `404`.

The last three ids are provider inventory failures, not model-quality results.
The official Go page does not include them in its current supported-model list.

The official list later visible on 2026-07-17 also named Grok 4.5 and Kimi K3.
They were not part of the captured sweep and have no quality result here. Their
published uncached prices ($2/$6 and $3/$15 per million input/output tokens)
both exceed GLM-5.2 ($1.40/$4.40), so they are outside this cost-reduction
shortlist rather than silently treated as tested. Source:
https://opencode.ai/docs/go/.

Testing these deployments is deferred until the frozen GLM-5.2 two-step
contour produces a material error confirmed by a current hash-bound human
review. That exact record may then become a private ceiling case, provided it
is absent from every active prompt example. Run Grok 4.5 first on that case;
run Kimi K3 only if Grok does not settle the disputed claim. A historical
decision, a no-reasoning disagreement, or an unreviewed plausible objection is
not sufficient to open this expensive stage.

## Results

### Earlier Candidates

| Profile | Tiny conformance | Target evidence | Decision |
|---|---:|---|---|
| DeepSeek V4 Pro reasoning | pass; 50.33 s; 6,139 tokens; $0.01784 | target 1 verifier used 24,151 tokens and $0.07709 but falsely rejected the supported registration gate | reject as replacement |
| Kimi K2.6 reasoning | pass; 180.86 s; 8,073 tokens; $0.02663 | target 1 verifier exceeded 420 s without a result | operationally unqualified |
| DeepSeek V4 Flash reasoning | pass; 23.95 s; 5,324 tokens; $0.00121 | correctly rejected target 2, but critic omitted required spans; falsely rejected the supported gate on target 1 | reject as replacement |
| Qwen3.7 Plus structured | failed | function calling added forbidden `claim_text` fields; native JSON-schema attempt did not preserve the supplied source payload | schema nonconformant |
| Qwen3.6 Plus structured | pass; 10.28 s; 3,207 tokens; about $0.00282 | target-scale verifier echoed 96 forbidden ledger fields; complex critic emitted no claim verdicts | reject as replacement |

Qwen thinking plus forced tool calling was also tested. Qwen3.6 produced no
tool call, matching the SDK warning that structured output is not guaranteed in
that mode. The strict schema was retained; unknown fields were not stripped to
make a model appear conformant.

### Expanded Go Sweep

All ten newly callable profiles passed the three-claim schema gate. That did
not predict target quality or target-scale output conformance.

The exploratory `prompt_json` calls used first-object extraction followed by
strict Pydantic validation. The post-run audit tightened the adapter to require
the whole final response to be one object and added an adapter version to
runtime identity. No `prompt_json` model was promoted, so this can only make
future qualification stricter. Any future retry must use the versioned strict
adapter rather than treating these exploratory passes as promotion evidence.

| Profile | Tiny conformance | Positive target | Later gate and decision |
|---|---|---|---|
| GLM-5 reasoning | pass; 3,289 tokens; 11.5 s; cost n/a | pass; 16,966 tokens; 119.5 s | negative correctly `revise`; positive verifier+critic passed in 31,658 tokens and 181.5 s; functionally target-qualified, price unresolved |
| Kimi K2.5 reasoning | pass; 7,548 tokens; 34.7 s; cost n/a | `hold`; falsely rejected the supported gate; 35,128 tokens | target-quality failure |
| Kimi K2.7 Code reasoning | pass; 3,660 tokens; 33.0 s; $0.00898 | timeout at 420.3 s without result | operationally unqualified |
| MiniMax M2.5 reasoning | pass; 2,926 tokens; 17.8 s; $0.00183 | `hold`; falsely rejected the supported gate; 8,063 tokens; $0.00618 | target-quality failure |
| MiniMax M2.7 reasoning | pass; 2,853 tokens; 16.9 s; $0.00174 | `hold`; falsely rejected the supported gate; 8,527 tokens; $0.00674 | target-quality failure |
| MiniMax M3 reasoning | pass; 3,901 tokens; 17.0 s; $0.00286 | pass; 30,399 tokens; 200.4 s; $0.03284 | negative target timed out at 420.5 s; operationally unqualified |
| MiMo-V2.5 reasoning | pass; 6,091 tokens; 62.2 s; $0.00144 | invalid prompt-JSON after 15,858 tokens and 148.7 s; $0.00388 | target-scale conformance failure |
| MiMo-V2.5-Pro reasoning | pass; 5,912 tokens; 50.5 s; $0.01723 | `hold`; falsely rejected the supported gate; 16,360 tokens; $0.04992 | target-quality failure |
| Qwen3.5 Plus reasoning | pass; 6,759 tokens; 80.0 s; cost n/a | invalid prompt-JSON after 20,653 tokens and 260.1 s | operationally unqualified |
| Qwen3.7 Max reasoning | pass; 5,083 tokens; 55.6 s; $0.02762 | semantically supported all claims, but omitted two mandatory routing spans; `hold`; 14,044 tokens; $0.08434 | negative semantics were correct but spans failed again; as critic it falsely rejected a supported gate outcome; reject and never use for bulk |

Qwen3.7 Max's mixed-profile critic saw only seven high-risk claims after a
passing GLM-5 verifier. It incorrectly rejected the supported registration-
regime desired outcome, changed the run to `hold`, took 96.6 seconds, and cost
$0.05018 for the critic call alone. Its verifier/critic role disagreement is
prompt brittleness, not evidence that an expensive escalation improves this
contour.

### Method Correction

The expanded sweep required each reasoning deployment to produce the final
JSON schema in the same call. That mixes three properties: semantic reasoning,
schema conversion, and target-scale output length. The established two-step
pattern instead asks the first model for a bounded plain-text memo and uses a
separate no-reasoning formatter.

Therefore an invalid JSON response, missing output span, or timeout in this
report disqualifies only the direct one-call profile. It does not disqualify the
same deployment as a reasoning half-stage. A semantically wrong final JSON
verdict is also provisional until the retained reasoning memo shows whether the
error originated in reasoning or in conversion. The measurements and tables
remain valid historical evidence; their earlier replacement decisions must not
be reused as two-step qualification decisions.

### Verbosity And Cost

The per-run uncached estimate is:

`(observed input tokens * input rate + observed output tokens * output rate) / 1,000,000`

This makes model verbosity part of the comparison. MiMo-V2.5 was cheapest on
the tiny record, but failed target-scale JSON. MiniMax M3 was inexpensive on the
tiny record and then generated 26,358 output tokens on the positive target
before timing out on the negative target. Qwen3.7 Max's single positive
verifier cost $0.08434, already slightly more than the complete GLM-5.2
positive verifier+critic control.

GLM-5.2 remains the priced control. The positive verifier+critic used 8,441
input and 15,735 output tokens, costing about $0.08105. With `before_pass`, the
negative verifier used 4,626 input and 22,890 output tokens, costing $0.10719.
Together that is $0.18824.

GLM-5 used 12,570 input and 46,952 output tokens for the equivalent positive
verifier+critic plus negative verifier evidence. At GLM-5.2 rates that would
cost $0.22419, 19.1% more. GLM-5 becomes cheaper only if its proportional rates
are below 84% of GLM-5.2's; with the same $1.40 input rate, its output rate must
be below about $3.63/M. OpenCode publishes no current GLM-5 rate, so a cost win
cannot be claimed.

## Decision

No profile with a published lower price qualified as a direct one-call bulk
verifier/critic replacement. GLM-5 is the only new deployment that passed both
activity-gate directions and the positive critic in that contour, but its
unpublished price and higher observed output volume block an economic
promotion. GLM-5.2 remains the priced direct-output control.

The direct report makes no decision about cheaper reasoning-plus-formatter
pairs. Those pairs require isolated formatter conformance, both activity-gate
targets with retained memos, and a bounded holdout. Until that evidence exists,
the accepted direct GLM-5.2 contour remains the comparison baseline; no new
two-step contour may produce automatic acceptance. Cheap-model non-pass routes
remain repair or human-review evidence rather than record rejection. Qwen3.7
Max remains excluded from bulk on price alone.

### First Two-Step Follow-Up

On 2026-07-17, MiniMax M3 reasoning plus a no-reasoning DeepSeek V4 Flash
formatter completed the 26-claim positive target without a schema failure. The
formatter used 7,291 input and 3,741 output tokens in 22.591 seconds; its priced
portion was about $0.002068. Python derived source offsets from exact quotes and
reported no invalid spans. The controller returned `hold` because four claims
were unsupported and seven supported memo claims lacked one unique exact quote
and were converted to `unresolved`.

The separated memo showed that M3 itself still supported the reviewed-wrong
double-taxation framing and missing-Steuer-ID prerequisite. Therefore M3 fails
this target as a reasoning replacement even though the formatter path works.
DeepSeek's formatter result is one target-scale conformance observation, not a
bulk qualification.

The runtime registry version used by these live calls remains immutable at its
recorded SHA-256. Qualification conclusions live in this report rather than
mutating runtime lineage after the fact.

### Two-Step Shortlist Sweep

On 2026-07-17 the remaining plausible candidates were tested as reasoning-only
verifiers on both activity-gate targets. Every reasoning memo was converted by
the same DeepSeek V4 Flash no-reasoning formatter. Critic and repair were
disabled so that later stages could not mask primary reasoning quality.

| Reasoner | Technical result | Reasoning time, two records | Formatter time / tokens / priced cost | Semantic result |
|---|---|---:|---:|---|
| GLM-5 | completed 2/2; both `hold` | 115.452 s | 31.841 s / 19,592 / $0.003568 | failed: retained the wrong double-taxation and Steuer-ID-prerequisite claims on the positive case and treated a possible FOP-account document as proof of activity on the negative case |
| MiMo-V2.5 | completed 2/2; both `hold` | 77.127 s | 34.196 s / 20,150 / $0.003722 | failed: rejected the required positive activity gate, retained the reviewed-wrong hidden issues, and inconsistently treated candidate text as source evidence on the negative case |
| Qwen3.7 Max | completed 2/2; both `hold` | 241.981 s | 30.004 s / 18,667 / $0.003409 | failed: correctly removed the positive double-taxation issue but retained the Steuer-ID prerequisite and incorrectly grounded activity from the FOP-account document on the negative case |
| Qwen3.7 Plus | completed 2/2; both `hold` | 287.914 s | 31.361 s / 18,639 / $0.003402 | partial only: correctly rejected the negative registration gate, but its positive memo returned `pass` while retaining double taxation, Jobcenter relevance, and the Steuer-ID prerequisite |
| GLM-5.2 control | completed 2/2; one `pass`, one `hold` | 291.794 s | 37.424 s / 20,797 / $0.003862 | failed as a standalone verifier: correctly rejected the negative gate, but returned `pass` on the positive candidate while retaining double taxation, Jobcenter relevance, social-insurance expansion, and the Steuer-ID prerequisite |

The provider did not report reasoning-call token usage for these calls. The
token and cost columns therefore cover only the formatter and every run marks
its cost estimate incomplete. Memo character counts were retained but are not
converted into provider-token estimates because the relevant tokenizer and
hidden-thinking accounting are not observable here.

Qwen3.7 Plus required a new isolated registry because the earlier profile
combined thinking with forced structured output. The immutable registry is
`tg_question_canonicalization_atomic_qwen_two_step_models_v1.json`, SHA-256
`dba6d13e32e57157f5850ebd10527019968f3d93c52bf9377867d6a3601b62ca`.
Qwen3.6 Plus was not rerun: it is older, has a higher published output rate,
and had worse target-scale contract evidence than Qwen3.7 Plus. It is dominated
for the current cost-reduction objective rather than newly disqualified by a
two-step semantic result.

No standalone two-step verifier, including GLM-5.2, passed the reviewed
positive target. Qwen3.7 Plus is the only cheap candidate worth retaining for
diagnostic first-pass experiments because it correctly handled the negative
gate. Its positive false pass prevents promotion, and model agreement must not
turn into record-level `reject`.

### Two-Step Critic Role Check

The positive target was then used to test whether the adversarial critic role,
rather than the base verifier role, could recover the reviewed errors. Both
semantic calls used explicit reasoning and both formatter calls used DeepSeek
V4 Flash with reasoning disabled.

- GLM-5.2 verifier plus Qwen3.7 Plus critic completed in 265.425 seconds. The
  Qwen critic changed its memo route to `revise`, but only challenged the
  speculative §24 reference. It retained double taxation, Jobcenter relevance,
  social-insurance expansion, and the Steuer-ID prerequisite. The final `hold`
  was therefore not a target-quality pass.
- GLM-5.2 verifier plus GLM-5.2 critic completed in 213.972 seconds. The critic
  noticed that the source did not support treating Steuer-ID as a registration
  prerequisite, but its own route was `pass`; it retained double taxation and
  Jobcenter relevance. This also failed the target-quality criterion.

The formatter-only usage was respectively 20,646 tokens / $0.003697 and 21,594
tokens / $0.003842. Reasoning usage remained unavailable, so total costs are
incomplete. The mixed critic registry is
`tg_question_canonicalization_atomic_glm52_qwen37_critic_v1.json`, SHA-256
`be4da1b7fc6823e7544180683bd2361ecc25a25248d903d3bb1933f6e1d8caaa`.

This changes the immediate optimization decision. Model substitution is no
longer the next lever: verifier/critic v4 task framing must first pass the
GLM-5.2 positive control. Until then, the new two-step semantic contour is
diagnostic review evidence only. DeepSeek V4 Flash remains the successful
schema-conversion component; the older accepted direct GLM-5.2 contour remains
the operational comparison baseline, not proof that v4 two-step semantics are
qualified.

## Safe Simplification

The critic policy may be `before_pass`: run the independent critic only when
the deterministic primary controller would otherwise return `pass`. A primary
`revise` or `hold` cannot be promoted without repair, so a critic at that point
does not protect an acceptance decision. After repair, the same rule runs the
critic before any `pass_repaired` result.

On the negative GLM target, the primary verifier already returned `revise`.
The live `before_pass` run preserved terminal `hold`, recorded one verifier
call and an explicit critic skip, and used 27,516 tokens, 193.445 seconds, and
an estimated $0.10719. The earlier always-critic run used 51,205 tokens,
403.707 seconds, and an estimated $0.19027. Generation is nondeterministic, so
the whole-run difference is not purely critic cost; the avoided critic itself
accounted for 17,452 tokens, 113.009 seconds, and approximately $0.05564 in the
earlier run. On the positive target, the primary route was `pass`, so the critic
still runs. This preserves the reason the critic was introduced while removing
calls that cannot approve a record.

## V6 Relation Contract And Guarded Triage

On 2026-07-17 verifier and critic v6 moved field ownership and four relation
preflight decisions to the beginning of each memo. It also defined compound
normalized wording as a relationship rather than neutral context and required
one contiguous exact source quote. No private task text or examples were added
to the prompt profiles.

The GLM-5.2 reasoning control passed both reviewed directions:

- positive target: verifier and critic independently preserved the grounded
  German activity gate and rejected the Jobcenter eligibility condition,
  double-taxation mechanism, and Steuer-ID prerequisite; 278.505 seconds;
- negative target: both rejected activity grounded only by a possible FOP
  account document; the critic also removed an ungrounded foreign-registration
  condition from a compound tax claim; 398.803 seconds.

The summaries reported 71,787 tokens across the two runs, but reasoning usage
was omitted by the endpoint. Their cost estimates cover observed priced calls
only and remain incomplete. V6 is therefore the active atomic prompt contract,
not a bulk cost baseline.

### Cheaper V6 Candidates

| Contour | Technical result | Semantic result | Decision |
|---|---|---|---|
| Qwen3.7 Plus reasoning verifier + Flash formatter | 2/2 completed; 272.792 s | fixed the positive target, but inferred activity from the FOP-account document on the negative target | review triage only |
| MiniMax M3 reasoning verifier + Flash formatter | positive completed; 167.859 s | retained Jobcenter and double-taxation relations despite a correct preflight | reject replacement; negative not rerun |
| DeepSeek V4 Flash direct no reasoning | one completion and one exhausted schema failure; 52.178 s | completed record falsely passed all three positive relations | reject semantic role |
| GLM-5.2 direct no reasoning | 2/2 completed; 68.371 s; 16,131 tokens; $0.0441084 | one correct negative route and one false positive pass | unsafe without guards |
| GLM-5.2 no-reasoning verifier + no-reasoning critic `before_pass` | 2/2 completed; 95.988 s; 25,222 tokens; $0.0641108 | critic caught only the Steuer-ID relation | reject final boundary |
| GLM-5.2 no-reasoning verifier + reasoning critic escalation | 2/2 completed; 552.657 s | positive corrected, but both stages falsely grounded the negative activity gate and emitted `pass` | reject final boundary |

The last result is decisive: a better role prompt and an independent reasoning
critic do not make the foreign-activity gate stable across repeated calls.
Model agreement cannot be treated as source grounding.

### Controller V5

Controller v5 adds fail-closed guards for the four reviewed relation classes.
It never changes a model verdict or authorizes repair. It only blocks an
otherwise possible pass and records the conflicting claim and guard ids.
Offline replay changed both observed false passes to `hold` while preserving
existing `revise` routes. A fresh two-target no-reasoning run then produced two
holds in 107.348 seconds, 17,049 tokens, and $0.0481416.

The guarded no-reasoning profile was extended to the first 12 records of the
valid v22 GLM-5.2 calibration evidence. It completed 12/12 with no provider
failure in 302.916 seconds, used 66,873 tokens, and cost $0.1767462. Routes were
six `pass` and six `hold`. Manual inspection found five plausible passes and
one disputable central-question selection. This is insufficient for automatic
acceptance but useful for prioritizing review.

The deterministic pre-LLM risk selector found one relation-risk record among
all 50 v22 calibration records (2%). Its precision is useful, but that rate is
too small to be the main cost reduction. It should bypass cheap verification
for known risks, while the remaining low-risk queue still requires a verifier
or human review.

On the current 985-record legacy diagnostic dataset, controller v5 selected 18
records (1.83%): ten child-benefit/Jobcenter records, five cross-border-tax
mechanism records, and three foreign-activity actor/action records. Match counts
can overlap within one record. The source dataset lacked strict modern identity,
so the diagnostic input was reconstructed by an exact one-to-one `task_id` join,
marked `legacy_identity_unverified`, and given derived evidence hashes. It is
not import or promotion evidence.

The first three selected records were then run through two frozen v6 contours:

- GLM-5.2 reasoning plus Flash formatting completed 3/3 in 584.625 seconds,
  used 75,208 tokens, and cost $0.21734004. Every primary model route was
  `revise`; no critic call was needed;
- guarded GLM-5.2 without reasoning completed the same 3/3 in 53.305 seconds,
  used 14,798 tokens, and cost $0.0379372. Its model routes were one `hold`, one
  `pass`, and one `revise`; the deterministic controller blocked the pass;
- the two verifiers agreed on only 36/49 claim support labels (73.5%). Final
  `hold` agreement therefore does not mean semantic equivalence.

The no-reasoning run was then resumed across all 18 selected records. It
completed 18/18 in 383.907 request seconds, used 90,300 tokens, and cost
$0.235275. The model itself emitted ten `pass`, seven `revise`, and one `hold`
routes. Controller v5 blocked all ten passes, found guard conflicts on 17
records, and produced 18 terminal holds without invoking the critic. The one
remaining record was already revised by the model.

This full run confirms that a semantic call merely to rediscover a known
deterministic conflict is not justified. Without the controller, the cheap
model would have passed more than half of this selected queue. Send known-risk
records directly to human review. The low-risk queue has only avoided four
known guards and still needs review or separately qualified triage.

## Current Decision

- Keep verifier/critic v6 and controller v5 as the bounded atomic diagnostic.
- Keep DeepSeek V4 Flash as the no-reasoning schema formatter.
- Use GLM-5.2 no reasoning only for guarded review triage canaries.
- Send deterministic relation-risk records directly to human review. Strong
  reasoning may assist a concrete disputed claim, but a semantic call merely
  to rediscover the guard adds cost without changing the trust boundary.
- Do not promote Qwen3.7 Plus, MiniMax M3, DeepSeek V4 Flash, no-reasoning
  GLM-5.2, or the mixed escalation contour as an automatic acceptance boundary.
- Before any mass use, label a broader pass holdout and estimate false-pass
  rate, pass fraction, tail latency, and cost per reviewed record.

## Compact Memo Cost Experiment

Verifier v7 and v8 are immutable diagnostic profiles; v6 remains active. They
retain the v6 field and relation audit but ask the semantic model to define each
exact source quote once and reference quote ids from one compact line per
claim. DeepSeek V4 Flash expands that memo into the existing strict schema.
This changes neither the controller nor the human-review boundary.

An offline representation check over the 12-record direct GLM canary reduced
serialized verifier output from 94,032 to 22,994 characters (24.5%) by
deduplicating quotes and deriving materiality and routing. This is a design
ceiling, not measured token savings from a provider call.

The live results were mixed:

- v7 handled both activity-gate targets but routed 11/12 holdout records to
  `hold`; it incorrectly required literal source vocabulary for authority and
  routing classifications;
- v8 corrected that field-role error and handled both targets. With complete
  post-fix usage, the positive target cost $0.01411124 versus $0.019883 for
  direct GLM, and the negative target cost $0.01517744 versus $0.0242254;
- the first v8 holdout completed 12/12 in 298.142 seconds with two passes and
  ten holds, but one pass was the already disputable central-question case;
- the repeated v8 holdout completed 11/12 in 359.700 seconds, cost $0.13037052
  including the failed record, and produced one pass and ten holds. One Flash
  formatter response repeated the same invalid object after retry;
- Qwen3.7 Plus without reasoning plus Flash completed only one of the two
  targets. The completed record used candidate wording as source evidence, and
  the other formatter call exhausted 8,192 tokens.

At the observed 12-record averages, direct guarded GLM would extrapolate to
about $14.51 for the current 985-record contour, while repeated v8 would be
about $10.70 including its failed record. The apparent whole-corpus saving is
only about $3.81 and is not a forecast: generation, failure rate, and record
length vary. It does not justify lower completion reliability or weaker review
selection.

The compact GLM contour is cheaper on the two target records but is less useful
as a review selector and less operationally stable than direct guarded GLM.
Keep v7/v8 inactive. They do not replace active verifier/critic v6 or authorize
automatic acceptance. A future compact schema should be parsed directly by
Python instead of asking a second model to re-expand repetitive JSON, but only
after a reviewed claim-level benchmark exists.

The experiment also exposed a telemetry defect: plain LangChain `AIMessage`
objects were ignored by the usage extractor, which previously handled only
structured `{raw, parsed}` wrappers. Future runs now retain plain-message token
usage and can produce complete mixed-stage cost estimates. Historical
incomplete estimates remain unchanged because raw provider metadata was not
stored.

## Fresh Qualification Slice

On 2026-07-17 a predeclared stable-hash sample of 50 records used seed
`tg007-fresh-qualification-2026-07-17-v1`. Its selected task-id hash is
`dcf6eb6275c22aea26a1b4468a2a1d0e6149a194c6e0b0decb9dcecfb6b642b9`.
It has zero overlap with the prompt-regression registry and the previous v22
50-record calibration slice.

- Qwen3.6 Plus with frozen canonicalizer v22 completed 50/50: 24 included and
  26 excluded, with no provider or schema failures.
- Controller v5 found zero known relation-risk records, so all 50 entered the
  low-risk diagnostic queue.
- No-reasoning GLM-5.2 plus the Flash formatter completed 50/50 and emitted 23
  potential passes and 27 holds. It used 425,367 tokens. The recorded cost is
  `$0.4589889`, but remains explicitly incomplete because one retried provider
  attempt omitted complete billable usage.
- All 23 potential passes entered the frozen GLM-5.2 reasoning verifier/critic
  contour. It completed 23/23 with 21 passes and two repaired passes, used
  609,752 tokens, and has a complete `$1.24062926` uncached estimate.
- The measured reasoning escalation share is therefore 23/50, or 46%. This is
  a routing measurement, not an error rate or an acceptance qualification.

The fact that the reasoning contour retained every cheap potential pass is not
quality evidence. Hash-bound human review of all 50 records is the next gate.
Two separate review surfaces preserve the exact result used for each decision:
the 23 reasoning results and the 27 cheap holds. A material reviewed GLM error
may become a private expensive-model ceiling case; no such error is confirmed
yet.

## Fresh Qualification V3 Reviewed Outcome

The 2026-07-19/20 fresh 50-record slice completed identity-bound human review
and finalization:

- Qwen3.6 Plus included 23 records. Sixteen were accepted unchanged, five
  required a material retry, and two were rejected. All 27 excluded or failed
  records were also rejected at record level;
- the cheap verifier routed 18 included records to `hold`; manual review
  accepted 13 unchanged, retried three, and rejected two;
- the strong reasoning contour returned `pass` on five records; manual review
  accepted three unchanged and retried two. A 3/5 exact-accept result is both
  too small and materially too weak for automatic promotion;
- reviewed retries recovered all five correction cases. Three were accepted
  after one Qwen retry, one after a second Qwen retry, and one only after a
  fresh-context GLM-5.2 fallback. Finalization therefore contains 21 accepted
  records and an explicit 29-record reject backlog;
- strong-model reasoning was used on 5/50 source records. The final disputed
  fallback used GLM-5.2 without reasoning and still took 545.552 request
  seconds, showing that no-reasoning mode does not guarantee bounded latency;
- known metered spend was at least `$1.13056868`, about `$0.02261` per source
  record, including the correction experiments but excluding one cancelled GLM
  request without complete usage. This is an experiment cost, not a projected
  steady-state batch price.

The practical result is narrower than automatic qualification but still
useful: cheap generation plus selective reasoning made manual review light,
with the operator reporting only about two external lookups for 50 cards. The
route labels did not separate acceptable from unacceptable records reliably;
they only ordered review. Keep human acceptance as the sole promotion boundary
and collect a larger, independently sampled pass holdout before revisiting any
automatic-pass proposal.

## Architecture Decision

The current evidence favors a selective pipeline over a recursive agent loop:

1. run deterministic schema, identity, exact-span, and relation-risk checks;
2. send known relation risks directly to human review, with strong reasoning
   available only as evidence for a concrete dispute;
3. use one guarded no-reasoning pass only to prioritize the remaining review
   queue, never to accept a record;
4. invoke a reasoning verifier or critic only for a concrete disputed claim or
   a potential acceptance decision;
5. preserve imported human review as the sole promotion boundary.

The expensive-model branch is also human-triggered. Grok 4.5 and Kimi K3 stay
outside the runtime registry until a hash-bound review confirms a material
false pass or false hold from the frozen GLM-5.2 contour. They are ceiling
diagnostics for an individual disputed record, not bulk cascade stages.

Any future automatic-pass proposal must predeclare an acceptable false-pass
rate and confidence level. For example, demonstrating a one-sided 95% upper
bound below 1% with zero observed material false passes requires at least 299
independently human-reviewed passes under one frozen prompt, controller, model,
and runtime profile. Twelve records cannot support that claim.

## Label Readiness

The existing decision artifacts are not a training or qualification benchmark
for a learned router:

- the two current 1,000-record decision ledgers contain 1,995 decisions inferred
  from the generator's inclusion/exclusion route and only five human decisions,
  all rejects. An inferred first-pass route is an input feature, not truth;
- the 80-record adjudication review set contains 43 `retry_generator`, 35
  `reject`, and two `accept` decisions. All 80 were selected for verifier
  non-accept, and 70 also had verifier disagreement, so its class prevalence
  and measured error rates are intentionally selection-biased;
- the older 50-record review file contains 26 `accept` and 24 `reject`
  decisions, but neither it nor the 80-record set binds each decision to the
  exact rendered review payload and canonicalization evidence hash. The
  historical candidate output cannot therefore be reproduced unambiguously.

Do not relabel these artifacts heuristically or mix them into train and test
sets. A router/NLI benchmark must be sampled independently, bind every manual
decision to task id, candidate id, exact evidence hash, prompt/runtime/controller
identity, and keep a frozen untouched test split. Claim-level material-error
labels are additionally required before calibrating a negative NLI filter.
Until then, learned routing is blocked by label quality rather than model
availability. The next mass-processing step is label collection, not another
provider sweep.

Use the seeded `stable_hash` canonicalization sampling policy for that frozen
qualification population. Keep balanced topic/status sampling for defect
discovery only. The statistical denominator is the number of independently
reviewed potential passes, not the requested source-sample size.

This is consistent with cascade work such as
[FrugalGPT](https://arxiv.org/abs/2305.05176) and
[RouteLLM](https://arxiv.org/abs/2406.18665), but those learned routers require
substantially more task-specific preference or correctness labels than the
current artifacts provide. Do not train a router from the current ledgers or
biased review sets.

[Early-abstention cascade research](https://arxiv.org/abs/2502.09054) also
supports terminating a cascade before an expensive model when the eventual
route is already abstention. Controller v5 risk splitting is the deterministic
version of that pattern here: known conflicts go to human review without an
LLM call. Its published benchmark gains are not legal-domain estimates and are
not used in the local cost calculation.

[Chain-of-Verification](https://arxiv.org/abs/2309.11495) motivates independent
verification questions; v6 relation preflight already implements their useful
part. Repeated self-critique is not an independent oracle. Research on
[intrinsic self-correction](https://arxiv.org/abs/2310.01798) reports that it
can degrade reasoning without external feedback, while
[mistake-location experiments](https://arxiv.org/abs/2311.08516) show that
models correct more reliably after the error location is supplied. Controller
v5 therefore contributes more than another unconstrained critic: it identifies
the relation and blocks the pass before asking for correction.

Do not replace this with majority voting. A 2026 study of nine judges found
only about two effective independent votes because their errors were correlated
([Apple Machine Learning Research](https://machinelearning.apple.com/research/correlated-llm-evaluation-panels)).
Likewise, keep deterministic claim ids instead of adding an LLM decomposition
stage: decomposition can improve verification but also introduces its own
noise ([Decomposition Dilemmas](https://arxiv.org/abs/2411.02400)). Semantic
entropy is a possible uncertainty diagnostic, but its published black-box form
uses repeated generations and explicitly does not catch systematic errors
([Nature 2024](https://www.nature.com/articles/s41586-024-07421-0)); that is a
poor fit for the stable relation mistakes observed here.

The next genuinely cheaper architecture experiment is an offline multilingual
NLI or small-classifier negative filter over the deterministic claim ledger.
It may emit only `hold`/escalation signals and must be calibrated on human claim
labels. It cannot emit `pass` or replace exact-source and relation guards.
