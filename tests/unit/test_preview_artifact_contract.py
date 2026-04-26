from __future__ import annotations

import json

from ingestion.legal_preview_loader import build_preview_from_manifest_path, write_preview_artifact


def test_preview_artifact_shape_matches_contract(tmp_path) -> None:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")
    output = write_preview_artifact(tmp_path / "preview.json", preview)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert set(loaded) == {
        "preview_id",
        "created_at",
        "source_scope",
        "missing_inputs",
        "source_documents",
        "source_fragments",
    }
    assert loaded["source_documents"][0]["source_document_id"].startswith("source-document:")
    assert loaded["source_fragments"][0]["section_reference"] == "§ 1"
    assert loaded["source_fragments"][0]["body_text"]
