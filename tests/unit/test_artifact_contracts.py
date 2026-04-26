from __future__ import annotations

import pytest

from evaluation.load_cases import ensure_no_answer_fields, structural_retrieval_artifact
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
