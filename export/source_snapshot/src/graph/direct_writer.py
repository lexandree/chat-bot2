"""Helpers for profile-aware Neo4j writes outside the generic repository layer."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from graph.neo4j_client import Neo4jClient
from retrieval.embedding_profile import EmbeddingProfile


class DirectGraphWriter:
    """A thin query builder for large vector writes and profile-aware upserts."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def upsert_embedding_profile(self, profile: EmbeddingProfile) -> dict[str, Any]:
        payload = profile.as_payload()
        payload.setdefault("created_at", datetime.now(UTC).isoformat())
        query = (
            "MERGE (p:EmbeddingProfile {profile_id: $payload.profile_id}) "
            "SET p += $payload RETURN p"
        )
        self.client.execute(query, payload=payload)
        return payload

    def upsert_node_embedding(
        self,
        label: str,
        key_field: str,
        key_value: str,
        vector: list[float],
        profile_id: str,
        extra_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(extra_payload or {})
        payload["embedding_v1"] = vector
        payload["embedding_profile_id"] = profile_id
        payload["embedding_updated_at"] = datetime.now(UTC).isoformat()
        query = (
            f"MERGE (n:{label} {{{key_field}: $key_value}}) "
            "SET n += $payload "
            "WITH n "
            "MATCH (p:EmbeddingProfile {profile_id: $profile_id}) "
            "MERGE (n)-[:EMBEDDED_WITH]->(p) "
            "RETURN n"
        )
        self.client.execute(
            query,
            key_value=key_value,
            payload=payload,
            profile_id=profile_id,
        )
        return payload


def validate_embedding(vector: list[float], expected_dimensions: int) -> None:
    if len(vector) != expected_dimensions:
        raise ValueError(
            f"Embedding length mismatch: expected {expected_dimensions}, got {len(vector)}"
        )
