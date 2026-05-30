# Contract: Legal Issue Cluster Coverage

## Boundary

Cluster coverage is an evaluation and retrieval-preparation artifact. It does
not prove legal corpus coverage, does not create legal truth, and does not
mutate Neo4j graph state.

Coverage summaries must explicitly distinguish canonical issue coverage from
the earlier raw Telegram question embedding diagnostic run.

## Legal Issue Cluster JSONL Shape

Each cluster record must include:

```json
{
  "legal_issue_cluster_id": "tg-legal-issue-cluster:...",
  "legal_issue_frame_slug": "residence_document_address_update_with_expired_or_extended_permit",
  "canonical_question_representative": "...",
  "law_area": "migration_status",
  "authority_context": ["Buergeramt", "Auslaenderbehoerde"],
  "candidate_ids": ["tg-qa-candidate:..."],
  "canonicalization_evidence_ids": ["tg-question-canonicalization-evidence:..."],
  "representative_raw_questions": [
    {
      "candidate_id": "tg-qa-candidate:...",
      "question_text_redacted": "..."
    }
  ],
  "cluster_size": 5,
  "cluster_confidence": "medium",
  "cluster_quality_flags": [],
  "merge_policy_version": "tg_legal_issue_cluster_policy_v1",
  "review_route": "needs_cluster_review",
  "coverage_status": "unmeasured"
}
```

Clusters with broad, conflicting, low-confidence, or low-cohesion evidence must
be flagged instead of automatically approved.

## Issue Cluster Summary And Manifest Requirements

The issue cluster command must write:

- issue cluster JSONL
- issue cluster summary JSON
- issue cluster manifest JSON

The summary JSON must include:

- source canonicalization evidence artifact paths
- source canonical embedding record artifact paths when used
- processed evidence count
- completed cluster count
- emitted cluster count
- excluded, uncertain, and failed counts
- counts by law area
- counts by authority context
- counts by cluster quality flag
- counts by review route
- merge policy version
- runtime contour
- generated timestamp

The manifest JSON must include:

- input artifact paths
- output artifact paths
- policy versions
- embedding profile ids when embeddings were used
- runtime contour
- known limitations
- unresolved backlog counts

## Coverage Report JSONL Shape

Each coverage record must include:

```json
{
  "coverage_record_id": "tg-legal-issue-coverage:...",
  "legal_issue_cluster_id": "tg-legal-issue-cluster:...",
  "coverage_analysis_version": "tg_legal_issue_coverage_v1",
  "coverage_status": "partial",
  "best_reviewed_case_id": "tg-eval-case:...",
  "best_question_bank_entry_id": "",
  "question_similarity_score": 0.84,
  "issue_frame_similarity_score": 0.91,
  "supporting_candidate_ids": ["tg-qa-candidate:..."],
  "coverage_gap_flags": ["reviewed_case_exists_but_no_cluster_answer"],
  "known_limitations": [
    "telegram_answers_are_evaluation_material_not_legal_truth"
  ]
}
```

Allowed `coverage_status` values:

- `covered`
- `partial`
- `uncovered`
- `excluded`
- `uncertain`

## Coverage Summary Requirements

The summary JSON must include:

- source canonicalization artifact paths
- source issue cluster artifact paths
- reviewed 006 final dataset artifact paths
- question-bank artifact paths when present
- counts by coverage status
- counts by law area
- counts by authority context
- counts by cluster quality flag
- excluded and uncertain counts
- top uncovered issue clusters by size
- known limitations
- generated timestamp

## Coverage Interpretation Rules

- `covered` means a reviewed evaluation case or approved question-bank entry
  covers the same canonical issue frame.
- `partial` means a related reviewed case or question-bank entry exists but the
  issue differs materially or lacks reviewed reference answer material.
- `uncovered` means no reviewed case or question-bank entry currently covers
  the canonical issue cluster.
- `excluded` means the input is not a legal standalone issue cluster.
- `uncertain` means canonicalization or clustering evidence is insufficient for
  a coverage decision.

Coverage status must not imply that current law is correctly answered.
