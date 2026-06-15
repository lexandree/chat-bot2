from __future__ import annotations

import pytest

from ingestion.legal_corpus_workflow import build_new_law_preflight


def test_new_law_preflight_builds_full_preview_without_graph_writes(tmp_path) -> None:
    preview = tmp_path / "preview.json"

    artifact = build_new_law_preflight(
        manifest_path="tests/fixtures/legal_xml_new_law_manifest.json",
        new_law_code="VwVfG",
        preview_output_path=preview,
    )

    assert artifact["status"] == "ready"
    assert artifact["active_law_codes"] == ["AufenthG", "VwVfG"]
    assert artifact["source_fragment_counts_by_law_code"] == {"AufenthG": 2, "VwVfG": 1}
    assert artifact["new_law_incoming_reference_count"] == 0
    assert artifact["new_law_unresolved_incoming_reference_count"] == 0
    assert artifact["graph_writes_performed"] is False
    assert preview.exists()


def test_new_law_preflight_rejects_law_absent_from_manifest(tmp_path) -> None:
    with pytest.raises(ValueError, match="absent from active corpus manifest"):
        build_new_law_preflight(
            manifest_path="tests/fixtures/legal_xml_new_law_manifest.json",
            new_law_code="MissingG",
            preview_output_path=tmp_path / "preview.json",
        )
