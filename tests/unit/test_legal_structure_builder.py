from __future__ import annotations

from ingestion.legal_preview_loader import build_preview_from_manifest_path
from ingestion.legal_structure_builder import (
    build_relationship_evidence_from_preview,
    build_relationship_evidence_from_records,
    build_structural_legal_graph,
)


def test_structural_graph_mapping_from_preview_artifact_defers_relationships() -> None:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")

    graph = build_structural_legal_graph(preview)

    assert graph["legal_acts"][0]["legal_act_id"] == "legal-act:AufenthG"
    assert [section["legal_section_id"] for section in graph["legal_sections"]] == [
        "legal-section:AufenthG:1:current",
        "legal-section:AufenthG:2:current",
    ]
    assert graph["legal_fragments"][0]["source_fragment_id"] == "source-fragment:AufenthG:1"
    assert graph["legal_references"] == []


def test_relationship_evidence_from_preview_contains_context_and_resolved_target() -> None:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")

    references = build_relationship_evidence_from_preview(preview, law_codes=["AufenthG"])

    assert len(references) == 1
    reference = references[0]
    assert reference["target_legal_section_id"] == "legal-section:AufenthG:2:current"
    assert reference["resolution_status"] == "resolved"
    assert reference["primary_relation_type"] == "CITES"
    assert reference["relation_type"] == "CITES"
    assert reference["source_legal_section_id"] == "legal-section:AufenthG:1:current"
    assert reference["source_legal_fragment_id"] == "legal-fragment:AufenthG:1:1"
    assert reference["source_fragment_id"] == "source-fragment:AufenthG:1"
    assert reference["context_text"]
    assert reference["context_checksum"]
    assert reference["classifier_policy_version"] == "legal-ref-context-v1"
    assert reference["temporal_evidence_status"] == "available"
    assert reference["effective_from"] or reference["publication_date"]


def test_relationship_resolution_statuses_are_selected_scope_aware() -> None:
    source_fragments = [
        _fragment("1", "Siehe § 2 TestG."),
        _fragment("3", "Siehe § 99 TestG."),
        _fragment("4", "Siehe § 1 OtherG."),
        _fragment("5", "Siehe § 6 TestG."),
    ]
    legal_sections = [
        _section("1"),
        _section("2"),
        _section("6", suffix="current"),
        _section("6", suffix="old"),
    ]

    references = build_relationship_evidence_from_records(
        source_fragments=source_fragments,
        legal_sections=legal_sections,
        law_codes=["TestG"],
    )

    statuses = {
        reference["source_legal_section_id"]: reference["resolution_status"]
        for reference in references
    }
    assert statuses["legal-section:TestG:1:current"] == "resolved"
    assert statuses["legal-section:TestG:3:current"] == "unresolved"
    assert statuses["legal-section:TestG:4:current"] == "out_of_scope"
    assert statuses["legal-section:TestG:5:current"] == "ambiguous"
    ambiguous = next(item for item in references if item["resolution_status"] == "ambiguous")
    assert ambiguous["target_legal_section_id"] == ""
    assert ambiguous["unresolved_target_evidence"]["candidate_legal_section_ids"] == [
        "legal-section:TestG:6:current",
        "legal-section:TestG:6:old",
    ]


def test_relationship_evidence_preserves_temporal_metadata() -> None:
    references = build_relationship_evidence_from_records(
        source_fragments=[
            {
                **_fragment("1", "Nach § 2 TestG gilt dies."),
                "effective_from": "2026-01-01",
                "publication_date": "2025-12-01",
            }
        ],
        legal_sections=[_section("1"), _section("2")],
        law_codes=["TestG"],
    )

    reference = references[0]
    assert reference["effective_from"] == "2026-01-01"
    assert reference["publication_date"] == "2025-12-01"
    assert reference["temporal_evidence_status"] == "available"


def _fragment(section: str, body_text: str) -> dict[str, object]:
    return {
        "source_fragment_id": f"source-fragment:TestG:{section}",
        "source_document_id": "source-document:TestG",
        "law_code": "TestG",
        "section_reference": f"§ {section}",
        "title": f"Section {section}",
        "body_text": body_text,
        "source_legal_section_id": f"legal-section:TestG:{section}:current",
        "source_legal_fragment_id": f"legal-fragment:TestG:{section}:1",
    }


def _section(section: str, *, suffix: str = "current") -> dict[str, object]:
    return {
        "legal_section_id": f"legal-section:TestG:{section}:{suffix}",
        "legal_act_id": "legal-act:TestG",
        "law_code": "TestG",
        "section_reference": f"§ {section}",
        "normalized_reference": f"§ {section}",
        "title": f"Section {section}",
    }
