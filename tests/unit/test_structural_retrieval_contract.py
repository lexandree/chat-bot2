from __future__ import annotations

from graph.types import StructuralRetrievalResult


def test_structural_retrieval_result_has_no_answer_fields() -> None:
    result = StructuralRetrievalResult(
        query_reference={"law_code": "AufenthG", "section_reference": "§ 1"},
        matched_legal_section_id="legal-section:AufenthG:1:current",
        source_references=["source-fragment:AufenthG:1"],
        relation_types=["CITES"],
        depth_limit=1,
        fanout_limit=25,
        node_limit=100,
        visited_count=2,
    )
    payload = result.as_dict()

    assert "answer_text" not in payload
    assert "answer" not in payload
    assert "generated_answer" not in payload
