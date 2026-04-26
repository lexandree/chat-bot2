from __future__ import annotations

import pytest

from graph.schema import (
    bootstrap_schema,
    build_schema_statements,
    candidate_review_placeholders_present,
    schema_object_names,
)


class RecordingClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict[str, object]]] = []

    def write(self, query: str, parameters: dict[str, object] | None = None) -> list[dict[str, object]]:
        self.writes.append((query, parameters or {}))
        return []


def test_schema_definitions_include_stable_names_and_candidate_placeholders() -> None:
    statements = build_schema_statements(embedding_dimensions=1024)
    names = schema_object_names(1024)

    assert "source_document_id_unique" in names
    assert "legal_reference_id_unique" in names
    assert "candidate_id_unique" in names
    assert "source_fragment_embedding_v1" in names
    assert candidate_review_placeholders_present(statements)
    assert len(names) == len(set(names))


def test_schema_vector_dimensions_are_embedded_in_vector_index_statements() -> None:
    vector_statements = [item for item in build_schema_statements(768) if item.category == "vector_index"]

    assert vector_statements
    assert all("`vector.dimensions`: 768" in statement.cypher for statement in vector_statements)


def test_schema_rejects_invalid_vector_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        build_schema_statements(0)


def test_bootstrap_schema_executes_all_statements_against_client() -> None:
    client = RecordingClient()

    names = bootstrap_schema(client, 3)

    assert len(client.writes) == len(names)
    assert client.writes[0][0].startswith("CREATE CONSTRAINT")
