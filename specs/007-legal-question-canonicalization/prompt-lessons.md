# Prompt Lessons From Manual Review

This file records compact lessons from manual review reasons that may become
future canonicalizer, verifier, or adjudicator prompt changes. It is not a
prompt profile by itself. Keep entries short, evidence-linked, and generalized.

Do not copy raw Telegram corpus text into this tracked file. Refer to task ids
and summarize the lesson.

Every evidence-linked lesson must also remain represented in
`prompt-regression-cases.json`. A later prompt change is accepted only after the
accumulated regression set is rerun; a smoke test covering only the newest
lesson does not establish that older corrections still work.

## PL-001: Preserve Problematic Or Non-Existent Premises

Evidence:

- `tg-question-canonicalization-task:9128be47d294c4c1f450`
- `tg-question-canonicalization-task:a763836dd3425c7b2c56`

Lesson: If the source asks about a legally impossible or unlawful arrangement,
do not normalize it into a neutral administrative procedure. Preserve the
problematic premise in `canonical_question` or `hidden_issues`.

Examples of premises to preserve:

- fictitious residence or registration;
- living somewhere other than the registered accommodation;
- expected "housing allocation" that does not legally exist in the assumed
  form;
- staying first and regularizing residence/work only later without a clear
  current legal basis.

Prompt implication: The canonical question should ask about permissibility,
legal basis, consequences, or risks of the arrangement, not silently turn it
into a normal application workflow.

## PL-002: Automatic Section 24 Extensions Are Legal Proof Issues

Evidence:

- `tg-question-canonicalization-task:a4c7963852779cb306db`

Lesson: When a third party rejects an expired-looking document despite a general
automatic extension of section 24 protection/residence/work authorization, the
legal issue is not merely "where to get a personal letter". It is whether the
third party must accept the general legal extension/status proof and what remedy
exists if they refuse.

Prompt implication: Mention general legal extension versus individual document
date in `hidden_issues`; keep the refusal by employer, bank, provider, or eID
system as a material fact.

## PL-003: Single Main Legal Question Only

Evidence:

- `tg-question-canonicalization-task:07394709c97ecde3e681`
- `tg-question-canonicalization-task:28d8f24b80290c7adca7`
- `tg-question-canonicalization-task:36605c7aff7841dd4cdd`
- `tg-question-canonicalization-task:6f74dbd8a3aa123c1b5d`

Lesson: Manual review repeatedly rejects canonical questions that combine
several legal questions or preserve too many source sub-questions. Keep one
main legal question. Secondary facts, conditions, and downstream consequences
belong in `facts` or `hidden_issues`.

Prompt implication: When the source contains several legal questions, choose
the one that controls the main legal route or the user's primary desired
outcome. Do not include operational or explanatory sub-questions in
`canonical_question`.

## PL-004: Material Hidden Facts Must Not Be Dropped

Evidence:

- `tg-question-canonicalization-task:e3b770e687da904e55a6`
- `tg-question-canonicalization-task:f9aac53d0a80c80538ad`
- `tg-question-canonicalization-task:1edf40e7edd6028ad0ce`
- `tg-question-canonicalization-task:46695c482b641b454c45`

Lesson: Some source details look secondary but materially change the legal
question. Examples include a concrete future job, roughly equal spouses'
salaries for tax-class choice, a birth certificate requested for tax/payroll
status, or absence from Germany combined with health-insurance cancellation.

Prompt implication: Keep such details in the canonical question when they define
the legal issue; otherwise record them in `hidden_issues` so later retrieval and
review do not miss the decisive condition.

## PL-005: Law Area Corrections Are Often Domain-Specific

Evidence:

- `tg-question-canonicalization-task:7861225eb6f2e7969cd6`
- `tg-question-canonicalization-task:28d8f24b80290c7adca7`
- `tg-question-canonicalization-task:727f89d2d2d9234449ef`
- `tg-question-canonicalization-task:942850b7a6ba64066cad`
- `tg-question-canonicalization-task:7d033f4c0406a5f11479`
- `tg-question-canonicalization-task:9d28951753e98c5ed2e0`

Lesson: Topic hints from the Telegram pipeline often overfit to migration or
employment. Manual reasons identified separate legal domains such as telecom
consumer contract law, traffic/vehicle-registration law, statutory health
insurance, BAMF language-course administration, and eID/eAT rules under
residence law.

Prompt implication: Treat `topic_labels` and `law_code_candidates` as weak
hints. Prefer the legal object and authority named by the source over broad
Telegram topic labels.

