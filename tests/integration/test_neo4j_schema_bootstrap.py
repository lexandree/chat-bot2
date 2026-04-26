from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphFoundationRepository


pytestmark = pytest.mark.neo4j


def test_live_neo4j_connectivity_and_schema_bootstrap_idempotency() -> None:
    if os.environ.get("RUN_LIVE_NEO4J_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set RUN_LIVE_NEO4J_TESTS=true to run live Neo4j checks")
    settings = load_settings()
    settings.require_neo4j()
    client = Neo4jGraphClient(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    try:
        repo = GraphFoundationRepository(client, database_name=settings.neo4j_database)
        first = repo.prepare_foundation(embedding_dimensions=settings.embedding_vector_dimensions)
        second = repo.prepare_foundation(embedding_dimensions=settings.embedding_vector_dimensions)
    finally:
        client.close()

    assert first.status == "ready"
    assert second.status == "ready"
    assert first.schema_objects == second.schema_objects
