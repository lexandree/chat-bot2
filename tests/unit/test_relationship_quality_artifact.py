from __future__ import annotations

import pytest

from evaluation.load_cases import build_relationship_quality_artifact, relationship_quality_artifact
from graph.types import (
    RELATION_TYPES,
    RESOLUTION_STATUSES,
    TARGET_UNIT_STATUSES,
    TEMPORAL_EVIDENCE_STATUSES,
    UNIT_STATUSES,
    UNRESOLVED_REASONS,
)


def test_relationship_quality_artifact_shape_and_all_relation_counts() -> None:
    artifact = _artifact()
    payload = artifact.as_dict()

    assert payload["artifact_id"].startswith("relationship-quality:")
    assert set(payload["counts_by_relation_type"]) == set(RELATION_TYPES)
    assert payload["counts_by_relation_type"]["CITES"] == 1
    assert payload["counts_by_relation_type"]["SUPERSEDED_BY"] == 0
    assert set(payload["counts_by_resolution_status"]) == set(RESOLUTION_STATUSES)
    assert set(payload["counts_by_source_unit_status"]) == set(UNIT_STATUSES)
    assert set(payload["counts_by_target_unit_status"]) == set(TARGET_UNIT_STATUSES)
    assert set(payload["counts_by_unresolved_reason"]) == set(UNRESOLVED_REASONS)


def test_relationship_quality_artifact_samples_are_bounded_deterministic_and_no_answer_fields() -> None:
    artifact = _artifact(
        sample_reference_evidence=[
            {"legal_reference_id": "legal-reference:2", "primary_relation_type": "CITES"},
            {"legal_reference_id": "legal-reference:1", "primary_relation_type": "CITES"},
        ]
    )
    payload = relationship_quality_artifact(artifact)

    assert [item["legal_reference_id"] for item in payload["sample_reference_evidence"]] == [
        "legal-reference:1",
        "legal-reference:2",
    ]
    assert "answer_text" not in str(payload)
    with pytest.raises(ValueError):
        build_relationship_quality_artifact(
            selected_scope={"law_codes": ["TestG"]},
            classifier_policy_version="legal-ref-context-v1",
            generated_at="2026-01-01T00:00:00Z",
            counts_by_relation_type={},
            counts_by_resolution_status={},
            sample_edges_by_relation_type={},
            sample_reference_evidence=[{"legal_reference_id": "bad", "answer_text": "forbidden"}],
            top_unresolved_targets=[],
            source_to_relation_coverage={},
            fanout_summary={},
            temporal_metadata_completeness={},
        )


def test_temporal_metadata_completeness_minimum_shape() -> None:
    artifact = _artifact()
    temporal = artifact.as_dict()["temporal_metadata_completeness"]

    assert temporal["selected_scope"] == {"law_codes": ["TestG"]}
    assert set(temporal["counts_by_temporal_evidence_status"]) == set(TEMPORAL_EVIDENCE_STATUSES)
    assert set(temporal["counts_by_relation_type"]) == set(RELATION_TYPES)
    assert temporal["counts_by_relation_type"]["CITES"] == {
        "total": 1,
        "with_any_temporal_metadata": 1,
        "missing_required_temporal_fields": 5,
    }
    assert set(temporal["missing_field_summary"]) == {
        "effective_from",
        "effective_until",
        "publication_date",
        "source_version_id",
        "source_revision_marker",
        "temporal_context_text",
        "temporal_context_checksum",
    }


def test_relationship_quality_artifact_top_missing_targets_are_filtered_and_bounded() -> None:
    artifact = _artifact(
        counts_by_source_unit_status={"active": 2, "inactive": 1},
        counts_by_target_unit_status={"active": 1, "inactive": 1, "missing_target_in_corpus": 2},
        counts_by_unresolved_reason={"missing_target_in_corpus": 2, "ambiguous_target": 1},
        top_missing_targets=[
            {
                "target_law_code": "TestG",
                "target_section_reference": "§ 99",
                "reason": "missing_target_in_corpus",
                "count": 2,
                "source_samples": [
                    {
                        "legal_reference_id": "legal-reference:2",
                        "source_legal_section_id": "legal-section:TestG:3:current",
                        "source_fragment_id": "source-fragment:TestG:3",
                        "raw_reference_text": "§ 99 TestG",
                    }
                ],
            },
            {
                "target_law_code": "TestG",
                "target_section_reference": "§ 6",
                "reason": "ambiguous_target",
                "count": 1,
                "source_samples": [],
            },
        ],
    )
    payload = artifact.as_dict()

    assert payload["counts_by_source_unit_status"]["inactive"] == 1
    assert payload["counts_by_target_unit_status"]["missing_target_in_corpus"] == 2
    assert payload["counts_by_unresolved_reason"]["ambiguous_target"] == 1
    assert payload["top_missing_targets"] == [
        {
            "count": 2,
            "reason": "missing_target_in_corpus",
            "source_samples": [
                {
                    "legal_reference_id": "legal-reference:2",
                    "raw_reference_text": "§ 99 TestG",
                    "source_fragment_id": "source-fragment:TestG:3",
                    "source_legal_section_id": "legal-section:TestG:3:current",
                }
            ],
            "target_law_code": "TestG",
            "target_section_reference": "§ 99",
        }
    ]


def _artifact(**overrides):
    kwargs = {
        "selected_scope": {"law_codes": ["TestG"]},
        "classifier_policy_version": "legal-ref-context-v1",
        "generated_at": "2026-01-01T00:00:00Z",
        "counts_by_relation_type": {"CITES": 1},
        "counts_by_resolution_status": {"resolved": 1},
        "sample_edges_by_relation_type": {
            "CITES": [
                {
                    "source_legal_section_id": "legal-section:TestG:1:current",
                    "target_legal_section_id": "legal-section:TestG:2:current",
                    "legal_reference_id": "legal-reference:1",
                }
            ]
        },
        "sample_reference_evidence": [{"legal_reference_id": "legal-reference:1"}],
        "top_unresolved_targets": [],
        "source_to_relation_coverage": {"by_law_code": {"TestG": {"reference_count": 1}}},
        "fanout_summary": {"source_section_count": 1, "max_fanout": 1, "avg_fanout": 1.0},
        "temporal_metadata_completeness": {
            "selected_scope": {"law_codes": ["TestG"]},
            "counts_by_temporal_evidence_status": {"available": 1},
            "counts_by_relation_type": {
                "CITES": {
                    "total": 1,
                    "with_any_temporal_metadata": 1,
                    "missing_required_temporal_fields": 5,
                }
            },
            "missing_field_summary": {
                "effective_until": 1,
                "source_version_id": 1,
                "source_revision_marker": 1,
                "temporal_context_text": 1,
                "temporal_context_checksum": 1,
            },
            "total_reference_evidence_count": 1,
        },
    }
    kwargs.update(overrides)
    return build_relationship_quality_artifact(**kwargs)
