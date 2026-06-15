# Future Inference Questions From 007

This file records future retrieval and answer-planning issues discovered during
007 canonicalization work. These notes are intentionally out of scope for 007:
they do not authorize chatbot inference, answer synthesis, trusted legal facts,
or graph mutation. They exist so recurring ambiguity patterns are not lost
while the canonical question dataset is being built.

## How To Use This Backlog

- Add an item when a reviewed Telegram question exposes a future answer-planning
  behavior that canonicalization cannot safely solve.
- Keep each item tied to concrete reviewed examples when possible.
- Treat entries as future design input for retrieval, route selection,
  clarification questions, and answer planning.
- Do not use this file to override current 007 canonicalization results.

## FIQ-001: Confusable Legal Routes Require Clarification

**Observed example**:
`tg-question-canonicalization-task:095e4b46476f1ae97e13`

**Source pattern**: A user uses words such as `refugee`, `Asyl`, `asylum`,
`Asylheim`, or "apply for asylum" without enough material context to identify
the intended legal route. The same Russian-language question can refer to
temporary protection under section 24 AufenthG for a person who satisfies its
eligibility conditions or to the asylum procedure under AsylG for a person who
does not. Citizenship alone does not resolve the route: a Ukrainian national
may not qualify for section 24, for example when the material residence and
displacement circumstances fall outside its scope.

**Problem**: User terminology is not a reliable legal-status classifier. In
early Ukrainian refugee chats, users often used `Asyl` colloquially for
"refugee registration" or "protection in Germany". In a different user
context, the same term and the same question wording can correctly refer to the
formal asylum procedure. The legal branches are materially different:

- asylum procedure under AsylG;
- temporary protection / residence under section 24 AufenthG.

Canonicalization may still accept the record as a legal question because the
message contains a real legal need. A future live answer, however, must not
silently choose one route when the user's wording does not disambiguate it.

**Future retrieval requirement**: Retrieval for an unresolved query mentioning
`refugee`, `Asyl`, `asylum`, or equivalent colloquial terms should recall both
asylum-procedure material and section 24 temporary-protection material with
comparable priority. Corpus prior may influence ranking for offline dataset
work, but it must not silently determine the legal route for future live
answering. The route choice must not be decided by keyword match alone.

**Future answer-planning requirement**: Before generating a legal answer, the
planner should detect that several legal routes can fit the question and emit a
clarification request instead of answering directly.

Example clarification:

```text
What citizenship, prior residence and current status does the person have, what circumstances caused the move to Germany, and do you mean the asylum procedure or temporary protection under section 24 AufenthG?
```

After the user chooses a route, the answer planner can continue on the selected
branch and explain the consequences for registration, work authorization,
benefits, and responsible authorities.

**Related future graph/retrieval concept**: Add reviewable links for
`confusable_legal_route`, for example:

- asylum procedure <-> section 24 temporary protection;
- initial reception / asylum accommodation <-> Ukrainian temporary-protection
  registration and allocation;
- legal status route <-> work authorization consequence.

These links are not duplicates and do not mean "same legal intent". They are
recall and clarification aids for future inference.

## FIQ-002: Retrieval Should Surface Adjacent Routes Before Answer Planning

**Observed examples**:

- `tg-question-canonicalization-task:095e4b46476f1ae97e13`
- `tg-question-canonicalization-task:36605c7aff7841dd4cdd`

**Problem**: A user may ask with an imprecise or colloquial route label. If
retrieval returns only the literal route, the answer planner may produce a
legally correct answer to the wrong branch. If retrieval returns adjacent
confusable routes, the planner can ask a clarification instead.

**Future requirement**: For known confusable route families, retrieval should be
recall-biased before answer planning. Example route family:

- asylum procedure;
- section 24 temporary protection;
- registration/allocation procedures for newly arrived Ukrainian refugees;
- work authorization consequences of each route.

The future planner should then choose one of:

- answer directly when one route is clearly selected by the source;
- ask a clarification when multiple routes remain plausible;
- explain the route distinction before answering when the question itself is
  about the distinction.

This is a future inference behavior, not a 007 dataset acceptance rule.

## FIQ-003: Material Context Must Control Legal Route Selection

**Problem**: Nationality, prior residence, displacement circumstances, current
legal status, prior application history, relevant date, and the user's intended
procedure can change the applicable legal route while the surface question
remains unchanged. Nationality and a previously granted section-24 permit are
only pieces of evidence and must never be treated as automatic proof of the
currently applicable route. Eligibility for initial temporary protection and
eligibility for a later continuation or automatic extension may differ. For
example, some non-Ukrainian third-country nationals with temporary Ukrainian
residence status initially received protection but were outside later automatic
continuation categories. A retrieval or answer system that chooses a law from
wording, nationality, or historical status alone can produce a legally correct
answer to the wrong question.

**Future requirement**: Before selecting one legal route, the system should
represent:

- plausible legal-route hypotheses;
- evidence supporting each hypothesis;
- material context that is known;
- material context that remains unknown;
- the relevant decision or extension date;
- whether the question concerns initial eligibility, current validity,
  individual renewal, or automatic continuation;
- whether the unknown context can change the applicable law;
- a clarification question when route selection is unsafe.

The future planner may answer directly only when one route is sufficiently
supported. Otherwise it should retrieve the plausible branches, ask for the
missing material context, and continue on the selected branch.

**Current 007 boundary**: Canonicalization and retrieval evaluation may preserve
and measure the ambiguity, but must not invent nationality, status, or route.

## FIQ-004: Question Date And Legal Currentness Must Gate Retrieval

**Problem**: A legal question may have been valid and useful when asked but no
longer represent a current decision path. Transitional rules, temporary
protection categories, automatic extensions, deadlines, and one-time procedures
can expire or change. Implementing a correct historical answer may waste effort
and may introduce obsolete branches that interfere with current retrieval and
answer planning.

The source question date is therefore material evidence from the first
selection stage onward. It must remain distinct from the date of
canonicalization, review, retrieval, and answering.

**Future requirement**: Before a question or answer path is eligible for
current-default retrieval, the system should distinguish:

- a stable reusable legal issue that remains current;
- a historical question whose generalized legal issue remains reusable;
- a transition-bound or date-bound question that requires currentness review;
- a superseded or expired question that is useful only for historical
  evaluation;
- a question whose currentness cannot yet be determined.

Questions outside the current legal state should remain auditable and may be
useful for temporal evaluation, but they should not enter current-default
question-bank or answer-planning branches without explicit review.

**Current implementation gap**: `question_date` is preserved in the extracted
candidate and canonicalization batch, but the compact canonicalization LLM
payload currently omits it. Question-bank promotion also has no independent
temporal-currentness gate. These gaps must be resolved only together with a
reviewable temporal-routing contract; adding the date alone is insufficient.
