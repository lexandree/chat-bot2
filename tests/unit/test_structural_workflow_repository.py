from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.repositories import GraphDataRepository


FIXTURE_PATH = Path("tests/fixtures/structural_workflow_cases.json")


def test_repository_collects_seed_sections_resolved_edges_and_boundaries() -> None:
    client = FakeStructuralWorkflowClient()
    artifact = GraphDataRepository(client).structural_workflow_artifact(
        workflow_mode="seed_neighborhood",
        seed_legal_section_ids=["legal-section:TestG:1:current"],
        law_codes=["TestG"],
        allowed_relation_types=["CITES"],
        direction="outgoing",
        max_depth=1,
        fanout_limit=25,
        node_limit=100,
        edge_limit=500,
        source_sample_limit=5,
    )
    payload = artifact.as_dict()

    assert [section["role"] for section in payload["sections"]] == ["seed", "resolved_neighbor"]
    assert payload["resolved_edges"][0]["source_legal_section_id"] == "legal-section:TestG:1:current"
    assert payload["resolved_edges"][0]["target_legal_section_id"] == "legal-section:TestG:2:current"
    assert payload["coverage_boundary_stops"][0]["count"] == 2
    assert client.edge_query_parameters["direction"] == "outgoing"
    assert client.edge_query_parameters["allowed_relation_types"] == ["CITES"]


def test_repository_collects_law_scope_sections_and_bounded_edges() -> None:
    client = FakeStructuralWorkflowClient()
    artifact = GraphDataRepository(client).structural_workflow_artifact(
        workflow_mode="law_scope_overview",
        law_codes=["TestG", "OtherG"],
        allowed_relation_types=["CITES"],
        direction="outgoing",
        max_depth=1,
        fanout_limit=25,
        node_limit=10,
        edge_limit=1,
        source_sample_limit=5,
    )
    payload = artifact.as_dict()

    assert payload["workflow_request"]["workflow_mode"] == "law_scope_overview"
    assert payload["quality_summary"]["visited_section_count"] >= 2
    assert payload["quality_summary"]["resolved_edge_count"] == 1
    assert {section["role"] for section in payload["sections"]} == {"scope_member"}
    assert client.edge_query_parameters["limit"] == 2


def test_repository_passes_bounded_traversal_query_parameters() -> None:
    client = FakeStructuralWorkflowClient()
    GraphDataRepository(client).structural_workflow_artifact(
        workflow_mode="seed_neighborhood",
        seed_legal_section_ids=["legal-section:TestG:1:current"],
        law_codes=["TestG"],
        allowed_relation_types=["CITES"],
        direction="both",
        max_depth=2,
        fanout_limit=2,
        node_limit=5,
        edge_limit=3,
        source_sample_limit=5,
    )

    assert client.edge_query_parameters["direction"] == "both"
    assert client.edge_query_parameters["limit"] == 10


class FakeStructuralWorkflowClient:
    def __init__(self) -> None:
        cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        seed = cases["seed_neighborhood"]
        law_scope = cases["law_scope_overview"]
        self.sections = {
            item["legal_section_id"]: item
            for item in [*seed["sections"], *law_scope["sections"]]
        }
        self.edge_rows = []
        for edge in seed["resolved_edges"]:
            self.edge_rows.append(
                {
                    "source_legal_section_id": edge["source_legal_section_id"],
                    "target_legal_section_id": edge["target_legal_section_id"],
                    "relation_type": edge["relation_type"],
                    "legal_reference_id": edge["legal_reference_ids"][0],
                    "source_fragment_id": edge["source_fragment_ids"][0],
                    "target_law_code": edge["target_law_code"],
                    "target_section_reference": edge["target_section_reference"],
                    "target_unit_status": edge["target_unit_status"],
                    "classifier_policy_version": edge["classifier_policy_version"],
                    "effective_from": "",
                    "effective_until": "",
                    "publication_date": "",
                    "source_version_id": "",
                    "source_revision_marker": "",
                    "build_date": "",
                    "temporal_evidence_status": edge["temporal_evidence_status"],
                }
            )
        self.unresolved = [dict(item, law_code="TestG") for item in seed["unresolved_references"]]
        self.edge_query_parameters: dict[str, Any] = {}

    def read(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        if "MATCH (s:LegalSection)-[r]->(t:LegalSection)" in query:
            self.edge_query_parameters = dict(parameters)
            rows = [
                row
                for row in self.edge_rows
                if row["relation_type"] in parameters["allowed_relation_types"]
                and self._edge_in_scope(row, parameters["law_codes"], parameters["direction"])
            ]
            return sorted(rows, key=lambda item: item["legal_reference_id"])[: parameters["limit"]]
        if "WHERE s.legal_section_id IN $legal_section_ids" in query:
            ids = set(parameters["legal_section_ids"])
            return [self.sections[item] for item in sorted(ids) if item in self.sections]
        if "WHERE s.law_code IN $law_codes" in query:
            law_codes = set(parameters["law_codes"])
            return [
                section
                for section in sorted(self.sections.values(), key=lambda item: item["legal_section_id"])
                if section["law_code"] in law_codes
            ][: parameters["limit"]]
        if "n.source_legal_section_id IN $legal_section_ids" in query:
            ids = set(parameters["legal_section_ids"])
            return [item for item in self.unresolved if item["source_legal_section_id"] in ids]
        if "n.law_code IN $law_codes" in query:
            law_codes = set(parameters["law_codes"])
            return [item for item in self.unresolved if item["law_code"] in law_codes]
        return []

    def write(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def _edge_in_scope(self, row: dict[str, Any], law_codes: list[str], direction: str) -> bool:
        if not law_codes:
            return True
        source = self.sections[row["source_legal_section_id"]]
        target = self.sections[row["target_legal_section_id"]]
        if direction == "outgoing":
            return source["law_code"] in law_codes
        if direction == "incoming":
            return target["law_code"] in law_codes
        return source["law_code"] in law_codes or target["law_code"] in law_codes