## PL-006: German Target Jurisdiction Is The Default Corpus Context

Evidence:

- `tg-question-canonicalization-task:8412b1ff5c37895e4709`

Lesson: In this corpus, third countries named in a message are often facts about
prior stay, documents, family location, or travel. They are not automatically
the target jurisdiction. Unless the source explicitly asks about another
country's law, the target legal system is Germany.

Prompt implication: Keep named third countries in `facts` or `hidden_issues`
when relevant, but do not switch the law target away from Germany solely because
a third country is mentioned.

## PL-007: Old Or Live Information Is Not A Stable Legal Question

Evidence:

- `tg-question-canonicalization-task:00eb8d1093bff40bfe70`
- `tg-question-canonicalization-task:04d6da65cce23a6fba15`

Lesson: Some questions ask about stale policy states or current operational
availability. These are not stable canonical legal questions unless the source
asks about a legal right, legal deadline, legal consequence, or remedy.

Prompt implication: Use `requires_live_operational_data` only when the legal
question is otherwise valid but answerability depends on current operational
state. Exclude purely current capacity/open/available/status questions as
`non_legal_question`.

## PL-008: Asyl And Section 24 Can Be Ambiguous In Ukrainian Refugee Context

Evidence:

- `tg-question-canonicalization-task:095e4b46476f1ae97e13`
- `tg-question-canonicalization-task:36605c7aff7841dd4cdd`

Lesson: Users may use `Asyl` colloquially for refugee registration or protection
in Germany, but asylum procedure and section 24 temporary protection are
materially different legal routes. Do not blindly reinterpret every `Asyl`
mention as section 24, and do not blindly accept it as an AsylG procedure when
the surrounding context suggests early Ukrainian-refugee registration and work
authorization. Ukrainian citizenship alone does not establish eligibility for
section 24; prior residence, displacement circumstances, current status, and
other material eligibility facts may leave Asyl or another route applicable.
Likewise, a previously granted section-24 permit does not by itself establish
current validity or eligibility for automatic continuation: initial protection,
individual renewal, and later automatic continuation are distinct legal
questions whose answer may depend on the relevant date and status history.

Prompt implication: Preserve the source question date and distinguish it from
the date of review or answering. Treat age as evidence that currentness may need
review, not as proof that the question is obsolete. Keep stable generalized
legal issues reusable while flagging transition-bound or superseded branches
for temporal review.

Prompt implication: For canonicalization, preserve the ambiguity in
`hidden_issues` or lower confidence when the source itself does not resolve it.
For live answering, route selection belongs to future clarification behavior,
not to automatic canonicalization.

## PL-009: Review Models May Confuse Source Text With Candidate Fields

Evidence:

- `tg-question-canonicalization-task:6f74dbd8a3aa123c1b5d`

Lesson: Different verifier and adjudicator models may read operational details
from the source question or another verifier's reason as though those details
were still present in `canonical_question` or `legal_issue_frame`. This can
happen even when the prompt contains an explicit field-scope rule and an exact
few-shot example.

Prompt implication: The compact verifier and adjudication payloads repeat the
candidate fields under review in a final `field_scope_review` block. Models
must use that block before claiming that `canonical_question` or
`legal_issue_frame` contains source details. Keep disagreements visible for
model evaluation; do not silently replace semantic judge decisions with local
heuristics.

## PL-010: Prompt Corrections Require Cumulative Regression Controls

Evidence:

- `tg-question-canonicalization-task:04230717c49f5f4b0794`
- `tg-question-canonicalization-task:a0e72a464217a2d9f698`
- `tg-question-canonicalization-task:bb78bd7c608842ac8c21`
- `tg-question-canonicalization-task:0855ba449f60c588eb02`
- `tg-question-canonicalization-task:1f3696ce142780f7df9c`
- `tg-question-canonicalization-task:24fb2e6f4ac91b40db98`
- `tg-question-canonicalization-task:3fa30be0933f606aacbd`
- `tg-question-canonicalization-task:4dcbbe17b2f7e597c1b8`
- `tg-question-canonicalization-task:4e9f8d846a433c3a1cfe`
- `tg-question-canonicalization-task:5002f277b5b6ae0baf5b`
- `tg-question-canonicalization-task:50fccf445151cf7c028d`
- `tg-question-canonicalization-task:69be47c15a3a38a42201`
- `tg-question-canonicalization-task:86c2e4ded3b0c5677fae`
- `tg-question-canonicalization-task:8dd3c08a5614db5b4956`
- `tg-question-canonicalization-task:8e4492eddcad162175e5`
- `tg-question-canonicalization-task:9b4faa877a974acbecd4`
- `tg-question-canonicalization-task:a538b7a31f9c073ddb61`
- `tg-question-canonicalization-task:b93730e9b401180b7e1d`
- `tg-question-canonicalization-task:c25ee8314aa6baeffb4b`
- `tg-question-canonicalization-task:c5c7805c20ca608a6243`
- `tg-question-canonicalization-task:cc701f70bf2385fd125c`
- `tg-question-canonicalization-task:cf23f6be6ca1b53f8433`
- `tg-question-canonicalization-task:e279f6cac114c53a3174`
- `tg-question-canonicalization-task:e63232d2e9100417355f`
- `tg-question-canonicalization-task:f3db842a29413447527d`
- `tg-question-canonicalization-task:f84c01f87a432bc81f30`

