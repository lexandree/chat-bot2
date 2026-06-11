from __future__ import annotations

import json
from pathlib import Path

from evaluation.tg_qa_retrieval_benchmark import (
    build_private_artifact_snapshot_manifest,
    build_tg_qa_corpus_bounded_reference_benchmark,
    build_tg_qa_corpus_bounded_semantic_benchmark,
    build_tg_qa_retrieval_relevance_review_batch,
    build_tg_qa_reviewed_relevance_report,
    emit_tg_qa_corpus_bounded_semantic_embedding_batch,
    export_tg_qa_retrieval_relevance_review_html,
    import_tg_qa_retrieval_relevance_review_labels,
)


def test_private_snapshot_manifest_is_stable_and_contains_no_record_content(tmp_path: Path) -> None:
    dataset = tmp_path / "private_dataset.jsonl"
    metadata = tmp_path / "private_metadata.json"
    output = tmp_path / "snapshot.json"
    dataset.write_text('{"private_text":"do not publish"}\n', encoding="utf-8")
    metadata.write_text('{"record_count":1}\n', encoding="utf-8")

    first = build_private_artifact_snapshot_manifest(
        snapshot_name="private-v1",
        artifact_paths=[dataset, metadata],
        output_path=output,
    )
    second = build_private_artifact_snapshot_manifest(
        snapshot_name="private-v1",
        artifact_paths=[metadata, dataset],
        output_path=output,
    )
    dataset.write_text('{"private_text":"changed private content"}\n', encoding="utf-8")
    changed = build_private_artifact_snapshot_manifest(
        snapshot_name="private-v1",
        artifact_paths=[metadata, dataset],
        output_path=output,
    )

    serialized = output.read_text(encoding="utf-8")
    assert first["snapshot_id"] == second["snapshot_id"]
    assert changed["snapshot_id"] != first["snapshot_id"]
    assert first["artifact_count"] == 2
    assert first["contains_record_content"] is False
    assert "do not publish" not in serialized


