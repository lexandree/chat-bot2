from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.legal_preview_loader import build_preview_from_manifest
from ingestion.legal_xml_import import LegalXmlImportError, normalize_section_reference, parse_legal_xml_file


def test_parse_gesetze_im_internet_style_xml_fixture() -> None:
    sections = parse_legal_xml_file("tests/fixtures/legal_xml/aufenthg.xml", law_code="AufenthG")

    assert [section.section_reference for section in sections] == ["§ 1", "§ 2"]
    assert sections[0].law_code == "AufenthG"
    assert "§ 2 AufenthG" in sections[0].body_text


def test_normalize_section_reference_rejects_unsupported_values() -> None:
    with pytest.raises(LegalXmlImportError):
        normalize_section_reference("Artikel 1")


def test_malformed_required_file_reports_path_context(tmp_path: Path) -> None:
    malformed = tmp_path / "broken.xml"
    malformed.write_text("<dokumente><norm>", encoding="utf-8")

    manifest = {
        "inputs": [
            {
                "path": str(malformed),
                "law_code": "BrokenG",
                "required": True,
            }
        ]
    }

    with pytest.raises(LegalXmlImportError, match="broken.xml"):
        build_preview_from_manifest(manifest)
