from __future__ import annotations

import json
from math import sqrt
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.commands import dispatch
from app.settings import FoundationSettings
from evaluation.load_cases import (
    build_corpus_readiness_artifact,
    build_relationship_quality_artifact,
    build_structural_workflow_artifact,
)


pytestmark = pytest.mark.smoke


def test_cli_settings_validate_runs_without_live_services() -> None:
    result = _run_cli(["settings", "validate"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "valid"
    assert payload["configuration"]["neo4j_password"] == ""


def test_cli_preview_legal_xml_writes_artifact_without_graph(tmp_path: Path) -> None:
    output_path = tmp_path / "legal_xml_preview.json"

    result = _run_cli(
        [
            "preview",
            "legal-xml",
            "--manifest",
            "tests/fixtures/legal_xml_import_manifest.json",
            "--output",
            str(output_path),
            "--law-code",
            "AufenthG",
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "previewed"
    assert payload["source_fragment_count"] == 2
    assert artifact["source_scope"]["law_codes"] == ["AufenthG"]


def test_cli_graph_compare_writes_comparison_artifact_without_live_services(tmp_path: Path) -> None:
    new_snapshot = tmp_path / "new_snapshot.json"
    baseline_snapshot = tmp_path / "baseline_snapshot.json"
    output_path = tmp_path / "comparison.json"
    new_snapshot.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot:new",
                "selected_scope": {"law_codes": ["AufenthG"]},
                "source_scope": {"source_families": ["law"], "law_codes": ["AufenthG"]},
                "counts": {"SourceDocument": 1, "SourceFragment": 2},
                "labels": {"SourceDocument": 1, "SourceFragment": 2},
                "relation_types": {"HAS_SOURCE_FRAGMENT": 2},
                "sample_ids": {"source_fragment_ids": ["source-fragment:AufenthG:1"]},
                "source_coverage": {"law_codes": ["AufenthG"]},
                "embedding_profile_metadata": {"embedding_count": 0},
                "unresolved_reference_evidence": [],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    baseline_snapshot.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot:baseline",
                "selected_scope": {"law_codes": ["AufenthG"]},
                "source_scope": {"source_families": ["law"], "law_codes": ["AufenthG"]},
                "counts": {"SourceDocument": 1, "SourceFragment": 1},
                "labels": {"SourceDocument": 1, "SourceFragment": 1},
                "relation_types": {"HAS_SOURCE_FRAGMENT": 1},
                "sample_ids": {"source_fragment_ids": ["source-fragment:AufenthG:1"]},
                "source_coverage": {"law_codes": ["AufenthG"]},
                "embedding_profile_metadata": {"embedding_count": 0},
                "unresolved_reference_evidence": [],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        [
            "graph",
            "compare",
            "--new",
            str(new_snapshot),
            "--baseline",
            str(baseline_snapshot),
            "--output",
            str(output_path),
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["comparison_id"].startswith("comparison:")
    assert payload["comparison_artifact_path"] == str(output_path)
    assert artifact["baseline_snapshot_id"] == "snapshot:baseline"
    assert artifact["missing"]["counts"]["SourceFragment"] == 1


def test_cli_private_snapshot_and_corpus_bounded_reference_benchmark_are_offline(tmp_path: Path) -> None:
    dataset = tmp_path / "private_dataset.jsonl"
    preview = tmp_path / "preview.json"
    snapshot = tmp_path / "snapshot.json"
    cases = tmp_path / "reference_cases.jsonl"
    summary = tmp_path / "reference_summary.json"
    semantic_batch = tmp_path / "semantic_batch.jsonl"
    semantic_batch_summary = tmp_path / "semantic_batch_summary.json"
    semantic_vectors = tmp_path / "semantic_vectors.jsonl"
    semantic_cases = tmp_path / "semantic_cases.jsonl"
    semantic_summary = tmp_path / "semantic_summary.json"
    relevance_review_batch = tmp_path / "relevance_review_batch.jsonl"
    relevance_review_batch_summary = tmp_path / "relevance_review_batch_summary.json"
    relevance_review_html = tmp_path / "relevance_review.html"
    relevance_review_html_summary = tmp_path / "relevance_review_html_summary.json"
    raw_relevance_labels = tmp_path / "raw_relevance_labels.jsonl"
    relevance_labels = tmp_path / "relevance_labels.jsonl"
    relevance_labels_summary = tmp_path / "relevance_labels_summary.json"
    reviewed_relevance_cases = tmp_path / "reviewed_relevance_cases.jsonl"
    reviewed_relevance_summary = tmp_path / "reviewed_relevance_summary.json"
    _write_jsonl(
        dataset,
        [
            {
                "artifact_type": "tg_qa_canonical_question_dataset_record",
                "dataset_record_id": "dataset:1",
                "task_id": "task:1",
                "canonical_question": "Что регулирует § 1 AufenthG?",
            }
        ],
    )
    preview.write_text(
        json.dumps(
            {
                "preview_id": "preview:smoke",
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
                        "title": "Scope",
                        "body_text": "Test.",
                        "checksum": "sha256:test",
                        "order_index": 1,
                    }
                ],
                "missing_inputs": [],
                "source_scope": {"law_codes": ["AufenthG"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    snapshot_result = _run_cli(
        [
            "evaluation",
            "tg-qa-private-snapshot-manifest",
            "--snapshot-name",
            "private-smoke",
            "--artifact",
            str(dataset),
            "--output",
            str(snapshot),
        ]
    )
    benchmark_result = _run_cli(
        [
            "evaluation",
            "tg-qa-corpus-bounded-reference-benchmark",
            "--dataset",
            str(dataset),
            "--legal-preview",
            str(preview),
            "--dataset-snapshot-manifest",
            str(snapshot),
            "--law-code",
            "AufenthG",
            "--output",
            str(cases),
            "--summary-output",
            str(summary),
        ]
    )
    semantic_batch_result = _run_cli(
        [
            "evaluation",
            "tg-qa-corpus-bounded-semantic-embedding-batch",
            "--reference-cases",
            str(cases),
            "--legal-preview",
            str(preview),
            "--law-code",
            "AufenthG",
            "--output",
            str(semantic_batch),
            "--summary-output",
            str(semantic_batch_summary),
        ]
    )
    _write_jsonl(
        semantic_vectors,
        [
            {
                "embedding_item_id": item["embedding_item_id"],
                "embedding_status": "completed",
                "vector": [1.0, 0.0],
            }
            for item in _read_jsonl(semantic_batch)
        ],
    )
    semantic_benchmark_result = _run_cli(
        [
            "evaluation",
            "tg-qa-corpus-bounded-semantic-benchmark",
            "--reference-cases",
            str(cases),
            "--embedding-batch",
            str(semantic_batch),
            "--external-vectors",
            str(semantic_vectors),
            "--output",
            str(semantic_cases),
            "--summary-output",
            str(semantic_summary),
        ]
    )
    relevance_review_batch_result = _run_cli(
        [
            "evaluation",
            "tg-qa-retrieval-relevance-review-batch",
            "--semantic-cases",
            str(semantic_cases),
            "--embedding-batch",
            str(semantic_batch),
            "--max-cases",
            "1",
            "--top-k",
            "1",
            "--output",
            str(relevance_review_batch),
            "--summary-output",
            str(relevance_review_batch_summary),
        ]
    )
    relevance_review_html_result = _run_cli(
        [
            "evaluation",
            "tg-qa-retrieval-relevance-review-html",
            "--review-batch",
            str(relevance_review_batch),
            "--output",
            str(relevance_review_html),
            "--summary-output",
            str(relevance_review_html_summary),
        ]
    )
    review_card = _read_jsonl(relevance_review_batch)[0]
    _write_jsonl(
        raw_relevance_labels,
        [
            {
                "benchmark_case_id": review_card["benchmark_case_id"],
                "relevant_legal_section_ids": [review_card["expected_legal_section_id"]],
                "no_relevant_candidate_shown": False,
                "review_status": "reviewed",
                "explicit_reference_role": "answer_support",
            }
        ],
    )
    relevance_labels_result = _run_cli(
        [
            "evaluation",
            "tg-qa-retrieval-relevance-review-labels-import",
            "--review-batch",
            str(relevance_review_batch),
            "--labels",
            str(raw_relevance_labels),
            "--output",
            str(relevance_labels),
            "--summary-output",
            str(relevance_labels_summary),
        ]
    )
    reviewed_relevance_result = _run_cli(
        [
            "evaluation",
            "tg-qa-reviewed-relevance-report",
            "--semantic-cases",
            str(semantic_cases),
            "--review-labels",
            str(relevance_labels),
            "--k",
            "1",
            "--output",
            str(reviewed_relevance_cases),
            "--summary-output",
            str(reviewed_relevance_summary),
        ]
    )

    assert snapshot_result.returncode == 0, snapshot_result.stderr
    assert benchmark_result.returncode == 0, benchmark_result.stderr
    assert semantic_batch_result.returncode == 0, semantic_batch_result.stderr
    assert semantic_benchmark_result.returncode == 0, semantic_benchmark_result.stderr
    assert relevance_review_batch_result.returncode == 0, relevance_review_batch_result.stderr
    assert relevance_review_html_result.returncode == 0, relevance_review_html_result.stderr
    assert relevance_labels_result.returncode == 0, relevance_labels_result.stderr
    assert reviewed_relevance_result.returncode == 0, reviewed_relevance_result.stderr
    assert json.loads(snapshot_result.stdout)["contains_record_content"] is False
    assert json.loads(benchmark_result.stdout)["exact_reference_recall_at_1"] == 1.0
    assert json.loads(semantic_benchmark_result.stdout)["metric_scopes"][
        "silver_all_query_explicit_targets"
    ]["recall_at_1"] == 1.0
    assert json.loads(reviewed_relevance_result.stdout)["metrics"]["recall_at_1"] == 1.0
    assert "localStorage" in relevance_review_html.read_text(encoding="utf-8")
    assert len(cases.read_text(encoding="utf-8").splitlines()) == 1


def test_cli_relationships_quality_writes_artifact_with_injected_repository(tmp_path: Path) -> None:
    output_path = tmp_path / "relationship_quality.json"

    exit_code, payload = dispatch(
        [
            "relationships",
            "quality",
            "--law-code",
            "TestG",
            "--output",
            str(output_path),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["relationship_quality_artifact_path"] == str(output_path)
    assert artifact["counts_by_relation_type"]["CITES"] == 1
    assert "answer_text" not in artifact


def test_cli_corpus_readiness_writes_artifact_with_injected_repository(tmp_path: Path) -> None:
    output_path = tmp_path / "corpus_readiness.json"

    exit_code, payload = dispatch(
        [
            "corpus",
            "readiness",
            "--law-code",
            "TestG",
            "--output",
            str(output_path),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["corpus_readiness_artifact_path"] == str(output_path)
    assert artifact["counts_by_unit_status"]["active"] == 1
    assert artifact["counts_by_structure_class"]["simple_paragraph"] == 1
    assert "answer_text" not in artifact


def test_cli_evaluation_tg_qa_writes_candidates_summary_and_llm_batch(tmp_path: Path) -> None:
    output = tmp_path / "tg_qa_candidates.jsonl"
    summary_output = tmp_path / "tg_qa_summary.json"
    embedding_output = tmp_path / "tg_qa_embedding_batch.jsonl"
    llm_output = tmp_path / "tg_qa_llm_batch.jsonl"

    exit_code, payload = dispatch(
        [
            "evaluation",
            "tg-qa",
            "--input",
            "tests/fixtures/tg_sample_export",
            "--bot-catalog",
            "tests/fixtures/tg_wiki_bot_catalog_sample.json",
            "--output",
            str(output),
            "--summary-output",
            str(summary_output),
            "--embedding-batch-output",
            str(embedding_output),
            "--llm-batch-output",
            str(llm_output),
            "--max-candidates",
            "20",
            "--min-attention-score",
            "6",
        ],
        settings=FoundationSettings(),
    )

    candidates = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    embedding_items = [json.loads(line) for line in embedding_output.read_text(encoding="utf-8").splitlines()]
    llm_items = [json.loads(line) for line in llm_output.read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["emitted_candidate_count"] == 2
    assert payload["known_wiki_bot_answer_candidate_count"] == 2
    assert payload["other_bot_answer_candidate_count"] == 1
    assert payload["known_bot_answer_via_trigger_count"] == 2
    assert summary["trust_boundary"] == "telegram_answers_are_evaluation_material_not_legal_truth"
    assert summary["embedding_batch_output_path"] == str(embedding_output)
    assert candidates[0]["answer_candidate_status"] == "strong"
    assert candidates[0]["selection_status"] == "pending_embedding_cluster"
    assert candidates[0]["review_route"] == "embedding_cluster_selection"
    assert candidates[0]["answer_source_counts"] == {"human_reply": 2, "known_wiki_bot": 2, "other_bot": 1}
    assert candidates[0]["answer_link_counts"]["bot_reply_to_trigger"] == 1
    assert candidates[0]["answer_link_counts"]["bot_after_trigger"] == 1
    assert candidates[0]["trigger_evidence_count"] == 2
    assert candidates[0]["answer_candidates"][2]["known_bot_usernames"] == ["@berlin_wiki_bot"]
    assert candidates[0]["answer_candidates"][2]["answer_link_type"] == "bot_reply_to_trigger"
    assert candidates[0]["answer_candidates"][3]["answer_candidate_priority"] == "low"
    assert candidates[0]["answer_candidates"][4]["answer_link_type"] == "bot_after_trigger"
    assert candidates[0]["bot_mentions"] == ["@berlin_wiki_bot"]
    assert candidates[1]["quality_flags"] == ["low_topic_relevance", "missing_answer_candidate"]
    assert embedding_items[0]["cluster_usage"] == ["question_cluster", "qa_cluster"]
    assert llm_items[0]["task_type"] == "tg_qa_candidate_classification"
    assert "test@example.com" not in output.read_text(encoding="utf-8")


def test_cli_evaluation_tg_qa_downstream_fixture_pipeline(tmp_path: Path) -> None:
    candidates = tmp_path / "tg_qa_candidates.jsonl"
    extraction_summary = tmp_path / "tg_qa_summary.json"
    embedding_batch = tmp_path / "tg_qa_embedding_batch.jsonl"
    exit_code, _payload = dispatch(
        [
            "evaluation",
            "tg-qa",
            "--input",
            "tests/fixtures/tg_sample_export",
            "--bot-catalog",
            "tests/fixtures/tg_wiki_bot_catalog_sample.json",
            "--output",
            str(candidates),
            "--summary-output",
            str(extraction_summary),
            "--embedding-batch-output",
            str(embedding_batch),
            "--max-candidates",
            "20",
            "--min-attention-score",
            "6",
        ],
        settings=FoundationSettings(),
    )
    assert exit_code == 0

    batch_items = [json.loads(line) for line in embedding_batch.read_text(encoding="utf-8").splitlines()]
    assert _tg_qa_embed_batch_cli_help_mentions_endpoint_settings()
    vectors = tmp_path / "fixture_vectors.jsonl"
    _write_jsonl(vectors, [_tg_qa_fixture_vector(item) for item in batch_items])

    embedding_records = tmp_path / "tg_qa_embedding_records.jsonl"
    embedding_summary = tmp_path / "tg_qa_embedding_summary.json"
    embed_exit, embed_payload = dispatch(
        [
            "evaluation",
            "tg-qa-embeddings-import",
            "--embedding-batch",
            str(embedding_batch),
            "--external-vectors",
            str(vectors),
            "--output",
            str(embedding_records),
            "--summary-output",
            str(embedding_summary),
            "--embedding-profile-id",
            "fixture_profile",
            "--dimensions",
            "3",
        ],
        settings=FoundationSettings(),
    )
    assert embed_exit == 0
    assert embed_payload["completed_count"] == len(batch_items)

    neighbors = tmp_path / "tg_qa_neighbors.jsonl"
    similarity_summary = tmp_path / "tg_qa_similarity_summary.json"
    sim_exit, sim_payload = dispatch(
        [
            "evaluation",
            "tg-qa-similarity",
            "--embedding-records",
            str(embedding_records),
            "--output",
            str(neighbors),
            "--summary-output",
            str(similarity_summary),
        ],
        settings=FoundationSettings(),
    )
    assert sim_exit == 0
    assert sim_payload["neighbor_count"] > 0

    question_clusters = tmp_path / "question_clusters.jsonl"
    answer_clusters = tmp_path / "answer_clusters.jsonl"
    qa_clusters = tmp_path / "qa_clusters.jsonl"
    cluster_summary = tmp_path / "cluster_summary.json"
    cluster_exit, cluster_payload = dispatch(
        [
            "evaluation",
            "tg-qa-clusters",
            "--candidates",
            str(candidates),
            "--neighbors",
            str(neighbors),
            "--question-clusters-output",
            str(question_clusters),
            "--answer-clusters-output",
            str(answer_clusters),
            "--qa-clusters-output",
            str(qa_clusters),
            "--summary-output",
            str(cluster_summary),
        ],
        settings=FoundationSettings(),
    )
    assert cluster_exit == 0
    assert cluster_payload["qa_cluster_count"] >= 2

    selection = tmp_path / "cluster_selection.jsonl"
    selection_summary = tmp_path / "selection_summary.json"
    select_exit, select_payload = dispatch(
        [
            "evaluation",
            "tg-qa-selection",
            "--candidates",
            str(candidates),
            "--qa-clusters",
            str(qa_clusters),
            "--answer-clusters",
            str(answer_clusters),
            "--output",
            str(selection),
            "--summary-output",
            str(selection_summary),
        ],
        settings=FoundationSettings(),
    )
    assert select_exit == 0
    assert select_payload["counts_by_selection_status"]["auto_selected"] == 1

    review_queue = tmp_path / "review_queue.jsonl"
    review_summary = tmp_path / "review_summary.json"
    queue_exit, queue_payload = dispatch(
        [
            "evaluation",
            "tg-qa-review-queue",
            "--candidates",
            str(candidates),
            "--selection",
            str(selection),
            "--output",
            str(review_queue),
            "--summary-output",
            str(review_summary),
        ],
        settings=FoundationSettings(),
    )
    assert queue_exit == 0
    assert queue_payload["queue_count"] >= 1
    queue_item = json.loads(review_queue.read_text(encoding="utf-8").splitlines()[0])
    review_decision_input = tmp_path / "review_decision_input.jsonl"
    _write_jsonl(
        review_decision_input,
        [
            {
                "qa_cluster_id": queue_item["qa_cluster_id"],
                "decision": "uncertain",
                "reviewer_hash": "fixture-reviewer",
                "decision_reason": "fixture backlog case remains outside final dataset",
            }
        ],
    )
    review_decisions = tmp_path / "review_decisions.jsonl"
    review_decision_summary = tmp_path / "review_decision_summary.json"
    review_exit, review_payload = dispatch(
        [
            "evaluation",
            "tg-qa-review-import",
            "--review-queue",
            str(review_queue),
            "--decisions",
            str(review_decision_input),
            "--output",
            str(review_decisions),
            "--summary-output",
            str(review_decision_summary),
        ],
        settings=FoundationSettings(),
    )
    assert review_exit == 0
    assert review_payload["imported_count"] == 1

    final_cases = tmp_path / "final_cases.jsonl"
    final_manifest = tmp_path / "dataset_manifest.json"
    final_quality = tmp_path / "dataset_quality.json"
    final_exit, final_payload = dispatch(
        [
            "evaluation",
            "tg-qa-final",
            "--candidates",
            str(candidates),
            "--selection",
            str(selection),
            "--review-decisions",
            str(review_decisions),
            "--output",
            str(final_cases),
            "--manifest-output",
            str(final_manifest),
            "--quality-output",
            str(final_quality),
        ],
        settings=FoundationSettings(),
    )
    assert final_exit == 0
    assert final_payload["case_count"] == 1
    assert json.loads(final_manifest.read_text(encoding="utf-8"))["case_count"] == 1


def test_cli_tg_qa_coverage_embeddings_import_uses_settings_profile_when_only_model_id_is_passed(
    tmp_path: Path,
) -> None:
    embedding_batch = tmp_path / "coverage_batch.jsonl"
    external_vectors = tmp_path / "coverage_vectors.jsonl"
    output = tmp_path / "coverage_embedding_records.jsonl"
    summary_output = tmp_path / "coverage_embedding_summary.json"

    batch_item = {
        "embedding_item_id": "tg-coverage-embedding:test",
        "candidate_id": "tg-eval-case:test",
        "answer_candidate_id": "",
        "source_message_id": "msg-1",
        "text_role": "question",
        "coverage_scope": "dataset",
        "coverage_subject_id": "tg-eval-case:test",
        "coverage_subject_kind": "case",
        "coverage_text_source": "question_text",
        "qa_cluster_id": "tg-qa-pair-cluster:test",
        "case_id": "tg-eval-case:test",
        "text_redacted": "Нужна ли регистрация?",
        "reference_answer_source": "manual_review_override",
        "topic_labels": ["migration_status"],
        "law_code_candidates": ["AufenthG"],
        "graph_db_evaluation_fit": "direct_legal",
        "question_intent": "eligibility_or_right",
        "issue_spotting_level": "medium",
        "issue_spotting_required": True,
        "confidence_tier": "high",
    }
    _write_jsonl(embedding_batch, [batch_item])
    _write_jsonl(
        external_vectors,
        [
            {
                "embedding_item_id": batch_item["embedding_item_id"],
                "candidate_id": batch_item["candidate_id"],
                "answer_candidate_id": "",
                "text_role": "question",
                "backend_name": "fixture_vectors",
                "vector": [1.0, 0.0, 0.0],
            }
        ],
    )

    exit_code, payload = dispatch(
        [
            "evaluation",
            "tg-qa-coverage-embeddings-import",
            "--embedding-batch",
            str(embedding_batch),
            "--external-vectors",
            str(external_vectors),
            "--output",
            str(output),
            "--summary-output",
            str(summary_output),
            "--model-id",
            "jina-q8",
        ],
        settings=FoundationSettings(
            embedding_profile_id="fixture_profile",
            embedding_vector_dimensions=3,
        ),
    )

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert payload["completed_count"] == 1
    assert summary["embedding_profile"]["embedding_profile_id"] == "fixture_profile"
    assert summary["embedding_profile"]["model_id"] == "jina-q8"
    assert records[0]["embedding_profile_id"] == "fixture_profile"
    assert records[0]["model"] == "jina-q8"


def test_cli_evaluation_tg_qa_canonicalization_offline_pipeline(tmp_path: Path) -> None:
    candidates = tmp_path / "canonical_candidates.jsonl"
    canonical_batch = tmp_path / "canonical_batch.jsonl"
    canonical_batch_summary = tmp_path / "canonical_batch_summary.json"
    canonical_sample = tmp_path / "canonical_sample.jsonl"
    canonical_sample_summary = tmp_path / "canonical_sample_summary.json"
    canonical_results = tmp_path / "canonical_results.jsonl"
    canonical_review_html = tmp_path / "canonical_review.html"
    canonical_review_summary = tmp_path / "canonical_review_summary.json"
    canonical_evidence = tmp_path / "canonical_evidence.jsonl"
    canonical_manifest = tmp_path / "canonical_manifest.json"
    embedding_batch = tmp_path / "canonical_embedding_batch.jsonl"
    embedding_batch_summary = tmp_path / "canonical_embedding_batch_summary.json"
    embedding_vectors = tmp_path / "canonical_vectors.jsonl"
    embedding_records = tmp_path / "canonical_embedding_records.jsonl"
    embedding_summary = tmp_path / "canonical_embedding_summary.json"
    clusters = tmp_path / "issue_clusters.jsonl"
    cluster_summary = tmp_path / "issue_cluster_summary.json"
    cluster_manifest = tmp_path / "issue_cluster_manifest.json"
    reviewed_cases = tmp_path / "reviewed_cases.jsonl"
    coverage = tmp_path / "coverage.jsonl"
    coverage_summary = tmp_path / "coverage_summary.json"
    review_input = tmp_path / "cluster_review_input.jsonl"
    review_decisions = tmp_path / "cluster_review_decisions.jsonl"
    review_summary = tmp_path / "cluster_review_summary.json"
    question_bank = tmp_path / "question_bank.jsonl"
    question_bank_summary = tmp_path / "question_bank_summary.json"
    question_bank_manifest = tmp_path / "question_bank_manifest.json"
    case_candidates = tmp_path / "case_candidates.jsonl"
    case_candidate_summary = tmp_path / "case_candidate_summary.json"
    case_candidate_manifest = tmp_path / "case_candidate_manifest.json"
    final_cases = tmp_path / "final_cases.jsonl"
    final_manifest = tmp_path / "final_manifest.json"
    final_quality = tmp_path / "final_quality.json"
    settings = FoundationSettings(
        embedding_profile_id="fixture_profile",
        embedding_vector_dimensions=3,
    )
    _write_jsonl(candidates, [_tg_canonical_fixture_candidate()])

    batch_exit, batch_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-batch",
            "--candidates",
            str(candidates),
            "--output",
            str(canonical_batch),
            "--summary-output",
            str(canonical_batch_summary),
            "--filter-mode",
            "law_or_topic",
        ],
        settings=settings,
    )

    batch_items = [json.loads(line) for line in canonical_batch.read_text(encoding="utf-8").splitlines()]
    sample_exit, sample_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-sample",
            "--batch",
            str(canonical_batch),
            "--output",
            str(canonical_sample),
            "--summary-output",
            str(canonical_sample_summary),
            "--sample-size",
            "50",
        ],
        settings=settings,
    )
    _write_jsonl(canonical_results, [_tg_canonical_fixture_result(batch_items[0])])
    review_cards_exit, review_cards_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-review-cards",
            "--batch",
            str(canonical_sample),
            "--html-output",
            str(canonical_review_html),
            "--summary-output",
            str(canonical_review_summary),
            "--qwen-results",
            str(canonical_results),
        ],
        settings=settings,
    )
    import_exit, import_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-import",
            "--batch",
            str(canonical_batch),
            "--results",
            str(canonical_results),
            "--output",
            str(canonical_evidence),
            "--manifest-output",
            str(canonical_manifest),
            "--canonicalization-run-id",
            "tg-question-canonicalization-run:smoke",
        ],
        settings=settings,
    )

    embed_batch_exit, embed_batch_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonical-embedding-batch",
            "--canonicalization-evidence",
            str(canonical_evidence),
            "--output",
            str(embedding_batch),
            "--summary-output",
            str(embedding_batch_summary),
        ],
        settings=settings,
    )

    embedding_items = [json.loads(line) for line in embedding_batch.read_text(encoding="utf-8").splitlines()]
    _write_jsonl(embedding_vectors, [_tg_canonical_fixture_vector(item) for item in embedding_items])
    embed_import_exit, embed_import_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonical-embeddings-import",
            "--embedding-batch",
            str(embedding_batch),
            "--external-vectors",
            str(embedding_vectors),
            "--output",
            str(embedding_records),
            "--summary-output",
            str(embedding_summary),
            "--embedding-profile-id",
            "fixture_profile",
            "--dimensions",
            "3",
        ],
        settings=settings,
    )

    cluster_exit, cluster_payload = dispatch(
        [
            "evaluation",
            "tg-qa-issue-clusters",
            "--canonicalization-evidence",
            str(canonical_evidence),
            "--embedding-records",
            str(embedding_records),
            "--output",
            str(clusters),
            "--summary-output",
            str(cluster_summary),
            "--manifest-output",
            str(cluster_manifest),
        ],
        settings=settings,
    )

    cluster_items = [json.loads(line) for line in clusters.read_text(encoding="utf-8").splitlines()]
    _write_jsonl(
        reviewed_cases,
        [
            {
                "case_id": "tg-reviewed-case:fixture",
                "legal_issue_frame_slug": cluster_items[0]["legal_issue_frame_slug"],
            }
        ],
    )
    coverage_exit, coverage_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonical-coverage",
            "--issue-clusters",
            str(clusters),
            "--reviewed-final-cases",
            str(reviewed_cases),
            "--output",
            str(coverage),
            "--summary-output",
            str(coverage_summary),
        ],
        settings=settings,
    )

    _write_jsonl(
        review_input,
        [
            {
                "legal_issue_cluster_id": cluster_items[0]["legal_issue_cluster_id"],
                "decision": "approve_final_evaluation",
                "reference_answer_action": "keep_selected_telegram_answer",
                "selected_reference_answer_text_redacted": "Reviewed Telegram answer fixture.",
                "reviewer_hash": "smoke-reviewer",
                "decision_reason": "smoke promotion fixture",
            }
        ],
    )
    review_exit, review_payload = dispatch(
        [
            "evaluation",
            "tg-qa-cluster-review-import",
            "--issue-clusters",
            str(clusters),
            "--decisions",
            str(review_input),
            "--output",
            str(review_decisions),
            "--summary-output",
            str(review_summary),
        ],
        settings=settings,
    )
    bank_exit, bank_payload = dispatch(
        [
            "evaluation",
            "tg-qa-question-bank-build",
            "--issue-clusters",
            str(clusters),
            "--review-decisions",
            str(review_decisions),
            "--output",
            str(question_bank),
            "--summary-output",
            str(question_bank_summary),
            "--manifest-output",
            str(question_bank_manifest),
        ],
        settings=settings,
    )
    candidate_exit, candidate_payload = dispatch(
        [
            "evaluation",
            "tg-qa-issue-final-candidates",
            "--question-bank",
            str(question_bank),
            "--review-decisions",
            str(review_decisions),
            "--output",
            str(case_candidates),
            "--summary-output",
            str(case_candidate_summary),
            "--manifest-output",
            str(case_candidate_manifest),
        ],
        settings=settings,
    )
    final_exit, final_payload = dispatch(
        [
            "evaluation",
            "tg-qa-reviewed-evaluation-dataset-build",
            "--final-case-candidates",
            str(case_candidates),
            "--output",
            str(final_cases),
            "--manifest-output",
            str(final_manifest),
            "--quality-output",
            str(final_quality),
        ],
        settings=settings,
    )
    boundary_exit, boundary_payload = dispatch(["evaluation", "tg-qa-canonical-boundary-check"], settings=settings)

    assert batch_exit == sample_exit == review_cards_exit == import_exit == embed_batch_exit == embed_import_exit == 0
    assert cluster_exit == coverage_exit == review_exit == bank_exit == candidate_exit == final_exit == boundary_exit == 0
    assert batch_payload["emitted_task_count"] == 1
    assert sample_payload["emitted_sample_count"] == 1
    assert review_cards_payload["card_count"] == 1
    assert "Export JSONL" in canonical_review_html.read_text(encoding="utf-8")
    assert import_payload["completed_count"] == 1
    assert embed_batch_payload["emitted_item_count"] == 2
    assert embed_import_payload["completed_count"] == 2
    assert cluster_payload["emitted_cluster_count"] == 1
    assert coverage_payload["counts_by_coverage_status"] == {"covered": 1}
    assert review_payload["imported_count"] == 1
    assert bank_payload["completed_entry_count"] == 1
    assert candidate_payload["eligible_count"] == 1
    assert final_payload["case_count"] == 1
    assert boundary_payload["status"] == "passed"


