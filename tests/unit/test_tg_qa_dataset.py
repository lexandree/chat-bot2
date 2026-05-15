from __future__ import annotations

import json
from pathlib import Path
from math import sqrt

import pytest

from evaluation.tg_qa_dataset import (
    build_final_tg_qa_dataset,
    build_tg_qa_dataset_corpus_coverage_report,
    build_tg_qa_manual_review_queue,
    cluster_tg_qa_candidates,
    emit_tg_qa_cluster_llm_batch,
    emit_tg_qa_dataset_corpus_coverage_embedding_batch,
    extract_tg_qa_dataset,
    export_tg_qa_human_review,
    import_tg_qa_embedding_records,
    import_tg_qa_dataset_corpus_coverage_embeddings,
    import_tg_qa_llm_results,
    import_tg_qa_manual_review_decisions,
    filter_tg_qa_llm_batch_by_results,
    load_bot_catalog,
    merge_final_tg_qa_datasets,
    merge_tg_qa_llm_results,
    normalize_telegram_text,
    redact_text,
    resolve_export_paths,
    run_tg_qa_llm_batch,
    run_tg_qa_similarity,
    select_tg_qa_clusters,
    vectorize_tg_qa_embedding_batch,
    verify_tg_qa_boundaries,
)
from retrieval.embedding_profile import EmbeddingProfile


SAMPLE_EXPORT = Path("tests/fixtures/tg_sample_export")
SAMPLE_CATALOG = Path("tests/fixtures/tg_wiki_bot_catalog_sample.json")


def test_normalize_telegram_text_handles_mixed_text_parts() -> None:
    assert normalize_telegram_text(["Hello ", {"type": "mention", "text": "@bot"}]) == "Hello @bot"


def test_redact_text_removes_obvious_pii() -> None:
    redacted, flags = redact_text("Пишите @person на a@example.com, телефон +49 151 12345678, сайт https://x.y")

    assert "[USERNAME]" in redacted
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "[URL]" in redacted
    assert set(flags) == {"email_redacted", "phone_redacted", "url_redacted", "username_redacted"}


def test_load_bot_catalog_and_resolve_export_paths() -> None:
    catalog = load_bot_catalog(SAMPLE_CATALOG)
    paths = resolve_export_paths([SAMPLE_EXPORT])

    assert catalog[0].usernames == ("@berlin_wiki_bot",)
    assert paths == [SAMPLE_EXPORT / "result.json"]


