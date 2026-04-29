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


def test_live_neo4j_relationship_quality_artifact_generation() -> None:
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
        repo.refresh_relationships(law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
        artifact = repo.relationship_quality_artifact(law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
    finally:
        cleanup_live_test_scope(client)
        client.close()

    payload = artifact.as_dict()
    assert payload["artifact_id"].startswith("relationship-quality:")
    assert payload["selected_scope"]["law_codes"] == [LIVE_RELATIONSHIP_LAW_CODE]
    assert payload["counts_by_resolution_status"]["resolved"] == 2
    assert payload["counts_by_resolution_status"]["unresolved"] == 1
    assert payload["counts_by_resolution_status"]["out_of_scope"] == 1
    assert payload["sample_edges_by_relation_type"]["CITES"]
    assert payload["temporal_metadata_completeness"]["total_reference_evidence_count"] == 4
    assert "answer_text" not in payload
