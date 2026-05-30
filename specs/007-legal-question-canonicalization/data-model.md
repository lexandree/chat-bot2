# Data Model: Legal Question Canonicalization And Cluster Coverage

## CanonicalizationBatchItem

Review task emitted for a deterministic or LLM-assisted canonicalization pass.

Required fields:

- `task_id`
- `candidate_id`
- `task_scope`: `question_candidate`
- `canonicalization_contract_version`
- `prompt_version` or `policy_version`
- `prompt_example_set_id`
- `runtime_hint`
- redacted `input`
- `expected_output_schema`

Input must include redacted 006 candidate evidence only: source ids, redacted
question text, topic labels, law-code candidates, dialogue flags, selected
answer metadata when available, and source artifact references. Raw Telegram
exports and unredacted text are forbidden.

## CanonicalizationEvidence

Imported canonicalization result for one 006 candidate.

Required fields:

- `canonicalization_evidence_id`
- `task_id`
- `candidate_id`
- `canonicalization_run_id`
- `canonicalization_contract_version`
- `prompt_version` or `policy_version`
- `runtime_contour`
- `backend`
- `model_id` when applicable
- `status`: `completed`, `failed`, or `skipped`
- `failure_reason`
- `canonical_question`
- `canonical_question_language`
- `legal_issue_frame`
- `legal_issue_frame_slug`
- `law_area`
- `facts`
- `desired_outcome`
- `authority_context`
- `hidden_issues`
- `is_legal_answer_required`
- `is_standalone_question`
- `exclusion_reason`
- `confidence`: `low`, `medium`, or `high`
- `quality_flags`
- `provenance`

Validation rules:

- `canonical_question` must preserve the source user's language when status is
  `completed` and the candidate is not excluded.
- `legal_issue_frame_slug` must be stable, lowercase, and machine-oriented.
- `exclusion_reason=none` is valid only when `is_legal_answer_required=true`
  and `is_standalone_question=true`.
- LLM-created fields are review evidence only and cannot create final dataset
  eligibility.

## CanonicalizationRunManifest

Run-level metadata for one canonicalization pass.

Required fields:

- `canonicalization_run_id`
- `input_artifact_path`
- `batch_artifact_path`
- `result_artifact_path`
- `evidence_output_path`
- `runtime_contour`
- `backend`
- `model_id` when applicable
- `prompt_version` or `policy_version`
- `canonicalization_contract_version`
- `input_scope`
- `processed_count`
- `completed_count`
- `failed_count`
- `skipped_count`
- `excluded_count`
- `uncertain_count`
- `started_at`
- `completed_at`
- `known_limitations`

## CanonicalEmbeddingBatchItem

External vectorization input for canonical question and issue-frame text.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `canonicalization_evidence_id`
- `text_role`: `canonical_question` or `legal_issue_frame`
- `embedding_input_text`
- `embedding_prefix`: `Query:`
- `cluster_usage`
- `canonicalization_run_id`
- `embedding_profile_expected`

## CanonicalEmbeddingRecord

Imported vector evidence for a canonical embedding item.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `canonicalization_evidence_id`
- `text_role`
- `embedding_profile_id`
- `provider`
- `model`
- `variant`
- `dimensions`
- `normalized`
- `query_prefix`
- `document_prefix`
- `routing_mode`
- `task_semantics`
- `backend_name`
- `vector`
- `embedding_status`
- `failure_reason`

Embedding records are evaluation artifacts and do not write vectors to Neo4j.

## LegalIssueCluster

Cluster of canonicalized candidates representing one reviewable legal issue.

Required fields:

- `legal_issue_cluster_id`
- `legal_issue_frame_slug`
- `canonical_question_representative`
- `law_area`
- `authority_context`
- `candidate_ids`
- `canonicalization_evidence_ids`
- `representative_raw_questions`
- `cluster_size`
- `cluster_confidence`
- `cluster_quality_flags`
- `merge_policy_version`
- `review_route`
- `coverage_status`

Quality flags must identify broad, low-cohesion, conflicting, low-confidence,
or privacy-sensitive clusters instead of silently approving them.

## LegalIssueCluster Summary And Manifest

Issue cluster generation must write a cluster JSONL artifact plus summary and
manifest artifacts.

Summary required fields:

- source canonicalization evidence artifact path
- source canonical embedding record artifact path
- processed evidence count
- completed cluster count
- emitted cluster count
- excluded evidence count
- uncertain evidence count
- failed evidence count
- counts by law area
- counts by authority context
- counts by cluster quality flag
- counts by review route
- merge policy version
- runtime contour
- generated timestamp

Manifest required fields:

- artifact type
- input artifact paths
- output artifact paths
- policy versions
- embedding profile ids when embeddings were used
- runtime contour
- known limitations
- unresolved backlog counts

## ClusterCoverageRecord

Coverage evidence comparing one canonical issue cluster to reviewed 006 seed
cases or question-bank entries.

Required fields:

- `coverage_record_id`
- `legal_issue_cluster_id`
- `coverage_analysis_version`
- `coverage_status`: `covered`, `partial`, `uncovered`, `excluded`, or
  `uncertain`
