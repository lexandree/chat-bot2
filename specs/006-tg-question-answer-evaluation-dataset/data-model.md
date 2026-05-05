# Data Model: Telegram Q/A Evaluation Dataset

## TgQaCandidate

Stage 1 candidate extracted from Telegram exports.

Required fields:

- `candidate_id`
- `export_id`
- `question_message_id`
- `question_date`
- `question_text_redacted`
- `topic_labels`
- `law_code_candidates`
- `answer_candidates`
- `trigger_evidence`
- `answer_source_counts`
- `answer_link_counts`
- `confidence_tier`
- `selection_status`
- `review_route`
- `quality_flags`

## AnswerCandidate

Answer-like message linked to a question candidate.

Required fields:

- `answer_candidate_id`
- `message_id`
- `date`
- `text_redacted`
- `answer_source_type`: `human_reply`, `known_wiki_bot`, or `other_bot`
- `answer_source_markers`
- `answer_candidate_priority`
- `answer_link_type`: `direct_reply_to_question`, `bot_reply_to_trigger`,
  `bot_after_trigger`, or future extension value
- `link_confidence`: `high`, `medium`, or `low`
- `trigger_message_id`
- `question_to_trigger_seconds`
- `trigger_to_bot_seconds`

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

Required fields:

- `embedding_item_id`
- `candidate_id`
- `text_role`: `question`, `answer`, or `qa_pair`
- `embedding_input_text`
- `embedding_prefix`
- `answer_candidate_id`
- `answer_source_type`
- `answer_link_type`
- `cluster_usage`
- `selection_policy`

## EmbeddingRecord

Vectorization output imported back into 006 artifacts.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `text_role`
- `embedding_profile_id`
- `provider`
- `model`
- `dimensions`
- `normalized`
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

## LlmAnalysisResult

External LLM analysis result for non-trivial clusters.

Required fields:

- `task_id`
- `qa_cluster_id`
- `llm_run_id`
- `is_real_user_question`
- `current_topic_relevance`
- `answer_candidate_quality`
- `normalized_question`
- `short_answer_summary`
- `drift_or_conflict_assessment`
- `recommended_selection_status`
- `needs_human_review`

## ManualReviewDecision

Human review decision.

Required fields:

- `review_decision_id`
- `qa_cluster_id`
- `decision`: `approve`, `reject`, `merge`, `split`, `needs_more_context`, or
  `uncertain`
- `selected_candidate_id`
- `selected_answer_candidate_id`
- `reviewer_hash`
- `reviewed_at`
- `decision_reason`

## FinalEvaluationCase

Record used by later retrieval/evaluation workflows.

Required fields:

- `case_id`
- `qa_cluster_id`
- `normalized_question`
- `question_text_redacted`
- `selected_answer_text_redacted`
- `selected_answer_candidate_id`
- `answer_source_type`
- `answer_link_type`
- `topic_labels`
- `law_code_candidates`
- `status`: `auto_selected` or `review_approved`
- `answer_drift_status`
- `provenance`

## DatasetManifest

Run-level metadata for final dataset.

Required fields:

- `dataset_id`
- `generated_at`
- `source_candidate_artifact`
- `source_cluster_artifact`
- `source_review_artifact`
- `case_count`
- `counts_by_status`
- `counts_by_topic_label`
- `counts_by_law_code_candidate`
- `counts_by_answer_source_type`
- `quality_report_path`