Lesson: Records previously selected for targeted prompt smoke tests or broad
prompt A/B controls remain useful after the immediate experiment. A later
prompt can regress on an older boundary even when it fixes the newest example.

Prompt implication: Keep all historical targeted and control records in the
cumulative prompt-regression registry. Evaluate the full accumulated set before
accepting a prompt change.

## PL-011: Future Legal Trigger Is Not Live Operational State

Evidence:

- `tg-question-canonicalization-task:27bde86910c8c3e7bb23`

Lesson: A hypothetical future event can still define a stable legal question.
Asking whether a status, entitlement, obligation, or document remains valid if
its underlying circumstances change is different from asking what is open,
available, or accepting people today.

Prompt implication: Include questions about the legal consequence of a stated
hypothetical trigger. Keep `requires_live_operational_data` for answers that
depend on changing operational facts rather than legal consequences.

## PL-012: Preserve The Strength Of The Explicit Source Request

Evidence:

- `tg-question-canonicalization-task:04d6da65cce23a6fba15`
- `tg-question-canonicalization-task:50fccf445151cf7c028d`
- `tg-question-canonicalization-task:69be47c15a3a38a42201`

Lesson: A canonicalizer can create a plausible legal issue that is stronger
than the source author's actual request. Practical questions about where people
are housed or whether temporary shelter is available remain operational unless
the source explicitly asks about a legal right, criterion, procedure,
consequence, or remedy. A confirmation fragment remains non-standalone when its
meaning depends on an unstated prior event or procedure.

Prompt implication: Build the canonical question from explicit source intent.
Keep plausible legal distinctions in `hidden_issues` only after the source
contains an included standalone legal request.

## PL-013: Verifier Must Respect Field Ownership And Central Selection

Evidence:

- `tg-question-canonicalization-task:883e4b7d89874ec48ba5`
- `tg-question-canonicalization-task:ac144f6d03d44b2949f1`
- `tg-question-canonicalization-task:d1b3941f46c446d1da47`
- `tg-question-canonicalization-task:e8db88759a2a7322b705`

Lesson: Review models can incorrectly judge source-level flags from the already
cleaned canonical question, require one selected canonical question to preserve
every other legal question in the source, or ignore that a candidate invented
an obligation, consequence, or remedy absent from the source.

Prompt implication: Evaluate `quality_flags` against the source and
canonicalization process they describe. Accept selection of one central legal
question from a multi-question source. Treat an obligation together with its
explicit direct consequence or remedy as one integrated legal issue when the
clauses belong to the same legal relationship, while rejecting consequences
invented beyond the source request. Count substantive requests when assigning
source-composition flags; greetings, thanks, politeness, and conversational
framing without a separate request are neutral framing rather than a
non-legal query. Keep the source-composition definitions in the versioned
output schema and contrast them with few-shot examples; a general instruction
alone did not reliably separate `multiple_legal_questions` from
`mixed_with_non_legal_query`. Include both sides of the contrast: multiple
legal requests without a non-legal request, and a legal request accompanied by
a separate operational request about current practice or recent experiences.

## PL-014: Adjudicator Must Preserve Review Semantics And Operational Routing

Evidence:

- `tg-question-canonicalization-task:5c1f820459067746d5e9`
- `tg-question-canonicalization-task:bf9d449f72a9213d681e`
- `tg-question-canonicalization-task:d759b2ac5a746d4e10fe`
- `tg-question-canonicalization-task:fbdcf57f55b80f9b63fb`

Lesson: Final judges can repeat verifier errors even when they agree with each
other. In particular, they may judge source-level `quality_flags` only from the
cleaned canonical question, or convert live intake and document-identification
questions into hypothetical legal questions.

