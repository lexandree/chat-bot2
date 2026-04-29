from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from graph.types import RELATION_TYPES
from tests.integration.live_support import (
    LIVE_RELATIONSHIP_LAW_CODE,
    build_live_relationship_test_preview,
    cleanup_live_test_scope,
)


pytestmark = pytest.mark.neo4j


def test_live_neo4j_relationship_refresh_idempotency_and_status_counts() -> None:
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

        before_counts = _relationship_counts(client)
        first = repo.refresh_relationships(law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
        second = repo.refresh_relationships(law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
        verified = repo.verify_relationships(law_codes=[LIVE_RELATIONSHIP_LAW_CODE])
        after_counts = _relationship_counts(client)
    finally:
        cleanup_live_test_scope(client)
        client.close()

    assert before_counts == {"legal_reference_count": 0, "typed_edge_count": 0, "related_edge_count": 0}
    assert first.created_reference_count == second.created_reference_count == 4
    assert first.created_edge_count == second.created_edge_count == 2
    assert after_counts == {"legal_reference_count": 4, "typed_edge_count": 2, "related_edge_count": 0}
    assert verified.counts_by_resolution_status["resolved"] == 2
    assert verified.counts_by_resolution_status["unresolved"] == 1
    assert verified.counts_by_resolution_status["out_of_scope"] == 1
    assert verified.counts_by_relation_type["CITES"] >= 1
    assert verified.counts_by_relation_type["DEFINES"] >= 1


def _relationship_counts(client: Neo4jGraphClient) -> dict[str, int]:
    reference_rows = client.read(
        "MATCH (n:LegalReference) WHERE n.law_code = $law_code RETURN count(n) AS count",
        {"law_code": LIVE_RELATIONSHIP_LAW_CODE},
    )
    edge_rows = client.read(
        "MATCH (s:LegalSection)-[r]->(:LegalSection) "
        "WHERE s.law_code = $law_code AND type(r) IN $relation_types "
        "RETURN count(r) AS count",
        {"law_code": LIVE_RELATIONSHIP_LAW_CODE, "relation_types": list(RELATION_TYPES)},
    )
    related_rows = client.read(
        "MATCH (s:LegalSection)-[r:RELATED]->(:LegalSection) "
        "WHERE s.law_code = $law_code "
        "RETURN count(r) AS count",
        {"law_code": LIVE_RELATIONSHIP_LAW_CODE},
    )
    return {
        "legal_reference_count": int(reference_rows[0].get("count", 0) if reference_rows else 0),
        "typed_edge_count": int(edge_rows[0].get("count", 0) if edge_rows else 0),
        "related_edge_count": int(related_rows[0].get("count", 0) if related_rows else 0),
    }
