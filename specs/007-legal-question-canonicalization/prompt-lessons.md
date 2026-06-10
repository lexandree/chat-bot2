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
authorization.

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