Prompt implication: Keep adjudicator field ownership aligned with the verifier.
Preserve source-level mixed and multiple-question flags after successful
selection. Accept exclusion of live intake/capacity and visual document-
identification questions unless the source explicitly asks for a legal rule,
effect, deadline, consequence, or remedy.

## PL-015: Unanimous Review Evidence Can Still Violate The Contract

Evidence:

- `tg-question-canonicalization-task:aca51e8e5d6edd7b10f1`
- `tg-question-canonicalization-task:bf9d449f72a9213d681e`
- `tg-question-canonicalization-task:fbdcf57f55b80f9b63fb`

Lesson: Multiple review models can anchor on each other's shared interpretation
and unanimously rewrite an operational source into a hypothetical legal
question. They can also accept an included candidate while identifying a
quality flag that would misroute downstream filtering.

Prompt implication: Treat verifier votes as evidence rather than authority.
Preserve operational exclusion when the source asks only about current intake,
distribution, or ordinary issuance timing. For included records, retry a
clearly inaccurate quality flag when it affects downstream filtering.

## PL-016: Source Authority Options Are Claims, Not Ground Truth

Evidence:

- `tg-question-canonicalization-task:af824a5eb347e19602f6`

Lesson: When a source asks whether an incorrectly named authority is competent,
a retry can replace one false authority option with another false option from
the source. Preserving the user's uncertainty does not require presenting the
named authority as a legally valid alternative.

Prompt implication: Canonicalize the criterion for determining the competent
authority when named options are unverified. Preserve the mistaken option only
as a fact or hidden issue, and keep `authority_context` limited to supported
authorities or a neutral competent-authority role.

## PL-017: Expected Focus Needs Machine-Checkable Field Contracts

Evidence:

- `tg-question-canonicalization-task:07394709c97ecde3e681`
- `tg-question-canonicalization-task:36605c7aff7841dd4cdd`
- `tg-question-canonicalization-task:6f74dbd8a3aa123c1b5d`
- `tg-question-canonicalization-task:727f89d2d2d9234449ef`
- `tg-question-canonicalization-task:095e4b46476f1ae97e13`
- `tg-question-canonicalization-task:0855ba449f60c588eb02`
- `tg-question-canonicalization-task:a538b7a31f9c073ddb61`

Lesson: A cumulative run can satisfy routing and output-shape checks while
violating the natural-language `expected_focus`. Typical failures include
choosing a secondary legal object, silently resolving an ambiguous route,
selecting `law_area` from refugee context, or assigning a quality flag without
the source premise required by that flag.

Prompt implication: Put material field ownership and selection rules in the
versioned output schema and contrastive examples. Encode stable expectations as
machine-checkable registry invariants rather than relying on manual reading of
`expected_focus`. Distinguish current official legal rules from current
operational state: a dated legal restriction is not itself live operational
data. Treat a separate ordinary duration or difficulty request accompanying a
legal question as mixed operational content. Resolve ambiguous abbreviations
from the surrounding legal topic and corpus context, and protect material
resolved meanings with evidence-term invariants. Treat separate funding,
language, tax-jurisdiction, and similar requests as distinct issues when
selecting one central canonical question, even when they are legally related to
the selected access, eligibility, or status-compliance issue.

## PL-018: Law-Code Hints Are Not Citation Evidence

Evidence:

- `tg-question-canonicalization-task:2ba9156e4de45257e559`
- `tg-question-canonicalization-task:5b80007c046785dceec8`

Lesson: A weak upstream `law_code_candidates` hint can combine with an informal
section-number mention and create a precise but false citation. In this case,
the source said only "24 paragraph", the hint supplied `AsylG`, and the
canonical question incorrectly emitted `§24 AsylG` instead of the Ukrainian
temporary-protection context under `§24 AufenthG`.

Prompt implication: Use `law_code_candidates` for topical routing only. Treat
the source text and resolved legal context as citation evidence; preserve
uncertainty when they do not establish the law code. Review any law code that
appears only in the canonical question before using it as a retrieval target.

## PL-019: Foreign Registration Does Not Resolve German Work Classification

Evidence:

- `tg-question-canonicalization-task:20338f0eb2122742b0ae`
- `tg-question-canonicalization-task:2ec442161386f8e093f5`

Lesson: When a person lives in Germany and physically performs remote work from
Germany through a Ukrainian FOP or another foreign self-employment vehicle, a
benefit, health-insurance, or foreign-tax question can obscure the threshold
German classification and registration issue. Foreign registration or tax
payment does not by itself establish how the activity must be treated in
Germany.