def test_cli_legal_intent_pair_review_exports_100_pair_html(tmp_path: Path) -> None:
    evidence = tmp_path / "legal_intent_evidence.jsonl"
    pairs = tmp_path / "legal_intent_pairs.jsonl"
    pairs_summary = tmp_path / "legal_intent_pairs_summary.json"
    intent_candidates_input = tmp_path / "legal_intent_candidates_input.jsonl"
    intent_candidates = tmp_path / "legal_intent_candidates.jsonl"
    intent_candidates_summary = tmp_path / "legal_intent_candidates_summary.json"
    similarity_decisions = tmp_path / "legal_intent_similarity_decisions.jsonl"
    similarity_summary = tmp_path / "legal_intent_similarity_summary.json"
    slot_decisions = tmp_path / "legal_intent_slot_decisions.jsonl"
    slot_summary = tmp_path / "legal_intent_slot_summary.json"
    decisions_input = tmp_path / "legal_intent_decisions_input.jsonl"
    decisions = tmp_path / "legal_intent_decisions.jsonl"
    decisions_summary = tmp_path / "legal_intent_decisions_summary.json"
    html = tmp_path / "legal_intent_review.html"
    html_summary = tmp_path / "legal_intent_review_summary.json"
    labels_input = tmp_path / "legal_intent_labels_input.jsonl"
    labels = tmp_path / "legal_intent_labels.jsonl"
    labels_summary = tmp_path / "legal_intent_labels_summary.json"
    report = tmp_path / "legal_intent_report.jsonl"
    report_summary = tmp_path / "legal_intent_report_summary.json"
    records = []
    for index in range(15):
        records.append(
            {
                "canonicalization_evidence_id": f"tg-question-canonicalization-evidence:li-{index:02d}",
                "task_id": f"task:{index:02d}",
                "task_scope": "question_candidate",
                "candidate_id": f"tg-qa-candidate:li-{index:02d}",
                "canonicalization_run_id": "tg-question-canonicalization-run:smoke-li",
                "status": "completed",
                "failure_reason": "",
                "canonical_question": f"Как обновить адрес на ВНЖ после переезда вариант {index}?",
                "canonical_question_language": "ru",
                "legal_issue_frame": "Residence document address update after moving",
                "legal_issue_frame_slug": "residence_document_address_update_after_moving",
                "law_area": "migration_status",
                "facts": [],
                "desired_outcome": "update address on residence document",
                "authority_context": ["Buergeramt"],
                "hidden_issues": [],
                "is_legal_answer_required": True,
                "is_standalone_question": True,
                "exclusion_reason": "none",
                "confidence": "high",
                "quality_flags": [],
                "source_question_text_redacted": f"Как обновить адрес на ВНЖ после переезда вариант {index}?",
                "provenance": {"source_message_ids": [f"fixture:{index:02d}"]},
            }
        )
    _write_jsonl(evidence, records)

    pair_exit, pair_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-pair-benchmark",
            "--canonicalization-evidence",
            str(evidence),
            "--output",
            str(pairs),
            "--summary-output",
            str(pairs_summary),
        ],
        settings=FoundationSettings(),
    )
    pair_records = [json.loads(line) for line in pairs.read_text(encoding="utf-8").splitlines()]
    selected_pair_id = pair_records[0]["pair_id"]
    _write_jsonl(
        intent_candidates_input,
        [
            {
                "canonicalization_evidence_id": record["canonicalization_evidence_id"],
                "desired_action": "update_residence_document_address",
                "legal_object": "residence_document_address",
                "authority_context": ["Buergeramt"],
                "evidence_refs": [{"field": "desired_action", "source_field": "canonical_question"}],
                "confidence": "medium",
            }
            for record in records
        ],
    )
    intent_import_exit, intent_import_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-candidates-import",
            "--canonicalization-evidence",
            str(evidence),
            "--candidates",
            str(intent_candidates_input),
            "--output",
            str(intent_candidates),
            "--summary-output",
            str(intent_candidates_summary),
        ],
        settings=FoundationSettings(),
    )
    similarity_exit, similarity_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-similarity-baseline",
            "--pair-benchmark",
            str(pairs),
            "--output",
            str(similarity_decisions),
            "--summary-output",
            str(similarity_summary),
        ],
        settings=FoundationSettings(),
    )
    slot_exit, slot_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-slot-comparator",
            "--pair-benchmark",
            str(pairs),
            "--legal-intent-candidates",
            str(intent_candidates),
            "--output",
            str(slot_decisions),
            "--summary-output",
            str(slot_summary),
        ],
        settings=FoundationSettings(),
    )
    _write_jsonl(
        decisions_input,
        [
            {
                "pair_id": selected_pair_id,
                "decision_source": "smoke_judge",
                "pair_class": "same_legal_intent",
                "answer_equivalence": "safe_to_share_answer",
                "canonical_question_equivalence": "safe_to_share_question",
                "allowed_downstream_actions": ["allow_reference_answer_sharing"],
                "short_reason": "Smoke equivalent pair.",
                "confidence": "medium",
                "risk": "low",
            }
        ],
    )
    decision_exit, decision_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-pair-decisions-import",
            "--pair-benchmark",
            str(pairs),
            "--decisions",
            str(decisions_input),
            "--output",
            str(decisions),
            "--summary-output",
            str(decisions_summary),
        ],
        settings=FoundationSettings(),
    )
    html_exit, html_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-pair-review-html",
            "--pair-benchmark",
            str(pairs),
            "--pair-decisions",
            str(decisions),
            "--output",
            str(html),
            "--summary-output",
            str(html_summary),
        ],
        settings=FoundationSettings(),
    )
    _write_jsonl(
        labels_input,
        [
            {
                "pair_id": selected_pair_id,
                "pair_class": "same_legal_intent",
                "answer_equivalence": "safe_to_share_answer",
                "canonical_question_equivalence": "safe_to_share_question",
                "allowed_downstream_actions": ["allow_reference_answer_sharing"],
                "decision_reason": "Smoke human label.",
            }
        ],
    )
    label_exit, label_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-pair-labels-import",
            "--pair-benchmark",
            str(pairs),
            "--labels",
            str(labels_input),
            "--output",
            str(labels),
            "--summary-output",
            str(labels_summary),
        ],
        settings=FoundationSettings(),
    )
    report_exit, report_payload = dispatch(
        [
            "evaluation",
            "tg-qa-legal-intent-equivalence-report",
            "--pair-benchmark",
            str(pairs),
            "--pair-decisions",
            str(decisions),
            "--review-labels",
            str(labels),
            "--output",
            str(report),
            "--summary-output",
            str(report_summary),
        ],
        settings=FoundationSettings(),
    )

    assert pair_exit == intent_import_exit == similarity_exit == slot_exit == decision_exit == html_exit == label_exit == report_exit == 0
    assert pair_payload["pair_count"] == 105
    assert intent_import_payload["completed_count"] == 15
    assert similarity_payload["processed_count"] == 105
    assert slot_payload["processed_count"] == 105
    assert decision_payload["completed_count"] == 1
    assert html_payload["card_count"] == 105
    assert label_payload["completed_count"] == 1
    assert report_payload["reviewed_label_count"] == 1
    assert "Export JSONL" in html.read_text(encoding="utf-8")
    assert "007 legal intent pair review" in html.read_text(encoding="utf-8")


