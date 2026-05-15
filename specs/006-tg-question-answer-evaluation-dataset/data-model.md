# Data Model: Telegram Q/A Evaluation Dataset

## TgQaCandidate

Stage 1 candidate extracted from Telegram exports.

Required fields:

- `candidate_id`
- `export_id`
- `question_message_id`
- `question_reply_to_message_id`
- `question_is_reply`
- `question_date`
- `question_text_redacted`
- `topic_labels`
- `law_code_candidates`
- `answer_candidates`
- `trigger_evidence`
- `source_message_ids`
- `answer_source_counts`
- `answer_link_counts`
- `answer_candidate_status`: aggregate status across linked answer candidates:
  `strong`, `partial`, or `no_answer`
- `trigger_evidence_count`
- `confidence_tier`
- `selection_policy`
- `selection_status`
- `review_route`
- `embedding_processing_status`
- `clustering_status`
- `question_cluster_id`
- `answer_cluster_id`
- `qa_cluster_id`
- `selected_answer_candidate_id`
- `selected_answer_date`
- `historical_answer_variant_count`
- `answer_drift_status`
- `review_status`
- `llm_processing_status`
- `trigger_linking_policy`
- `bot_answer_marking_policy`
- `quality_flags`

## AnswerCandidate

Answer-like message linked to a question candidate.

Required fields:

- `answer_candidate_id`
- `message_id`
- `date`
- `text_redacted`
- `answer_candidate_status`: `strong`, `partial`, or `no_answer`
- `answer_candidate_usable`: boolean eligibility for automatic latest-answer
  selection
- `answer_source_type`: `human_reply`, `known_wiki_bot`, or `other_bot`
- `answer_source_markers`
- `answer_candidate_priority`
- `author_bot_kind`
- `known_bot_usernames`
- `marking_reason`
- `answer_link_type`: `direct_reply_to_question`, `bot_reply_to_trigger`,
  `bot_after_trigger`, or future extension value
- `link_confidence`: `high`, `medium`, or `low`
- `trigger_message_id`
- `trigger_author_hash`
- `trigger_date`
- `question_to_trigger_seconds`
- `trigger_to_bot_seconds`
- `pii_redaction_status`

Usable answer predicate:

- `answer_candidate_status` is `strong` or `partial`;
- `answer_candidate_priority` is not `low`;
- `link_confidence` is `high` or `medium`;
- `text_redacted` is non-empty;
- the candidate is not excluded later by manual review or LLM/manual conflict
  evidence.

## TriggerEvidence

Short non-question message that caused or likely caused a known wiki-bot answer.

Required fields:

- `trigger_message_id`
- `trigger_date`
- `trigger_author_hash`
- `trigger_text_redacted`
- `trigger_link_type`: `direct_reply_trigger` or `nearby_trigger`
- `link_confidence`
- `linked_bot_message_id`
- `question_to_trigger_seconds`

## EmbeddingBatchItem

External vectorization input.

This item must preserve the existing Jina retrieval embedding semantics from
`src/retrieval/embedding_profile.py`.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `text_role`: `question`, `answer`, or `qa_pair`
- `embedding_input_text`
- `embedding_prefix`: `Query:` for `question`, `Document:` for `answer` and
  `qa_pair`
- `answer_candidate_id`
- `answer_source_type`
- `answer_link_type`
- `cluster_usage`
- `selection_policy`

## EmbeddingRecord

Vectorization output imported back into 006 artifacts.

Embedding records are file artifacts for evaluation-dataset construction. They
reuse the project Jina-compatible embedding contract but do not write vectors to
Neo4j.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `text_role`
- `embedding_profile_id`
- `provider`
- `model`
- `dimensions`
- `normalized`
- `query_prefix`
- `document_prefix`
- `routing_mode`
- `backend_name`
- `vector`
- `embedding_status`
- `failure_reason`

## SimilarityNeighbor

Nearest-neighbor evidence between embedded items.

Required fields:

- `source_embedding_item_id`
- `neighbor_embedding_item_id`
- `candidate_id`
- `neighbor_candidate_id`
- `similarity_space`: `question`, `answer`, or `qa_pair`
- `similarity_score`
- `rank`
- `threshold_version`