- `best_reviewed_case_id`
- `best_question_bank_entry_id`
- `question_similarity_score`
- `issue_frame_similarity_score`
- `supporting_candidate_ids`
- `coverage_gap_flags`
- `known_limitations`

Coverage records must not treat Telegram answers as legal truth.

## ClusterReviewDecision

Human decision for one legal issue cluster.

Required fields:

- `cluster_review_decision_id`
- `legal_issue_cluster_id`
- `decision`: `approve_question_bank`, `approve_final_evaluation`, `reject`,
  `merge`, `split`, `needs_more_context`, or `uncertain`
- `decision_scope`
- `reviewed_canonical_question`
- `reviewed_legal_issue_frame_slug`
- `reference_answer_action`: `none`, `keep_selected_telegram_answer`,
  `replace_manual`, or `needs_manual_answer`
- `reference_answer_source`
- `selected_reference_answer_text_redacted` when retaining a reviewed Telegram
  answer for final evaluation promotion
- `manual_reference_answer_text_redacted`
- `reviewer_hash`
- `reviewed_at`
- `decision_reason`

Promotion rule:

- `approve_question_bank` may create a question-bank entry without a reference
  answer.
- `approve_final_evaluation` requires reviewed reference answer material.

## QuestionBankEntry

Reviewed or reviewable canonical issue entry.

Required fields:

- `question_bank_entry_id`
- `legal_issue_cluster_id`
- `canonical_question`
- `legal_issue_frame_slug`
- `law_area`
- `authority_context`
- `representative_raw_questions`
- `coverage_status`
- `review_status`
- `reference_answer_status`
- `provenance`

## QuestionBank Summary And Manifest

Question-bank build must write a question-bank JSONL artifact plus summary and
manifest artifacts.

Summary required fields:

- source issue cluster artifact path
- source review decision artifact path
- processed cluster count
- completed entry count
- excluded count
- failed decision count
- approved entry count
- rejected entry count
- needs-more-context count
- uncertain count
- missing reference answer count
- counts by law area
- counts by authority context
- counts by coverage status
- counts by reference answer status
- review policy version
- question-bank policy version
- runtime contour
- generated timestamp

Manifest required fields:

- artifact type
- input artifact paths
- output artifact paths
- review policy version
- question-bank policy version
- known limitations
- unresolved backlog counts

## ReviewedEvaluationCaseCandidate

Candidate for a final evaluation case created from a reviewed issue cluster.

Required fields:

- `case_candidate_id`
- `legal_issue_cluster_id`
- `source_006_case_id` when applicable
- `canonical_question`
- `question_text_redacted`
- `reference_answer_text_redacted`
- `reference_answer_source`
- `reference_answer_role`
- `review_status`
- `promotion_status`: `eligible`, `blocked_missing_reference_answer`, or
  `rejected`
- `provenance`

Only `eligible` records with reviewed reference answer material may enter a
reviewed evaluation dataset.

## FinalCaseCandidate Promotion Summary And Manifest

Final case candidate promotion must write a candidate JSONL artifact plus
summary and manifest artifacts.

Summary required fields:

- source question-bank artifact path
- source review decision artifact path
- processed question-bank entry count
- completed candidate count
- excluded count
- uncertain count
- failed count
- emitted candidate count
- eligible count
- blocked missing reference answer count
- rejected count
- LLM-only rejection count
- manual reference answer count
- accepted Telegram reference answer count
- counts by law area
- counts by authority context
- promotion policy version
- reference answer policy version
- runtime contour
- generated timestamp

Manifest required fields:

- artifact type
- input artifact paths
- output artifact paths
- promotion policy version
- reference answer policy version
- known limitations
- unresolved backlog counts

## ReviewedEvaluationDataset Artifact

Exported final evaluation dataset produced from eligible
`ReviewedEvaluationCaseCandidate` records.

Required files:

- reviewed final cases JSONL
- manifest JSON
- quality summary JSON

Each reviewed final case must include:

- `case_id`
- `case_candidate_id`
- `legal_issue_cluster_id`
- `canonical_question`
- `question_text_redacted`
- `reference_answer_text_redacted`
- `reference_answer_source`
- `reference_answer_role`
- `review_status`
- `provenance`

The manifest must include:

- source final case candidate artifact path
- case count
- counts by reference answer source
- counts by law area
- counts by review status
- policy versions
- generated timestamp
- known limitations

The quality summary must include:

- eligible input count
- exported case count
- blocked/rejected excluded counts
- missing reference answer exclusion count
- LLM-only exclusion count
- duplicate cluster or case id rejection count

## State Transitions

- Canonicalization evidence: `pending` -> `completed`, `failed`, or `skipped`.
- Issue cluster: `draft` -> `needs_review`, `review_approved`,
  `review_rejected`, `needs_split`, `needs_merge`, or `uncertain`.
- Question-bank entry: `candidate` -> `approved` or `rejected`.
- Evaluation promotion: `candidate` -> `eligible`,
  `blocked_missing_reference_answer`, or `rejected`.
- Reviewed evaluation dataset case: `eligible_candidate` -> `exported` or
  `excluded`.
