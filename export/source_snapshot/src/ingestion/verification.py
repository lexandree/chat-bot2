"""Shared verification helpers for profile-aware graph writes."""

from __future__ import annotations


def assert_local_only_metadata(metadata: dict[str, object]) -> None:
    backend_name = str(metadata.get("backend_name", ""))
    routing_mode = str(metadata.get("routing_mode", ""))
    if routing_mode != "local_only":
        raise RuntimeError(f"Graph-write routing must remain local_only, got {routing_mode}")
    if backend_name not in {"llama_server_local", "fallback-hash-v1", "jina-embeddings-v5-text-small-retrieval-GGUF"}:
        raise RuntimeError(f"Graph-write backend must remain local, got {backend_name}")


def assert_embedding_profile(vector: list[float], expected_dim: int, profile_id: str) -> dict[str, object]:
    if len(vector) != expected_dim:
        raise RuntimeError(f"Embedding dimension mismatch for profile {profile_id}: {len(vector)}")
    return {"embedding_profile_id": profile_id, "embedding_dimension": expected_dim}