def test_cli_canonicalization_review_decision_import_and_routing_support_partial_disputed_subset(tmp_path: Path) -> None:
    candidates = tmp_path / "canonical_candidates.jsonl"
    canonical_batch = tmp_path / "canonical_batch.jsonl"
    canonical_batch_summary = tmp_path / "canonical_batch_summary.json"
    qwen_results = tmp_path / "qwen_results.jsonl"
    verifier_results = tmp_path / "verifier_results.jsonl"
    raw_review_decisions = tmp_path / "review_with_verifier_decisions.jsonl"
    imported_review_decisions = tmp_path / "review_decisions_imported.jsonl"
    imported_review_summary = tmp_path / "review_decisions_imported_summary.json"
    routed_results = tmp_path / "routed_results.jsonl"
    routed_summary = tmp_path / "routed_summary.json"
    decision_ledger = tmp_path / "decision_ledger.jsonl"
    retry_qwen_batch = tmp_path / "retry_qwen_batch.jsonl"
    send_deepseek_batch = tmp_path / "send_deepseek_batch.jsonl"
    backlog = tmp_path / "routing_backlog.jsonl"
    settings = FoundationSettings()

    _write_jsonl(
        candidates,
        [
            _tg_canonical_fixture_candidate(),
            {
                **_tg_canonical_fixture_candidate(),
                "candidate_id": "tg-qa-candidate:canonical-smoke-non-legal",
                "question_text_redacted": "Где купить детскую смесь в Кронахе?",
                "source_message_id": "canonical-smoke-message-2",
                "topic_labels": [],
                "law_code_candidates": [],
            },
            {
                **_tg_canonical_fixture_candidate(),
                "candidate_id": "tg-qa-candidate:canonical-smoke-retry",
                "question_text_redacted": "Как обновить статус в C24 при автоматическом продлении?",
                "source_message_id": "canonical-smoke-message-3",
            },
        ],
    )
    batch_exit, _batch_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-batch",
            "--candidates",
            str(candidates),
            "--output",
            str(canonical_batch),
            "--summary-output",
            str(canonical_batch_summary),
            "--filter-mode",
            "all",
        ],
        settings=settings,
    )
    batch_items = [json.loads(line) for line in canonical_batch.read_text(encoding="utf-8").splitlines()]
    _write_jsonl(
        qwen_results,
        [
            _tg_canonical_fixture_result(batch_items[0]),
            {
                **_tg_canonical_fixture_result(batch_items[1]),
                "canonical_question": "",
                "legal_issue_frame": "",
                "legal_issue_frame_slug": "",
                "law_area": "",
                "facts": [],
                "desired_outcome": "",
                "authority_context": [],
                "hidden_issues": [],
                "is_legal_answer_required": False,
                "exclusion_reason": "non_legal_question",
            },
            _tg_canonical_fixture_result(batch_items[2]),
        ],
    )
    _write_jsonl(
        verifier_results,
        [
            {
                "task_id": batch_items[2]["task_id"],
                "verdict": "fail",
                "confidence": 81,
                "risk": "medium",
                "bad_fields": ["law_area"],
                "short_reason": "Retry fixture.",
                "suggested_action": "retry_qwen",
            }
        ],
    )
    _write_jsonl(
        raw_review_decisions,
        [
            {
                "task_id": batch_items[2]["task_id"],
                "candidate_id": batch_items[2]["candidate_id"],
                "decision": "retry_qwen",
            }
        ],
    )

    review_exit, review_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-review-decisions-import",
            "--batch",
            str(canonical_batch),
            "--qwen-results",
            str(qwen_results),
            "--decisions",
            str(raw_review_decisions),
            "--output",
            str(imported_review_decisions),
            "--summary-output",
            str(imported_review_summary),
            "--verifier-results",
            str(verifier_results),
        ],
        settings=settings,
    )
    routing_exit, routing_payload = dispatch(
        [
            "evaluation",
            "tg-qa-canonicalization-routing",
            "--batch",
            str(canonical_batch),
            "--qwen-results",
            str(qwen_results),
            "--output",
            str(routed_results),
            "--summary-output",
            str(routed_summary),
            "--review-decisions",
            str(imported_review_decisions),
            "--verifier-results",
            str(verifier_results),
            "--decision-ledger-output",
            str(decision_ledger),
            "--retry-qwen-batch-output",
            str(retry_qwen_batch),
            "--send-deepseek-batch-output",
            str(send_deepseek_batch),
            "--backlog-output",
            str(backlog),
        ],
        settings=settings,
    )

    routed = [json.loads(line) for line in routed_results.read_text(encoding="utf-8").splitlines()]
    ledger = [json.loads(line) for line in decision_ledger.read_text(encoding="utf-8").splitlines()]
    backlog_rows = [json.loads(line) for line in backlog.read_text(encoding="utf-8").splitlines()]
    retry_rows = [json.loads(line) for line in retry_qwen_batch.read_text(encoding="utf-8").splitlines()]

    assert batch_exit == review_exit == routing_exit == 0
    assert review_payload["counts_by_decision"] == {"retry_qwen": 1}
    assert routing_payload["accepted_result_count"] == 1
    assert routing_payload["retry_qwen_count"] == 1
    assert routing_payload["send_deepseek_count"] == 0
    assert routing_payload["counts_by_decision"] == {"accept": 1, "reject": 1, "retry_qwen": 1}
    assert [row["task_id"] for row in routed] == [batch_items[0]["task_id"]]
    assert {row["decision_source"] for row in ledger} == {
        "implicit_accept_qwen_included",
        "implicit_reject_qwen_exclusion",
        "human_review",
    }
    assert {row["decision"] for row in backlog_rows} == {"reject", "retry_qwen"}
    assert [row["task_id"] for row in retry_rows] == [batch_items[2]["task_id"]]
    assert send_deepseek_batch.read_text(encoding="utf-8") == ""


