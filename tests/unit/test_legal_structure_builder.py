from __future__ import annotations

from ingestion.legal_preview_loader import build_preview_from_manifest_path
from ingestion.legal_structure_builder import build_structural_legal_graph


def test_structural_graph_mapping_from_preview_artifact() -> None:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")

    graph = build_structural_legal_graph(preview)

    assert graph["legal_acts"][0]["legal_act_id"] == "legal-act:AufenthG"
    assert [section["legal_section_id"] for section in graph["legal_sections"]] == [
        "legal-section:AufenthG:1:current",
        "legal-section:AufenthG:2:current",
    ]
    assert graph["legal_fragments"][0]["source_fragment_id"] == "source-fragment:AufenthG:1"
    assert graph["legal_references"][0]["target_legal_section_id"] == "legal-section:AufenthG:2:current"
    assert graph["legal_references"][0]["resolution_status"] == "resolved"
