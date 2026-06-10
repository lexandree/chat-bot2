# 007: Legal-Intent Pair Review Guide

This guide applies to the HTML review surface:

`data/evaluation/tg_qa_legal_intent_equivalence/real_data_007_last_2000_similarity_t90_86_80_review.html`

The purpose of this review is to decide whether two similar canonical questions
represent the same legal intent for deduplication, clustering, and possible
reference-answer reuse. High similarity is evidence, not proof.

## Main Rule

Do not start with "are these questions similar?" Start with:

"Can the same legal answer safely answer both questions?"

If one question contains an extra condition that can change the legal answer, it
is not `same_legal_intent`, even when the text looks almost identical.

Example: a question about "leaving and returning" and a question only about
"re-entering" can be `same_topic_different_issue`, because exit/travel adds a
separate legal check.

## Field 1: `pair_class`

This is the main classification of the relationship between the two questions.

### `exact_duplicate`

Almost the same question. Differences are only language, word order, style, or
clearly immaterial details.

Use it when:

- both questions test the same set of legal conditions;
- the answer is definitely the same;
- one question could be removed as a duplicate without losing meaning.

Usual companion fields:

- `answer_equivalence`: `safe_to_share_answer`
- `canonical_question_equivalence`: `safe_to_share_question`

### `same_legal_intent`

The wording differs, but the legal intent is the same. This is not a literal
duplicate, but one answer should cover both questions.

Use it when:

- different wording leads to the same legal check;
- extra details do not change the applicable law or answer;
- GraphRAG can route both questions to the same reference answer.

Usual companion fields:

- `answer_equivalence`: `safe_to_share_answer`
- `canonical_question_equivalence`: `safe_to_share_question`

### `same_topic_different_issue`

The topic is shared, but the legal issue differs. This is the most important
hard-negative class: similarity is high, but answer reuse is unsafe.

Use it when:

- both questions involve the same broad area, such as Fiktionsbescheinigung,
  Jobcenter, Anmeldung, section 24, housing, or work;
- one question contains a material condition absent from the other;
- or the questions test different legal acts, rights, duties, risks, deadlines,
  authorities, or procedures;
- a shared answer could be incomplete or wrong for one side of the pair.

Usual companion fields:

- `answer_equivalence`: `not_safe_to_share_answer`
- `canonical_question_equivalence`: `not_safe_to_share_question`

### `related_context`

The questions are contextually related, but they are not the same legal question.
One may be useful as a nearby retrieval neighbor, but not as a duplicate.

Use it when:

- one question helps understand the other;
- both may belong to one broad topic or FAQ section;
- but the answer to one is not the answer to the other.

Usual companion fields:

- `answer_equivalence`: `not_safe_to_share_answer`
- `canonical_question_equivalence`: `not_safe_to_share_question`

Sometimes `canonical_question_equivalence` can be `uncertain` when the wording is
so broad that the source is needed to understand the overlap.

### `different`

Different questions. The relationship is weak or accidental.

Use it when:

- the law areas differ;
- the actions or subjects differ;
- similarity matched generic words, but the legal meaning is different.

Usual companion fields:

- `answer_equivalence`: `not_safe_to_share_answer`
- `canonical_question_equivalence`: `not_safe_to_share_question`

### `uncertain`

The pair cannot be classified reliably without more context.

Use it when:

- both questions are too noisy or fragmentary;
- it is unclear which facts are material;
- the same word may be used in different senses;
- manual source review or a future reasoning judge is needed.

Usual companion fields:

- `answer_equivalence`: `uncertain`
- `canonical_question_equivalence`: `uncertain`

## Field 2: `answer_equivalence`

This answers: can one reference answer safely be used for both questions?

### `safe_to_share_answer`

The same legal answer should be correct for both sides of the pair.

Use it only when:

- differences do not change the applicable law;
- differences do not change conditions, exceptions, risks, or procedure;
- there is no hidden "yes, but" for one side of the pair.

Typical with:

- `exact_duplicate`
- `same_legal_intent`

### `not_safe_to_share_answer`

One answer may be incomplete, misleading, or wrong for one side of the pair.

Use it when:

- there are different legal checks;
- there are different procedures or authorities;
- one wording is broader and includes an additional material issue;
- one wording requires clarification that the other does not;
- the pair should be preserved as a hard negative for similarity evaluation.

Typical with:

- `same_topic_different_issue`
- `related_context`
- `different`

### `uncertain`

There is not enough confidence to allow or reject shared-answer reuse.

Use it when:

- facts are missing;
- it is unclear whether a difference changes the legal answer;
- you are unsure between `same_legal_intent` and `same_topic_different_issue`.

## Field 3: `canonical_question_equivalence`

This answers: can the canonical questions themselves be treated as
interchangeable wordings of one question?

This field is close to `answer_equivalence`, but not identical.

### `safe_to_share_question`

The canonical questions can be merged or used as variants of one question.

Use it when:

- one question can be reworded into the other without losing material meaning;
- all legally important conditions match;
- one canonical question can represent the pair.

Typical with:

- `exact_duplicate`
- `same_legal_intent`

### `not_safe_to_share_question`

The canonical questions should not be treated as interchangeable.

Use it when:

- one question contains an additional legally material condition;
- one question is narrower or broader in a way that changes meaning;
- one question concerns a right while the other concerns procedure, logistics, or
  adjacent context;
- a shared representative would distort at least one side of the pair.

Typical with:

- `same_topic_different_issue`
- `related_context`
- `different`

### `uncertain`

It is unclear whether the question formulations can be merged.

Use it when:

- the question is too broad;
- the source is needed for interpretation;
- one side looks like a poor canonicalization.

## Practical Matrix

| pair_class | answer_equivalence | canonical_question_equivalence |
| --- | --- | --- |
| `exact_duplicate` | `safe_to_share_answer` | `safe_to_share_question` |
| `same_legal_intent` | `safe_to_share_answer` | `safe_to_share_question` |
| `same_topic_different_issue` | `not_safe_to_share_answer` | `not_safe_to_share_question` |
| `related_context` | `not_safe_to_share_answer` | `not_safe_to_share_question` |
| `different` | `not_safe_to_share_answer` | `not_safe_to_share_question` |
| `uncertain` | `uncertain` | `uncertain` |

You can deviate from the matrix, but then it is better to explain why in
`decision_reason`.

## When To Fill `decision_reason`

Fill a reason when:

- choosing `same_topic_different_issue` despite high similarity;
- overriding a model decision;
- unsure between `same_legal_intent` and `related_context`;
- choosing `uncertain`;
- any field differs from the practical matrix above.

A good short reason names the material difference:

`Exit/travel conditions add a separate legal check; re-entry-only answer may be incomplete.`

## Review Order

1. Open the `not different` filter.
2. For each pair, ask: "Is one answer safe for both?"
3. If yes, usually choose `same_legal_intent`.
4. If no, but the topic is close, usually choose `same_topic_different_issue`.
5. If the relationship is only contextual, choose `related_context`.
6. If there is no meaningful relationship, choose `different`.
7. If context is insufficient, choose `uncertain`.

The `random control` filter can be spot-checked. The main value right now is in
hard-negative pairs where similarity looks high but answer reuse is unsafe.
