# Contract: Legal Intent Equivalence Diagnostics

## Boundary

Legal intent equivalence diagnostics are an optional 007 evaluation layer over
canonical question artifacts. They exist to measure and improve future
retrieval, clustering, deduplication, and answer-reuse safety.

This contract does not create trusted legal answers, does not mutate Neo4j
state, does not approve question-bank entries, and does not make embedding
similarity a legal truth signal. Embeddings, lexical similarity, rerankers, and
LLM pair judgments are candidate-generation or diagnostic evidence only.

007 canonicalization may continue without this layer. Legal intent diagnostics
consume completed 007 artifacts and write separate private evaluation
artifacts.

## Artifact Directory

Generated Phase 8 artifacts must live under:

```text
data/evaluation/tg_qa_legal_intent_equivalence/
```

Expected artifact classes include:

- legal-intent candidate JSONL, summary JSON, and manifest JSON;
- pair benchmark JSONL, summary JSON, and manifest JSON;
- pair-decision JSONL, summary JSON, and manifest JSON;
- pair-review HTML and exported review label JSONL;
- equivalence evaluation report JSON, JSONL, Markdown, or TSV artifacts.

The directory is private generated data and must remain ignored unless a later
explicit publication step sanitizes specific outputs.

## Pair Classes

Allowed pair classes:

- `exact_duplicate`: same legal question and same material facts; duplicate
  removal may be considered after review.
- `same_legal_intent`: different wording but the same legal right, duty,
  remedy, procedure, status question, or authority-competence question.
- `same_topic_different_issue`: same broad topic or entity vocabulary, but at
  least one material legal distinction differs.
- `related_context`: useful surrounding context or neighboring issue, but not
  safe for canonical-question or answer reuse.
- `different`: no material legal overlap for retrieval or reuse decisions.
- `uncertain`: insufficient, contradictory, or ambiguous evidence.

Pair class is not enough by itself. Each pair decision must separately record
whether duplicate removal, canonical-question sharing, reference-answer
sharing, FAQ-pattern grouping, retrieval-cluster grouping, or human-review
routing is allowed.

## Legal Intent Candidate Shape

Each legal intent candidate describes one included canonical question.

```json
{
  "legal_intent_candidate_id": "tg-legal-intent-candidate:...",
  "candidate_id": "tg-qa-candidate:...",
  "canonicalization_evidence_id": "tg-question-canonicalization-evidence:...",
  "source_canonical_question": "...",
  "source_legal_issue_frame": "...",
  "law_area": "migration_status",
  "legal_domain": "residence_status",
  "actor": "ukrainian_refugee",
  "subject": "self",
  "current_status": "temporary_protection",
  "target_status": "continued_residence_or_work_authorization",
  "desired_action": "force_third_party_accept_automatic_extension",
  "legal_object": "automatic_extension_of_section_24_residence_document",
  "authority_context": ["Auslaenderbehoerde"],
  "third_party_context": ["employer"],
  "location_scope": "germany",
  "temporal_condition": "after_automatic_extension_before_new_card",
  "operational_boundary": "legal_obligation_not_live_capacity",
  "material_slots_unknown": [],
  "ambiguities": [],
  "evidence_refs": [
    {
      "field": "desired_action",
      "source_field": "canonical_question",
      "support_text": "..."
    }
  ],
  "validation_flags": [],
  "confidence": "medium",
  "review_status": "candidate",
  "policy_version": "tg_legal_intent_candidate_policy_v1",
  "provenance": {
    "source_canonicalization_artifact": "data/evaluation/..."
  }
}
```

Allowed `confidence` values:

- `low`
- `medium`
- `high`

Allowed `review_status` values:

- `candidate`
- `review_approved`
- `review_rejected`
- `needs_more_context`
- `uncertain`

Validation rules:

- Unsupported material slots must be marked unknown or ambiguous instead of
  guessed.
- High confidence is invalid when unresolved material slots would change the
  pair class or answer-reuse decision.
- Multi-intent questions must be flagged with `multiple_legal_intents` rather
  than forced into one legal intent.
