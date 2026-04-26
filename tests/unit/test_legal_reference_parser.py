from __future__ import annotations

from ingestion.legal_reference_parser import parse_explicit_legal_references


def test_parse_german_section_reference_with_default_law_code() -> None:
    references = parse_explicit_legal_references("Siehe § 2 Abs. 1 AufenthG.", default_law_code="SGBII")

    assert len(references) == 1
    assert references[0].target_law_code == "AufenthG"
    assert references[0].target_section_reference == "§ 2"
    assert references[0].normalized_reference_text == "§ 2 Abs. 1"


def test_parse_reference_without_law_uses_default_law_code() -> None:
    references = parse_explicit_legal_references("Nach § 2 gilt dies.", default_law_code="AufenthG")

    assert references[0].target_law_code == "AufenthG"
    assert references[0].relation_type == "CITES"
