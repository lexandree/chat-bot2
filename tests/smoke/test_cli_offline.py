from __future__ import annotations

import json
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
    assert payload["known_wiki_bot_answer_candidate_count"] == 1
    assert payload["other_bot_answer_candidate_count"] == 1
    assert summary["trust_boundary"] == "telegram_answers_are_evaluation_material_not_legal_truth"
    assert summary["embedding_batch_output_path"] == str(embedding_output)
    assert candidates[0]["answer_candidate_status"] == "strong"
    assert candidates[0]["selection_status"] == "pending_embedding_cluster"
    assert candidates[0]["review_route"] == "embedding_cluster_selection"
    assert candidates[0]["answer_source_counts"] == {"human_reply": 2, "known_wiki_bot": 1, "other_bot": 1}
    assert candidates[0]["answer_candidates"][2]["known_bot_usernames"] == ["@berlin_wiki_bot"]
    assert candidates[0]["answer_candidates"][3]["answer_candidate_priority"] == "low"
    assert candidates[0]["bot_mentions"] == ["@berlin_wiki_bot"]
    assert candidates[1]["quality_flags"] == ["low_topic_relevance", "missing_answer_candidate"]
    assert embedding_items[0]["cluster_usage"] == ["question_cluster", "qa_cluster"]
    assert llm_items[0]["task_type"] == "tg_qa_candidate_classification"
    assert "test@example.com" not in output.read_text(encoding="utf-8")


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


def _load_cli_cases() -> dict:
    return json.loads(Path("tests/fixtures/structural_workflow_cli_cases.json").read_text(encoding="utf-8"))


def _without_run_fields(payload: dict) -> dict:
    normalized = json.loads(json.dumps(payload))
    for key in ("artifact_id", "generated_at", "workflow_id"):
        normalized.pop(key, None)
    return normalized


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