def test_extract_tg_qa_dataset_from_minimal_sample(tmp_path: Path) -> None:
    output = tmp_path / "candidates.jsonl"
    summary_output = tmp_path / "summary.json"
    embedding_output = tmp_path / "embedding_batch.jsonl"
    llm_output = tmp_path / "llm_batch.jsonl"

    result = extract_tg_qa_dataset(
        input_paths=[SAMPLE_EXPORT],
        bot_catalog_path=SAMPLE_CATALOG,
        output_path=output,
        summary_output_path=summary_output,
        embedding_batch_output_path=embedding_output,
        llm_batch_output_path=llm_output,
        max_candidates=20,
        min_attention_score=6,
    )

    assert len(result.candidates) == 2
    candidate = next(item for item in result.candidates if item["law_code_candidates"] == ["AufenthG", "BeschV"])
    off_topic = next(item for item in result.candidates if item["law_code_candidates"] == [])
    assert candidate["is_question"] is True
    assert candidate["question_is_reply"] is False
    assert candidate["question_reply_to_message_id"] == ""
    assert candidate["answer_candidate_status"] == "strong"
    assert candidate["bot_mentions"] == ["@berlin_wiki_bot"]
    assert candidate["law_code_candidates"] == ["AufenthG", "BeschV"]
    assert candidate["topic_labels"] == ["employment", "migration_status"]
    assert candidate["reply_count"] == 4
    assert candidate["source_message_ids"] == ["3", "7", "9", "4", "5", "8", "11", "10"]
    assert "[EMAIL]" in candidate["question_text_redacted"]
    assert "[PHONE]" in candidate["question_text_redacted"]
    assert "[USERNAME]" in candidate["question_text_redacted"]
    assert candidate["confidence_tier"] == "high"
    assert candidate["selection_policy"] == "semantic_qa_cluster_latest_usable_answer"
    assert candidate["selection_status"] == "pending_embedding_cluster"
    assert candidate["review_route"] == "embedding_cluster_selection"
    assert candidate["embedding_processing_status"] == "not_run"
    assert candidate["clustering_status"] == "not_run"
    assert candidate["question_cluster_id"] == ""
    assert candidate["answer_cluster_id"] == ""
    assert candidate["qa_cluster_id"] == ""
    assert candidate["answer_drift_status"] == "not_evaluated"
    assert candidate["answer_candidates"][0]["answer_candidate_id"].startswith("tg-answer-candidate:")
    assert candidate["answer_candidates"][0]["answer_source_type"] == "human_reply"
    assert candidate["answer_candidates"][0]["answer_candidate_status"] in {"strong", "partial"}
    assert candidate["answer_candidates"][0]["answer_candidate_usable"] is True
    assert len(candidate["answer_candidates"]) == 5
    known_bot_answer = next(item for item in candidate["answer_candidates"] if item["answer_source_type"] == "known_wiki_bot")
    other_bot_answer = next(item for item in candidate["answer_candidates"] if item["answer_source_type"] == "other_bot")
    assert known_bot_answer["known_bot_usernames"] == ["@berlin_wiki_bot"]
    assert known_bot_answer["answer_source_markers"] == ["known_wiki_bot_answer", "via_trigger"]
    assert known_bot_answer["answer_link_type"] == "bot_reply_to_trigger"
    assert known_bot_answer["link_confidence"] == "high"
    assert known_bot_answer["trigger_message_id"] == "7"
    nearby_bot_answer = next(
        item
        for item in candidate["answer_candidates"]
        if item["answer_source_type"] == "known_wiki_bot" and item["answer_link_type"] == "bot_after_trigger"
    )
    assert nearby_bot_answer["link_confidence"] == "medium"
    assert nearby_bot_answer["trigger_message_id"] == "9"
    assert known_bot_answer["answer_candidate_priority"] == "normal"
    assert known_bot_answer["marking_reason"] == "known_wiki_bot_author_match"
    assert other_bot_answer["answer_source_markers"] == ["other_bot_answer"]
    assert other_bot_answer["answer_link_type"] == "direct_reply_to_question"
    assert other_bot_answer["answer_candidate_priority"] == "low"
    assert other_bot_answer["answer_candidate_usable"] is False
    assert other_bot_answer["marking_reason"] == "bot_like_author_outside_known_catalog"
    assert candidate["trigger_evidence_count"] == 2
    assert candidate["trigger_evidence"][0]["trigger_link_type"] == "direct_reply_trigger"
    assert candidate["trigger_evidence"][0]["linked_bot_message_id"] == "8"
    assert candidate["trigger_evidence"][1]["trigger_link_type"] == "nearby_trigger"
    assert candidate["trigger_evidence"][1]["linked_bot_message_id"] == "10"
    assert candidate["answer_link_counts"] == {
        "bot_after_trigger": 1,
        "bot_reply_to_trigger": 1,
        "direct_reply_to_question": 3,
    }
    assert candidate["answer_source_counts"] == {"human_reply": 2, "known_wiki_bot": 2, "other_bot": 1}
    assert candidate["known_wiki_bot_answer_candidate_count"] == 2
    assert candidate["other_bot_answer_candidate_count"] == 1
    assert candidate["known_bot_answer_via_trigger_count"] == 2
    assert candidate["bot_answer_marking_policy"] == "all_reply_answers_kept_with_bot_source_markers"
    assert candidate["review_status"] == "pending"
    assert candidate["llm_processing_status"] == "not_run"
    assert off_topic["confidence_tier"] == "low"
    assert off_topic["selection_status"] == "uncertain"
    assert off_topic["quality_flags"] == ["low_topic_relevance", "missing_answer_candidate"]

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    embedding_items = [json.loads(line) for line in embedding_output.read_text(encoding="utf-8").splitlines()]
    llm_items = [json.loads(line) for line in llm_output.read_text(encoding="utf-8").splitlines()]
    written_candidates = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert summary["processed_message_count"] == 11
    assert summary["text_message_count"] == 10
    assert summary["candidate_pool_count"] == 2
    assert summary["candidate_offset"] == 0
    assert summary["max_candidates"] == 20
    assert summary["emitted_candidate_count"] == 2
    assert summary["counts_by_answer_candidate_status"] == {"no_answer": 1, "strong": 1}
    assert summary["counts_by_confidence_tier"] == {"high": 1, "low": 1}
    assert summary["counts_by_selection_status"] == {"pending_embedding_cluster": 1, "uncertain": 1}
    assert summary["bot_mention_candidate_count"] == 1
    assert summary["answer_candidate_count"] == 5
    assert summary["answer_source_counts"] == {"human_reply": 2, "known_wiki_bot": 2, "other_bot": 1}
    assert summary["answer_link_counts"] == {
        "bot_after_trigger": 1,
        "bot_reply_to_trigger": 1,
        "direct_reply_to_question": 3,
    }
    assert summary["trigger_evidence_count"] == 2
    assert summary["known_wiki_bot_answer_candidate_count"] == 2
    assert summary["other_bot_answer_candidate_count"] == 1
    assert summary["known_bot_answer_via_trigger_count"] == 2
    assert summary["selection_policy"] == "semantic_qa_cluster_latest_usable_answer"
    assert written_candidates[0]["candidate_id"] == candidate["candidate_id"]
    assert summary["orphan_trigger_chain_count"] == 0
    assert len(result.embedding_batch_items) == 12
    assert embedding_items[0]["text_role"] == "question"
    assert embedding_items[0]["embedding_input_text"].startswith("Query: ")
    assert any(
        item["text_role"] == "answer"
        and item["answer_source_type"] == "known_wiki_bot"
        and item["answer_link_type"] == "bot_reply_to_trigger"
        and item["embedding_input_text"].startswith("Document: ")
        for item in embedding_items
    )
    assert any(
        item["text_role"] == "qa_pair"
        and item["embedding_input_text"].startswith("Document: Question: ")
        and item["cluster_usage"] == ["qa_cluster"]
        for item in embedding_items
    )
    assert llm_items[0]["task_id"] == candidate["candidate_id"]
    assert llm_items[0]["task_scope"] == "candidate"
    assert llm_items[0]["input"]["answer_source_counts"] == {"human_reply": 2, "known_wiki_bot": 2, "other_bot": 1}
    assert llm_items[0]["input"]["known_bot_answer_via_trigger_count"] == 2
    assert llm_items[0]["runtime_hint"] == "operator_managed_llama_server_openai_compatible"
    assert llm_items[0]["llm_contract_version"] == "tg_qa_llm_analysis_v1"
    assert llm_items[0]["prompt_version"] == "tg_qa_candidate_classifier_v4_1"
    assert "preserve the source user's language" in llm_items[0]["system_instruction"]
    assert "Do not classify by topic words alone" in llm_items[0]["system_instruction"]
    assert "ordinary legal question" in llm_items[0]["system_instruction"]
    assert "issue_spotting_required" in llm_items[0]["expected_output_schema"]
    assert "issue_spotting_level" in llm_items[0]["expected_output_schema"]
    assert "drift_or_conflict_assessment" in llm_items[0]["expected_output_schema"]

    offset_result = extract_tg_qa_dataset(
        input_paths=[SAMPLE_EXPORT],
        bot_catalog_path=SAMPLE_CATALOG,
        max_candidates=1,
        candidate_offset=1,
        min_attention_score=6,
    )
    assert len(offset_result.candidates) == 1
    assert offset_result.summary["candidate_pool_count"] == 2
    assert offset_result.summary["candidate_offset"] == 1
    assert offset_result.summary["max_candidates"] == 1
    assert offset_result.candidates[0]["candidate_id"] == off_topic["candidate_id"]


