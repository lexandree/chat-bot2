from __future__ import annotations

import json
from pathlib import Path

from evaluation.tg_qa_dataset import (
    extract_tg_qa_dataset,
    load_bot_catalog,
    normalize_telegram_text,
    redact_text,
    resolve_export_paths,
)


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
    assert len(result.embedding_batch_items) == 7
    assert embedding_items[0]["text_role"] == "question"
    assert embedding_items[0]["embedding_input_text"].startswith("Query: ")
    assert any(
        item["text_role"] == "answer"
        and item["answer_source_type"] == "known_wiki_bot"
        and item["answer_link_type"] == "bot_reply_to_trigger"
        and item["embedding_input_text"].startswith("Document: ")
        for item in embedding_items
    )
    assert llm_items[0]["task_id"] == candidate["candidate_id"]
    assert llm_items[0]["input"]["answer_source_counts"] == {"human_reply": 2, "known_wiki_bot": 2, "other_bot": 1}
    assert llm_items[0]["input"]["known_bot_answer_via_trigger_count"] == 2
    assert llm_items[0]["runtime_hint"] == "openai_compatible_or_langchain_optional"
