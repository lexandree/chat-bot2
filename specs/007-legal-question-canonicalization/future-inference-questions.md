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

**Source pattern**: A Ukrainian refugee context uses words such as `Asyl`,
`asylum`, `Asylheim`, or "apply for asylum" together with early-arrival tasks,
housing, registration, and work authorization.

**Problem**: In early Ukrainian refugee chats, users often used `Asyl`
colloquially for "refugee registration" or "protection in Germany", while the
legal branches are materially different:

- asylum procedure under AsylG;
- temporary protection / residence under section 24 AufenthG.

Canonicalization may still accept the record as a legal question because the
message contains a real legal need. A future live answer, however, must not
silently choose one route when the user's wording does not disambiguate it.

**Future retrieval requirement**: Retrieval for a query mentioning `Asyl` in a
Ukrainian refugee context should recall both asylum-procedure material and
section 24 temporary-protection material with comparable priority. The route
choice must not be decided by keyword match alone.

**Future answer-planning requirement**: Before generating a legal answer, the
planner should detect that several legal routes can fit the question and emit a
clarification request instead of answering directly.

Example clarification:

```text
Do you mean the asylum procedure, or temporary protection for Ukrainians under section 24 AufenthG?
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
