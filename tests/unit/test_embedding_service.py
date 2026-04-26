from __future__ import annotations

import pytest

from retrieval.embedding_profile import EmbeddingProfile
from retrieval.embedding_service import EmbeddingInput, EmbeddingService


class FakeBackend:
    backend_name = "local_embedding_endpoint"

    def __init__(self, *, fail_preflight: bool = False, vectors: list[list[float]] | None = None) -> None:
        self.fail_preflight = fail_preflight
        self.vectors = vectors or [[1.0, 0.0]]
        self.prefighted = False
        self.inputs: list[str] = []

    def preflight(self) -> None:
        self.prefighted = True
        if self.fail_preflight:
            raise RuntimeError("endpoint unavailable")

    def embed(self, inputs: list[str]) -> list[list[float]]:
        self.inputs = inputs
        return self.vectors


def test_embedding_service_prefixes_documents_and_returns_profile_metadata() -> None:
    backend = FakeBackend()
    profile = EmbeddingProfile(embedding_profile_id="profile", dimensions=2)
    service = EmbeddingService(profile=profile, backend=backend)

    records = service.embed_inputs(
        [EmbeddingInput(entity_kind="source_fragment", entity_id="f1", text="Text", law_code="AufenthG")]
    )

    assert backend.prefighted is True
    assert backend.inputs == ["Document: Text"]
    assert records[0].embedding_profile_id == "profile"
    assert records[0].backend_name == "local_embedding_endpoint"
    assert records[0].vector_dimensions == 2


def test_embedding_service_fails_before_embedding_when_preflight_fails() -> None:
    backend = FakeBackend(fail_preflight=True)
    service = EmbeddingService(
        profile=EmbeddingProfile(embedding_profile_id="profile", dimensions=2),
        backend=backend,
    )

    with pytest.raises(RuntimeError, match="endpoint unavailable"):
        service.embed_inputs([EmbeddingInput(entity_kind="source_document", entity_id="d1", text="Doc")])

    assert backend.inputs == []


def test_embedding_service_validates_vector_profile() -> None:
    backend = FakeBackend(vectors=[[1.0, 1.0]])
    service = EmbeddingService(
        profile=EmbeddingProfile(embedding_profile_id="profile", dimensions=2, normalized=True),
        backend=backend,
    )

    with pytest.raises(ValueError, match="normalized"):
        service.embed_inputs([EmbeddingInput(entity_kind="source_document", entity_id="d1", text="Doc")])
