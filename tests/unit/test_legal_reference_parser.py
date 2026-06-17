from __future__ import annotations

import json
from pathlib import Path

from graph.types import CLASSIFIER_POLICY_VERSION
from ingestion.legal_reference_parser import parse_explicit_legal_references


def test_parse_german_section_reference_with_default_law_code() -> None:
    references = parse_explicit_legal_references("Siehe § 2 Abs. 1 AufenthG.", default_law_code="SGBII")

    assert len(references) == 1
    assert references[0].target_law_code == "AufenthG"
    assert references[0].target_section_reference == "§ 2"
    assert references[0].normalized_reference_text == "§ 2 Abs. 1"


def test_parse_full_absatz_and_nummer_words_without_treating_absatz_as_law() -> None:
    references = parse_explicit_legal_references(
        "Die Rechtsfolge bestimmt sich nach § 26 Absatz 1 Satz 2 Nummer 3 AsylG.",
        default_law_code="AufenthG",
    )

    assert len(references) == 1
    assert references[0].raw_reference_text == "§ 26 Absatz 1 Satz 2 Nummer 3 AsylG"
    assert references[0].target_law_code == "AsylG"
    assert references[0].target_section_reference == "§ 26"
    assert references[0].normalized_reference_text == "§ 26 Abs. 1 Satz 2 Nr. 3"
    assert references[0].subsection_anchor == {
        "section_reference": "§ 26",
        "subsection": "1",
        "sentence": "2",
        "number": "3",
    }


def test_parse_reference_without_law_uses_default_law_code() -> None:
    references = parse_explicit_legal_references("Nach § 2 gilt dies.", default_law_code="AufenthG")

    assert references[0].target_law_code == "AufenthG"
    assert references[0].target_law_code_explicit is False
    assert references[0].primary_relation_type == "CITES"
    assert references[0].relation_type == "CITES"


def test_parse_reference_preserves_explicit_law_code_flag_and_build_date() -> None:
    reference = parse_explicit_legal_references(
        "Nach § 2 TestG gilt dies.",
        default_law_code="OtherG",
        build_date="2026-04-30",
    )[0]

    assert reference.target_law_code == "TestG"
    assert reference.target_law_code_explicit is True
    assert reference.build_date == "2026-04-30"


def test_parse_reference_does_not_treat_following_title_word_as_law_code() -> None:
    references = parse_explicit_legal_references(
        "Die Voraussetzungen nach § 3d Schutz vor Verfolgung bleiben unberührt.",
        default_law_code="AsylG",
    )

    assert references[0].raw_reference_text == "§ 3d"
    assert references[0].target_law_code == "AsylG"
    assert references[0].target_section_reference == "§ 3d"


def test_parse_full_law_name_alias_as_explicit_vwvfg_reference() -> None:
    reference = parse_explicit_legal_references(
        "Der Ausländer kann sich nach § 14 des Verwaltungsverfahrensgesetzes begleiten lassen.",
        default_law_code="AsylG",
    )[0]

    assert reference.raw_reference_text == "§ 14"
    assert reference.target_law_code == "VwVfG"
    assert reference.target_law_code_explicit is True


def test_parse_full_law_name_alias_after_reference_range_context() -> None:
    references = parse_explicit_legal_references(
        "Die §§ 48 und 49 des Verwaltungsverfahrensgesetzes bleiben unberührt.",
        default_law_code="IntV",
    )

    assert references[0].target_law_code == "VwVfG"
    assert references[0].target_law_code_explicit is True


def test_full_law_name_alias_does_not_cross_sentence_boundary() -> None:
    references = parse_explicit_legal_references(
        "Nach § 2 gilt dies. § 14 des Verwaltungsverfahrensgesetzes bleibt unberührt.",
        default_law_code="AsylG",
    )

    assert references[0].target_law_code == "AsylG"
    assert references[0].target_law_code_explicit is False
    assert references[1].target_law_code == "VwVfG"
    assert references[1].target_law_code_explicit is True


def test_full_law_name_alias_does_not_cross_later_section_marker() -> None:
    references = parse_explicit_legal_references(
        "Nach § 2 gilt dies, während § 14 des Verwaltungsverfahrensgesetzes unberührt bleibt.",
        default_law_code="AsylG",
    )

    assert references[0].target_law_code == "AsylG"
    assert references[1].target_law_code == "VwVfG"