def test_tg_qa_downstream_pipeline_uses_fixture_vectors_and_review_boundaries(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    summary_path = tmp_path / "summary.json"
    embedding_batch_path = tmp_path / "embedding_batch.jsonl"
    extract_tg_qa_dataset(
        input_paths=[SAMPLE_EXPORT],
        bot_catalog_path=SAMPLE_CATALOG,
        output_path=candidates_path,
        summary_output_path=summary_path,
        embedding_batch_output_path=embedding_batch_path,
        max_candidates=20,
        min_attention_score=6,
    )
    batch_items = [json.loads(line) for line in embedding_batch_path.read_text(encoding="utf-8").splitlines()]
    vectors_path = tmp_path / "fixture_vectors.jsonl"
    _write_jsonl(vectors_path, [_fixture_vector_record(item) for item in batch_items])

    embedding_records_path = tmp_path / "embedding_records.jsonl"
    embedding_summary_path = tmp_path / "embedding_summary.json"
    embedding_result = import_tg_qa_embedding_records(
        embedding_batch_path=embedding_batch_path,
        external_vectors_path=vectors_path,
        output_path=embedding_records_path,
        summary_output_path=embedding_summary_path,
        profile_metadata=EmbeddingProfile(embedding_profile_id="fixture_profile", dimensions=3),
    )
    assert embedding_result["summary"]["completed_count"] == len(batch_items)
    assert embedding_result["summary"]["failed_count"] == 0
    assert embedding_result["summary"]["embedding_profile"]["embedding_profile_id"] == "fixture_profile"

    neighbors_path = tmp_path / "neighbors.jsonl"
    similarity_summary_path = tmp_path / "similarity_summary.json"
    similarity_result = run_tg_qa_similarity(
        embedding_records_path=embedding_records_path,
        output_path=neighbors_path,
        summary_output_path=similarity_summary_path,
    )
    neighbor_spaces = {item["similarity_space"] for item in similarity_result["neighbors"]}
    assert {"question", "answer", "qa_pair"} <= neighbor_spaces
    assert similarity_result["summary"]["approval_side_effect"] == "none_similarity_does_not_merge_or_approve"

    question_clusters_path = tmp_path / "question_clusters.jsonl"
    answer_clusters_path = tmp_path / "answer_clusters.jsonl"
    qa_clusters_path = tmp_path / "qa_clusters.jsonl"
    cluster_summary_path = tmp_path / "cluster_summary.json"
    cluster_result = cluster_tg_qa_candidates(
        candidates_path=candidates_path,
        neighbors_path=neighbors_path,
        question_clusters_output_path=question_clusters_path,
        answer_clusters_output_path=answer_clusters_path,
        qa_clusters_output_path=qa_clusters_path,
        summary_output_path=cluster_summary_path,
    )
    assert cluster_result["summary"]["qa_cluster_count"] >= 2
    assert all(cluster["clustering_policy_version"] == "tg_qa_cluster_policy_v1" for cluster in cluster_result["qa_clusters"])

    selection_path = tmp_path / "cluster_selection.jsonl"
    selection_summary_path = tmp_path / "selection_summary.json"
    selection_result = select_tg_qa_clusters(
        candidates_path=candidates_path,
        qa_clusters_path=qa_clusters_path,
        answer_clusters_path=answer_clusters_path,
        output_path=selection_path,
        summary_output_path=selection_summary_path,
    )
    selections = selection_result["selections"]
    assert any(item["selection_status"] == "auto_selected" for item in selections)
    auto_selected = next(item for item in selections if item["selection_status"] == "auto_selected")
    assert auto_selected["answer_drift_status"] == "stable"
    assert auto_selected["selected_answer_candidate_id"]
    assert auto_selected["historical_answer_variant_count"] >= 1

    llm_batch_path = tmp_path / "cluster_llm_batch.jsonl"
    llm_batch = emit_tg_qa_cluster_llm_batch(
        candidates_path=candidates_path,
        selection_path=selection_path,
        output_path=llm_batch_path,
    )
    assert llm_batch["summary"]["batch_item_count"] >= 1
    llm_task = llm_batch["batch_items"][0]
    compact_llm_batch_path = tmp_path / "cluster_llm_batch_compact.jsonl"
    overflow_llm_batch_path = tmp_path / "cluster_llm_batch_overflow.jsonl"
    compact_llm_batch = emit_tg_qa_cluster_llm_batch(
        candidates_path=candidates_path,
        selection_path=selection_path,
        output_path=compact_llm_batch_path,
        prompt_profile="compact",
        input_char_budget=1,
        overflow_output_path=overflow_llm_batch_path,
    )
    assert compact_llm_batch["summary"]["prompt_profile"] == "compact"
    assert compact_llm_batch["summary"]["overflow_item_count"] >= 1
    assert compact_llm_batch["batch_items"][0]["prompt_version"] == "tg_qa_cluster_reviewer_compact_v4_1"
    assert "preserve the source user's language" in compact_llm_batch["batch_items"][0]["system_instruction"]
    assert "Do not classify by topic words alone" in compact_llm_batch["batch_items"][0]["system_instruction"]
    assert "ordinary legal question" in compact_llm_batch["batch_items"][0]["system_instruction"]
    assert compact_llm_batch["batch_items"][0]["input"]["context_note"]["profile"] == "compact_small_context"
    assert overflow_llm_batch_path.exists()
    manual_overlay_path = tmp_path / "manual_overlay.tsv"
    manual_overlay_path.write_text(
        "\t".join(["qa_cluster_id", "manual_question_text", "manual_reference_answer_text"])
        + "\n"
        + "\t".join(
            [
                llm_task["task_id"],
                "Manual corrected question from reviewer@example.com?",
                "Manual corrected answer from reviewer@example.com.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    overlay_batch = emit_tg_qa_cluster_llm_batch(
        candidates_path=candidates_path,
        selection_path=selection_path,
        manual_review_path=manual_overlay_path,
    )
    overlay_item = next(item for item in overlay_batch["batch_items"] if item["task_id"] == llm_task["task_id"])
    overlay = overlay_item["input"]["review_overlay"]
    assert overlay_batch["summary"]["manual_review_overlay_count"] == 1
    assert overlay["question_text_source"] == "manual_question_text"
    assert "[EMAIL]" in overlay["question_text_redacted"]
    assert "[EMAIL]" in overlay["reference_answer_text_redacted"]
    llm_results_path = tmp_path / "llm_results.jsonl"
    _write_jsonl(
        llm_results_path,
        [
            _llm_result_for_task(llm_task, run_id="llm-run-fixture"),
            _llm_result_for_task(llm_task, run_id="llm-run-fixture"),
        ],
    )
    llm_evidence_path = tmp_path / "llm_evidence.jsonl"
    llm_manifest_path = tmp_path / "llm_manifest.json"
    llm_import = import_tg_qa_llm_results(
        batch_path=llm_batch_path,
        result_path=llm_results_path,
        evidence_output_path=llm_evidence_path,
        manifest_output_path=llm_manifest_path,
        llm_run_id="llm-run-fixture",
    )
    assert llm_import["manifest"]["completed_count"] == 2
    assert llm_import["manifest"]["duplicate_result_count"] == 1
    assert llm_import["manifest"]["manual_spot_check_sample_size"] == 2
    assert llm_import["evidence"][0]["can_create_final_record"] is False

    review_queue_path = tmp_path / "review_queue.jsonl"
    review_summary_path = tmp_path / "review_summary.json"
    review_queue = build_tg_qa_manual_review_queue(
        candidates_path=candidates_path,
        selection_path=selection_path,
        llm_evidence_path=llm_evidence_path,
        output_path=review_queue_path,
        summary_output_path=review_summary_path,
    )
    assert review_queue["summary"]["queue_count"] >= 1

    human_review_md = tmp_path / "human_review.md"
    human_review_tsv = tmp_path / "human_review.tsv"
    human_review_summary = tmp_path / "human_review_summary.json"
    human_review = export_tg_qa_human_review(
        review_queue_path=review_queue_path,
        markdown_output_path=human_review_md,
        tsv_output_path=human_review_tsv,
        summary_output_path=human_review_summary,
        max_text_chars=300,
    )
    assert human_review["summary"]["review_item_count"] == review_queue["summary"]["queue_count"]
    human_review_text = human_review_md.read_text(encoding="utf-8")
    assert "Telegram Q/A Human Review" in human_review_text
    assert "Question To Classify" in human_review_text
    assert "Reference Answer For Later Graph DB Comparison" in human_review_text
    tsv_header = human_review_tsv.read_text(encoding="utf-8").splitlines()[0]
    assert tsv_header.startswith("rank\tbucket\tsuggested_decision")
    assert "reference_answer" in tsv_header
    assert "manual_question_text" in tsv_header
    assert "graph_db_evaluation_fit" in tsv_header
    assert "issue_spotting_required" in tsv_header
    assert "issue_spotting_level" in tsv_header
    assert human_review["records"][0]["decision_scope"] == "question_dataset_inclusion"
    assert human_review["records"][0]["reference_answer_role"].endswith("not_legal_truth")
    assert human_review["records"][0]["suggested_decision"] in {"approve", "reject", "needs_more_context", "uncertain"}

    decisions_input_path = tmp_path / "review_decisions_input.jsonl"
    queue_item = review_queue["queue"][0]
    _write_jsonl(
        decisions_input_path,
        [
            {
                "qa_cluster_id": queue_item["qa_cluster_id"],
                "decision": "uncertain",
                "reviewer_hash": "reviewer-fixture",
                "decision_reason": "fixture keeps dirty chat case out of final dataset",
            }
        ],
    )
    imported_decisions_path = tmp_path / "review_decisions.jsonl"
    review_decision_summary_path = tmp_path / "review_decision_summary.json"
    imported_decisions = import_tg_qa_manual_review_decisions(
        review_queue_path=review_queue_path,
        decisions_path=decisions_input_path,
        output_path=imported_decisions_path,
        summary_output_path=review_decision_summary_path,
    )
    assert imported_decisions["summary"]["imported_count"] == 1
    assert imported_decisions["decisions"][0]["trust_boundary"].endswith("not_legal_truth")

    final_cases_path = tmp_path / "final_cases.jsonl"
    final_manifest_path = tmp_path / "dataset_manifest.json"
    final_quality_path = tmp_path / "dataset_quality_report.json"
    final_result = build_final_tg_qa_dataset(
        candidates_path=candidates_path,
        selection_path=selection_path,
        review_decisions_path=imported_decisions_path,
        output_path=final_cases_path,
        manifest_output_path=final_manifest_path,
        quality_output_path=final_quality_path,
    )
    assert final_result["manifest"]["case_count"] == 1
    assert final_result["cases"][0]["status"] == "auto_selected"
    assert final_result["cases"][0]["reference_answer_text_redacted"]
    assert final_result["cases"][0]["reference_answer_role"].endswith("not_legal_truth")
    assert final_result["cases"][0]["question_inclusion_status"] == "auto_selected"
    serialized_final = final_cases_path.read_text(encoding="utf-8")
    assert "test@example.com" not in serialized_final
    assert "generated_answer" not in serialized_final

    override_decisions_input_path = tmp_path / "review_decisions_override_input.jsonl"
    _write_jsonl(
        override_decisions_input_path,
        [
            {
                "qa_cluster_id": queue_item["qa_cluster_id"],
                "decision": "approve",
                "selected_candidate_id": queue_item["candidate_ids"][0],
                "selected_answer_candidate_id": queue_item.get("selected_answer_candidate", {}).get("answer_candidate_id", ""),
                "reference_answer_action": "keep_selected",
                "reference_answer_status": "manual_reference_answer",
                "question_intent": "legal_information_request",
                "legal_answer_requirement": "requires_hidden_issue_spotting",
                "graph_db_evaluation_fit": "legal_core",
                "issue_spotting_required": True,
                "issue_spotting_level": "high",
                "issue_spotting_confidence": "medium",
                "issue_spotting_reason": "surface insurance wording misses tax and self-employment duties",
                "hidden_legal_issue_categories": ["self_employment", "tax_obligation"],
                "answer_must_expand_beyond_user_wording": True,
                "exclusion_reason": "none",
                "manual_question_text": "Manual question, contact test@example.com?",
                "manual_reference_answer_text": "Manual reference answer, contact test@example.com should be redacted.",
                "reviewer_hash": "reviewer-fixture",
                "decision_reason": "question is useful but selected chat answer is not",
            }
        ],
    )
    override_decisions_path = tmp_path / "review_decisions_override.jsonl"
    override_import = import_tg_qa_manual_review_decisions(
        review_queue_path=review_queue_path,
        decisions_path=override_decisions_input_path,
        output_path=override_decisions_path,
    )
    override_final = build_final_tg_qa_dataset(
        candidates_path=candidates_path,
        selection_path=selection_path,
        review_decisions_path=override_decisions_path,
    )
    override_case = next(item for item in override_final["cases"] if item["qa_cluster_id"] == queue_item["qa_cluster_id"])
    assert override_import["summary"]["manual_answer_overrode_reference_action_count"] == 1
    assert override_import["summary"]["manual_question_override_count"] == 1
    assert override_import["summary"]["issue_spotting_required_count"] == 1
    assert override_import["summary"]["counts_by_issue_spotting_level"] == {"high": 1}
    assert override_import["summary"]["counts_by_issue_spotting_confidence"] == {"medium": 1}
    assert override_import["summary"]["counts_by_graph_db_evaluation_fit"] == {"legal_core": 1}
    assert override_import["summary"]["counts_by_hidden_legal_issue_category"] == {
        "self_employment": 1,
        "tax_obligation": 1,
    }
    assert override_import["decisions"][0]["requested_reference_answer_action"] == "keep_selected"
    assert override_import["decisions"][0]["reference_answer_action"] == "replace_manual"
    assert override_import["decisions"][0]["manual_reference_answer_text_redacted"].endswith("redacted.")
    assert "[EMAIL]" in override_import["decisions"][0]["manual_question_text_redacted"]
    assert "[EMAIL]" in override_case["normalized_question"]
    assert override_case["question_text_source"] == "manual_review_override"
    assert override_case["original_question_text_redacted"] != override_case["question_text_redacted"]
    assert override_case["graph_db_evaluation_fit"] == "legal_core"
    assert override_case["issue_spotting_required"] is True
    assert override_case["issue_spotting_level"] == "high"
    assert override_case["issue_spotting_confidence"] == "medium"
    assert override_case["issue_spotting_reason"].startswith("surface insurance")
    assert override_case["hidden_legal_issue_categories"] == ["self_employment", "tax_obligation"]
    assert "[EMAIL]" in override_case["reference_answer_text_redacted"]
    assert override_case["reference_answer_source"] == "manual_review_override"
    assert override_case["reference_answer_status"] == "manual_reference_answer"
    assert override_final["quality"]["issue_spotting_required_count"] == 1
    assert override_final["quality"]["counts_by_issue_spotting_level"]["high"] == 1
    assert override_final["quality"]["counts_by_graph_db_evaluation_fit"]["legal_core"] == 1

    tsv_decisions_input_path = tmp_path / "review_decisions_input.tsv"
    tsv_decisions_input_path.write_text(
        "\t".join(
            [
                "qa_cluster_id",
                "decision",
                "selected_candidate_id",
                "selected_answer_candidate_id",
                "graph_db_evaluation_fit",
                "issue_spotting_required",
                "issue_spotting_level",
                "issue_spotting_confidence",
                "issue_spotting_reason",
                "hidden_legal_issue_categories",
                "manual_question_text",
                "manual_reference_answer_text",
            ]
        )
        + "\n"
        + "\t".join(
            [
                queue_item["qa_cluster_id"],
                "approve",
                queue_item["candidate_ids"][0],
                queue_item.get("selected_answer_candidate", {}).get("answer_candidate_id", ""),
                "legal_adjacent",
                "true",
                "medium",
                "high",
                "TSV issue spotting reason",
                "income_reporting,tax_obligation",
                "TSV manual question, contact reviewer@example.com?",
                "TSV manual reference answer.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tsv_decisions_path = tmp_path / "review_decisions_from_tsv.jsonl"
    tsv_import = import_tg_qa_manual_review_decisions(
        review_queue_path=review_queue_path,
        decisions_path=tsv_decisions_input_path,
        output_path=tsv_decisions_path,
    )
    tsv_final = build_final_tg_qa_dataset(
        candidates_path=candidates_path,
        selection_path=selection_path,
        review_decisions_path=tsv_decisions_path,
    )
    tsv_case = next(item for item in tsv_final["cases"] if item["qa_cluster_id"] == queue_item["qa_cluster_id"])
    assert tsv_import["summary"]["manual_question_override_count"] == 1
    assert tsv_import["summary"]["counts_by_graph_db_evaluation_fit"] == {"legal_adjacent": 1}
    assert tsv_import["summary"]["counts_by_hidden_legal_issue_category"] == {
        "income_reporting": 1,
        "tax_obligation": 1,
    }
    assert "[EMAIL]" in tsv_case["question_text_redacted"]
    assert tsv_case["question_text_source"] == "manual_review_override"
    assert tsv_case["issue_spotting_required"] is True
    assert tsv_case["issue_spotting_level"] == "medium"
    assert tsv_case["issue_spotting_confidence"] == "high"

    duplicate_tsv_input_path = tmp_path / "review_decisions_duplicate.tsv"
    duplicate_tsv_input_path.write_text(
        "\t".join(
            [
                "qa_cluster_id",
                "decision",
                "selected_candidate_id",
                "selected_answer_candidate_id",
                "manual_question_text",
            ]
        )
        + "\n"
        + "\t".join(
            [
                queue_item["qa_cluster_id"],
                "approve",
                queue_item["candidate_ids"][0],
                queue_item.get("selected_answer_candidate", {}).get("answer_candidate_id", ""),
                "Split candidate question A?",
            ]
        )
        + "\n"
        + "\t".join(
            [
                queue_item["qa_cluster_id"],
                "approve",
                queue_item["candidate_ids"][0],
                queue_item.get("selected_answer_candidate", {}).get("answer_candidate_id", ""),
                "Split candidate question B?",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate qa_cluster_id rows are not supported"):
        import_tg_qa_manual_review_decisions(
            review_queue_path=review_queue_path,
            decisions_path=duplicate_tsv_input_path,
        )

    merge_input_one = tmp_path / "merge_input_one.jsonl"
    merge_input_two = tmp_path / "merge_input_two.jsonl"
    merge_manifest_one = tmp_path / "merge_manifest_one.json"
    merge_manifest_two = tmp_path / "merge_manifest_two.json"
    merge_output = tmp_path / "merged_final_cases.jsonl"
    merge_manifest_output = tmp_path / "merged_final_manifest.json"
    merge_quality_output = tmp_path / "merged_final_quality.json"
    case_one = dict(override_case)
    case_one["case_id"] = "tg-eval-case:one"
    case_one["qa_cluster_id"] = "tg-qa-pair-cluster:one"
    case_one.pop("issue_spotting_level", None)
    case_one.pop("issue_spotting_confidence", None)
    case_one.pop("issue_spotting_reason", None)
    case_one["provenance"] = {"source_candidate_artifact": "fixture-one"}
    case_two = dict(final_result["cases"][0])
    case_two["case_id"] = "tg-eval-case:two"
    case_two["qa_cluster_id"] = "tg-qa-pair-cluster:two"
    case_two["provenance"] = {"source_candidate_artifact": "fixture-two"}
    _write_jsonl(merge_input_one, [case_one])
    _write_jsonl(merge_input_two, [case_two])
    merge_manifest_one.write_text(
        json.dumps({"known_limitations": ["fixture_limit_one"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    merge_manifest_two.write_text(
        json.dumps({"known_limitations": ["fixture_limit_two"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    merged = merge_final_tg_qa_datasets(
        case_paths=[merge_input_one, merge_input_two],
        manifest_paths=[merge_manifest_one, merge_manifest_two],
        output_path=merge_output,
        manifest_output_path=merge_manifest_output,
        quality_output_path=merge_quality_output,
    )
    assert merged["manifest"]["case_count"] == 2
    assert merged["manifest"]["counts_by_reference_answer_source"]["manual_review_override"] == 1
    assert merged["manifest"]["counts_by_reference_answer_source"]["selected_telegram_answer"] == 1
    assert merged["quality"]["manual_reviewed_count"] == 1
    assert merged["quality"]["auto_selected_count"] == 1
    merged_cases = [json.loads(line) for line in merge_output.read_text(encoding="utf-8").splitlines()]
    merged_case_one = next(item for item in merged_cases if item["case_id"] == "tg-eval-case:one")
    assert merged_case_one["issue_spotting_level"] == "unclassified"
    assert merged_case_one["issue_spotting_confidence"] == "unclassified"
    assert merged_case_one["issue_spotting_reason"] == ""
    assert merged_case_one["provenance"]["source_final_case_artifact"] == str(merge_input_one)
    assert "telegram_answers_are_evaluation_material_not_legal_truth" in merged["manifest"]["known_limitations"]

    coverage_cases_path = tmp_path / "coverage_cases.jsonl"
    _write_jsonl(coverage_cases_path, [case_one])
    coverage_batch_path = tmp_path / "coverage_embedding_batch.jsonl"
    coverage_batch_summary_path = tmp_path / "coverage_embedding_batch_summary.json"
    coverage_batch = emit_tg_qa_dataset_corpus_coverage_embedding_batch(
        final_cases_path=coverage_cases_path,
        candidates_path=candidates_path,
        output_path=coverage_batch_path,
        summary_output_path=coverage_batch_summary_path,
    )
    assert coverage_batch["summary"]["dataset_case_count"] == 1
    assert coverage_batch["summary"]["corpus_candidate_count"] == len(
        candidates_path.read_text(encoding="utf-8").splitlines()
    )
    coverage_vectors_path = tmp_path / "coverage_vectors.jsonl"
    coverage_vector_records = []
    for item in coverage_batch["batch_items"]:
        scope = item["coverage_scope"]
        role = item["text_role"]
        source_message_id = str(item.get("source_message_id", ""))
        if scope == "dataset" and role == "question":
            vector = [1.0, 0.0, 0.0]
        elif scope == "dataset" and role == "answer":
            vector = [0.0, 1.0, 0.0]
        elif scope == "corpus" and role == "question" and source_message_id == "3":
            vector = [1.0, 0.0, 0.0]
        elif scope == "corpus" and role == "question":
            vector = [0.6, sqrt(1 - 0.6**2), 0.0]
        else:
            vector = [0.0, 1.0, 0.0]
        coverage_vector_records.append(
            {
                "embedding_item_id": item["embedding_item_id"],
                "candidate_id": item["candidate_id"],
                "answer_candidate_id": item.get("answer_candidate_id", ""),
                "text_role": role,
                "backend_name": "fixture_vectors",
                "vector": vector,
            }
        )
    _write_jsonl(coverage_vectors_path, coverage_vector_records)
    coverage_records_path = tmp_path / "coverage_records.jsonl"
    coverage_import_summary_path = tmp_path / "coverage_import_summary.json"
    coverage_import = import_tg_qa_dataset_corpus_coverage_embeddings(
        embedding_batch_path=coverage_batch_path,
        external_vectors_path=coverage_vectors_path,
        output_path=coverage_records_path,
        summary_output_path=coverage_import_summary_path,
        profile_metadata=EmbeddingProfile(embedding_profile_id="fixture_profile", dimensions=3),
    )
    assert coverage_import["summary"]["completed_count"] == len(coverage_batch["batch_items"])
    coverage_report_path = tmp_path / "coverage_report.jsonl"
    coverage_report_summary_path = tmp_path / "coverage_report_summary.json"
    coverage_report = build_tg_qa_dataset_corpus_coverage_report(
        embedding_records_path=coverage_records_path,
        output_path=coverage_report_path,
        summary_output_path=coverage_report_summary_path,
        chunk_size=2,
        max_samples_per_bucket=5,
    )
    assert coverage_report["summary"]["dataset_case_count"] == 1
    assert coverage_report["summary"]["corpus_candidate_count"] == len(
        candidates_path.read_text(encoding="utf-8").splitlines()
    )
    assert coverage_report["summary"]["counts_by_question_coverage_band"]["high"] == 1
    assert coverage_report["summary"]["counts_by_question_coverage_band"]["uncovered"] == 1
    assert coverage_report["summary"]["counts_by_coverage_status"]["covered"] == 1
    assert coverage_report["summary"]["counts_by_coverage_status"]["uncovered"] == 1
    assert coverage_report["summary"]["counts_by_answer_support_band"]["strong"] >= 1

    filtered_coverage_batch = emit_tg_qa_dataset_corpus_coverage_embedding_batch(
        final_cases_path=coverage_cases_path,
        candidates_path=candidates_path,
        corpus_filter_mode="law_or_topic",
        include_corpus_answers=False,
    )
    filtered_expected_count = 0
    for line in candidates_path.read_text(encoding="utf-8").splitlines():
        candidate = json.loads(line)
        if candidate.get("law_code_candidates") or candidate.get("topic_labels"):
            filtered_expected_count += 1
    assert filtered_coverage_batch["summary"]["corpus_filter_mode"] == "law_or_topic"
    assert filtered_coverage_batch["summary"]["include_corpus_answers"] is False
    assert filtered_coverage_batch["summary"]["corpus_candidate_count_before_filter"] == len(
        candidates_path.read_text(encoding="utf-8").splitlines()
    )
    assert filtered_coverage_batch["summary"]["corpus_candidate_count"] == filtered_expected_count
    assert filtered_coverage_batch["summary"]["corpus_candidate_filtered_out_count"] == (
        len(candidates_path.read_text(encoding="utf-8").splitlines()) - filtered_expected_count
    )
    assert filtered_coverage_batch["summary"]["corpus_candidate_with_representative_answer_count"] == 0
    assert "corpus:answer" not in filtered_coverage_batch["summary"]["counts_by_scope_role"]


def test_run_tg_qa_llm_batch_extracts_json_from_gemma_wrapper(tmp_path: Path) -> None:
    batch_path = tmp_path / "llm_batch.jsonl"
    output_path = tmp_path / "llm_results.jsonl"
    summary_path = tmp_path / "llm_run_summary.json"
    task = {
        "task_id": "tg-qa-cluster:fixture",
        "task_scope": "qa_cluster",
        "llm_contract_version": "tg_qa_llm_analysis_v1",
        "prompt_version": "tg_qa_cluster_reviewer_compact_v1",
        "expected_output_schema": {
            "is_real_user_question": "boolean",
            "current_topic_relevance": "none|low|medium|high",
            "answer_candidate_quality": "none|partial|strong|conflicting",
            "normalized_question": "string",
            "short_answer_summary": "string",
            "drift_or_conflict_assessment": "stable|changed|conflicting|insufficient_history|not_evaluated",
            "recommended_selection_status": "needs_llm_review|needs_manual_review|uncertain|rejected",
            "needs_human_review": "boolean",
        },
        "input": {"qa_cluster_id": "tg-qa-cluster:fixture", "candidates": []},
    }
    _write_jsonl(batch_path, [task])
    requests: list[dict] = []

    def fake_transport(payload: dict) -> dict:
        requests.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '<|channel>thought\n<channel|>{"is_real_user_question":true,'
                            '"current_topic_relevance":"medium",'
                            '"answer_candidate_quality":"partial",'
                            '"normalized_question":"fixture question",'
                            '"short_answer_summary":"fixture summary",'
                            '"drift_or_conflict_assessment":"insufficient_history",'
                            '"recommended_selection_status":"needs_manual_review",'
                            '"needs_human_review":true}'
                        )
                    }
                }
            ]
        }

    result = run_tg_qa_llm_batch(
        batch_path=batch_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://temporary-tunnel.example",
        model_id="gemma-4-26B-A4B-it-UD-Q6_K.gguf",
        llm_run_id="llm-run-fixture",
        max_tokens=256,
        transport=fake_transport,
    )

    records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert requests[0]["model"] == "gemma-4-26B-A4B-it-UD-Q6_K.gguf"
    assert requests[0]["messages"][0]["role"] == "user"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert result["summary"]["completed_count"] == 1
    assert result["summary"]["http_user_agent"] == "chat_bot2-evaluation-runner/006"
    assert result["summary"]["reasoning_effort"] == ""
    assert result["summary"]["thinking_type"] == ""
    assert records[0]["status"] == "completed"
    assert records[0]["qa_cluster_id"] == "tg-qa-cluster:fixture"
    assert records[0]["recommended_selection_status"] == "needs_manual_review"
    assert summary["endpoint_shape"] == "https://<redacted-host>/v1/chat/completions"
    assert summary["auth_mode"] == "none"


def test_human_review_marks_dialogue_fragments_and_clarifying_answers(tmp_path: Path) -> None:
    review_queue_path = tmp_path / "review_queue.jsonl"
    _write_jsonl(
        review_queue_path,
        [
            {
                "qa_cluster_id": "tg-qa-pair-cluster:dialogue",
                "candidate_ids": ["tg-qa-candidate:dialogue"],
                "redacted_question": (
                    "О, это новость. По 24 параграфу? У вас внж (Aufenthaltstitel) уже есть? "
                    "И на мужа тоже, если вы оба не работаете?"
                ),
                "selected_answer_candidate": {
                    "answer_candidate_id": "tg-answer-candidate:dialogue",
                    "text_redacted": "На мужа нет, тк я одна здесь.",
                    "answer_source_type": "human_reply",
                    "answer_link_type": "direct_reply_to_question",
                },
                "llm_notes": [
                    {
                        "status": "completed",
                        "is_real_user_question": True,
                        "current_topic_relevance": "high",
                        "answer_candidate_quality": "partial",
                        "normalized_question": "У вас уже есть Aufenthaltstitel по §24 AufenthG?",
                        "short_answer_summary": "context reply",
                        "recommended_selection_status": "needs_manual_review",
                        "needs_human_review": True,
                    }
                ],
            },
            {
                "qa_cluster_id": "tg-qa-pair-cluster:answer-clarification",
                "candidate_ids": ["tg-qa-candidate:answer-clarification"],
                "redacted_question": "Какие варианты поддержки оплаты C1 есть для работающего человека?",
                "selected_answer_candidate": {
                    "answer_candidate_id": "tg-answer-candidate:answer-clarification",
                    "text_redacted": "А в какой школе такая цена? В VHS обычно дешевле.",
                    "answer_source_type": "human_reply",
                    "answer_link_type": "direct_reply_to_question",
                },
                "llm_notes": [
                    {
                        "status": "completed",
                        "is_real_user_question": True,
                        "current_topic_relevance": "high",
                        "answer_candidate_quality": "partial",
                        "normalized_question": "Какие варианты поддержки оплаты C1 есть для работающего человека?",
                        "short_answer_summary": "clarifying reply",
                        "recommended_selection_status": "needs_llm_review",
                        "needs_human_review": False,
                    }
                ],
            },
        ],
    )

    result = export_tg_qa_human_review(review_queue_path=review_queue_path)
    by_cluster = {record["qa_cluster_id"]: record for record in result["records"]}

    dialogue = by_cluster["tg-qa-pair-cluster:dialogue"]
    assert dialogue["question_dialogue_role"] == "dialogue_clarification_question"
    assert dialogue["suggested_decision"] == "reject"

    answer_clarification = by_cluster["tg-qa-pair-cluster:answer-clarification"]
    assert answer_clarification["question_dialogue_role"] == "standalone_question_with_clarifying_answer"
    assert answer_clarification["suggested_decision"] == "approve"
    assert answer_clarification["reference_answer_status"] == "reference_answer_is_clarifying_question"
    assert answer_clarification["suggested_reference_answer_action"] == "replace_manual"


def test_run_tg_qa_llm_batch_streams_results_before_completion(tmp_path: Path) -> None:
    batch_path = tmp_path / "llm_batch.jsonl"
    output_path = tmp_path / "llm_results.jsonl"
    summary_path = tmp_path / "llm_run_summary.json"
    task = {
        "task_id": "tg-qa-cluster:fixture",
        "task_scope": "qa_cluster",
        "llm_contract_version": "tg_qa_llm_analysis_v1",
        "prompt_version": "tg_qa_cluster_reviewer_compact_v1",
        "expected_output_schema": {
            "is_real_user_question": "boolean",
            "current_topic_relevance": "none|low|medium|high",
            "answer_candidate_quality": "none|partial|strong|conflicting",
            "normalized_question": "string",
            "short_answer_summary": "string",
            "drift_or_conflict_assessment": "stable|changed|conflicting|insufficient_history|not_evaluated",
            "recommended_selection_status": "needs_llm_review|needs_manual_review|uncertain|rejected",
            "needs_human_review": "boolean",
        },
        "input": {"qa_cluster_id": "tg-qa-cluster:fixture", "candidates": []},
    }
    _write_jsonl(batch_path, [task, {**task, "task_id": "tg-qa-cluster:fixture-2"}])
    observed_line_counts: list[int] = []

    def fake_transport(payload: dict) -> dict:
        observed_line_counts.append(
            len(output_path.read_text(encoding="utf-8").splitlines()) if output_path.exists() else 0
        )
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"is_real_user_question":true,'
                            '"current_topic_relevance":"medium",'
                            '"answer_candidate_quality":"partial",'
                            '"normalized_question":"fixture question",'
                            '"short_answer_summary":"fixture summary",'
                            '"drift_or_conflict_assessment":"insufficient_history",'
                            '"recommended_selection_status":"needs_manual_review",'
                            '"needs_human_review":true}'
                        )
                    }
                }
            ]
        }

    run_tg_qa_llm_batch(
        batch_path=batch_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://temporary-tunnel.example",
        model_id="fixture-model",
        llm_run_id="llm-run-fixture",
        transport=fake_transport,
    )

    assert observed_line_counts == [0, 1]
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 2


def test_run_tg_qa_llm_batch_can_send_thinking_type_and_filter_retry_batch(tmp_path: Path) -> None:
    batch_path = tmp_path / "llm_batch.jsonl"
    results_path = tmp_path / "llm_results.jsonl"
    retry_path = tmp_path / "retry_batch.jsonl"
    output_path = tmp_path / "run_results.jsonl"
    summary_path = tmp_path / "run_summary.json"
    tasks = [
        {
            "task_id": "tg-qa-cluster:failed",
            "task_scope": "qa_cluster",
            "llm_contract_version": "tg_qa_llm_analysis_v1",
            "prompt_version": "tg_qa_cluster_reviewer_v1",
            "expected_output_schema": {},
            "input": {},
        },
        {
            "task_id": "tg-qa-cluster:done",
            "task_scope": "qa_cluster",
            "llm_contract_version": "tg_qa_llm_analysis_v1",
            "prompt_version": "tg_qa_cluster_reviewer_v1",
            "expected_output_schema": {},
            "input": {},
        },
    ]
    _write_jsonl(batch_path, tasks)
    _write_jsonl(
        results_path,
        [
            {"task_id": "tg-qa-cluster:failed", "status": "failed"},
            {"task_id": "tg-qa-cluster:done", "status": "completed"},
        ],
    )
    retry = filter_tg_qa_llm_batch_by_results(
        batch_path=batch_path,
        results_path=results_path,
        output_path=retry_path,
    )
    requests: list[dict] = []

    def fake_transport(payload: dict) -> dict:
        requests.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"is_real_user_question":true,'
                            '"current_topic_relevance":"medium",'
                            '"answer_candidate_quality":"partial",'
                            '"normalized_question":"fixture question",'
                            '"short_answer_summary":"fixture summary",'
                            '"drift_or_conflict_assessment":"insufficient_history",'
                            '"recommended_selection_status":"needs_manual_review",'
                            '"needs_human_review":true}'
                        )
                    }
                }
            ]
        }

    result = run_tg_qa_llm_batch(
        batch_path=retry_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://temporary-tunnel.example",
        model_id="fixture-model",
        llm_run_id="llm-run-fixture",
        thinking_type="disabled",
        omit_temperature=True,
        extra_body={"options": {"thinking": {"type": "disabled"}}},
        transport=fake_transport,
    )

    assert retry["summary"]["retry_batch_item_count"] == 1
    assert retry["batch_items"][0]["task_id"] == "tg-qa-cluster:failed"
    assert requests[0]["thinking"] == {"type": "disabled"}
    assert "temperature" not in requests[0]
    assert requests[0]["options"] == {"thinking": {"type": "disabled"}}
    assert result["summary"]["thinking_type"] == "disabled"
    assert result["summary"]["omit_temperature"] is True
    assert result["summary"]["extra_body_keys"] == ["options"]


def test_merge_tg_qa_llm_results_replaces_failed_primary_with_completed_retry(tmp_path: Path) -> None:
    primary_path = tmp_path / "primary_results.jsonl"
    retry_path = tmp_path / "retry_results.jsonl"
    output_path = tmp_path / "merged_results.jsonl"
    _write_jsonl(
        primary_path,
        [
            {"task_id": "task:1", "status": "completed", "llm_run_id": "primary"},
            {"task_id": "task:2", "status": "failed", "llm_run_id": "primary"},
        ],
    )
    _write_jsonl(
        retry_path,
        [
            {"task_id": "task:2", "status": "completed", "llm_run_id": "retry"},
            {"task_id": "task:1", "status": "completed", "llm_run_id": "retry"},
        ],
    )

    result = merge_tg_qa_llm_results(
        primary_results_path=primary_path,
        retry_results_path=retry_path,
        output_path=output_path,
    )

    merged = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert result["summary"]["replaced_count"] == 1
    assert result["summary"]["ignored_retry_count"] == 1
    assert result["summary"]["counts_by_status"] == {"completed": 2}
    assert merged[0]["task_id"] == "task:1"
    assert merged[0]["llm_run_id"] == "primary"
    assert merged[1]["task_id"] == "task:2"
    assert merged[1]["llm_run_id"] == "retry"


def test_vectorize_tg_qa_embedding_batch_uses_endpoint_shape_and_writes_external_vectors(tmp_path: Path) -> None:
    embedding_batch_path = tmp_path / "embedding_batch.jsonl"
    batch_items = [
        {
            "embedding_item_id": "tg-embedding:q1",
            "candidate_id": "candidate:1",
            "text_role": "question",
            "embedding_input_text": "Query: test question",
        },
        {
            "embedding_item_id": "tg-embedding:a1",
            "candidate_id": "candidate:1",
            "answer_candidate_id": "answer:1",
            "text_role": "answer",
            "embedding_input_text": "Document: test answer",
        },
    ]
    _write_jsonl(embedding_batch_path, batch_items)
    output_path = tmp_path / "external_vectors.jsonl"
    summary_path = tmp_path / "vectorization_summary.json"
    requests: list[dict] = []

    def fake_transport(payload: dict) -> dict:
        requests.append(payload)
        return {
            "data": [
                {"embedding": [1.0, 0.0, 0.0]},
                {"embedding": [0.0, 1.0, 0.0]},
            ]
        }

    result = vectorize_tg_qa_embedding_batch(
        embedding_batch_path=embedding_batch_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://temporary-tunnel.example/v1/embeddings",
        model_id="jina-q8",
        batch_size=2,
        transport=fake_transport,
    )

    vectors = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert requests == [
        {
            "model": "jina-q8",
            "input": ["Query: test question", "Document: test answer"],
        }
    ]
    assert vectors[0]["embedding_status"] == "completed"
    assert vectors[0]["vector"] == [1.0, 0.0, 0.0]
    assert result["summary"]["completed_count"] == 2
    assert summary["endpoint_shape"] == "https://<redacted-host>/v1/embeddings"
    assert summary["batch_count"] == 1
    assert summary["duration_seconds"] >= 0
    assert summary["embedding_input_text_stats"]["max_words"] == 3
    assert summary["embedding_input_text_stats"]["tokenizer"] == "not_measured_whitespace_words_only"
    assert summary["trust_boundary"] == "embedding_vectors_are_generated_evaluation_artifacts_not_trusted_legal_facts"


def test_tg_qa_boundary_verification_passes_for_006_files() -> None:
    result = verify_tg_qa_boundaries()

    assert result["status"] == "passed"
    assert result["failed_source_checks"] == []
    assert result["missing_ignore_patterns"] == []


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )


def _fixture_vector_record(item: dict) -> dict:
    text_role = item["text_role"]
    source_message_id = str(item.get("source_message_id", ""))
    if text_role == "question" and source_message_id == "3":
        vector = [1.0, 0.0, 0.0]
    elif text_role == "question":
        vector = [0.83, sqrt(1 - 0.83**2), 0.0]
    elif text_role == "answer":
        vector = [0.0, 1.0, 0.0]
    else:
        vector = [0.0, 0.0, 1.0]
    return {
        "embedding_item_id": item["embedding_item_id"],
        "candidate_id": item["candidate_id"],
        "answer_candidate_id": item.get("answer_candidate_id", ""),
        "text_role": text_role,
        "backend_name": "fixture_vectors",
        "vector": vector,
    }


def _llm_result_for_task(task: dict, *, run_id: str) -> dict:
    return {
        "task_id": task["task_id"],
        "task_scope": task["task_scope"],
        "candidate_id": "",
        "qa_cluster_id": task["task_id"],
        "llm_run_id": run_id,
        "llm_contract_version": task["llm_contract_version"],
        "prompt_version": task["prompt_version"],
        "runtime_contour": "fixture_llama_server",
        "backend": "llama-server",
        "model_file": "gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf",
        "model_id": "fixture",
        "quantization": "Q8_K_XL",
        "status": "completed",
        "failure_reason": "",
        "is_real_user_question": True,
        "current_topic_relevance": "medium",
        "answer_candidate_quality": "partial",
        "normalized_question": "fixture normalized question",
        "short_answer_summary": "fixture summary",
        "drift_or_conflict_assessment": "insufficient_history",
        "recommended_selection_status": "needs_manual_review",
        "needs_human_review": True,
    }