Prompt implication: Apply a mandatory foreign-activity gate when the source
shows activity performed physically from Germany through a foreign business
registration while German classification and registration remain unresolved.
Select applicable German registration duties as the central issue and preserve
tax, benefit, insurance, contribution, and proof questions as downstream
issues. Resolve the applicable route among tax registration, Gewerbe,
professional or freelance activity, social insurance, and residence law.
Treat foreign tax payment as a fact; add treaty or foreign-tax-credit analysis
when the source explicitly requests that mechanism.
Keep a statement that an authority was not contacted as a source fact rather
than an eligibility condition unless source evidence establishes that
dependency. Phrase social-insurance treatment in Russian evidence as the legal
regime of social insurance rather than a literal translation of
`treatment`.

## Research Note: J-Space And Instruction Focus

Sources:

- https://www.anthropic.com/research/global-workspace
- https://www.anthropic.com/research/introspection

Anthropic's J-space experiments indicate that concepts named in instructions
can enter a small, reportable workspace used for deliberate reasoning. A
negative instruction reduced activation of the named concept relative to a
positive instruction, but still raised it above an unmentioned baseline.
Direct positive instructions produced stronger deliberate control of the
target representation.

Prompt-design implication: State the desired decision procedure and target
concepts first. Use short negative directives for high-cost, concrete failure
modes when they are clearer than a positive equivalent. Keep such directives
few, avoid duplicated catalogs across instruction, schema, and examples, and
validate the effect empirically on the deployed model.

Scope: These experiments concern Claude models and internal activation
measurements. Their application to GLM is a testable prompt-design hypothesis,
not an established cross-model law.

Local GLM smoke result: naming a failure concept in a short negative directive
did not reliably suppress it. Removing the concept entirely from the next
compact profile also did not suppress it when the source facts semantically
suggested the same association. Attention-aware wording can reduce prompt-side
priming, but it cannot replace source-grounded output invariants, retry routing,
or human review for legally material unsupported inferences.

## PL-020: Distinguish Native Reasoning From Visible Analysis Prose

Evidence:

- private two-item GLM-5.2 `analysis_json` diagnostic
- private two-item GLM-5.2 `analysis_critic_json` diagnostic
- private one-item GLM-5.2 native-thinking high-budget probe

Lesson: Asking the model to emit a long decision memo is not equivalent to
enabling the provider's native reasoning mode. The OpenCode GLM-5.2 endpoint
returns `reasoning_content` both when `thinking.type=enabled` is explicit and
when the parameter is omitted, so the endpoint currently enables native
thinking by default. Completion-token usage includes this hidden reasoning,
but the endpoint does not report a separate reasoning-token count.

A low completion limit can therefore truncate a reasoning call before its
visible structured result. Use an explicit thinking setting for reproducible
runs, allocate a reasoning-stage completion budget comfortably above the input
size, and record whether reasoning metadata was observable. Do not record zero
reasoning tokens when the provider omitted the token breakdown; record the
metric as unavailable.

The high-budget probe completed, but it retained the same unsupported
Jobcenter-to-child-benefit relationship and foreign-tax mechanism. More tokens
fixed the experimental truncation and did not fix the semantic failure. A
free-text critic detected material unsupported relationships in an earlier
probe, while the final formatter ignored its repairs. A production multi-stage
contour therefore needs an enforceable typed verdict and controller branch,
not merely additional reasoning prose appended to the formatter context.

Full private reasoning capture localized the failure to the first analysis
pass. The model formed the Jobcenter-to-benefit relationship before producing
the memo. It also renamed a question about possible German tax liability as a
double-taxation mechanism and then treated that renamed mechanism as explicit
source evidence. In a separate evidence-status drift, activity performed from
Germany began as an inference and was promoted to an explicit fact in the
memo. The JSON-stage reasoning only checked the memo against the prompt and did
not independently recheck those relationships against the source.

Controller implication: a critic must receive the original source and audit
relationships, not only fields. Its typed result must separately cover causal
dependencies, eligibility conditions, legal mechanisms, and evidence-status
changes. A `revise` verdict must prevent formatter execution until a corrected
plan passes or the item is routed to review.

Preserved-reasoning diagnostic: the OpenCode GLM-5.2 endpoint returns
`reasoning_content`, but its request validator rejects both the documented
nested `thinking.clear_thinking` form and a top-level `clear_thinking` field.
Passing the generator reasoning as ordinary untrusted text was accepted but
anchored the critic to the generator's errors: it returned `pass` and repeated
the unsupported relationships. An independent critic on the same source and
memo was more effective.

