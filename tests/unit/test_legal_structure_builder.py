from __future__ import annotations

from ingestion.legal_preview_loader import build_preview_from_manifest
from ingestion.legal_preview_loader import build_preview_from_manifest_path
from ingestion.legal_structure_builder import (
    _resolve_candidate,
    build_relationship_evidence_from_preview,
    build_relationship_evidence_from_records,
    build_structural_legal_graph,
)
from graph.types import ParsedReferenceCandidate


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


def test_source_status_detection_preserves_inactive_markers_and_false_positive_body_text() -> None:
    preview = build_preview_from_manifest(
        {
            "inputs": [
                {
                    "path": "tests/fixtures/legal_xml/corpus_boundary_status.xml",
                    "law_code": "StatusG",
                }
            ]
        }
    )

    graph = build_structural_legal_graph(preview)
    sections = {section["section_reference"]: section for section in graph["legal_sections"]}

    assert sections["§ 1"]["unit_status"] == "active"
    assert sections["§ 1"]["source_version_id"] == "v1"
    assert sections["§ 1"]["source_revision_marker"] == "build-2026-04-30"
    assert sections["§ 2"]["unit_status"] == "inactive"
    assert sections["§ 2"]["status_marker_text"] == "(weggefallen)"
    assert sections["§ 3"]["unit_status"] == "inactive"
    assert sections["§ 3"]["status_marker_text"] == "aufgehoben"
    assert sections["§ 4"]["unit_status"] == "active"
    assert sections["§ 4"]["status_marker_text"] == ""
    assert sections["§ 5"]["unit_status"] == "inactive"
    assert sections["§ 5"]["status_marker_text"] == "außer Kraft"


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
    assert ambiguous["unresolved_reason"] == "ambiguous_target"
    assert ambiguous["target_legal_section_id"] == ""
    assert ambiguous["unresolved_target_evidence"]["candidate_legal_section_ids"] == [
        "legal-section:TestG:6:current",
        "legal-section:TestG:6:old",
    ]


def test_relationship_resolution_reasons_and_inactive_target_status_are_explicit() -> None:
    source_fragments = [
        _fragment("1", "Siehe § 2 TestG."),
        _fragment("3", "Siehe § 99 TestG."),
        _fragment("4", "Siehe § 1 OtherG."),
    ]
    legal_sections = [
        _section("1"),
        _section("2", unit_status="inactive"),
        _section("3"),
        _section("4"),
    ]

    references = build_relationship_evidence_from_records(
        source_fragments=source_fragments,
        legal_sections=legal_sections,
        law_codes=["TestG"],
    )

    by_source = {reference["source_legal_section_id"]: reference for reference in references}
    inactive_target = by_source["legal-section:TestG:1:current"]
    assert inactive_target["resolution_status"] == "resolved"
    assert inactive_target["target_unit_status"] == "inactive"
    assert inactive_target["unresolved_reason"] == ""

    missing_target = by_source["legal-section:TestG:3:current"]
    assert missing_target["resolution_status"] == "unresolved"
    assert missing_target["target_unit_status"] == "missing_target_in_corpus"
    assert missing_target["unresolved_reason"] == "missing_target_in_corpus"
    assert missing_target["unresolved_target_evidence"]["reason"] == "missing_target_in_corpus"

    out_of_scope = by_source["legal-section:TestG:4:current"]
    assert out_of_scope["resolution_status"] == "out_of_scope"
    assert out_of_scope["target_unit_status"] == "out_of_scope_law"
    assert out_of_scope["unresolved_reason"] == "out_of_scope_law"


def test_target_without_law_code_reason_requires_section_without_law() -> None:
    reference = _resolve_candidate(
        ParsedReferenceCandidate(
            parsed_reference_id="parsed-reference:no-law",
            source_legal_section_id="legal-section:TestG:1:current",
            source_legal_fragment_id="legal-fragment:TestG:1:1",
            source_fragment_id="source-fragment:TestG:1",
            law_code="TestG",
            raw_reference_text="§ 2",
            normalized_reference_text="§ 2",
            target_law_code="",
            target_section_reference="§ 2",
        ),
        ordinal=1,
        selected_law_codes={"TestG"},
        section_index={},
    )

    assert reference.resolution_status == "unresolved"
    assert reference.unresolved_reason == "target_without_law_code"
    assert reference.target_law_code == ""
    assert reference.target_section_reference == "§ 2"
    assert reference.unresolved_target_evidence["reason"] == "target_without_law_code"


def test_parse_incomplete_reason_allows_missing_target_fields_with_evidence() -> None:
    reference = _resolve_candidate(
        ParsedReferenceCandidate(
            parsed_reference_id="parsed-reference:incomplete",
            source_legal_section_id="legal-section:TestG:1:current",
            source_legal_fragment_id="legal-fragment:TestG:1:1",
            source_fragment_id="source-fragment:TestG:1",
            law_code="TestG",
            raw_reference_text="§",
            normalized_reference_text="§",
            target_law_code="TestG",
            target_section_reference="",
        ),
        ordinal=1,
        selected_law_codes={"TestG"},
        section_index={},
    )

    assert reference.resolution_status == "unresolved"
    assert reference.unresolved_reason == "parse_incomplete"
    assert reference.target_section_reference == ""
    assert reference.unresolved_target_evidence["raw_reference_text"] == "§"


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


def _section(section: str, *, suffix: str = "current", unit_status: str = "active") -> dict[str, object]:
    return {
        "legal_section_id": f"legal-section:TestG:{section}:{suffix}",
        "legal_act_id": "legal-act:TestG",
        "law_code": "TestG",
        "section_reference": f"§ {section}",
        "normalized_reference": f"§ {section}",
        "title": f"Section {section}",
        "unit_status": unit_status,
    }