- Operational or live-data questions must distinguish legal right or duty from
  current local capacity, opening status, processing speed, or intake status.
- A legal intent candidate is review evidence only and cannot approve a final
  evaluation case or trusted answer source.

## Pair Benchmark Record Shape

Each benchmark record compares two canonical questions.

```json
{
  "pair_id": "tg-legal-intent-pair:...",
  "left_canonicalization_evidence_id": "tg-question-canonicalization-evidence:...",
  "right_canonicalization_evidence_id": "tg-question-canonicalization-evidence:...",
  "left_candidate_id": "tg-qa-candidate:...",
  "right_candidate_id": "tg-qa-candidate:...",
  "pair_source_reasons": [
    "high_canonical_question_similarity",
    "same_law_area"
  ],
  "similarity_evidence": {
    "canonical_question_score": 0.91,
    "legal_issue_frame_score": 0.84,
    "embedding_profile_id": "..."
  },
  "benchmark_status": "needs_pair_review",
  "provenance": {
    "source_dataset_artifact": "data/evaluation/..."
  }
}
```

Recommended pair source reasons:

- `strict_duplicate_candidate`
- `preserved_variant_candidate`
- `high_canonical_question_similarity`
- `high_legal_issue_frame_similarity`
- `same_law_area`
- `law_area_conflict`
- `coverage_related_pair`
- `manual_seed`
- `random_negative`
- `adversarial_hard_negative`

Stable pair identity must be independent of left/right ordering. Rebuilding a
benchmark from unchanged inputs must preserve `pair_id` and pair source
metadata.

## Pair Equivalence Decision Shape

Each automated or manual pair decision must include:

```json
{
  "pair_decision_id": "tg-legal-intent-pair-decision:...",
  "pair_id": "tg-legal-intent-pair:...",
  "decision_source": "llm_judge_or_manual_or_policy",
  "pair_class": "same_topic_different_issue",
  "answer_equivalence": "not_safe_to_share_answer",
  "canonical_question_equivalence": "not_safe_to_share_question",
  "allowed_downstream_actions": ["route_human_review"],
  "material_differences": [
    {
      "field": "desired_action",
      "left": "register residence",
      "right": "apply for residence permit",
      "why_material": "different authority and procedure"
    }
  ],
  "shared_material_facts": ["temporary protection context"],
  "unknowns": [],
  "ambiguities": [],
  "short_reason": "...",
  "confidence": "medium",
  "risk": "medium",
  "validation_flags": [],
  "policy_version": "tg_legal_intent_pair_policy_v1",
  "runtime_metadata": {
    "model_id": "",
    "prompt_version": ""
  }
}
```

Allowed `answer_equivalence` values:

- `safe_to_share_answer`
- `not_safe_to_share_answer`
- `uncertain`

Allowed `canonical_question_equivalence` values:

- `safe_to_share_question`
- `not_safe_to_share_question`
- `uncertain`

Allowed downstream actions:

- `allow_duplicate_removal`
- `allow_canonical_question_sharing`
- `allow_reference_answer_sharing`
- `allow_faq_pattern_grouping`
- `allow_retrieval_cluster_grouping`
- `route_human_review`
- `preserve_hard_negative`

Validation rules:

- `exact_duplicate` requires both `safe_to_share_question` and
  `safe_to_share_answer` unless a validation flag routes the pair to review.
- `same_legal_intent` may share an answer only when no material legal slot
  changes and no unresolved ambiguity affects the answer.
- `same_topic_different_issue` must not allow duplicate removal or answer
  sharing.
- `related_context` may allow retrieval-cluster grouping only when the report
  makes the limitation explicit.
- Similarity scores must not directly set pair class, answer equivalence, or
  canonical-question equivalence.

## Pair Decision Producers

The implementation provides three diagnostic decision producers. All three
write `PairEquivalenceDecision` JSONL and remain review evidence only.

