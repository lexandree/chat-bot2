from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from tests.integration.live_support import (
    LIVE_TEST_LAW_CODE,
    LIVE_TEST_SECTION_ID,
    build_live_test_preview,
    cleanup_live_test_scope,
)


pytestmark = pytest.mark.neo4j


def test_live_neo4j_exact_resolution_and_bounded_traversal_on_fixture_data() -> None:
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
        repo.load_preview(preview, law_codes=[LIVE_TEST_LAW_CODE])
        resolved = repo.resolve_reference(law_code=LIVE_TEST_LAW_CODE, section_reference="§ 1")
        traversed = repo.traverse(
            legal_section_id=resolved.matched_legal_section_id,
            allowed_relation_types=["CITES"],
            depth_limit=1,
            fanout_limit=25,
            node_limit=100,
        )
    finally:
        cleanup_live_test_scope(client)
        client.close()

    assert resolved.matched_legal_section_id == LIVE_TEST_SECTION_ID
    assert traversed.depth_limit == 1
    assert "answer_text" not in traversed.as_dict()
