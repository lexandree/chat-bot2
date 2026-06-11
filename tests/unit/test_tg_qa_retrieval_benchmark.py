from __future__ import annotations

import json
from pathlib import Path

from evaluation.tg_qa_retrieval_benchmark import (
    build_private_artifact_snapshot_manifest,
    build_tg_qa_corpus_bounded_reference_benchmark,
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


def _dataset_record(record_id: str, question: str) -> dict:
    return {
        "artifact_type": "tg_qa_canonical_question_dataset_record",
        "dataset_record_id": record_id,
        "task_id": f"task:{record_id}",
        "canonical_question": question,
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
                "title": "Scope",
                "body_text": "Test.",
                "checksum": "sha256:test",
                "order_index": 1,
            }
        ],
        "missing_inputs": [],
        "source_scope": {"law_codes": ["AufenthG"]},
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