The independent critic improved after its contract required exact
`facts_only_context_terms` and `unsupported_terms_to_remove`, but repeated runs
showed that the model did not populate those lists reliably. The stable contour
combines LLM review with deterministic contract enrichment from source terms
and field-scoped checks. For example, an authority-contact term can remain in
`facts` while being forbidden in benefit-eligibility fields, and an unsupported
tax mechanism can be rejected without removing the foreign-business terms
needed by the central registration issue. A failed check enters an explicit
repair branch; a remaining violation fails the item instead of promoting it.

On the target record this contour removed authority-contact and employment
context from the broad child-benefit issue, preserved those details as facts,
and reduced the tax issue to possible German tax liability without adding a
double-taxation or tax-residence mechanism. A second diagnostic record exposed
an upstream evidence limitation: the canonicalizer input mentioned a foreign
business account only as a possible proof-of-income document. It did not itself
establish active foreign-registered work performed from Germany. The critic
therefore correctly treated the mandatory activity gate as unproven from that
input. If fuller source context establishes the activity, that context must be
included before canonicalization rather than inferred from the account mention.

The controlled critic should remain an optional operator contour until it
passes a broader regression sample; it must not replace the reviewed
single-pass baseline based on two diagnostic records.

## PL-021: Compound Claims Need Policy Invariants And Claim-Scoped Repair

Evidence:

- private GLM-5.2 atomic verifier, critic, repair, and final-state smokes on
  `tg-question-canonicalization-task:20338f0eb2122742b0ae`;
- Bundesagentur fuer Arbeit guidance on Kindergeld eligibility and the role of
  Familienkasse;
- Bundesagentur fuer Arbeit guidance for the narrow adult-child jobseeker
  exception.

Lesson: A typed critic is necessary but not sufficient when one list item
contains several propositions. Verifier and critic can both mark the item
unsupported while correcting only the named benefit and retaining an
authority-to-eligibility relationship. A parent or household's Jobcenter
registration is not a general Kindergeld prerequisite; Familienkasse handles
the claim. Registration with Arbeitsagentur or Jobcenter can matter in the
narrow, materially different case of an adult child seeking work or training.

Prompt implication: encode that narrow public policy invariant explicitly and
keep the exception. Represent parent/household authority contact as a fact and
the broad child-benefit request as a separate issue. Ask the critic to enumerate
all unsupported relations in a compound claim.

Controller implication: unsupported list claims authorize deletion, not free
replacement. Preserve supported list items exactly and remove unsupported
indices deterministically before re-ledgering. This converted the target hidden
issues from a partially rewritten three-item list to the single supported
German activity-classification issue. The separately verified normalized state
passed verifier v3 and critic v3 with no disagreement in 203.908 seconds and
24,176 total tokens, but remains review evidence only.

Official policy references:

- https://www.arbeitsagentur.de/familie-und-kinder/infos-rund-um-kindergeld/kindergeld-anspruch-hoehe-dauer
- https://www.arbeitsagentur.de/familie-und-kinder/infos-rund-um-kindergeld/kindergeld-ab-18-jahren
- https://www.arbeitsagentur.de/familie-und-kinder/veraenderungen-mitteilen

## PL-022: Activity Gates Require An Actor-Action-Location Link

Evidence:

- `tg-question-canonicalization-task:2ec442161386f8e093f5`
- private GLM-5.2 atomic verifier+critic v2 and v3 comparison.

Lesson: A foreign-business keyword is not activity evidence. Generic income,
an account named as a possible proof document, or a choice between bank
statements does not establish that the author performs work through that
foreign registration from Germany. The activity gate requires an action
predicate linking actor, work/services/business activity, foreign
registration, and German location.

Prompt implication: audit this evidence-status link before applying the
foreign-activity gate. When it is missing, mark registration/classification
claims unsupported or unresolved and preserve the explicit insurance, tax,
timing, and proof-of-income questions.

Measured result: verifier v2 plus critic v2 retained the unsupported activity
gate. Verifier v3 and critic v3 independently rejected the central registration
question, legal frame, and activity-classification hidden issue, explicitly
noting that the FOP account appeared only as a possible document. The two-call
run used 51,205 tokens and 403.707 seconds, so this remains a bounded diagnostic
rather than a bulk default.

## PL-023: Preserve Questions Without Promoting Their Premises

Evidence:

- `tg-question-canonicalization-task:20338f0eb2122742b0ae`;
- `tg-question-canonicalization-task:2ec442161386f8e093f5`;
- private two-step verifier and critic model sweep on 2026-07-17.

