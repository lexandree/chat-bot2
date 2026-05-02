from __future__ import annotations

from typing import Any

from graph.repositories import GraphDataRepository
from graph.types import RELATION_TYPES
from graph.writer import GraphWriter
from ingestion.legal_preview_loader import build_preview_from_manifest_path


class FakeClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, Any]]] = []

    def write(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        self.writes.append((query, parameters))
        return []


class FakeRefreshClient(FakeClient):
    def read(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        if "MATCH (sf:SourceFragment)-[:MAPS_TO]->" in query:
            return [
                {
                    "source_fragment_id": "source-fragment:TestG:1",
                    "source_document_id": "source-document:TestG",
                    "law_code": "TestG",
                    "section_reference": "§ 1",
                    "title": "Section 1",
                    "body_text": "Siehe § 2 TestG.",
                    "checksum": "sha256:1",
                    "source_legal_section_id": "legal-section:TestG:1:current",
                    "source_legal_fragment_id": "legal-fragment:TestG:1:1",
                },
                {
                    "source_fragment_id": "source-fragment:TestG:3",
                    "source_document_id": "source-document:TestG",
                    "law_code": "TestG",
                    "section_reference": "§ 3",
                    "title": "Section 3",
                    "body_text": "Siehe § 99 TestG.",
                    "checksum": "sha256:3",
                    "source_legal_section_id": "legal-section:TestG:3:current",
                    "source_legal_fragment_id": "legal-fragment:TestG:3:1",
                },
            ]
        if "MATCH (s:LegalSection)" in query:
            return [
                _section_row("1"),
                _section_row("2"),
                _section_row("3"),
            ]
        if "MATCH (d:SourceDocument)" in query:
            return [
                {
                    "source_document_id": "source-document:TestG",
                    "source_family": "law",
                    "jurisdiction": "DE",
                    "language": "de",
                    "law_code": "TestG",
                    "source_uri": "fixture://testg",
                    "local_reference": "",
                    "publication_date": "2026-01-01",
                    "effective_date": "2026-01-01",
                    "retrieved_at": "",
                    "checksum": "sha256:document",
                }
            ]
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


def test_writer_persists_source_status_and_version_metadata_on_legal_section() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_legal_section(
        {
            "legal_section_id": "legal-section:TestG:2:current",
            "legal_act_id": "legal-act:TestG",
            "law_code": "TestG",
            "section_reference": "§ 2",
            "unit_status": "inactive",
            "status_marker_text": "(weggefallen)",
            "source_document_id": "source-document:TestG",
            "source_fragment_id": "source-fragment:TestG:2",
            "source_version_id": "v1",
            "source_revision_marker": "build-2026-04-30",
            "build_date": "2026-04-30",
            "content_checksum": "sha256:test",
        }
    )

    record = client.writes[0][1]["record"]
    assert record["unit_status"] == "inactive"
    assert record["status_marker_text"] == "(weggefallen)"
    assert record["source_version_id"] == "v1"
    assert record["source_revision_marker"] == "build-2026-04-30"


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


def test_writer_persists_target_status_and_unresolved_reason_evidence() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.upsert_legal_reference(
        _reference_record(
            target_unit_status="inactive",
            unresolved_reason="",
            source_version_id="v1",
            source_revision_marker="build-2026-04-30",
            build_date="2026-04-30",
        )
    )
    writer.upsert_legal_reference(
        _reference_record(
            legal_reference_id="legal-reference:missing",
            target_legal_section_id="",
            target_unit_status="missing_target_in_corpus",
            unresolved_reason="missing_target_in_corpus",
            resolution_status="unresolved",
            unresolved_target_evidence={"reason": "missing_target_in_corpus"},
        )
    )

    resolved_record = client.writes[0][1]["record"]
    edge_record = client.writes[1][1]["edge_record"]
    unresolved_record = client.writes[2][1]["record"]
    assert resolved_record["target_unit_status"] == "inactive"
    assert edge_record["target_unit_status"] == "inactive"
    assert edge_record["source_version_id"] == "v1"
    assert unresolved_record["target_unit_status"] == "missing_target_in_corpus"
    assert unresolved_record["unresolved_reason"] == "missing_target_in_corpus"


def test_writer_cleanup_removes_scoped_relationship_edges_and_reference_nodes() -> None:
    client = FakeClient()
    writer = GraphWriter(client)

    writer.cleanup_relationships_for_scope(law_codes=["AufenthG"])

    queries = [query for query, _ in client.writes]
    assert any("type(r) = 'CITES'" in query for query in queries)
    assert any("MATCH (n:LegalReference)" in query and "DETACH DELETE n" in query for query in queries)


def test_relationship_refresh_repeats_cleanup_and_upsert_semantics_deterministically() -> None:
    client = FakeRefreshClient()
    repo = GraphDataRepository(client)

    first = repo.refresh_relationships(law_codes=["TestG"])
    second = repo.refresh_relationships(law_codes=["TestG"])

    cleanup_node_deletes = [
        query
        for query, _ in client.writes
        if "MATCH (n:LegalReference)" in query and "DETACH DELETE n" in query
    ]
    cleanup_edge_deletes = [
        query
        for query, _ in client.writes
        if "MATCH (s:LegalSection)-[r]->(:LegalSection)" in query and "DELETE r" in query
    ]
    assert first.created_reference_count == second.created_reference_count == 2
    assert first.created_edge_count == second.created_edge_count == 1
    assert first.counts_by_unresolved_reason["missing_target_in_corpus"] == 1
    assert len(cleanup_node_deletes) == 2
    assert len(cleanup_edge_deletes) == len(RELATION_TYPES) * 2


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


def _section_row(section: str) -> dict[str, Any]:
    return {
        "legal_section_id": f"legal-section:TestG:{section}:current",
        "legal_act_id": "legal-act:TestG",
        "law_code": "TestG",
        "section_reference": f"§ {section}",
        "normalized_reference": f"§ {section}",
        "title": f"Section {section}",
        "valid_from": "",
        "valid_to": "",
        "version_identity": "current",
        "unit_status": "active",
    }