## ClusterRecord

Question, answer, or combined Q/A cluster.

Required fields:

- `cluster_id`
- `cluster_type`: `question`, `answer`, or `qa_pair`
- `candidate_ids`
- `answer_candidate_ids`
- `representative_candidate_id`
- `cluster_size`
- `cluster_confidence`
- `cluster_quality_flags`
- `similarity_thresholds`
- `clustering_policy_version`

## ClusteringPolicy

Versioned deterministic policy for similarity search, clustering, and drift
routing.

Required fields:

- `clustering_policy_version`
- `question_similarity_threshold`
- `answer_similarity_threshold`
- `qa_pair_similarity_threshold`
- `top_k`
- `max_component_size`
- `topic_overlap_required`
- `law_overlap_required`
- `answer_conflict_similarity_ceiling`
- `answer_changed_similarity_floor`
- `stable_cluster_min_answer_count`
- `auto_select_allowed_answer_statuses`
- `auto_select_allowed_link_confidences`
- `auto_select_excluded_answer_priorities`

Initial fixture policy:

- `question_similarity_threshold`: `0.82`
- `answer_similarity_threshold`: `0.86`
- `qa_pair_similarity_threshold`: `0.84`
- `top_k`: `20`
- `max_component_size`: `50`
- `topic_overlap_required`: `true` for auto-selection
- `law_overlap_required`: `false`
- `answer_conflict_similarity_ceiling`: `0.72`
- `answer_changed_similarity_floor`: `0.72`
- `stable_cluster_min_answer_count`: `1`
- `auto_select_allowed_answer_statuses`: `strong`, `partial`
- `auto_select_allowed_link_confidences`: `high`, `medium`
- `auto_select_excluded_answer_priorities`: `low`

Answer drift decision table:

- `not_evaluated`: clustering or selection has not run yet.
- `insufficient_history`: embeddings, neighbor evidence, or usable answer
  variants are missing, so drift cannot be assessed.
- `stable`: at least one usable answer exists, no competing answer cluster is
  above the conflict threshold, and all retained usable variants either belong
  to the selected answer cluster or have answer similarity at or above
  `answer_similarity_threshold`.
- `changed`: older usable variants differ from the selected latest answer, the
  variants are chronologically ordered, and selected-vs-older answer similarity
  is at or above `answer_changed_similarity_floor` but below
  `answer_similarity_threshold`.
- `conflicting`: multiple usable answer variants cannot be ordered as a simple
  historical change, have incompatible topic/law/source evidence, or have
  selected-vs-alternative answer similarity below
  `answer_conflict_similarity_ceiling`.

## ClusterSelection

Selection decision candidate for a Q/A cluster.

Required fields:

- `qa_cluster_id`
- `selection_status`
- `selected_candidate_id`
- `selected_answer_candidate_id`
- `selected_answer_date`
- `historical_answer_variants`
- `answer_drift_status`
- `selection_reasons`
- `review_route`

## LlmBatchItem

Review task emitted for an operator-managed LLM pass.

Required fields:

- `task_id`
- `task_scope`: `candidate` or `qa_cluster`
- `llm_contract_version`
- `prompt_version`
- `prompt_profile`: `full`, `compact`, or empty for older candidate batches
- redacted `input`
- `expected_output_schema`

For `qa_cluster` tasks, `full` profile preserves complete redacted cluster
evidence for long-context endpoints. `compact` profile preserves selected/latest
evidence first, truncates long redacted text, records `input_char_budget`, and
may have a companion full overflow item for a separate long-context run.

## LlmAnalysisResult

External LLM analysis result for non-trivial candidates or clusters.

Required fields:

- `task_id`
- `task_scope`: `candidate` or `qa_cluster`
- `candidate_id` when `task_scope=candidate`
- `qa_cluster_id` when `task_scope=qa_cluster`
- `llm_run_id`
- `llm_contract_version`
- `prompt_version`
- `runtime_contour`
- `backend`
- `model_file`
- `model_id` when available
- `quantization` when available
- `status`: `completed`, `failed`, or `skipped`
- `failure_reason`
- `is_real_user_question`
- `current_topic_relevance`
- `answer_candidate_quality`
- `normalized_question`
- `short_answer_summary`
- `drift_or_conflict_assessment`
- `recommended_selection_status`
- `needs_human_review`
- `question_intent`
- `legal_answer_requirement`
- `graph_db_evaluation_fit`
- `issue_spotting_required`
- `issue_spotting_level`: `none`, `low`, `medium`, `high`, or
  `unclassified`; calibration evidence only
