"""Embedding backend protocol and local-only backend selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from retrieval.embedding_endpoint_client import EmbeddingEndpointClient
from retrieval.embedding_profile import EmbeddingProfile


class EmbeddingBackend(Protocol):
    backend_name: str

    def preflight(self) -> None:
        ...

    def embed(self, inputs: list[str]) -> list[list[float]]:
        ...


@dataclass(slots=True)
class LocalEmbeddingEndpointBackend:
    client: EmbeddingEndpointClient
    backend_name: str = "local_embedding_endpoint"

    def preflight(self) -> None:
        self.client.preflight()

    def embed(self, inputs: list[str]) -> list[list[float]]:
        return self.client.embed(inputs)


def build_local_embedding_backend(
    *,
    endpoint_url: str,
    profile: EmbeddingProfile,
) -> LocalEmbeddingEndpointBackend:
    profile.validate()
    client = EmbeddingEndpointClient(endpoint_url, model_id=profile.model_id)
    return LocalEmbeddingEndpointBackend(client=client)
