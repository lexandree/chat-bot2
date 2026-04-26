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
