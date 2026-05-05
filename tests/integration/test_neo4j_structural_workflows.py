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


def test_live_neo4j_structural_workflow_seed_and_law_scope_artifacts() -> None:
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

        seed_artifact = repo.structural_workflow_artifact(
            workflow_mode="seed_neighborhood",
            seed_legal_section_ids=[f"legal-section:{LIVE_RELATIONSHIP_LAW_CODE}:1:current"],
            law_codes=[LIVE_RELATIONSHIP_LAW_CODE],
            allowed_relation_types=["CITES"],
            direction="outgoing",
            max_depth=1,
            fanout_limit=25,
            node_limit=100,
            edge_limit=500,
            source_sample_limit=5,
        )
        scope_artifact = repo.structural_workflow_artifact(
            workflow_mode="law_scope_overview",
            law_codes=[LIVE_RELATIONSHIP_LAW_CODE],
            allowed_relation_types=["CITES", "DEFINES"],
            direction="outgoing",
            max_depth=1,
            fanout_limit=25,
            node_limit=100,
            edge_limit=500,
            source_sample_limit=5,
        )
    finally:
        cleanup_live_test_scope(client)
        client.close()

    seed_payload = seed_artifact.as_dict()
    scope_payload = scope_artifact.as_dict()
    assert seed_payload["artifact_type"] == "structural_workflow"
    assert seed_payload["quality_summary"]["workflow_mode"] == "seed_neighborhood"
    assert seed_payload["quality_summary"]["resolved_edge_count"] >= 1
    assert scope_payload["quality_summary"]["workflow_mode"] == "law_scope_overview"
    assert scope_payload["quality_summary"]["resolved_edge_count"] >= 2
    assert scope_payload["quality_summary"]["boundary_stop_count"] >= 1
    assert "answer_text" not in seed_payload
    assert "answer_text" not in scope_payload
