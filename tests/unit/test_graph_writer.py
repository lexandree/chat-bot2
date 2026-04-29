from __future__ import annotations

from typing import Any

from graph.repositories import GraphDataRepository
from graph.writer import GraphWriter
from ingestion.legal_preview_loader import build_preview_from_manifest_path


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


def test_base_graph_load_writes_source_and_legal_structure_only() -> None:
    client = FakeClient()
    repo = GraphDataRepository(client)
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")

    report = repo.load_preview(preview, law_codes=["AufenthG"])

    queries = [query for query, _ in client.writes]
    assert report.legal_reference_count == 0
    assert not any("LegalReference" in query for query in queries)
    assert not any("CITES" in query or "DEFINES" in query or "RELATED" in query for query in queries)


def test_writer_materializes_edge_only_for_resolved_references() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_legal_reference(_reference_record(resolution_status="resolved"))
    writer.upsert_legal_reference(_reference_record(legal_reference_id="legal-reference:2", resolution_status="unresolved"))

    edge_writes = [query for query, _ in client.writes if "MERGE (s)-[r:CITES" in query]
    assert len(edge_writes) == 1


def test_writer_creates_one_primary_edge_and_preserves_secondary_signals() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_legal_reference(
        _reference_record(
            primary_relation_type="REQUIRES",
            secondary_relation_signals=["APPLIES_IF", "CITES"],
        )
    )

    edge_writes = [query for query, _ in client.writes if "MERGE (s)-[r:" in query]
    record = client.writes[0][1]["record"]
    assert len(edge_writes) == 1
    assert "MERGE (s)-[r:REQUIRES" in edge_writes[0]
    assert record["secondary_relation_signals_json"] == '["APPLIES_IF","CITES"]'


def test_writer_persists_temporal_evidence_on_reference_and_edge() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_legal_reference(
        _reference_record(
            effective_from="2026-01-01",
            publication_date="2025-12-01",
            temporal_evidence_status="available",
        )
    )

    reference_record = client.writes[0][1]["record"]
    edge_record = client.writes[1][1]["edge_record"]
    assert reference_record["effective_from"] == "2026-01-01"
    assert reference_record["publication_date"] == "2025-12-01"
    assert edge_record["effective_from"] == "2026-01-01"
    assert edge_record["publication_date"] == "2025-12-01"
    assert edge_record["temporal_evidence_status"] == "available"


def test_writer_cleanup_removes_scoped_relationship_edges_and_reference_nodes() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.cleanup_relationships_for_scope(law_codes=["AufenthG"])

    queries = [query for query, _ in client.writes]
    assert any("type(r) = 'CITES'" in query for query in queries)
    assert any("MATCH (n:LegalReference)" in query and "DETACH DELETE n" in query for query in queries)


def _reference_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "legal_reference_id": "legal-reference:1",
        "source_legal_section_id": "legal-section:AufenthG:1:current",
        "source_legal_fragment_id": "legal-fragment:AufenthG:1:1",
        "source_fragment_id": "source-fragment:AufenthG:1",
        "law_code": "AufenthG",
        "target_law_code": "AufenthG",
        "target_section_reference": "§ 2",
        "target_legal_section_id": "legal-section:AufenthG:2:current",
        "primary_relation_type": "CITES",
        "relation_type": "CITES",
        "resolution_status": "resolved",
        "classifier_policy_version": "legal-ref-context-v1",
        "secondary_relation_signals": [],
        "unresolved_target_evidence": {},
    }
    record.update(overrides)
    return record
