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
    llm_output = tmp_path / "llm_batch.jsonl"

    result = extract_tg_qa_dataset(
        input_paths=[SAMPLE_EXPORT],
        bot_catalog_path=SAMPLE_CATALOG,
        output_path=output,
        summary_output_path=summary_output,
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
    assert candidate["reply_count"] == 2
    assert candidate["source_message_ids"] == ["3", "4", "5"]
    assert "[EMAIL]" in candidate["question_text_redacted"]
    assert "[PHONE]" in candidate["question_text_redacted"]
    assert "[USERNAME]" in candidate["question_text_redacted"]
    assert candidate["review_status"] == "pending"
    assert candidate["llm_processing_status"] == "not_run"
    assert off_topic["quality_flags"] == ["low_topic_relevance", "missing_answer_candidate"]

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    llm_items = [json.loads(line) for line in llm_output.read_text(encoding="utf-8").splitlines()]
    written_candidates = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert summary["processed_message_count"] == 6
    assert summary["text_message_count"] == 5
    assert summary["emitted_candidate_count"] == 2
    assert summary["counts_by_answer_candidate_status"] == {"no_answer": 1, "strong": 1}
    assert summary["bot_mention_candidate_count"] == 1
    assert written_candidates[0]["candidate_id"] == candidate["candidate_id"]
    assert llm_items[0]["task_id"] == candidate["candidate_id"]
    assert llm_items[0]["runtime_hint"] == "openai_compatible_or_langchain_optional"
