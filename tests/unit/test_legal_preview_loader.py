from __future__ import annotations

from ingestion.legal_preview_loader import build_preview_from_manifest_path, sha256_text


def test_preview_has_stable_ids_ordering_checksums_and_missing_optional_inputs() -> None:
    first = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")
    second = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")

    assert first == second
    assert first["source_scope"]["law_codes"] == ["AufenthG"]
    assert first["missing_inputs"] == [
        {
            "path": "tests/fixtures/legal_xml/missing_optional.xml",
            "required": False,
            "reason": "missing",
        }
    ]
    assert [fragment["source_fragment_id"] for fragment in first["source_fragments"]] == [
        "source-fragment:AufenthG:1",
        "source-fragment:AufenthG:2",
    ]
    assert first["source_fragments"][0]["checksum"].startswith("sha256:")
    assert first["source_fragments"][0]["checksum"] == sha256_text(first["source_fragments"][0]["body_text"])


def test_preview_law_code_filter_limits_fragments() -> None:
    preview = build_preview_from_manifest_path(
        "tests/fixtures/legal_xml_import_manifest.json",
        law_codes=["OtherG"],
    )

    assert preview["source_documents"] == []
    assert preview["source_fragments"] == []
    assert preview["source_scope"]["law_codes"] == ["OtherG"]