1. `tg-qa-legal-intent-similarity-baseline`
   - uses stored `similarity_evidence` plus optional embedding records;
   - computes `recos_canonical_question_score` and
     `recos_legal_issue_frame_score` when vectors are available;
   - defines recos as `dot(a, b) / dot(sort(abs(a)), sort(abs(b)))`, clamped to
     the `[-1, 1]` range, with `0.0` used when vectors are missing, empty, or
     dimension-mismatched;
   - records cosine and recos thresholds in `runtime_metadata`;
   - always flags that similarity-only output is not safe for automatic
     trusted action.

2. `tg-qa-legal-intent-candidate-extractor-run`
   - extracts schema-guided material slots from included canonicalization
     evidence;
   - may be bounded to unique evidence referenced by a pair benchmark;
   - treats model-generated ids and source fields as untrusted and replaces
     them with values from canonicalization evidence;
   - uses prompt profile `tg_legal_intent_extractor_v1_positive`;
   - supports resume/retry/progress behavior like the existing 007 LLM
     runners.

3. `tg-qa-legal-intent-slot-comparator`
   - compares imported `LegalIntentCandidate` material slots;
   - treats explicit differences in `desired_action`, `legal_object`, status,
     authority, third-party context, temporal condition, location scope, or
     operational boundary as material;
   - routes missing or ambiguous slots to `uncertain` rather than guessing.
   - is diagnostic and may identify candidate material differences, but
     free-form slot values cannot establish positive equivalence by exact
     string equality.

4. `tg-qa-legal-intent-pair-judge-run`
   - runs an operator-managed structured-output LLM judge over benchmark pairs;
   - may consume legal-intent candidates when available;
   - uses prompt profile `tg_legal_intent_pair_judge_v1`;
   - supports resume/retry/progress behavior like the existing 007 LLM runners.
   - should consume extracted candidates as a second confirmation gate before
     allowing duplicate removal, canonical-question sharing, or reference-answer
     sharing for pairs that a cheaper method proposes as equivalent.

## Pair Review Label Shape

Manual review labels must be exportable without editing raw JSON directly.

```json
{
  "pair_review_label_id": "tg-legal-intent-pair-review:...",
  "pair_id": "tg-legal-intent-pair:...",
  "pair_class": "same_legal_intent",
  "answer_equivalence": "safe_to_share_answer",
  "canonical_question_equivalence": "safe_to_share_question",
  "allowed_downstream_actions": [
    "allow_canonical_question_sharing",
    "allow_reference_answer_sharing"
  ],
  "decision_reason": "...",
  "reviewer_hash": "reviewer:...",
  "reviewed_at": "2026-05-30T00:00:00Z"
}
```

Review import must reject duplicate pair ids with conflicting labels unless an
explicit replacement mode is used.

## Evaluation Report Requirements

Legal intent equivalence evaluation reports must include:

- input dataset, benchmark, legal-intent candidate, pair decision, and review
  label artifact paths;
- counts by pair class, law area, pair source reason, review state, method, and
  risk;
- confusion counts for each method against reviewed labels when label volume is
  sufficient;
- false duplicate risk examples;
- false separation risk examples;
- high-similarity hard negatives;
- insufficient-label warnings when reviewed labels are too few or too
  imbalanced;
- generated timestamp, policy versions, embedding profiles, and runtime
  contour.

Evaluation reports must be able to conclude that a method is:

- safe only for candidate generation;
- safe for a narrow downstream action after review;
- unsafe for automatic action;
- or insufficiently supported by current labels.

## Interpretation Rules

- Dense similarity answers "near in vector space", not "same legal question".
- Legal equivalence is a pair-level judgment over material legal distinctions.
- Complete-linkage or all-pair compatibility is required before a cluster can
  be treated as equivalence-safe; connected components are not enough because
  A-B and B-C similarity does not prove A-C equivalence.
- Duplicate removal is stricter than retrieval grouping.
- Reference-answer sharing is stricter than same-topic grouping.
- Mixed operational/legal questions should preserve the legal part only when it
  is independently answerable and material; otherwise they route to review or
  exclusion.
- LLM-derived slot extraction and pair judgments remain candidates until
  validated and reviewed.
