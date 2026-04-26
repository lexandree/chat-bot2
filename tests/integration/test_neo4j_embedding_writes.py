from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from tests.integration.live_support import LIVE_TEST_LAW_CODE, build_live_test_preview, cleanup_live_test_scope
from retrieval.embedding_backend import build_local_embedding_backend
from retrieval.embedding_profile import EmbeddingProfile
from retrieval.embedding_service import EmbeddingService


pytestmark = [pytest.mark.neo4j, pytest.mark.embedding]


def test_live_neo4j_graph_write_embeddings() -> None:
    if os.environ.get("RUN_LIVE_NEO4J_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set RUN_LIVE_NEO4J_TESTS=true to run live Neo4j checks")
    if os.environ.get("RUN_LIVE_EMBEDDING_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set RUN_LIVE_EMBEDDING_TESTS=true to run live embedding checks")
    settings = load_settings()
    settings.require_neo4j()
    profile = EmbeddingProfile(
        embedding_profile_id=settings.embedding_profile_id,
        model_id=settings.embedding_model_id,
        dimensions=settings.embedding_vector_dimensions,
        normalized=settings.embedding_normalized,
    )
    backend = build_local_embedding_backend(endpoint_url=settings.embedding_endpoint_url, profile=profile)
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
        report = repo.write_embeddings(
            law_codes=[LIVE_TEST_LAW_CODE],
            embedding_service=EmbeddingService(profile=profile, backend=backend),
        )
    finally:
        cleanup_live_test_scope(client)
        client.close()

    assert report.processed_count >= 1
    assert report.embedding_profile_id == settings.embedding_profile_id
