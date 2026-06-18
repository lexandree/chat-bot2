from __future__ import annotations

import json
from pathlib import Path

from evaluation.tg_qa_retrieval_benchmark import (
    build_private_artifact_snapshot_manifest,
    build_tg_qa_corpus_bounded_reference_benchmark,
    build_tg_qa_corpus_bounded_semantic_benchmark,
    build_tg_qa_retrieval_relevance_review_batch,
    build_tg_qa_retrieval_mechanism_report,
    build_tg_qa_route_ambiguity_report,
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
    curated_case = _reference_case("case:1", "Section one?", "legal-section:AufenthG:1:current")
    curated_case["target_evidence_type"] = "curated_checked"
    _write_jsonl(
        reference_cases,
        [
            curated_case,
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

    all_expected = result["summary"]["metric_scopes"]["all_expected_targets"]
    silver = result["summary"]["metric_scopes"]["query_explicit_silver_targets"]
    curated = result["summary"]["metric_scopes"]["curated_checked_targets"]
    reviewed = result["summary"]["metric_scopes"]["reviewed_accepted_targets"]
    assert result["summary"]["counts_by_target_evidence_type"] == {
        "curated_checked": 1,
        "query_explicit_silver": 1,
    }
    assert all_expected["recall_at_1"] == 0.5
    assert all_expected["recall_at_2"] == 1.0
    assert all_expected["mean_reciprocal_rank"] == 0.75
    assert all_expected["ndcg_at_2"] == 0.815465
    assert curated["recall_at_1"] == 1.0
    assert silver["recall_at_1"] == 0.0
    assert silver["recall_at_2"] == 1.0
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
                "question_date": "2024-02-03T00:00:00Z",
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
    assert any(card["question_date"] == "2024-02-03T00:00:00Z" for card in batch_result["cards"])
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
                "rerun_after_corpus_expansion": ["VwVfG", "VwVfG"],
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
    html_text = review_html.read_text(encoding="utf-8")
    assert "localStorage" in html_text
    assert "rerun_after_corpus_expansion" in html_text
    assert "corpus rerun" in html_text
    assert imported["summary"]["completed_count"] == 2
    assert imported["summary"]["counts_by_explicit_reference_role"] == {
        "answer_support": 1,
        "status_context": 1,
    }
    assert imported["summary"]["counts_by_rerun_after_corpus_expansion_law_code"] == {
        "VwVfG": 1
    }
    assert imported["labels"][0]["rerun_after_corpus_expansion"] == ["VwVfG"]
    assert evaluated["summary"]["metrics"]["hit_rate_at_1"] == 1.0
    assert evaluated["summary"]["metrics"]["recall_at_1"] == 1.0
    assert evaluated["summary"]["metrics"]["mean_reciprocal_rank"] == 1.0
    assert evaluated["summary"]["positive_label_coverage_rate"] == 0.5
    assert evaluated["summary"]["bounded_candidate_failure_rate"] == 0.5
    assert evaluated["summary"]["counts_by_rerun_after_corpus_expansion_law_code"] == {
        "VwVfG": 1
    }


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
        "reviewed_label_requires_shown_relevant_sections_xor_no_relevant_candidate_shown"
    )


def test_retrieval_mechanism_report_groups_only_reviewed_evidence(tmp_path: Path) -> None:
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    labels = tmp_path / "labels.jsonl"
    output = tmp_path / "mechanisms.jsonl"
    summary = tmp_path / "mechanisms_summary.json"
    case = _semantic_case(
        "case:route",
        "legal-section:AufenthG:24:current",
        [
            "legal-section:AsylG:3:current",
            "legal-section:AufenthG:2:current",
        ],
    )
    case["top_candidates"][0]["law_code"] = "AsylG"
    _write_jsonl(semantic_cases, [case])
    _write_jsonl(
        labels,
        [
            {
                "benchmark_case_id": "case:route",
                "status": "completed",
                "review_status": "reviewed",
                "relevant_legal_section_ids": [
                    "legal-section:AufenthG:2:current",
                    "legal-section:VwVfG:14:current",
                ],
                "explicit_reference_role": "status_context",
                "rerun_after_corpus_expansion": ["VwVfG"],
            },
            {
                "benchmark_case_id": "case:ignored",
                "status": "completed",
                "review_status": "uncertain",
                "relevant_legal_section_ids": ["legal-section:AufenthG:2:current"],
            },
        ],
    )

    result = build_tg_qa_retrieval_mechanism_report(
        semantic_cases_path=semantic_cases,
        review_labels_path=labels,
        output_path=output,
        summary_output_path=summary,
        sample_limit=1,
    )

    assert result["summary"]["reviewed_label_count"] == 1
    assert result["summary"]["evaluated_case_count"] == 1
    assert result["summary"]["counts_by_diagnostic_signal"] == {
        "asyl_aufenthg_route_mismatch": 1,
        "corpus_expansion_required": 1,
        "expected_reference_not_relevant": 1,
        "explicit_reference_not_answer_support": 1,
        "multi_law_support": 1,
        "multi_section_support": 1,
        "relevant_evidence_unranked": 1,
        "relevant_only_below_top1": 1,
        "top1_wrong_law": 1,
    }
    assert result["summary"]["sample_case_ids_by_diagnostic_signal"]["top1_wrong_law"] == [
        "case:route"
    ]


def test_retrieval_relevance_review_import_rejects_non_list_corpus_rerun_marker(
    tmp_path: Path,
) -> None:
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
                "no_relevant_candidate_shown": False,
                "review_status": "reviewed",
                "explicit_reference_role": "answer_support",
                "rerun_after_corpus_expansion": "VwVfG",
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
        "rerun_after_corpus_expansion_must_be_string_list"
    )


def test_retrieval_relevance_review_accepts_corpus_section_outside_shown_candidates(
    tmp_path: Path,
) -> None:
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    embedding_batch = tmp_path / "embedding_batch.jsonl"
    review_batch = tmp_path / "review_batch.jsonl"
    review_summary = tmp_path / "review_summary.json"
    raw_labels = tmp_path / "raw_labels.jsonl"
    labels = tmp_path / "labels.jsonl"
    labels_summary = tmp_path / "labels_summary.json"
    report = tmp_path / "report.jsonl"
    report_summary = tmp_path / "report_summary.json"
    _write_jsonl(
        semantic_cases,
        [
            _semantic_case(
                "case:outside",
                "legal-section:AufenthG:1:current",
                ["legal-section:AufenthG:2:current"],
            )
        ],
    )
    _write_jsonl(
        embedding_batch,
        [
            _document_embedding_item("legal-section:AufenthG:1:current", "Document: First."),
            _document_embedding_item("legal-section:AufenthG:2:current", "Document: Second."),
            _document_embedding_item("legal-section:AufenthG:4:current", "Document: Fourth."),
        ],
    )
    build_tg_qa_retrieval_relevance_review_batch(
        semantic_cases_path=semantic_cases,
        embedding_batch_path=embedding_batch,
        max_cases=1,
        top_k=1,
        output_path=review_batch,
        summary_output_path=review_summary,
    )
    _write_jsonl(
        raw_labels,
        [
            {
                "benchmark_case_id": "case:outside",
                "relevant_legal_section_ids": [],
                "additional_relevant_legal_section_ids": ["legal-section:AufenthG:4:current"],
                "no_relevant_candidate_shown": True,
                "review_status": "reviewed",
                "explicit_reference_role": "incorrect",
            }
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
        top_ks=(1, 10),
        output_path=report,
        summary_output_path=report_summary,
    )

    assert imported["summary"]["completed_count"] == 1
    assert imported["labels"][0]["relevant_legal_section_ids"] == [
        "legal-section:AufenthG:4:current"
    ]
    assert evaluated["summary"]["metrics"]["recall_at_10"] == 0.0
    assert evaluated["summary"]["excluded_counts"] == {
        "positive_label_with_unranked_relevant_sections": 1,
        "reviewed_no_relevant_candidate_shown": 1,
    }
    assert evaluated["summary"]["bounded_candidate_failure_rate"] == 1.0


def test_retrieval_relevance_review_adds_unqualified_same_question_reference(tmp_path: Path) -> None:
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    embedding_batch = tmp_path / "embedding_batch.jsonl"
    review_batch = tmp_path / "review_batch.jsonl"
    summary = tmp_path / "summary.json"
    semantic_case = _semantic_case(
        "case:multi-reference",
        "legal-section:AufenthG:32:current",
        ["legal-section:AufenthG:8:current"],
    )
    semantic_case["canonical_question"] = "Почему в письме указан §32 AufenthG, а в паспорте §24?"
    _write_jsonl(semantic_cases, [semantic_case])
    _write_jsonl(
        embedding_batch,
        [
            _document_embedding_item("legal-section:AufenthG:8:current", "Document: Extension."),
            _document_embedding_item("legal-section:AufenthG:24:current", "Document: Temporary protection."),
            _document_embedding_item("legal-section:AufenthG:32:current", "Document: Child residence."),
        ],
    )

    result = build_tg_qa_retrieval_relevance_review_batch(
        semantic_cases_path=semantic_cases,
        embedding_batch_path=embedding_batch,
        max_cases=1,
        top_k=1,
        output_path=review_batch,
        summary_output_path=summary,
    )

    candidates = {
        item["legal_section_id"]: item for item in result["cards"][0]["candidates"]
    }
    assert candidates["legal-section:AufenthG:24:current"]["candidate_source"] == (
        "same_question_inferred_law_reference"
    )
    assert candidates["legal-section:AufenthG:24:current"]["is_same_question_reference"] is True
    assert candidates["legal-section:AufenthG:24:current"]["rank"] == 0
    assert candidates["legal-section:AufenthG:24:current"]["score"] == 0.0
    assert candidates["legal-section:AufenthG:32:current"]["is_explicit_reference_target"] is True


def test_retrieval_relevance_review_distinguishes_curated_target_from_explicit_reference(
    tmp_path: Path,
) -> None:
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    embedding_batch = tmp_path / "embedding_batch.jsonl"
    review_batch = tmp_path / "review_batch.jsonl"
    summary = tmp_path / "summary.json"
    semantic_case = _semantic_case(
        "case:curated",
        "legal-section:AufenthG:4:current",
        ["legal-section:AufenthG:1:current"],
    )
    semantic_case["target_evidence_type"] = "curated_checked"
    _write_jsonl(semantic_cases, [semantic_case])
    _write_jsonl(
        embedding_batch,
        [
            _document_embedding_item("legal-section:AufenthG:1:current", "Document: Scope."),
            _document_embedding_item("legal-section:AufenthG:4:current", "Document: Title required."),
        ],
    )

    result = build_tg_qa_retrieval_relevance_review_batch(
        semantic_cases_path=semantic_cases,
        embedding_batch_path=embedding_batch,
        max_cases=1,
        top_k=1,
        output_path=review_batch,
        summary_output_path=summary,
    )

    card = result["cards"][0]
    candidates = {item["legal_section_id"]: item for item in card["candidates"]}
    assert card["target_evidence_type"] == "curated_checked"
    assert candidates["legal-section:AufenthG:4:current"]["is_expected_target"] is True
    assert candidates["legal-section:AufenthG:4:current"]["is_explicit_reference_target"] is False
    assert candidates["legal-section:AufenthG:4:current"]["candidate_source"] == (
        "curated_expected_target_added_for_review"
    )


def test_clean_curated_retrieval_fixture_has_balanced_unambiguous_questions() -> None:
    fixture_path = (
        Path(__file__).parents[2]
        / "specs"
        / "007-legal-question-canonicalization"
        / "clean-retrieval-reference-cases.jsonl"
    )
    cases = [
        json.loads(line)
        for line in fixture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(cases) == 24
    assert len({item["benchmark_case_id"] for item in cases}) == 24
    assert {
        law_code: sum(item["target_law_code"] == law_code for item in cases)
        for law_code in ("AufenthG", "AsylG", "BeschV")
    } == {"AufenthG": 8, "AsylG": 8, "BeschV": 8}
    assert all(item["target_evidence_type"] == "curated_checked" for item in cases)
    assert all(item["canonical_question"].count("?") == 1 for item in cases)
    assert all("§" not in item["canonical_question"] for item in cases)
    assert all(item["curation_reason"] for item in cases)


def test_route_ambiguity_fixture_preserves_paired_and_unresolved_routes() -> None:
    fixture_path = (
        Path(__file__).parents[2]
        / "specs"
        / "007-legal-question-canonicalization"
        / "route-ambiguity-reference-cases.jsonl"
    )
    cases = [
        json.loads(line)
        for line in fixture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(cases) == 12
    assert len({item["benchmark_case_id"] for item in cases}) == 12
    assert {
        route_class: sum(item["route_class"] == route_class for item in cases)
        for route_class in ("section_24", "asyl", "unresolved_requires_clarification")
    } == {"section_24": 5, "asyl": 5, "unresolved_requires_clarification": 2}
    assert all(item["target_evidence_type"] == "route_ambiguity_checked" for item in cases)
    assert all(item["curation_reason"] for item in cases)
    assert all(item["material_context"] for item in cases)
    assert all(item["surface_group_id"] for item in cases)
    assert sum(item["outcome"] == "mechanically_resolved" for item in cases) == 10
    assert sum(item["outcome"] == "route_unresolved_requires_clarification" for item in cases) == 2
    assert all(
        bool(item["expected_legal_section_id"]) == (item["outcome"] == "mechanically_resolved")
        for item in cases
    )
    same_surface_routes = {
        item["route_class"]
        for item in cases
        if item["surface_group_id"] == "same-surface-bezhentsvo"
    }
    assert same_surface_routes == {"section_24", "asyl"}


def test_route_ambiguity_report_measures_route_visibility(tmp_path: Path) -> None:
    reference_cases = tmp_path / "route_cases.jsonl"
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    output = tmp_path / "route_report.jsonl"
    summary = tmp_path / "route_summary.json"
    _write_jsonl(
        reference_cases,
        [
            {
                "benchmark_case_id": "case:section24",
                "route_class": "section_24",
                "surface_group_id": "same",
                "canonical_question": "Question 24?",
                "outcome": "mechanically_resolved",
                "expected_legal_section_id": "legal-section:AufenthG:24:current",
                "expected_route_law_codes": ["AufenthG"],
                "plausible_route_law_codes": ["AufenthG", "AsylG"],
            },
            {
                "benchmark_case_id": "case:asyl",
                "route_class": "asyl",
                "surface_group_id": "same",
                "canonical_question": "Question asylum?",
                "outcome": "mechanically_resolved",
                "expected_legal_section_id": "legal-section:AsylG:13:current",
                "expected_route_law_codes": ["AsylG"],
                "plausible_route_law_codes": ["AsylG"],
            },
            {
                "benchmark_case_id": "case:unresolved",
                "route_class": "unresolved_requires_clarification",
                "surface_group_id": "same",
                "canonical_question": "Question unresolved?",
                "outcome": "route_unresolved_requires_clarification",
                "expected_legal_section_id": "",
                "expected_route_law_codes": ["AufenthG", "AsylG"],
                "plausible_route_law_codes": ["AufenthG", "AsylG"],
            },
        ],
    )
    _write_jsonl(
        semantic_cases,
        [
            {
                "benchmark_case_id": "case:section24",
                "top_candidates": [
                    {"legal_section_id": "legal-section:AsylG:13:current", "law_code": "AsylG"},
                    {"legal_section_id": "legal-section:AufenthG:24:current", "law_code": "AufenthG"},
                ],
            },
            {
                "benchmark_case_id": "case:asyl",
                "top_candidates": [
                    {"legal_section_id": "legal-section:AsylG:13:current", "law_code": "AsylG"},
                ],
            },
        ],
    )

    result = build_tg_qa_route_ambiguity_report(
        reference_cases_path=reference_cases,
        semantic_cases_path=semantic_cases,
        output_path=output,
        summary_output_path=summary,
        top_ks=(1, 2),
    )

    assert result["summary"]["evaluated_case_count"] == 2
    assert result["summary"]["both_aufenthg_asylg_plausible_case_count"] == 1
    assert result["summary"]["top1_wrong_route_count"] == 1
    assert result["summary"]["excluded_counts"] == {
        "route_unresolved_requires_clarification": 1
    }
    assert result["summary"]["metrics_by_k"]["at_1"]["expected_route_hit_rate"] == 0.5
    assert result["summary"]["metrics_by_k"]["at_1"]["wrong_route_only_rate"] == 0.5
    assert result["summary"]["metrics_by_k"]["at_2"]["expected_route_hit_rate"] == 1.0
    assert result["summary"]["metrics_by_k"]["at_2"]["both_aufenthg_asylg_recalled_rate"] == 1.0
    assert result["summary"]["route_union_candidate_generation"]["expected_route_hit_rate"] == 1.0
    assert result["summary"]["route_union_candidate_generation"]["expected_legal_section_hit_rate"] == 1.0
    assert result["summary"]["route_union_candidate_generation"]["avg_candidate_count"] == 1.5

    section24 = next(item for item in result["cases"] if item["benchmark_case_id"] == "case:section24")
    assert section24["route_union_candidate_generation"] == {
        "policy_version": "top1_plus_first_recorded_candidate_per_plausible_route_law_v1",
        "base_unrestricted_k": 1,
        "per_plausible_route_law_k": 1,
        "candidate_count": 2,
        "candidate_legal_section_ids": [
            "legal-section:AsylG:13:current",
            "legal-section:AufenthG:24:current",
        ],
        "candidate_law_codes": ["AsylG", "AufenthG"],
        "expected_route_hit": True,
        "expected_legal_section_hit": True,
        "missing_plausible_route_law_codes": [],
    }


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
