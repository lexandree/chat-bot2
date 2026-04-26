from __future__ import annotations

import pytest

from retrieval.embedding_profile import (
    DOCUMENT_PREFIX,
    QUERY_PREFIX,
    EmbeddingProfile,
    validate_vector,
)


def test_embedding_profile_preserves_asymmetric_prefixes() -> None:
    profile = EmbeddingProfile(embedding_profile_id="jina_v5_q8_1024_norm_v1", dimensions=3)

    assert profile.prefix_text("Was ist § 1?", kind="query") == f"{QUERY_PREFIX}Was ist § 1?"
    assert profile.prefix_text("§ 1 Text", kind="document") == f"{DOCUMENT_PREFIX}§ 1 Text"


def test_embedding_profile_rejects_non_local_graph_write_routing() -> None:
    profile = EmbeddingProfile(embedding_profile_id="bad", routing_mode="prefer_api")

    with pytest.raises(ValueError, match="local_only"):
        profile.validate()


def test_vector_validation_checks_dimensions_and_normalization() -> None:
    profile = EmbeddingProfile(embedding_profile_id="small", dimensions=3, normalized=True)

    validate_vector([1.0, 0.0, 0.0], profile)
    with pytest.raises(ValueError, match="dimensions"):
        validate_vector([1.0, 0.0], profile)
    with pytest.raises(ValueError, match="normalized"):
        validate_vector([1.0, 1.0, 0.0], profile)