- `issue_spotting_confidence`: `low`, `medium`, `high`, or `unclassified`
- `issue_spotting_reason`: short factual reason for the level
- `hidden_legal_issue_categories`: at most five broad taxonomy labels inferred
  from the facts; labels are for reporting, not keyword-triggered decisions
  (`residence_status`, `asylum_or_temporary_protection`,
  `work_authorization`, `self_employment`, `tax_income_reporting`,
  `social_benefits`, `health_insurance`, `family_or_children`,
  `housing_registration`, `education_language`, `authority_procedure`,
  `deadline_or_proof`, `travel_cross_border`, `criminal_or_fraud_risk`,
  `other`)
- `answer_must_expand_beyond_user_wording`
- `exclusion_reason`

## LlmRunManifest

Run-level metadata for one operator-managed LLM batch.

Required fields:

- `llm_run_id`
- `input_batch_path`
- `result_output_path`
- `runtime_contour`
- `backend`
- `model_file`
- `model_id` when available
- `quantization` when available
- `prompt_version`
- `llm_contract_version`
- `server_parameters`
- `endpoint_shape`
- `json_valid_result_count`
- `schema_valid_result_count`
- `manual_spot_check_sample_size`
- `manual_spot_check_outcome`
- `processed_count`
- `completed_count`
- `failed_count`
- `skipped_count`
- `unprocessed_count`
- `started_at`
- `completed_at`
- `operator_notes_path`

Import and resume rules:

- LLM result import key is `(llm_run_id, task_scope, task_id)`.
- Re-importing the same result key must update or de-duplicate the existing
  review evidence instead of appending duplicates.
- Partial JSONL imports are allowed: valid lines are imported, invalid lines are
  counted as failed, and unprocessed task ids remain backlog.
- Re-running import for the same manifest must preserve stable per-item status
  and must not promote any LLM result into `auto_selected` or final dataset
  records.

## ManualReviewDecision

Human review decision.

Manual review decides whether the question/case belongs in the evaluation
dataset. It does not approve the Telegram answer as legal truth. The selected
answer remains a reference/community answer used later for comparison with
graph DB output.

Current 006 import/build supports at most one manual decision row per
`qa_cluster_id`. Duplicating TSV rows to emulate a split is invalid. `split`
remains a reviewer classification outcome or backlog marker until a later
feature introduces explicit multi-case fan-out.

Required fields:

- `review_decision_id`
- `qa_cluster_id`
- `decision`: `approve`, `reject`, `merge`, `split`, `needs_more_context`, or
  `uncertain`
- `decision_scope`: `question_dataset_inclusion`
- `selected_candidate_id`
- `selected_answer_candidate_id`
- `reference_answer_action`: `keep_selected`, `replace_manual`, or
  `needs_manual_answer`
- `requested_reference_answer_action`: raw reviewer/sheet value before automatic
  override
- `reference_answer_role`:
  `community_answer_for_graph_db_comparison_not_legal_truth`
- `reference_answer_status`: reviewer's answer-side status such as
  `usable_reference_answer`, `partial_reference_answer`,
  `reference_answer_probably_not_answer`, `reference_answer_conflicting`,
  `missing_reference_answer`, `unreviewed_reference_answer`, or
  `manual_reference_answer`
- `manual_reference_answer_text_redacted`: required when
  `reference_answer_action=replace_manual`; when non-empty, it overrides
  `keep_selected`
- `manual_reference_answer_redaction_flags`
- `manual_question_text_redacted`: optional reviewer-supplied standalone
  evaluation question, used when the selected Telegram fragment is only dialogue
  context or when the LLM-normalized question should be promoted manually
