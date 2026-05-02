from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from tests.integration.live_support import (
    LIVE_RELATIONSHIP_LAW_CODE,
    build_live_relationship_test_preview,
    cleanup_live_test_scope,
)


pytestmark = pytest.mark.neo4j


def test_live_neo4j_source_status_persistence_and_verify_counts() -> None:
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
        preview = build_live_relationship_test_preview()
        repo.load_preview(preview, law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
        verified = repo.verify_scope(law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
        rows = client.read(
            "MATCH (s:LegalSection) "
            "WHERE s.law_code = $law_code "
            "RETURN s.section_reference AS section_reference, "
            "s.unit_status AS unit_status, "
            "s.status_marker_text AS status_marker_text "
            "ORDER BY section_reference",
            {"law_code": LIVE_RELATIONSHIP_LAW_CODE},
        )
    finally:
        cleanup_live_test_scope(client)
        client.close()

    by_section = {row["section_reference"]: row for row in rows}
    assert by_section["§ 2"]["unit_status"] == "inactive"
    assert by_section["§ 2"]["status_marker_text"] == "(weggefallen)"
    assert verified.counts_by_source_unit_status["inactive"] == 1
    assert verified.counts_by_source_unit_status["active"] == 3
