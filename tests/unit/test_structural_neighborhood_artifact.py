from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evaluation.load_cases import build_structural_workflow_artifact, structural_workflow_artifact


FIXTURE_PATH = Path("tests/fixtures/structural_workflow_cases.json")


def test_structural_workflow_artifact_shape_mode_and_no_answer_fields() -> None:
    case = _case("seed_neighborhood")
    artifact = build_structural_workflow_artifact(
        workflow_request=case["workflow_request"],
        selected_scope={"law_codes": ["TestG"]},
        generated_at="2026-01-01T00:00:00Z",
        sections=case["sections"],
        resolved_edges=case["resolved_edges"],
        unresolved_references=case["unresolved_references"],
        traversal_metadata=case["traversal_metadata"],
    )
    payload = structural_workflow_artifact(artifact)

    assert payload["artifact_id"].startswith("structural-workflow:")
    assert payload["artifact_type"] == "structural_workflow"
    assert payload["workflow_request"]["workflow_mode"] == "seed_neighborhood"
    assert payload["quality_summary"]["workflow_mode"] == "seed_neighborhood"
    assert payload["sections"][0]["role"] == "seed"
    assert payload["resolved_edges"][0]["legal_reference_ids"] == ["legal-reference:TestG:1:2"]
    assert "answer_text" not in json.dumps(payload)


def test_structural_workflow_artifact_rejects_answer_fields() -> None:
    case = _case("seed_neighborhood")
    bad_sections = copy.deepcopy(case["sections"])
    bad_sections[0]["answer_text"] = "not allowed"

    with pytest.raises(ValueError):
        build_structural_workflow_artifact(
            workflow_request=case["workflow_request"],
            generated_at="2026-01-01T00:00:00Z",
            sections=bad_sections,
            resolved_edges=case["resolved_edges"],
            unresolved_references=[],
        )


def test_coverage_boundary_stops_group_missing_targets_and_bound_samples() -> None:
    case = _case("seed_neighborhood")
    artifact = build_structural_workflow_artifact(
        workflow_request=case["workflow_request"],
        selected_scope={"law_codes": ["TestG"]},
        generated_at="2026-01-01T00:00:00Z",
        sections=case["sections"],
        resolved_edges=case["resolved_edges"],
        unresolved_references=list(reversed(case["unresolved_references"])),
        missing_target_inventory_reference={
            "status": "available",
            "law_codes": ["TestG"],
            "targets": [
                {
                    "reason": "missing_target_in_corpus",
                    "target_law_code": "TestG",
                    "target_section_reference": "§ 99",
                }
            ],
        },
    )
    stop = artifact.as_dict()["coverage_boundary_stops"][0]

    assert stop["reason"] == "missing_target_in_corpus"
    assert stop["target_law_code"] == "TestG"
    assert stop["target_section_reference"] == "§ 99"
    assert stop["count"] == 2
    assert stop["inventory_match"] == "matched"
    assert len(stop["source_samples"]) == 1
    assert stop["source_samples"][0]["legal_reference_id"] == "legal-reference:TestG:1:99"


def test_quality_summary_reports_truncation_cycles_inactive_and_provenance() -> None:
    case = _case("seed_neighborhood")
    payload = build_structural_workflow_artifact(
        workflow_request=case["workflow_request"],
        selected_scope={"law_codes": ["TestG"]},
        generated_at="2026-01-01T00:00:00Z",
        sections=case["sections"],
        resolved_edges=case["resolved_edges"],
        unresolved_references=case["unresolved_references"],
        traversal_metadata=case["traversal_metadata"],
    ).as_dict()
    summary = payload["quality_summary"]

    assert summary["visited_section_count"] == 3
    assert summary["resolved_edge_count"] == 2
    assert summary["resolved_edges_by_relation_type"]["CITES"] == 2
    assert summary["boundary_stops_by_reason"]["missing_target_in_corpus"] == 2
    assert summary["truncation_count"] == 1
    assert summary["cycle_boundary_count"] == 1
    assert summary["inactive_section_count"] == 1
    assert summary["provenance_completeness"]["section_required_identity"]["missing_count"] == 0
    assert summary["missing_target_inventory_status"] == "not_provided"


def test_structural_workflow_artifact_is_deterministic_except_run_fields() -> None:
    case = _case("seed_neighborhood")
    first = build_structural_workflow_artifact(
        workflow_request=case["workflow_request"],
        selected_scope={"law_codes": ["TestG"]},
        generated_at="2026-01-01T00:00:00Z",
        sections=list(reversed(case["sections"])),
        resolved_edges=list(reversed(case["resolved_edges"])),
        unresolved_references=list(reversed(case["unresolved_references"])),
        traversal_metadata=case["traversal_metadata"],
    ).as_dict()
    second = build_structural_workflow_artifact(
        workflow_request=case["workflow_request"],
        selected_scope={"law_codes": ["TestG"]},
        generated_at="2026-01-02T00:00:00Z",
        sections=case["sections"],
        resolved_edges=case["resolved_edges"],
        unresolved_references=case["unresolved_references"],
        traversal_metadata=case["traversal_metadata"],
    ).as_dict()

    assert _without_run_fields(first) == _without_run_fields(second)


def _case(name: str) -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[name]


def _without_run_fields(payload: dict) -> dict:
    normalized = copy.deepcopy(payload)
    for key in ("artifact_id", "generated_at", "workflow_id"):
        normalized.pop(key, None)
    return normalized
