from __future__ import annotations

import os

import pytest

from app.settings import load_settings
from retrieval.embedding_backend import build_local_embedding_backend
from retrieval.embedding_profile import EmbeddingProfile
from retrieval.embedding_service import EmbeddingInput, EmbeddingService


pytestmark = pytest.mark.embedding


def test_live_local_embedding_endpoint() -> None:
    if os.environ.get("RUN_LIVE_EMBEDDING_TESTS", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set RUN_LIVE_EMBEDDING_TESTS=true to run live embedding checks")
    settings = load_settings()
    profile = EmbeddingProfile(
        embedding_profile_id=settings.embedding_profile_id,
        model_id=settings.embedding_model_id,
        dimensions=settings.embedding_vector_dimensions,
        normalized=settings.embedding_normalized,
    )
    backend = build_local_embedding_backend(endpoint_url=settings.embedding_endpoint_url, profile=profile)
    service = EmbeddingService(profile=profile, backend=backend)

    records = service.embed_inputs(
        [EmbeddingInput(entity_kind="source_fragment", entity_id="fixture", text="Fixture text")]
    )

    assert len(records) == 1
    assert records[0].vector_dimensions == settings.embedding_vector_dimensions
