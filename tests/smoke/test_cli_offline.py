from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


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
