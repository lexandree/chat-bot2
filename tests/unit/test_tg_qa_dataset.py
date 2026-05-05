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
    assert candidate["source_message_ids"] == ["3", "4", "5", "7"]
    assert "[EMAIL]" in candidate["question_text_redacted"]
    assert "[PHONE]" in candidate["question_text_redacted"]
    assert "[USERNAME]" in candidate["question_text_redacted"]
    assert candidate["confidence_tier"] == "high"
    assert candidate["selection_policy"] == "semantic_qa_cluster_latest_usable_answer"
    assert candidate["selection_status"] == "pending_embedding_cluster"
    assert candidate["review_route"] == "embedding_cluster_then_llm_review"
    assert candidate["embedding_processing_status"] == "not_run"
    assert candidate["clustering_status"] == "not_run"
    assert candidate["question_cluster_id"] == ""
    assert candidate["answer_cluster_id"] == ""
    assert candidate["qa_cluster_id"] == ""
    assert candidate["answer_drift_status"] == "not_evaluated"
    assert candidate["answer_candidates"][0]["answer_candidate_id"].startswith("tg-answer-candidate:")
    assert candidate["answer_candidates"][0]["answer_source_type"] == "human_reply"
    assert candidate["marked_known_bot_answer_status"] == "available"
    assert candidate["marked_known_bot_answer_candidates"][0]["answer_source_type"] == "known_wiki_bot"
    assert candidate["marked_known_bot_answer_candidates"][0]["known_bot_usernames"] == ["@berlin_wiki_bot"]
    assert candidate["marked_known_bot_answer_candidates"][0]["marking_reason"] == "known_wiki_bot_prepared_answer"
    assert candidate["ignored_other_bot_reply_count"] == 1
    assert candidate["bot_answer_marking_policy"] == "known_wiki_bot_answers_marked_other_bots_low_priority"
    assert candidate["review_status"] == "pending"
    assert candidate["llm_processing_status"] == "not_run"
    assert off_topic["confidence_tier"] == "low"
    assert off_topic["selection_status"] == "uncertain"
    assert off_topic["quality_flags"] == ["low_topic_relevance", "missing_answer_candidate"]

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    embedding_items = [json.loads(line) for line in embedding_output.read_text(encoding="utf-8").splitlines()]
    llm_items = [json.loads(line) for line in llm_output.read_text(encoding="utf-8").splitlines()]
    written_candidates = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert summary["processed_message_count"] == 8
    assert summary["text_message_count"] == 7
    assert summary["emitted_candidate_count"] == 2
    assert summary["counts_by_answer_candidate_status"] == {"no_answer": 1, "strong": 1}
    assert summary["counts_by_marked_known_bot_answer_status"] == {"available": 1, "none": 1}
    assert summary["counts_by_confidence_tier"] == {"high": 1, "low": 1}
    assert summary["counts_by_selection_status"] == {"pending_embedding_cluster": 1, "uncertain": 1}
    assert summary["bot_mention_candidate_count"] == 1
    assert summary["marked_known_bot_answer_candidate_count"] == 1
    assert summary["ignored_other_bot_reply_count"] == 1
    assert summary["selection_policy"] == "semantic_qa_cluster_latest_usable_answer"
    assert written_candidates[0]["candidate_id"] == candidate["candidate_id"]
    assert len(result.embedding_batch_items) == 5
    assert embedding_items[0]["text_role"] == "question"
    assert embedding_items[0]["embedding_input_text"].startswith("Query: ")
    assert any(
        item["text_role"] == "answer"
        and item["answer_source_type"] == "known_wiki_bot"
        and item["embedding_input_text"].startswith("Document: ")
        for item in embedding_items
    )
    assert llm_items[0]["task_id"] == candidate["candidate_id"]
    assert llm_items[0]["input"]["marked_known_bot_answer_status"] == "available"
    assert llm_items[0]["runtime_hint"] == "openai_compatible_or_langchain_optional"