Lesson: `facts` and `desired_outcome` describe what the author states or asks,
including an uncertain or legally mistaken premise. `canonical_question`,
`legal_issue_frame`, and `hidden_issues` describe the normalized legal
structure. An explicit question about two nearby facts supports preserving the
question as a requested outcome; it does not by itself prove the causal,
eligibility, prerequisite, or legal-mechanism relationship proposed by a hidden
issue.

Prompt implication: make field ownership the first decision. Then determine the
activity gate and audit relation classes separately. Keep foreign tax payment,
Jobcenter contact, and a missing identifier as source facts or requested
outcomes. Promote them into double-taxation, child-benefit eligibility, or
registration-prerequisite relationships only when the source independently
grounds that relationship. Require a compact relation-audit summary before
claim verdicts so the model commits to these distinctions once rather than
re-deriving them inconsistently for every claim.

Evaluation implication: a safe controller route such as `hold` is not a
semantic success by itself. Qualification checks the retained memo verdicts for
the target relationships. On the 2026-07-17 sweep, Qwen3.7 Plus and GLM-5.2
critics both produced safe terminal holds while retaining reviewed-wrong
relationships.

Measured v6 result: explicit field ownership, relation preflight, compound-
dependency semantics, and contiguous-quote rules made independent GLM-5.2
reasoning verifier and critic reject the three reviewed-wrong relationships on
the positive target. Both also rejected the activity gate when the second
source mentioned an FOP account only as a possible document. Repeated cheaper
and mixed-model calls still produced false passes, including one GLM-5.2
reasoning critic run. Prompt improvement therefore needs a fail-closed
controller guard and cannot serve as the only acceptance boundary.

## PL-024: Compact Output Must Preserve Classification Semantics

Evidence:

- private v7/v8 compact-memo GLM-5.2 and Qwen3.7 Plus diagnostics on
  2026-07-17;
- repeated 12-record v22 holdout runs;
- `atomic-model-profile-evaluation.md` aggregate measurements.

Lesson: deduplicating repeated source quotes can halve the semantic memo, but
brevity changes model attention. Compact v7 treated `authority_context`,
`law_area`, routing booleans, and `exclusion_reason=none` as unsupported unless
their formal labels appeared literally in the source. These are controlled
classifications, unlike factual and normalized dependency claims. V8 restored
necessary-inference semantics for narrow classifications, yet remained too
conservative and unstable for review selection.

Prompt implication: state field ownership for every field family, including
controlled classifications. `authority_context` may follow from the requested
legal process without a named authority; `exclusion_reason=none` follows from a
supported in-scope route. Continue to require independent grounding for causal,
eligibility, prerequisite, and legal-mechanism relationships.

Architecture implication: compact memos are an encoding optimization, not a
new trust boundary. A second formatter can reintroduce cost and schema failure,
and a cheaper semantic model can still quote candidate wording as if it were
source evidence. Python should eventually own quote-table expansion and field
metadata derivation. Until claim-level human labels exist, active verifier v6
plus controller v6 remains the diagnostic boundary and compact v7/v8 remain
inactive historical evidence.

## PL-025: Weak Input Hints Need A Deterministic Non-Leakage Boundary

Evidence: three repeated compact-profile generations for one reviewed retry on
2026-07-17. One omitted all named input hints, one copied `AsylG`, and one
copied `BeschV`. The atomic verifier held the `AsylG` run for unrelated span
formatting failure but accepted the `BeschV` claim as a necessary inference.

- `tg-question-canonicalization-task:de8172b5f0f694eca3cf`

Lesson: source-only semantic verification cannot reliably distinguish an
independently inferred legal code from a copied upstream hint. Repetition at
temperature zero does not make this behavior stable.

Architecture implication: retain law-code candidates as explicitly untrusted
audit provenance, keep them out of verifier prompts, and fail closed on exact
reuse when the source itself does not name the code. Semantic relatives still
require model or human review; controller v6 deliberately does not expand
abbreviations into guessed legal families.

## PL-026: Resolve The Full Request Before Selecting Its Central Proposition

Evidence:

- `tg-question-canonicalization-task:3cdfe5efd90835b24c2a`
- `tg-question-canonicalization-task:2afcd40df8ef111856cf`
- `tg-question-canonicalization-task:69254584bd1687cedfb5`
- `tg-question-canonicalization-task:fbcfbabb9c5e0fb28c6b`
- `tg-question-canonicalization-task:fcb96bbbd524d99891c9`
- `tg-question-canonicalization-task:383f700150474369ee31`
- five-record Qwen3.6 Plus no-reasoning v37 retry canary on 2026-07-19:
  all five completed and satisfied their reviewed field-level correction target.

