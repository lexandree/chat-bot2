"""Real Neo4j official-driver client for graph operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from neo4j import GraphDatabase


class Neo4jGraphClient:
    """Small production wrapper over the official Neo4j Python driver."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        *,
        database: str | None = None,
        driver_factory: Callable[..., Any] | None = None,
    ) -> None:
        if not uri:
            raise ValueError("Neo4j URI is required")
        if not username:
            raise ValueError("Neo4j username is required")
        self.database = database or None
        factory = driver_factory or GraphDatabase.driver
        self._driver = factory(uri, auth=(username, password))

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def close(self) -> None:
        self._driver.close()

    def read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute(query, parameters or {}, write=False)

    def write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute(query, parameters or {}, write=True)

    def vector_query(
        self,
        index_name: str,
        vector: list[float],
        *,
        k: int = 10,
        extra_parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        parameters = {"index_name": index_name, "k": k, "embedding": vector}
        parameters.update(extra_parameters or {})
        return self.read(
            "CALL db.index.vector.queryNodes($index_name, $k, $embedding) "
            "YIELD node, score RETURN node, score",
            parameters,
        )

    def _execute(self, query: str, parameters: dict[str, Any], *, write: bool) -> list[dict[str, Any]]:
        if not isinstance(parameters, dict):
            raise TypeError("parameters must be a dictionary")
        with self._driver.session(database=self.database) as session:
            runner = session.execute_write if write else session.execute_read
            return runner(_run_query, query, parameters)


def _run_query(tx: Any, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    result = tx.run(query, parameters)
    return [dict(record) for record in result]
