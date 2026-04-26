from __future__ import annotations

from ingestion.legal_preview_loader import build_preview_from_manifest_path
from ingestion.legal_structure_builder import build_structural_legal_graph
from ingestion.verification import build_deletion_report, build_load_report, build_verification_report


def test_load_report_counts_source_legal_and_unresolved_records() -> None:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")
    graph = build_structural_legal_graph(preview)

    report = build_load_report(preview, graph)

    assert report.write_semantics == "idempotent_upsert"
    assert report.source_document_count == 1
    assert report.source_fragment_count == 2
    assert report.legal_section_count == 2
    assert report.legal_reference_count == 1
    assert report.unresolved_reference_count == 0


def test_verification_report_assembly_includes_embedding_metadata_fields() -> None:
    report = build_verification_report(
        selected_scope={"law_codes": ["AufenthG"]},
        counts={
            "SourceDocument": 1,
            "SourceFragment": 2,
            "LegalAct": 1,
            "LegalSection": 2,
            "LegalFragment": 2,
            "LegalReference": 1,
        },
        embedding={
            "embedding_count": 3,
            "profile_ids": ["jina_v5_q8_1024_norm_v1"],
            "vector_dimensions": [1024],
            "backend_names": ["local_embedding_endpoint"],
        },
    )

    assert report.embedding_count == 3
    assert report.embedding_profile_ids == ["jina_v5_q8_1024_norm_v1"]
    assert report.vector_dimensions == [1024]
    assert report.backend_names == ["local_embedding_endpoint"]


def test_deletion_report_records_scope_and_removed_count() -> None:
    report = build_deletion_report(selected_scope={"law_codes": ["AufenthG"]}, matched_records=6)

    assert report.selected_scope == {"law_codes": ["AufenthG"]}
    assert report.matched_records == 6
    assert report.removed_records == 6
