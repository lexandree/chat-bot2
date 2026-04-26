from __future__ import annotations

import pytest

from evaluation.load_cases import (
    build_graph_snapshot_artifact,
    build_legacy_baseline_graph_snapshot_artifact,
    build_snapshot_comparison_report,
    ensure_no_answer_fields,
    structural_retrieval_artifact,
)
from graph.types import StructuralRetrievalResult


def test_structural_retrieval_artifact_omits_answer_fields() -> None:
    result = StructuralRetrievalResult(
        query_reference={"law_code": "AufenthG", "section_reference": "§ 1"},
        matched_legal_section_id="legal-section:AufenthG:1:current",
        source_references=["source-fragment:aufenthg:1"],
        relation_types=["CITES"],
        depth_limit=1,
        fanout_limit=25,
        node_limit=100,
        visited_count=1,
    )

    payload = structural_retrieval_artifact(result)

    assert "answer_text" not in payload
    assert "answer" not in payload
    assert "generated_answer" not in payload


def test_structural_retrieval_artifact_rejects_answer_fields() -> None:
    with pytest.raises(ValueError, match="forbidden answer fields"):
        ensure_no_answer_fields({"answer_text": None})


def test_graph_snapshot_artifact_shape_matches_contract() -> None:
    snapshot = build_graph_snapshot_artifact(
        selected_scope={"law_codes": ["AufenthG"]},
        source_scope={"source_families": ["law"], "law_codes": ["AufenthG"]},
        counts={"SourceDocument": 1, "SourceFragment": 2, "LegalReference": 1},
        labels={"SourceDocument": 1, "SourceFragment": 2, "LegalReference": 1},
        relation_types={"HAS_SOURCE_FRAGMENT": 2, "HAS_REFERENCE": 1},
        sample_ids={
            "source_document_ids": ["source-document:DE:de:AufenthG"],
            "source_fragment_ids": ["source-fragment:AufenthG:1", "source-fragment:AufenthG:2"],
            "legal_act_ids": ["legal-act:AufenthG"],
            "legal_section_ids": ["legal-section:AufenthG:1:current"],
            "legal_fragment_ids": ["legal-fragment:AufenthG:1:1"],
            "legal_reference_ids": ["legal-reference:legal-section:AufenthG:1:current:1"],
        },
        source_coverage={
            "law_codes": ["AufenthG"],
            "source_document_count": 1,
            "source_fragment_count": 2,
            "legal_act_count": 1,
            "legal_section_count": 1,
            "legal_fragment_count": 1,
            "legal_reference_count": 1,
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

    payload = snapshot.as_dict()

    assert payload["snapshot_id"].startswith("snapshot:")
    assert set(payload) == {
        "snapshot_id",
        "selected_scope",
        "source_scope",
        "counts",
        "labels",
        "relation_types",
        "sample_ids",
        "source_coverage",
        "embedding_profile_metadata",
        "unresolved_reference_evidence",
    }


def test_legacy_baseline_snapshot_shape_and_comparison_report() -> None:
    new_snapshot = build_graph_snapshot_artifact(
        selected_scope={"law_codes": ["AufenthG"]},
        source_scope={"source_families": ["law"], "law_codes": ["AufenthG"]},
        counts={"SourceDocument": 1, "SourceFragment": 2, "LegalSection": 2},
        labels={"SourceDocument": 1, "SourceFragment": 2, "LegalSection": 2},
        relation_types={"HAS_SOURCE_FRAGMENT": 2},
        sample_ids={
            "source_document_ids": ["source-document:DE:de:AufenthG"],
            "source_fragment_ids": ["source-fragment:AufenthG:1", "source-fragment:AufenthG:2"],
            "legal_act_ids": ["legal-act:AufenthG"],
            "legal_section_ids": ["legal-section:AufenthG:1:current", "legal-section:AufenthG:2:current"],
            "legal_fragment_ids": ["legal-fragment:AufenthG:1:1"],
            "legal_reference_ids": [],
        },
        source_coverage={
            "law_codes": ["AufenthG"],
            "source_document_count": 1,
            "source_fragment_count": 2,
            "legal_act_count": 1,
            "legal_section_count": 2,
            "legal_fragment_count": 1,
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
    baseline_snapshot = build_legacy_baseline_graph_snapshot_artifact(
        selected_scope={"law_codes": ["AufenthG"]},
        source_scope={"source_families": ["law"], "law_codes": ["AufenthG"]},
        counts={"SourceDocument": 1, "SourceFragment": 2, "LegalSection": 1},
        labels={"SourceDocument": 1, "SourceFragment": 2, "LegalSection": 1},
        relation_types={"HAS_SOURCE_FRAGMENT": 2},
        sample_ids={
            "source_document_ids": ["source-document:DE:de:AufenthG"],
            "source_fragment_ids": ["source-fragment:AufenthG:1", "source-fragment:AufenthG:2"],
            "legal_act_ids": ["legal-act:AufenthG"],
            "legal_section_ids": ["legal-section:AufenthG:1:current"],
            "legal_fragment_ids": ["legal-fragment:AufenthG:1:1"],
            "legal_reference_ids": [],
        },
        source_coverage={
            "law_codes": ["AufenthG"],
            "source_document_count": 1,
            "source_fragment_count": 2,
            "legal_act_count": 1,
            "legal_section_count": 1,
            "legal_fragment_count": 1,
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

    report = build_snapshot_comparison_report(new_snapshot, baseline_snapshot)

    assert baseline_snapshot.as_dict()["baseline_origin"] == "legacy_aufenthg_graph_scope"
    assert report.new_snapshot_id == new_snapshot.snapshot_id
    assert report.baseline_snapshot_id == baseline_snapshot.snapshot_id
    assert report.missing["counts"]["LegalSection"] == 1
    assert report.extra["counts"]["LegalSection"] == 2
    assert report.summary_counts["missing_items"] >= 1
