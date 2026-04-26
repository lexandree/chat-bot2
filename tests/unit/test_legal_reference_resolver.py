from __future__ import annotations

from retrieval.legal_reference_resolver import ReferenceQuery, resolve_from_section_records


def test_exact_reference_normalization_and_current_default_resolution() -> None:
    result = resolve_from_section_records(
        ReferenceQuery(law_code="AufenthG", section_reference="1"),
        [
            {
                "legal_section_id": "old",
                "law_code": "AufenthG",
                "normalized_reference": "§ 1",
                "is_current": False,
            },
            {
                "legal_section_id": "legal-section:AufenthG:1:current",
                "law_code": "AufenthG",
                "normalized_reference": "§ 1",
                "is_current": True,
                "source_references": ["source-fragment:AufenthG:1"],
            },
        ],
    )

    assert result.matched_legal_section_id == "legal-section:AufenthG:1:current"
    assert result.source_references == ["source-fragment:AufenthG:1"]


def test_exact_reference_unresolved_result_contains_auditable_evidence() -> None:
    result = resolve_from_section_records(ReferenceQuery(law_code="AufenthG", section_reference="§ 99"), [])

    assert result.matched_legal_section_id == ""
    assert result.unresolved_target_evidence[0]["reason"] == "not_found"
    assert "answer_text" not in result.as_dict()
