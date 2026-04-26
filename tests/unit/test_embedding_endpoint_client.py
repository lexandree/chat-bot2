from __future__ import annotations

import pytest

from retrieval.embedding_endpoint_client import EmbeddingEndpointClient, parse_embedding_response


def test_embedding_endpoint_client_request_and_response_parsing() -> None:
    requests = []

    def transport(payload):
        requests.append(payload)
        return {"data": [{"embedding": [1.0, 0.0]}, {"embedding": [0.0, 1.0]}]}

    client = EmbeddingEndpointClient(
        "http://127.0.0.1:18080/v1/embeddings",
        model_id="jina-q8",
        transport=transport,
    )

    vectors = client.embed(["Document: eins", "Document: zwei"])

    assert requests == [{"model": "jina-q8", "input": ["Document: eins", "Document: zwei"]}]
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


def test_embedding_endpoint_client_preflight_uses_transport() -> None:
    client = EmbeddingEndpointClient(
        "http://127.0.0.1:18080/v1/embeddings",
        model_id="jina-q8",
        transport=lambda _payload: {"embeddings": [[1.0]]},
    )

    client.preflight()


def test_embedding_response_count_must_match_request_count() -> None:
    with pytest.raises(ValueError, match="count"):
        parse_embedding_response({"data": []}, expected_count=1)
