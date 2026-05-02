from __future__ import annotations

from evaluation.load_cases import (
    build_graph_snapshot_artifact,
    build_legacy_baseline_graph_snapshot_artifact,
    build_snapshot_comparison_report,
)
from graph.types import RelationshipRefreshReport
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
    assert report.legal_reference_count == 0
    assert report.unresolved_reference_count == 0
    assert report.counts_by_source_unit_status == {"active": 2, "inactive": 0}


def test_relationship_refresh_report_counts_and_failure_visibility() -> None:
    report = RelationshipRefreshReport(
        refresh_id="relationship-refresh:test",
        selected_scope={"law_codes": ["AufenthG"]},
        classifier_policy_version="legal-ref-context-v1",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        processed_fragment_count=2,
        created_reference_count=2,
        created_edge_count=1,
        failed_count=1,
        status="failed",
        counts_by_relation_type={"CITES": 2},
        counts_by_resolution_status={"resolved": 1, "unresolved": 1},
        counts_by_target_unit_status={"active": 1, "missing_target_in_corpus": 1},
        counts_by_unresolved_reason={"missing_target_in_corpus": 1},
        errors=["boom"],
    )

    assert report.status == "failed"
    assert report.created_reference_count == 2
    assert report.created_edge_count == 1
    assert report.failed_count == 1
    assert report.counts_by_target_unit_status["missing_target_in_corpus"] == 1
    assert report.counts_by_unresolved_reason["missing_target_in_corpus"] == 1
    assert report.errors == ["boom"]


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
            "LegalSection:active": 1,
            "LegalSection:inactive": 1,
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
    assert report.counts_by_source_unit_status == {"active": 1, "inactive": 1}


def test_deletion_report_records_scope_and_removed_count() -> None:
    report = build_deletion_report(selected_scope={"law_codes": ["AufenthG"]}, matched_records=6)

    assert report.selected_scope == {"law_codes": ["AufenthG"]}
    assert report.matched_records == 6
    assert report.removed_records == 6


def test_snapshot_artifact_is_reproducible_for_identical_state() -> None:
    snapshot_kwargs = dict(
        selected_scope={"law_codes": ["AufenthG"]},
        source_scope={"source_families": ["law"], "law_codes": ["AufenthG"]},
        counts={"SourceDocument": 1, "SourceFragment": 2},
        labels={"SourceDocument": 1, "SourceFragment": 2},
        relation_types={"HAS_SOURCE_FRAGMENT": 2},
        sample_ids={
            "source_document_ids": ["source-document:DE:de:AufenthG"],
            "source_fragment_ids": ["source-fragment:AufenthG:1", "source-fragment:AufenthG:2"],
            "legal_act_ids": [],
            "legal_section_ids": [],
            "legal_fragment_ids": [],
            "legal_reference_ids": [],
        },
        source_coverage={
            "law_codes": ["AufenthG"],
            "source_document_count": 1,
            "source_fragment_count": 2,
            "legal_act_count": 0,
            "legal_section_count": 0,
            "legal_fragment_count": 0,
            "legal_reference_count": 0,
            "unresolved_reference_count": 0,
        },
        embedding_profile_metadata={
            "embedding_count": 0,
            "profile_ids": [],
            "model_ids": [],
            "vector_dimensions": [],
            "backend_names": [],
            "normalized_flags": [],
        },
        unresolved_reference_evidence=[],
    )

    first = build_graph_snapshot_artifact(**snapshot_kwargs)
    second = build_graph_snapshot_artifact(**snapshot_kwargs)

    assert first.as_dict() == second.as_dict()


def test_legacy_baseline_snapshot_remains_read_only_and_comparable() -> None:
    baseline = build_legacy_baseline_graph_snapshot_artifact(
        selected_scope={"law_codes": ["AufenthG"]},
        source_scope={"source_families": ["law"], "law_codes": ["AufenthG"]},
        counts={"SourceDocument": 1},
        labels={"SourceDocument": 1},
        relation_types={},
        sample_ids={
            "source_document_ids": ["source-document:DE:de:AufenthG"],
            "source_fragment_ids": [],
            "legal_act_ids": [],
            "legal_section_ids": [],
            "legal_fragment_ids": [],
            "legal_reference_ids": [],
        },
        source_coverage={
            "law_codes": ["AufenthG"],
            "source_document_count": 1,
            "source_fragment_count": 0,
            "legal_act_count": 0,
            "legal_section_count": 0,
            "legal_fragment_count": 0,
            "legal_reference_count": 0,
            "unresolved_reference_count": 0,
        },
        embedding_profile_metadata={
            "embedding_count": 0,
            "profile_ids": [],
            "model_ids": [],
            "vector_dimensions": [],
            "backend_names": [],
            "normalized_flags": [],
        },
        unresolved_reference_evidence=[],
        baseline_scope={"law_codes": ["AufenthG"]},
    )
    new_snapshot = build_graph_snapshot_artifact(
        selected_scope={"law_codes": ["AufenthG"]},
        source_scope={"source_families": ["law"], "law_codes": ["AufenthG"]},
        counts={"SourceDocument": 1, "SourceFragment": 1},
        labels={"SourceDocument": 1, "SourceFragment": 1},
        relation_types={},
        sample_ids={
            "source_document_ids": ["source-document:DE:de:AufenthG"],
            "source_fragment_ids": ["source-fragment:AufenthG:1"],
            "legal_act_ids": [],
            "legal_section_ids": [],
            "legal_fragment_ids": [],
            "legal_reference_ids": [],
        },
        source_coverage={
            "law_codes": ["AufenthG"],
            "source_document_count": 1,
            "source_fragment_count": 1,
            "legal_act_count": 0,
            "legal_section_count": 0,
            "legal_fragment_count": 0,
            "legal_reference_count": 0,
            "unresolved_reference_count": 0,
        },
        embedding_profile_metadata={
            "embedding_count": 0,
            "profile_ids": [],
            "model_ids": [],
            "vector_dimensions": [],
            "backend_names": [],
            "normalized_flags": [],
        },
        unresolved_reference_evidence=[],
    )

    report = build_snapshot_comparison_report(new_snapshot, baseline)

    assert baseline.as_dict()["baseline_origin"] == "legacy_aufenthg_graph_scope"
    assert baseline.as_dict()["baseline_scope"] == {"law_codes": ["AufenthG"]}
    assert report.new_snapshot_id == new_snapshot.snapshot_id
    assert report.baseline_snapshot_id == baseline.snapshot_id