def test_parse_common_external_law_aliases_after_reference_context() -> None:
    examples = [
        (
            "die in den §§ 376, 383 bis 385 und 408 der Zivilprozessordnung bezeichneten Gründe",
            "ZPO",
            "§ 376",
        ),
        (
            "Opfer einer Straftat nach den §§ 232 bis 233a des Strafgesetzbuches",
            "StGB",
            "§ 232",
        ),
        (
            "Betriebsübergang nach § 613a des Bürgerlichen Gesetzbuchs",
            "BGB",
            "§ 613a",
        ),
        (
            "Verstoß gegen § 404 Absatz 1 des Dritten Buches Sozialgesetzbuch",
            "SGB_3",
            "§ 404",
        ),
    ]

    for text, expected_law_code, expected_section in examples:
        reference = parse_explicit_legal_references(text, default_law_code="VwVfG")[0]
        assert reference.target_law_code == expected_law_code
        assert reference.target_section_reference == expected_section
        assert reference.target_law_code_explicit is True


def test_fixture_driven_mandatory_relation_classification() -> None:
    fixture = json.loads(Path("tests/fixtures/legal_relationship_cases.json").read_text(encoding="utf-8"))

    for case in fixture["cases"]:
        references = parse_explicit_legal_references(
            case["body_text"],
            default_law_code=case["default_law_code"],
            source_legal_section_id=case["source_legal_section_id"],
            source_legal_fragment_id=case["source_legal_fragment_id"],
            source_fragment_id=case["source_fragment_id"],
            law_code=case["law_code"],
            section_reference=case["section_reference"],
            title=case["title"],
        )

        assert len(references) == 1, case["case_id"]
        assert references[0].primary_relation_type == case["expected_primary_relation_type"], case["case_id"]
        assert references[0].classifier_policy_version == CLASSIFIER_POLICY_VERSION


def test_context_checksum_source_ids_subsection_anchor_and_policy_are_deterministic() -> None:
    text = "Vorheriger Satz. Die Erteilung setzt voraus, dass § 2 Abs. 1 Satz 2 Nr. 3 TestG gilt. Danach folgt Text."

    first = parse_explicit_legal_references(
        text,
        default_law_code="TestG",
        source_legal_section_id="legal-section:TestG:1:current",
        source_legal_fragment_id="legal-fragment:TestG:1:1",
        source_fragment_id="source-fragment:TestG:1",
        law_code="TestG",
        section_reference="§ 1",
    )[0]
    second = parse_explicit_legal_references(
        text,
        default_law_code="TestG",
        source_legal_section_id="legal-section:TestG:1:current",
        source_legal_fragment_id="legal-fragment:TestG:1:1",
        source_fragment_id="source-fragment:TestG:1",
        law_code="TestG",
        section_reference="§ 1",
    )[0]

    assert first.parsed_reference_id == second.parsed_reference_id
    assert first.context_checksum == second.context_checksum
    assert first.context_before == "Vorheriger Satz."
    assert first.context_text.startswith("Die Erteilung setzt voraus")
    assert first.context_after == "Danach folgt Text."
    assert first.source_legal_section_id == "legal-section:TestG:1:current"
    assert first.source_legal_fragment_id == "legal-fragment:TestG:1:1"
    assert first.source_fragment_id == "source-fragment:TestG:1"
    assert first.subsection_anchor == {
        "section_reference": "§ 2",
        "subsection": "1",
        "sentence": "2",
        "number": "3",
    }
    assert first.classifier_policy_version == CLASSIFIER_POLICY_VERSION


def test_optional_temporal_metadata_is_preserved_and_statuses_are_explicit() -> None:
    available = parse_explicit_legal_references(
        "Nach § 2 TestG gilt dies.",
        default_law_code="TestG",
        effective_from="2026-01-01",
        publication_date="2025-12-01",
    )[0]
    partial = parse_explicit_legal_references(
        "Ab 2026 gilt § 2 TestG.",
        default_law_code="TestG",
    )[0]
    not_available = parse_explicit_legal_references(
        "Nach § 2 TestG gilt dies.",
        default_law_code="TestG",
        temporal_metadata_expected=True,
    )[0]
    not_applicable = parse_explicit_legal_references(
        "Nach § 2 TestG gilt dies.",
        default_law_code="TestG",
    )[0]

    assert available.effective_from == "2026-01-01"
    assert available.publication_date == "2025-12-01"
    assert available.temporal_evidence_status == "available"
    assert partial.temporal_evidence_status == "partial"
    assert partial.temporal_context_checksum
    assert not_available.temporal_evidence_status == "not_available"
    assert not_applicable.temporal_evidence_status == "not_applicable"