- `manual_question_redaction_flags`
- `question_intent`
- `legal_answer_requirement`
- `graph_db_evaluation_fit`
- `issue_spotting_required`
- `issue_spotting_level`
- `issue_spotting_confidence`
- `issue_spotting_reason`
- `hidden_legal_issue_categories`
- `answer_must_expand_beyond_user_wording`
- `exclusion_reason`
- `reviewer_hash`
- `reviewed_at`
- `decision_reason`

## HumanReviewExportRecord

Human-facing review row generated from queue and LLM evidence. It is not a final
decision artifact; it exists to make manual classification practical.

Required fields:

- `qa_cluster_id`
- `decision_scope`: `question_dataset_inclusion`
- `suggested_decision`
- `question_dialogue_role`: `standalone_question`,
  `standalone_question_with_clarifying_answer`,
  `dialogue_clarification_question`, or `dialogue_context_fragment`
- `dialogue_issue_signals`
- `normalized_question`
- `original_redacted_question`
- `question_intent`
- `legal_answer_requirement`
- `graph_db_evaluation_fit`
- `issue_spotting_required`
- `issue_spotting_level`
- `issue_spotting_confidence`
- `issue_spotting_reason`
- `hidden_legal_issue_categories`
- `answer_must_expand_beyond_user_wording`
- `exclusion_reason`
- `reference_answer`
- `reference_answer_status`
- `suggested_reference_answer_action`
- `manual_reference_answer_text`
- `manual_question_text`

Dialogue fragment rule:

- `dialogue_clarification_question` and `dialogue_context_fragment` rows should
  normally be rejected as standalone evaluation cases.
- `standalone_question_with_clarifying_answer` rows may still be approved, but
  the reference answer should usually be replaced manually.

## FinalEvaluationCase

Record used by later retrieval/evaluation workflows.

Required fields:

- `case_id`
- `qa_cluster_id`
- `normalized_question`
- `question_text_redacted`
- `original_question_text_redacted`
- `question_text_source`: `selected_telegram_question` or
  `manual_review_override`
- `selected_answer_text_redacted`
- `reference_answer_text_redacted`
- `original_selected_answer_text_redacted`
- `selected_candidate_id`
- `selected_answer_candidate_id`
- `reference_answer_candidate_id`
- `reference_answer_source`: `selected_telegram_answer` or
  `manual_review_override`
- `reference_answer_action`
- `reference_answer_role`:
  `community_answer_for_graph_db_comparison_not_legal_truth`
- `reference_answer_status`
- `question_intent`
- `legal_answer_requirement`
- `graph_db_evaluation_fit`
- `issue_spotting_required`
- `issue_spotting_level`
- `issue_spotting_confidence`
- `issue_spotting_reason`
- `hidden_legal_issue_categories`
- `answer_must_expand_beyond_user_wording`
- `exclusion_reason`
- `manual_reference_answer_redaction_flags`
- `manual_question_redaction_flags`
- `question_inclusion_status`
- `answer_source_type`
- `answer_link_type`
- `selected_telegram_answer_source_type`
- `selected_telegram_answer_link_type`
- `topic_labels`
- `law_code_candidates`
- `status`: `auto_selected` or `review_approved`
- `answer_drift_status`
- `historical_answer_variant_count`
- `review_status`
- `provenance`

## DatasetManifest

Run-level metadata for final dataset.

Required fields:

- `dataset_id`
- `generated_at`
- `source_candidate_artifact`
- `source_cluster_artifact`
- `source_review_artifact`
- `run_ids_by_stage`
- `case_count`
- `counts_by_status`
- `counts_by_topic_label`
- `counts_by_law_code_candidate`
- `counts_by_answer_source_type`
- `counts_by_answer_link_type`
- `counts_by_reference_answer_source`
- `counts_by_reference_answer_action`
- `counts_by_reference_answer_status`
- `counts_by_graph_db_evaluation_fit`
- `counts_by_legal_answer_requirement`
- `counts_by_question_intent`
- `issue_spotting_required_count`
- `counts_by_issue_spotting_level`
- `counts_by_issue_spotting_confidence`
- `answer_must_expand_beyond_user_wording_count`
- `counts_by_hidden_legal_issue_category`
- `drift_conflict_counts`
- `known_limitations`
- `unresolved_backlog_counts`
- `quality_report_path`
