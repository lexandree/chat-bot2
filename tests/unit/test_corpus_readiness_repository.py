from __future__ import annotations

from typing import Any

from graph.repositories import GraphDataRepository
from graph.types import STRUCTURE_CLASS_RULES_VERSION


class FakeCorpusReadinessClient:
    def read(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        assert "MATCH (s:LegalSection)" in query
        return [
            _row("1", "Einfach", "Kurzer Absatz."),
            _row("2", "(weggefallen)", "(weggefallen)", unit_status="inactive"),
            _row("3", "Begriffsbestimmung", "Aufenthalt im Sinne dieses Gesetzes bedeutet Anwesenheit."),
            _row("4", "Liste", "1. erstes Element; 2. zweites Element; 3. drittes Element."),
            _row("5", "Gemischt", "Im Sinne dieses Gesetzes gilt: 1. eins; 2. zwei; 3. drei."),
            _row("6", "Lang", "x" * 1201),
        ]


def test_corpus_readiness_repository_classifies_structural_complexity() -> None:
    artifact = GraphDataRepository(FakeCorpusReadinessClient()).corpus_readiness_artifact(
        law_codes=["TestG"]
    )
    payload = artifact.as_dict()

    assert payload["structure_class_rules_version"] == STRUCTURE_CLASS_RULES_VERSION
    assert payload["counts_by_unit_status"] == {"active": 5, "inactive": 1}
    assert payload["counts_by_structure_class"] == {
        "definition_heavy": 1,
        "inactive_skipped": 1,
        "list_heavy": 1,
        "mixed_content": 1,
        "simple_paragraph": 1,
        "unknown": 1,
    }
    assert payload["complexity_summary"]["total_unit_count"] == 6
    assert payload["complexity_summary"]["signal_counts"]["list_signal"] == 2
    assert payload["active_unit_samples"][0]["structure_class"] == "simple_paragraph"
    assert payload["inactive_unit_samples"][0]["structure_class"] == "inactive_skipped"
    assert "answer_text" not in str(payload)


def _row(section: str, title: str, body_text: str, *, unit_status: str = "active") -> dict[str, Any]:
    return {
        "legal_section_id": f"legal-section:TestG:{section}:current",
        "law_code": "TestG",
        "section_reference": f"§ {section}",
        "title": title,
        "unit_status": unit_status,
        "status_marker_text": "(weggefallen)" if unit_status == "inactive" else "",
        "source_document_id": "source-document:TestG",
        "source_fragment_id": f"source-fragment:TestG:{section}",
        "source_version_id": "v1",
        "source_revision_marker": "build-2026-04-30",
        "build_date": "2026-04-30",
        "content_checksum": f"sha256:{section}",
        "legal_fragment_texts": [body_text],
        "source_fragment_texts": [body_text],
        "defines_evidence_count": 0,
    }
