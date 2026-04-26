from __future__ import annotations

from graph.repositories import GraphFoundationRepository


class FakeGraphClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.connectivity_checked = False
        self.writes: list[tuple[str, dict[str, object]]] = []

    def verify_connectivity(self) -> None:
        self.connectivity_checked = True
        if self.fail:
            raise RuntimeError("unreachable")

    def write(self, query: str, parameters: dict[str, object] | None = None) -> list[dict[str, object]]:
        self.writes.append((query, parameters or {}))
        return []


def test_graph_readiness_report_success_contains_stable_schema_names() -> None:
    client = FakeGraphClient()

    report = GraphFoundationRepository(client, database_name="neo4j").prepare_foundation(embedding_dimensions=32)

    assert report.status == "ready"
    assert report.connectivity_checked is True
    assert report.candidate_review_placeholders_present is True
    assert "source_document_id_unique" in report.schema_objects
    assert len(client.writes) == len(report.schema_objects)


def test_graph_readiness_report_failure_has_no_schema_writes() -> None:
    client = FakeGraphClient(fail=True)

    report = GraphFoundationRepository(client).prepare_foundation()

    assert report.status == "failed"
    assert report.errors == ["unreachable"]
    assert client.writes == []