def test_corpus_bounded_reference_benchmark_resolves_only_explicit_in_scope_law_refs(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    preview = tmp_path / "preview.json"
    snapshot = tmp_path / "snapshot.json"
    cases = tmp_path / "cases.jsonl"
    summary = tmp_path / "summary.json"
    _write_jsonl(
        dataset,
        [
            _dataset_record("record:resolved", "Что регулирует § 1 AufenthG?"),
            _dataset_record("record:missing", "Что регулирует § 99 AufenthG?"),
            _dataset_record("record:outside", "Что регулирует § 1 OtherG?"),
            _dataset_record("record:bare", "Что регулирует § 1?"),
            _dataset_record("record:none", "Какие правила действуют?"),
        ],
    )
    preview.write_text(json.dumps(_preview(), ensure_ascii=False), encoding="utf-8")
    build_private_artifact_snapshot_manifest(
        snapshot_name="private-v1",
        artifact_paths=[dataset],
        output_path=snapshot,
    )

    result = build_tg_qa_corpus_bounded_reference_benchmark(
        dataset_path=dataset,
        legal_preview_path=preview,
        dataset_snapshot_manifest_path=snapshot,
        law_codes=["AufenthG"],
        output_path=cases,
        summary_output_path=summary,
    )

    assert result["summary"]["reference_case_count"] == 2
    assert result["summary"]["counts_by_outcome"] == {
        "mechanically_resolved": 1,
        "missing_target_in_selected_corpus": 1,
    }
    assert result["summary"]["exact_reference_recall_at_1"] == 0.5
    assert result["summary"]["excluded_reference_counts"] == {
        "explicit_reference_outside_selected_corpus": 1,
        "no_explicit_section_reference": 1,
        "reference_without_explicit_law_code": 1,
    }
    assert all(item["dataset_snapshot_id"] == result["summary"]["dataset_snapshot_id"] for item in result["cases"])


def test_semantic_embedding_batch_preserves_query_document_asymmetry(tmp_path: Path) -> None:
    reference_cases = tmp_path / "reference_cases.jsonl"
    preview = tmp_path / "preview.json"
    batch = tmp_path / "batch.jsonl"
    summary = tmp_path / "summary.json"
    _write_jsonl(reference_cases, [_reference_case("case:1", "§ 1?", "legal-section:AufenthG:1:current")])
    preview.write_text(json.dumps(_preview(), ensure_ascii=False), encoding="utf-8")

    result = emit_tg_qa_corpus_bounded_semantic_embedding_batch(
        reference_cases_path=reference_cases,
        legal_preview_path=preview,
        law_codes=["AufenthG"],
        output_path=batch,
        summary_output_path=summary,
    )

    assert result["summary"]["query_embedding_item_count"] == 1
    assert result["summary"]["document_embedding_item_count"] == 2
    query = next(item for item in result["items"] if item["text_role"] == "semantic_query")
    document = next(
        item
        for item in result["items"]
        if item.get("legal_section_id") == "legal-section:AufenthG:1:current"
    )
    assert query["embedding_input_text"] == "Query: § 1?"
    assert document["embedding_input_text"] == "Document: Test one."
    assert "Scope one" not in document["embedding_input_text"]


def test_semantic_benchmark_reports_silver_and_reviewed_metrics(tmp_path: Path) -> None:
    reference_cases = tmp_path / "reference_cases.jsonl"
    preview = tmp_path / "preview.json"
    batch = tmp_path / "batch.jsonl"
    batch_summary = tmp_path / "batch_summary.json"
    vectors = tmp_path / "vectors.jsonl"
    reviews = tmp_path / "reviews.jsonl"
    cases = tmp_path / "cases.jsonl"
    summary = tmp_path / "summary.json"
    _write_jsonl(
        reference_cases,
        [
            _reference_case("case:1", "§ 1?", "legal-section:AufenthG:1:current"),
            _reference_case("case:2", "§ 2?", "legal-section:AufenthG:2:current"),
        ],
    )
    preview.write_text(json.dumps(_preview(), ensure_ascii=False), encoding="utf-8")
    emitted = emit_tg_qa_corpus_bounded_semantic_embedding_batch(
        reference_cases_path=reference_cases,
        legal_preview_path=preview,
        law_codes=["AufenthG"],
        output_path=batch,
        summary_output_path=batch_summary,
    )
    vector_rows = []
    for item in emitted["items"]:
        if item["text_role"] == "semantic_query":
            vector = [1.0, 0.0]
        elif item["legal_section_id"] == "legal-section:AufenthG:1:current":
            vector = [1.0, 0.0]
        else:
            vector = [0.0, 1.0]
        vector_rows.append(
            {
                "embedding_item_id": item["embedding_item_id"],
                "embedding_status": "completed",
                "vector": vector,
            }
        )
    _write_jsonl(vectors, vector_rows)
    _write_jsonl(
        reviews,
        [
            {
                "benchmark_case_id": "case:1",
                "reference_correctness_decision": "accept",
                "decision_reason": "fixture accepted",
            },
            {
                "benchmark_case_id": "case:2",
                "reference_correctness_decision": "exclude",
                "decision_reason": "fixture excluded",
            },
        ],
    )

    result = build_tg_qa_corpus_bounded_semantic_benchmark(
        reference_cases_path=reference_cases,
        embedding_batch_path=batch,
        external_vectors_path=vectors,
        reference_review_decisions_path=reviews,
        top_ks=(1, 2),
        output_path=cases,
        summary_output_path=summary,
    )

    silver = result["summary"]["metric_scopes"]["silver_all_query_explicit_targets"]
    reviewed = result["summary"]["metric_scopes"]["reviewed_accepted_targets"]
    assert silver["recall_at_1"] == 0.5
    assert silver["recall_at_2"] == 1.0
    assert silver["mean_reciprocal_rank"] == 0.75
    assert silver["ndcg_at_2"] == 0.815465
    assert reviewed["case_count"] == 1
    assert reviewed["recall_at_1"] == 1.0


def test_retrieval_relevance_review_batch_import_and_report_are_bounded(tmp_path: Path) -> None:
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    embedding_batch = tmp_path / "embedding_batch.jsonl"
    dataset = tmp_path / "dataset.jsonl"
    review_batch = tmp_path / "review_batch.jsonl"
    review_batch_summary = tmp_path / "review_batch_summary.json"
    review_html = tmp_path / "review.html"
    review_html_summary = tmp_path / "review_html_summary.json"
    raw_labels = tmp_path / "raw_labels.jsonl"
    labels = tmp_path / "labels.jsonl"
    labels_summary = tmp_path / "labels_summary.json"
    report = tmp_path / "report.jsonl"
    report_summary = tmp_path / "report_summary.json"
    _write_jsonl(
        semantic_cases,
        [
            _semantic_case("case:a1", "legal-section:AufenthG:1:current", ["legal-section:AufenthG:2:current"]),
            _semantic_case("case:a2", "legal-section:AufenthG:1:current", ["legal-section:AufenthG:1:current"]),
            _semantic_case("case:b1", "legal-section:AufenthG:2:current", ["legal-section:AufenthG:2:current"]),
        ],
    )
    _write_jsonl(
        embedding_batch,
        [
            _document_embedding_item("legal-section:AufenthG:1:current", "Document: First section."),
            _document_embedding_item("legal-section:AufenthG:2:current", "Document: Second section."),
        ],
    )
    _write_jsonl(
        dataset,
        [
            {
                "dataset_record_id": "record:case:a1",
                "source_question_text_redacted": "Question about section 1 without a law name.",
            },
            {
                "dataset_record_id": "record:case:a2",
                "source_question_text_redacted": "Question about AufenthG.",
            },
            {
                "dataset_record_id": "record:case:b1",
                "source_question_text_redacted": "Question about AufenthG.",
            },
        ],
    )

    batch_result = build_tg_qa_retrieval_relevance_review_batch(
        semantic_cases_path=semantic_cases,
        embedding_batch_path=embedding_batch,
        dataset_path=dataset,
        max_cases=2,
        top_k=1,
        output_path=review_batch,
        summary_output_path=review_batch_summary,
    )
    html_result = export_tg_qa_retrieval_relevance_review_html(
        review_batch_path=review_batch,
        output_path=review_html,
        summary_output_path=review_html_summary,
    )
    _write_jsonl(
        raw_labels,
        [
            {
                "benchmark_case_id": "case:b1",
                "relevant_legal_section_ids": ["legal-section:AufenthG:2:current"],
                "no_relevant_candidate_shown": False,
                "review_status": "reviewed",
                "explicit_reference_role": "answer_support",
            },
            {
                "benchmark_case_id": "case:a1",
                "relevant_legal_section_ids": [],
                "no_relevant_candidate_shown": True,
                "review_status": "reviewed",
                "explicit_reference_role": "status_context",
            },
        ],
    )
    imported = import_tg_qa_retrieval_relevance_review_labels(
        review_batch_path=review_batch,
        labels_path=raw_labels,
        output_path=labels,
        summary_output_path=labels_summary,
    )
    evaluated = build_tg_qa_reviewed_relevance_report(
        semantic_cases_path=semantic_cases,
        review_labels_path=labels,
        top_ks=(1, 2),
        output_path=report,
        summary_output_path=report_summary,
    )

    assert batch_result["summary"]["card_count"] == 2
    assert [item["benchmark_case_id"] for item in batch_result["cards"]] == ["case:b1", "case:a1"]
    assert len(batch_result["cards"][1]["candidates"]) == 2
    assert batch_result["cards"][1]["source_reference_diagnostics"] == [
        "explicit_target_law_code_absent_from_source"
    ]
    assert batch_result["summary"]["source_reference_diagnostic_counts"] == {
        "explicit_target_law_code_absent_from_source": 1
    }
    assert html_result["summary"]["card_count"] == 2
    assert "localStorage" in review_html.read_text(encoding="utf-8")
    assert imported["summary"]["completed_count"] == 2
    assert imported["summary"]["counts_by_explicit_reference_role"] == {
        "answer_support": 1,
        "status_context": 1,
    }
    assert evaluated["summary"]["metrics"]["hit_rate_at_1"] == 1.0
    assert evaluated["summary"]["metrics"]["recall_at_1"] == 1.0
    assert evaluated["summary"]["metrics"]["mean_reciprocal_rank"] == 1.0
    assert evaluated["summary"]["positive_label_coverage_rate"] == 0.5
    assert evaluated["summary"]["bounded_candidate_failure_rate"] == 0.5


def test_retrieval_relevance_review_import_rejects_conflicting_reviewed_label(tmp_path: Path) -> None:
    review_batch = tmp_path / "review_batch.jsonl"
    raw_labels = tmp_path / "raw_labels.jsonl"
    labels = tmp_path / "labels.jsonl"
    summary = tmp_path / "summary.json"
    _write_jsonl(
        review_batch,
        [
            {
                "benchmark_case_id": "case:1",
                "candidates": [{"legal_section_id": "legal-section:AufenthG:1:current"}],
            }
        ],
    )
    _write_jsonl(
        raw_labels,
        [
            {
                "benchmark_case_id": "case:1",
                "relevant_legal_section_ids": ["legal-section:AufenthG:1:current"],
                "no_relevant_candidate_shown": True,
                "review_status": "reviewed",
                "explicit_reference_role": "answer_support",
            }
        ],
    )

    result = import_tg_qa_retrieval_relevance_review_labels(
        review_batch_path=review_batch,
        labels_path=raw_labels,
        output_path=labels,
        summary_output_path=summary,
    )

    assert result["summary"]["failed_count"] == 1
    assert result["labels"][0]["failure_reason"] == (
        "reviewed_label_requires_relevant_sections_xor_no_relevant_candidate_shown"
    )


def _dataset_record(record_id: str, question: str) -> dict:
    return {
        "artifact_type": "tg_qa_canonical_question_dataset_record",
        "dataset_record_id": record_id,
        "task_id": f"task:{record_id}",
        "canonical_question": question,
    }


def _reference_case(case_id: str, question: str, expected_section_id: str) -> dict:
    law_code, section = expected_section_id.split(":")[1:3]
    return {
        "artifact_type": "tg_qa_corpus_bounded_explicit_reference_case",
        "benchmark_case_id": case_id,
        "dataset_record_id": f"record:{case_id}",
        "canonical_question": question,
        "target_law_code": law_code,
        "target_section_reference": f"§ {section}",
        "expected_legal_section_id": expected_section_id,
        "observed_legal_section_id": expected_section_id,
        "outcome": "mechanically_resolved",
    }


def _semantic_case(case_id: str, expected_section_id: str, ranked_section_ids: list[str]) -> dict:
    return {
        "benchmark_case_id": case_id,
        "dataset_record_id": f"record:{case_id}",
        "canonical_question": f"Question {case_id}",
        "expected_legal_section_id": expected_section_id,
        "expected_rank": (
            ranked_section_ids.index(expected_section_id) + 1 if expected_section_id in ranked_section_ids else 3
        ),
        "expected_score": 0.5,
        "top_candidates": [
            {
                "legal_section_id": section_id,
                "law_code": "AufenthG",
                "section_reference": f"§ {section_id.split(':')[2]}",
                "title": section_id,
                "score": 1.0 - index * 0.1,
            }
            for index, section_id in enumerate(ranked_section_ids)
        ],
    }


def _document_embedding_item(section_id: str, text: str) -> dict:
    return {
        "embedding_item_id": f"embedding:{section_id}",
        "text_role": "legal_section_document",
        "legal_section_id": section_id,
        "law_code": "AufenthG",
        "section_reference": f"§ {section_id.split(':')[2]}",
        "title": section_id,
        "embedding_input_text": text,
    }


def _preview() -> dict:
    return {
        "preview_id": "preview:test",
        "source_documents": [
            {
                "source_document_id": "source-document:DE:de:AufenthG",
                "law_code": "AufenthG",
                "title": "AufenthG",
                "source_family": "law",
                "jurisdiction": "DE",
                "language": "de",
            }
        ],
        "source_fragments": [
            {
                "source_document_id": "source-document:DE:de:AufenthG",
                "source_fragment_id": "source-fragment:AufenthG:1",
                "law_code": "AufenthG",
                "section_reference": "§ 1",
                "normalized_reference": "§ 1",
                "title": "Scope one",
                "body_text": "Test one.",
                "checksum": "sha256:test-one",
                "order_index": 1,
            },
            {
                "source_document_id": "source-document:DE:de:AufenthG",
                "source_fragment_id": "source-fragment:AufenthG:2",
                "law_code": "AufenthG",
                "section_reference": "§ 2",
                "normalized_reference": "§ 2",
                "title": "Scope two",
                "body_text": "Test two.",
                "checksum": "sha256:test-two",
                "order_index": 2,
            },
        ],
        "missing_inputs": [],
        "source_scope": {"law_codes": ["AufenthG"]},
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
