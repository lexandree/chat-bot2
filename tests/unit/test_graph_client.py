from __future__ import annotations

from typing import Any

from graph.client import Neo4jGraphClient


class FakeRecord(dict):
    pass


class FakeResult(list):
    pass


class FakeTx:
    def __init__(self, driver: "FakeDriver") -> None:
        self.driver = driver

    def run(self, query: str, parameters: dict[str, Any]) -> FakeResult:
        self.driver.runs.append((query, parameters))
        return FakeResult([FakeRecord({"ok": True, "query": query})])


class FakeSession:
    def __init__(self, driver: "FakeDriver", database: str | None) -> None:
        self.driver = driver
        self.database = database

    def __enter__(self) -> "FakeSession":
        self.driver.sessions.append(self.database)
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute_read(self, callback, query: str, parameters: dict[str, Any]):
        return callback(FakeTx(self.driver), query, parameters)

    def execute_write(self, callback, query: str, parameters: dict[str, Any]):
        return callback(FakeTx(self.driver), query, parameters)


class FakeDriver:
    def __init__(self) -> None:
        self.connected = False
        self.closed = False
        self.sessions: list[str | None] = []
        self.runs: list[tuple[str, dict[str, Any]]] = []

    def verify_connectivity(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def session(self, *, database: str | None = None) -> FakeSession:
        return FakeSession(self, database)


def test_graph_client_uses_parameterized_read_write_and_database() -> None:
    fake_driver = FakeDriver()
    client = Neo4jGraphClient(
        "neo4j://example",
        "neo4j",
        "secret",
        database="legal",
        driver_factory=lambda *_args, **_kwargs: fake_driver,
    )

    client.verify_connectivity()
    read_result = client.read("RETURN $value AS value", {"value": 1})
    write_result = client.write("CREATE (:Test {id: $id})", {"id": "x"})
    client.close()

    assert fake_driver.connected is True
    assert fake_driver.closed is True
    assert fake_driver.sessions == ["legal", "legal"]
    assert fake_driver.runs[0] == ("RETURN $value AS value", {"value": 1})
    assert fake_driver.runs[1] == ("CREATE (:Test {id: $id})", {"id": "x"})
    assert read_result[0]["ok"] is True
    assert write_result[0]["ok"] is True


def test_graph_client_vector_query_uses_neo4j_vector_procedure() -> None:
    fake_driver = FakeDriver()
    client = Neo4jGraphClient(
        "neo4j://example",
        "neo4j",
        "secret",
        driver_factory=lambda *_args, **_kwargs: fake_driver,
    )

    client.vector_query("source_fragment_embedding_v1", [1.0, 0.0], k=2)

    query, parameters = fake_driver.runs[0]
    assert "db.index.vector.queryNodes" in query
    assert parameters["index_name"] == "source_fragment_embedding_v1"
    assert parameters["k"] == 2
