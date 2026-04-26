from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from evaluation.load_cases import build_snapshot_comparison_report, write_json_artifact
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from tests.integration.live_support import (
    LIVE_TEST_LAW_CODE,
    build_live_test_preview,
    cleanup_live_test_scope,
)


pytestmark = pytest.mark.neo4j


def test_live_neo4j_snapshot_and_legacy_baseline_comparison(tmp_path) -> None:
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
        snapshot = repo.snapshot_scope(law_codes=[LIVE_TEST_LAW_CODE])
        legacy_baseline = repo.snapshot_scope(
            law_codes=["AufenthG"],
            read_only_baseline=True,
            baseline_scope={"law_codes": ["AufenthG"]},
        )
        comparison = build_snapshot_comparison_report(snapshot, legacy_baseline)
        snapshot_path = write_json_artifact(tmp_path / "snapshot.json", snapshot)
        baseline_path = write_json_artifact(tmp_path / "baseline.json", legacy_baseline)
        comparison_path = write_json_artifact(tmp_path / "comparison.json", comparison)
    finally:
        cleanup_live_test_scope(client)
        client.close()

    assert snapshot.snapshot_id.startswith("snapshot:")
    assert legacy_baseline.baseline_origin == "legacy_aufenthg_graph_scope"
    assert comparison.new_snapshot_id == snapshot.snapshot_id
    assert comparison.baseline_snapshot_id == legacy_baseline.snapshot_id
    assert snapshot_path.exists()
    assert baseline_path.exists()
    assert comparison_path.exists()
