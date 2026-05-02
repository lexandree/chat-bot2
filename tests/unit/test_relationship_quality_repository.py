from __future__ import annotations

from typing import Any

from graph.repositories import GraphDataRepository


class FakeQualityClient:
    def read(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        if "collect(DISTINCT n.classifier_policy_version)" in query:
            return [{"versions": ["legal-ref-context-v1"]}]
        if "MATCH (s:LegalSection)" in query and "coalesce(s.unit_status, 'active')" in query:
            return [{"unit_status": "active", "count": 1}, {"unit_status": "inactive", "count": 1}]
        if "AS target_unit_status, count(*) AS count" in query:
            return [{"target_unit_status": "active", "count": 1}]
        if "AND coalesce(n.unresolved_reason" in query:
            return [{"unresolved_reason": "missing_target_in_corpus", "count": 1}]
        if "n.law_code AS law_code" in query and "coalesce(n.primary_relation_type" in query:
            return [{"law_code": "TestG", "relation_type": "CITES", "count": 1}]
        if "coalesce(n.primary_relation_type" in query and "count(n) AS count" in query:
            return [{"relation_type": "CITES", "count": 1}]
        if "resolution_status" in query and "count(n) AS count" in query:
            return [{"resolution_status": "resolved", "count": 1}]
        if "type(r) = $relation_type" in query:
            if parameters["relation_type"] != "CITES":
                return []
            return [
                {
                    "source_legal_section_id": "legal-section:TestG:1:current",
                    "target_legal_section_id": "legal-section:TestG:2:current",
                    "legal_reference_id": "legal-reference:1",
                    "classifier_policy_version": "legal-ref-context-v1",
                    "temporal_evidence_status": "available",
                }
            ]
        if "ORDER BY n.legal_reference_id LIMIT $limit" in query:
            return [
                {
                    "legal_reference_id": "legal-reference:1",
                    "source_legal_section_id": "legal-section:TestG:1:current",
                    "source_legal_fragment_id": "legal-fragment:TestG:1:1",
                    "source_fragment_id": "source-fragment:TestG:1",
                    "law_code": "TestG",
                    "target_law_code": "TestG",
                    "target_section_reference": "§ 2",
                    "target_legal_section_id": "legal-section:TestG:2:current",
                    "target_unit_status": "active",
                    "unresolved_reason": "",
                    "primary_relation_type": "CITES",
                    "relation_type": "CITES",
                    "resolution_status": "resolved",
                    "classifier_policy_version": "legal-ref-context-v1",
                    "raw_reference_text": "§ 2 TestG",
                    "normalized_reference_text": "§ 2",
                    "context_checksum": "abc",
                    "source_version_id": "v1",
                    "source_revision_marker": "build-2026-04-30",
                    "build_date": "2026-04-30",
                    "temporal_evidence_status": "available",
                    "subsection_anchor_json": '{"section_reference":"§ 2"}',
                    "secondary_relation_signals_json": "[]",
                    "unresolved_target_evidence_json": "{}",
                }
            ]
        if "n.resolution_status <> 'resolved'" in query:
            return []
        if "n.unresolved_reason = 'missing_target_in_corpus'" in query:
            return [
                {
                    "target_law_code": "TestG",
                    "target_section_reference": "§ 99",
                    "reason": "missing_target_in_corpus",
                    "count": 1,
                    "source_samples": [
                        {
                            "legal_reference_id": "legal-reference:missing",
                            "source_legal_section_id": "legal-section:TestG:3:current",
                            "source_fragment_id": "source-fragment:TestG:3",
                            "raw_reference_text": "§ 99 TestG",
                        }
                    ],
                }
            ]
        if "MATCH (sf:SourceFragment)" in query:
            return [{"law_code": "TestG", "source_fragment_count": 2}]
        if "WITH s.legal_section_id AS legal_section_id" in query:
            return [
                {
                    "source_section_count": 1,
                    "max_fanout": 1,
                    "avg_fanout": 1.0,
                    "top_fanout_sections": [{"legal_section_id": "legal-section:TestG:1:current", "fanout": 1}],
                }
            ]
        if "temporal_evidence_status" in query:
            return [
                {
                    "relation_type": "CITES",
                    "temporal_evidence_status": "available",
                    "effective_from": "2026-01-01",
                    "effective_until": "",
                    "publication_date": "2025-12-01",
                    "source_version_id": "",
                    "source_revision_marker": "",
                    "temporal_context_text": "",
                    "temporal_context_checksum": "",
                }
            ]
        return []

    def write(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        return []


def test_relationship_quality_repository_collection_uses_graph_state() -> None:
    artifact = GraphDataRepository(FakeQualityClient()).relationship_quality_artifact(law_codes=["TestG"])
    payload = artifact.as_dict()

    assert payload["classifier_policy_version"] == "legal-ref-context-v1"
    assert payload["counts_by_relation_type"]["CITES"] == 1
    assert payload["counts_by_resolution_status"]["resolved"] == 1
    assert payload["counts_by_source_unit_status"]["inactive"] == 1
    assert payload["counts_by_target_unit_status"]["active"] == 1
    assert payload["counts_by_unresolved_reason"]["missing_target_in_corpus"] == 1
    assert payload["sample_edges_by_relation_type"]["CITES"][0]["legal_reference_id"] == "legal-reference:1"
    assert payload["sample_reference_evidence"][0]["subsection_anchor"] == {"section_reference": "§ 2"}
    assert payload["top_missing_targets"][0]["reason"] == "missing_target_in_corpus"
    assert payload["source_to_relation_coverage"]["by_law_code"]["TestG"]["reference_count"] == 1
    assert payload["fanout_summary"]["max_fanout"] == 1
    assert payload["temporal_metadata_completeness"]["counts_by_temporal_evidence_status"]["available"] == 1