def test_cli_traversal_neighborhood_writes_seed_artifact_with_injected_repository(tmp_path: Path) -> None:
    cases = _load_cli_cases()
    output_path = tmp_path / "seed_neighborhood.json"

    exit_code, payload = dispatch(
        [*cases["seed_neighborhood"]["argv"], "--output", str(output_path)],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    expected = cases["seed_neighborhood"]["expected_payload"]
    assert exit_code == 0
    for key, value in expected.items():
        assert payload[key] == value
    assert payload["structural_workflow_artifact_path"] == str(output_path)
    assert artifact["artifact_type"] == "structural_workflow"
    assert artifact["workflow_request"]["workflow_mode"] == "seed_neighborhood"
    assert "answer_text" not in json.dumps(artifact)


def test_cli_traversal_neighborhood_writes_law_scope_artifact_deterministically(tmp_path: Path) -> None:
    cases = _load_cli_cases()
    output_a = tmp_path / "law_scope_a.json"
    output_b = tmp_path / "law_scope_b.json"

    exit_a, payload_a = dispatch(
        [*cases["law_scope_overview"]["argv"], "--output", str(output_a)],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )
    exit_b, payload_b = dispatch(
        [*cases["law_scope_overview"]["argv"], "--output", str(output_b)],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )

    artifact_a = json.loads(output_a.read_text(encoding="utf-8"))
    artifact_b = json.loads(output_b.read_text(encoding="utf-8"))
    expected = cases["law_scope_overview"]["expected_payload"]
    assert exit_a == exit_b == 0
    for key, value in expected.items():
        assert payload_a[key] == value
        assert payload_b[key] == value
    assert _without_run_fields(artifact_a) == _without_run_fields(artifact_b)


def test_cli_traversal_neighborhood_reports_missing_target_inventory_status(tmp_path: Path) -> None:
    cases = _load_cli_cases()
    inventory_path = tmp_path / "missing_targets.json"
    inventory_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "selected_scope": {"law_codes": ["TestG"]},
                "top_missing_targets": [
                    {
                        "reason": "missing_target_in_corpus",
                        "target_law_code": "TestG",
                        "target_section_reference": "§ 99",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "seed_with_inventory.json"

    exit_code, payload = dispatch(
        [
            *cases["seed_neighborhood"]["argv"],
            "--missing-target-inventory",
            str(inventory_path),
            "--output",
            str(output_path),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["missing_target_inventory_status"] == "available"
    assert artifact["coverage_boundary_stops"][0]["inventory_match"] == "matched"

    items_path = tmp_path / "missing_targets_items_shape.json"
    items_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "selected_scope": {"law_codes": ["TestG"]},
                "items": [
                    {
                        "reason": "missing_target_in_corpus",
                        "target_law_code": "TestG",
                        "target_section_reference": "§ 99",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    items_output = tmp_path / "seed_with_items_inventory.json"
    items_exit, _items_payload = dispatch(
        [
            *cases["seed_neighborhood"]["argv"],
            "--missing-target-inventory",
            str(items_path),
            "--output",
            str(items_output),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )
    items_artifact = json.loads(items_output.read_text(encoding="utf-8"))
    assert items_exit == 0
    assert items_artifact["missing_target_inventory_reference"]["target_count"] == 1
    assert items_artifact["coverage_boundary_stops"][0]["inventory_match"] == "matched"

    missing_output = tmp_path / "seed_missing_inventory.json"
    missing_exit, missing_payload = dispatch(
        [
            *cases["seed_neighborhood"]["argv"],
            "--missing-target-inventory",
            str(tmp_path / "absent.json"),
            "--output",
            str(missing_output),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )
    assert missing_exit == 0
    assert missing_payload["missing_target_inventory_status"] == "missing_file"

    stale_path = tmp_path / "stale_inventory.json"
    stale_path.write_text("{not-json", encoding="utf-8")
    stale_output = tmp_path / "seed_stale_inventory.json"
    stale_exit, stale_payload = dispatch(
        [
            *cases["seed_neighborhood"]["argv"],
            "--missing-target-inventory",
            str(stale_path),
            "--output",
            str(stale_output),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )
    stale_artifact = json.loads(stale_output.read_text(encoding="utf-8"))
    assert stale_exit == 0
    assert stale_payload["missing_target_inventory_status"] == "stale"
    assert stale_artifact["coverage_boundary_stops"][0]["inventory_match"] == "stale_inventory"

    mismatch_path = tmp_path / "scope_mismatch_inventory.json"
    mismatch_path.write_text(
        json.dumps(
            {
                "selected_scope": {"law_codes": ["OtherG"]},
                "top_missing_targets": [
                    {
                        "reason": "missing_target_in_corpus",
                        "target_law_code": "TestG",
                        "target_section_reference": "§ 99",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    mismatch_output = tmp_path / "seed_scope_mismatch_inventory.json"
    mismatch_exit, mismatch_payload = dispatch(
        [
            *cases["seed_neighborhood"]["argv"],
            "--missing-target-inventory",
            str(mismatch_path),
            "--output",
            str(mismatch_output),
        ],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )
    assert mismatch_exit == 0
    assert mismatch_payload["missing_target_inventory_status"] == "scope_mismatch"


def test_cli_traversal_neighborhood_contains_no_answer_or_semantic_candidate_fields(tmp_path: Path) -> None:
    cases = _load_cli_cases()
    output_path = tmp_path / "seed_no_answer.json"

    exit_code, _payload = dispatch(
        [*cases["seed_neighborhood"]["argv"], "--output", str(output_path)],
        settings=FoundationSettings(),
        graph_repository_factory=lambda settings: FakeRelationshipRepository(),
    )

    serialized = output_path.read_text(encoding="utf-8")
    assert exit_code == 0
    for forbidden in ("answer_text", "generated_answer", "legal_advice", "semantic_candidates"):
        assert forbidden not in serialized


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": "src",
    }
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _tg_qa_embed_batch_cli_help_mentions_endpoint_settings() -> bool:
    result = _run_cli(["evaluation", "tg-qa-embed-batch", "--help"])
    return (
        result.returncode == 0
        and "--endpoint-url" in result.stdout
        and "--batch-size" in result.stdout
        and "--timeout-seconds" in result.stdout
    )


def _load_cli_cases() -> dict:
    return json.loads(Path("tests/fixtures/structural_workflow_cli_cases.json").read_text(encoding="utf-8"))


def _without_run_fields(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload))
    for key in ("artifact_id", "generated_at", "workflow_id"):
        normalized.pop(key, None)
    return normalized


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tg_qa_fixture_vector(item: dict) -> dict:
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


def _tg_canonical_fixture_candidate() -> dict:
    return {
        "candidate_id": "tg-qa-candidate:canonical-smoke",
        "question_text_redacted": "Нужно ли менять адрес на ВНЖ после переезда?",
        "topic_labels": ["migration_status"],
        "law_code_candidates": ["AufenthG"],
        "question_date": "2026-01-01T00:00:00",
        "answer_candidate_status": "strong",
        "quality_flags": [],
        "source_message_id": "canonical-smoke-message",
    }


def _tg_canonical_fixture_result(batch_item: dict) -> dict:
    return {
        "task_id": batch_item["task_id"],
        "task_scope": "question_candidate",
        "candidate_id": batch_item["candidate_id"],
        "canonicalization_run_id": "tg-question-canonicalization-run:smoke",
        "canonicalization_contract_version": "tg_question_canonicalization_v1",
        "prompt_version": "tg_question_canonicalizer_v4",
        "runtime_contour": "fixture",
        "backend": "deterministic_fixture",
        "model_id": "",
        "status": "completed",
        "failure_reason": "",
        "canonical_question": batch_item["input"]["question_text_redacted"],
        "canonical_question_language": "ru",
        "legal_issue_frame": "Residence document address update after moving",
        "legal_issue_frame_slug": "residence_document_address_update_after_moving",
        "law_area": "migration_status",
        "facts": ["moved residence"],
        "desired_outcome": "update residence document address",
        "authority_context": ["Buergeramt", "Auslaenderbehoerde"],
        "hidden_issues": ["continued lawful stay evidence"],
        "is_legal_answer_required": True,
        "is_standalone_question": True,
        "exclusion_reason": "none",
        "confidence": "high",
        "quality_flags": [],
    }


def _tg_canonical_fixture_vector(item: dict) -> dict:
    if item["text_role"] == "canonical_question":
        vector = [1.0, 0.0, 0.0]
    else:
        vector = [0.0, 1.0, 0.0]
    return {
        "embedding_item_id": item["embedding_item_id"],
        "backend_name": "fixture_vectors",
        "vector": vector,
    }


class FakeRelationshipRepository:
    def relationship_quality_artifact(self, *, law_codes: list[str], classifier_policy_version: str = ""):
        return build_relationship_quality_artifact(
            selected_scope={"law_codes": law_codes},
            classifier_policy_version=classifier_policy_version or "legal-ref-context-v1",
            generated_at="2026-01-01T00:00:00Z",
            counts_by_relation_type={"CITES": 1},
            counts_by_resolution_status={"resolved": 1},
            sample_edges_by_relation_type={},
            sample_reference_evidence=[],
            top_unresolved_targets=[],
            source_to_relation_coverage={},
            fanout_summary={},
            temporal_metadata_completeness={},
        )

    def corpus_readiness_artifact(self, *, law_codes: list[str]):
        return build_corpus_readiness_artifact(
            selected_scope={"law_codes": law_codes},
            generated_at="2026-01-01T00:00:00Z",
            counts_by_unit_status={"active": 1},
            counts_by_structure_class={"simple_paragraph": 1},
            active_unit_samples=[{"legal_section_id": "legal-section:TestG:1:current"}],
            inactive_unit_samples=[],
            complexity_summary={"total_unit_count": 1},
        )

    def structural_workflow_artifact(
        self,
        *,
        workflow_mode: str,
        seed_legal_section_ids: list[str],
        law_codes: list[str],
        allowed_relation_types: list[str],
        direction: str,
        max_depth: int,
        fanout_limit: int,
        node_limit: int,
        edge_limit: int,
        source_sample_limit: int,
        include_boundary_stops: bool,
        include_inactive_sections: bool,
        missing_target_inventory_reference: dict,
        source_relationship_quality_artifact: str = "",
    ):
        cases = json.loads(Path("tests/fixtures/structural_workflow_cases.json").read_text(encoding="utf-8"))
        if workflow_mode == "seed_neighborhood":
            case = cases["seed_neighborhood"]
            sections = case["sections"][:2]
            resolved_edges = case["resolved_edges"][:1]
            unresolved_references = case["unresolved_references"][:1]
        else:
            case = cases["law_scope_overview"]
            sections = case["sections"]
            resolved_edges = []
            unresolved_references = []
        return build_structural_workflow_artifact(
            workflow_request={
                "workflow_mode": workflow_mode,
                "seed_legal_section_ids": seed_legal_section_ids,
                "law_codes": law_codes,
                "direction": direction,
                "max_depth": max_depth,
                "allowed_relation_types": allowed_relation_types,
                "fanout_limit": fanout_limit,
                "node_limit": node_limit,
                "edge_limit": edge_limit,
                "source_sample_limit": source_sample_limit,
                "include_boundary_stops": include_boundary_stops,
                "include_inactive_sections": include_inactive_sections,
            },
            selected_scope={"law_codes": law_codes},
            generated_at="2026-01-01T00:00:00Z",
            sections=sections,
            resolved_edges=resolved_edges,
            unresolved_references=unresolved_references,
            traversal_metadata=case.get("traversal_metadata", {}),
            missing_target_inventory_reference=missing_target_inventory_reference,
            source_relationship_quality_artifact=source_relationship_quality_artifact,
        )