Lesson: central-question selection is downstream of discourse resolution. A
later question may identify the controlling authority or jurisdiction; failed
submission channels may be facts inside a legal status-termination procedure;
a desired allocation location may ask whether choice exists rather than how to
file; and a colloquial document name may identify a travel document rather
than a residence card. Current foreign earnings and date-sensitive status
proof also require legal classification before downstream consequences are
normalized.

Prompt implication: interpret the complete request first, resolve its actor,
act, legal object, jurisdiction, and desired outcome, and only then select one
canonical proposition. Preserve operational obstacles as secondary facts when
the requested act creates, changes, or terminates legal status. Use the question
date only together with established status context, and preserve uncertainty
where the source does not establish a specific regime.

Architecture implication: claim verification of a selected candidate cannot
reliably detect that an omitted source question changed the whole request's
jurisdiction. Full-source intent selection needs its own regression cases. The
schema still lacks a dedicated out-of-scope-jurisdiction exclusion, so a
correctly resolved foreign-law question remains a manual record-level reject
rather than being mislabeled non-legal.

Promotion implication: the five-record retry canary supports a broader blinded
regression run, not immediate replacement of v22. The canary reused previously
reviewed failures and therefore measures targeted correction rather than
generalization or unchanged-case stability.

## PL-027: Route Sparse Foreign-Activity Cases Instead Of Expanding The Main Prompt

Evidence:

- 52-record Qwen3.6 Plus v37 regression on 2026-07-19;
- targeted v38 and structured v39 seven-record smokes;
- selector plus GLM-5.2 focused v40/v41 runs on
  `tg-question-canonicalization-task:20338f0eb2122742b0ae`.

Lesson: v37 preserved routing on all 48 records shared with the v22 Qwen
baseline and fixed five reviewed retries, but lost the explicit German
classification and registration issue on the foreign-FOP case. Strengthening
or structuring the full Qwen prompt did not make that gate reliable. A
deterministic actor-action-location selector found one candidate among 52 and
did not select the account-as-document negative control.

Architecture implication: keep the ordinary prompt general. Route only source
texts that link work or services from Germany to a foreign business
registration to the compact focused profile and stronger model. The selector
is a routing hint, not an acceptance decision. Focused v41 keeps Kindergeld
central, preserves German activity classification, registration, residence
authorization, and social insurance, and keeps Jobcenter non-contact and
foreign tax payment as facts. Broader selected-record evidence is still needed
before treating this contour as qualified for unattended promotion.

## PL-028: Preserve A Named Legal Criterion Without Recasting The Facts

Evidence:

- `tg-question-canonicalization-task:1ea088739220a823f65e`;
- three candidate-conditioned Qwen retry rounds and one fresh-context GLM-5.2
  fallback on 2026-07-19/20.

Lesson: the author explicitly stated financial independence and separately
asked about an alleged minimum annual-income condition for section 18a. The
income statement is a named, potentially mistaken legal premise to verify; it
is not evidence that the author cannot support themselves. Every field must
preserve that distinction: facts retain financial independence, while the
canonical question and hidden issues retain the alleged section-18a threshold
as an uncertain criterion.

Prompt implication: first bind each source statement to its named legal object,
then preserve the author's factual assertions and mark the legal premise for
verification. Prefer wording such as "the assumed threshold for section 18a"
when the source asserts a criterion whose validity is unresolved.

Retry implication: repeated correction prompts that include the previous
candidate can preserve its semantic anchor. After two materially identical
failures, create a fresh task from the immutable source plus a concise positive
field-level target, then route it to a stronger model or human review. Every
fresh result remains review evidence and needs its own hash-bound decision.

## PL-029: Keep Full-Request Structure Beyond The Canonical Proposition

Evidence:

- `tg-question-canonicalization-task:df479089ebc29ee5fd16`;
- the two-round Qwen v37 reviewed retry on 2026-07-19.

Lesson: one source request can contain a central legal question, a second
independently answerable legal issue, and an operational obstacle. Selecting
the child's separate eAT PIN letter as the canonical proposition did not erase
the IdNr notification issue or the different-surname mailbox problem. The
former belongs in `hidden_issues`; the latter remains source context and is
represented by `mixed_with_non_legal_query`.

Architecture implication: downstream retrieval and the future router/selector
must consume the immutable full request together with the canonical question,
hidden issues, facts, and composition flags. Using only the single canonical
question would turn useful normalization into information loss and could route
the request to the wrong evidence class.
