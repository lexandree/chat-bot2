from __future__ import annotations

from typing import Any

from graph.writer import GraphWriter


class FakeClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, Any]]] = []

    def write(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        self.writes.append((query, parameters))
        return []


def test_writer_serializes_nested_source_metadata_for_neo4j_properties() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_source_document(
        {
            "source_document_id": "source-document:AufenthG",
            "law_code": "AufenthG",
            "freshness_metadata": {"retrieved_by": "fixture"},
        }
    )

    record = client.writes[0][1]["record"]
    assert "freshness_metadata" not in record
    assert record["freshness_metadata_json"] == '{"retrieved_by":"fixture"}'


def test_writer_serializes_unresolved_reference_evidence_for_neo4j_properties() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_legal_reference(
        {
            "legal_reference_id": "legal-reference:AufenthG:1:missing",
            "source_legal_section_id": "legal-section:AufenthG:1:current",
            "target_law_code": "AufenthG",
            "target_section_reference": "99",
            "resolution_status": "unresolved",
            "unresolved_target_evidence": {"reason": "not_found"},
        }
    )

    record = client.writes[0][1]["record"]
    assert "unresolved_target_evidence" not in record
    assert record["unresolved_target_evidence_json"] == '{"reason":"not_found"}'
