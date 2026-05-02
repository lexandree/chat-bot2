from __future__ import annotations

import pytest

from evaluation.load_cases import build_corpus_readiness_artifact, corpus_readiness_artifact
from graph.types import STRUCTURE_CLASSES, STRUCTURE_CLASS_RULES_VERSION, UNIT_STATUSES


def test_corpus_readiness_artifact_shape_buckets_and_no_answer_fields() -> None:
    artifact = build_corpus_readiness_artifact(
        selected_scope={"law_codes": ["TestG"]},
        generated_at="2026-01-01T00:00:00Z",
        counts_by_unit_status={"active": 2, "inactive": 1},
        counts_by_structure_class={"simple_paragraph": 1, "inactive_skipped": 1},
        active_unit_samples=[{"legal_section_id": "legal-section:TestG:1:current"}],
        inactive_unit_samples=[{"legal_section_id": "legal-section:TestG:2:current"}],
        complexity_summary={"total_unit_count": 3},
    )
    payload = corpus_readiness_artifact(artifact)

    assert payload["artifact_id"].startswith("corpus-readiness:")
    assert payload["structure_class_rules_version"] == STRUCTURE_CLASS_RULES_VERSION
    assert set(payload["counts_by_unit_status"]) == set(UNIT_STATUSES)
    assert set(payload["counts_by_structure_class"]) == set(STRUCTURE_CLASSES)
    assert payload["excluded_semantic_candidates"] == {
        "Condition": 0,
        "Exception": 0,
        "LegalEffect": 0,
        "LegalNorm": 0,
    }
    assert "answer_text" not in str(payload)


def test_corpus_readiness_artifact_rejects_answer_fields() -> None:
    with pytest.raises(ValueError):
        build_corpus_readiness_artifact(
            selected_scope={"law_codes": ["TestG"]},
            generated_at="2026-01-01T00:00:00Z",
            counts_by_unit_status={},
            counts_by_structure_class={},
            active_unit_samples=[{"legal_section_id": "bad", "generated_answer": "forbidden"}],
            inactive_unit_samples=[],
            complexity_summary={},
        )
