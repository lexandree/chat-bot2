from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from tests.integration.live_support import LIVE_TEST_LAW_CODE, build_live_test_preview, cleanup_live_test_scope


pytestmark = pytest.mark.neo4j


def test_live_neo4j_load_verify_delete_by_law_code_scope() -> None:
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
        GraphFoundationRepository(client, database_name=settings.neo4j_database).prepare_foundation(
            embedding_dimensions=settings.embedding_vector_dimensions,
        )
        repo = GraphDataRepository(client)
        cleanup_live_test_scope(client)
        preview = build_live_test_preview()
        first = repo.load_preview(preview, law_codes=[LIVE_TEST_LAW_CODE])
        second = repo.load_preview(preview, law_codes=[LIVE_TEST_LAW_CODE])
        verified = repo.verify_scope(law_codes=[LIVE_TEST_LAW_CODE])
        deleted = repo.delete_scope(law_codes=[LIVE_TEST_LAW_CODE], confirm=True)
    finally:
        cleanup_live_test_scope(client)
        client.close()

    assert first.legal_section_count == second.legal_section_count
    assert verified.legal_section_count >= 2
    assert deleted.removed_records >= 1
