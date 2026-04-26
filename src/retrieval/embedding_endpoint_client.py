"""Local embedding endpoint client using an OpenAI-compatible embeddings shape."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib import request


Transport = Callable[[dict[str, Any]], dict[str, Any]]


class EmbeddingEndpointClient:
    def __init__(
        self,
        endpoint_url: str,
        *,
        model_id: str,
        timeout_seconds: int = 30,
        transport: Transport | None = None,
    ) -> None:
        if not endpoint_url:
            raise ValueError("embedding endpoint URL is required")
        self.endpoint_url = endpoint_url
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
        self._transport = transport or self._urllib_transport

    def embed(self, inputs: list[str]) -> list[list[float]]:
        if not inputs:
            return []
        response = self._transport({"model": self.model_id, "input": inputs})
        return parse_embedding_response(response, expected_count=len(inputs))

    def preflight(self) -> None:
        vectors = self.embed(["Document: preflight"])
        if not vectors or not vectors[0]:
            raise RuntimeError("embedding endpoint returned no preflight vector")

    def _urllib_transport(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def parse_embedding_response(response: dict[str, Any], *, expected_count: int) -> list[list[float]]:
    if "data" in response:
        vectors = [item["embedding"] for item in response["data"]]
    elif "embeddings" in response:
        vectors = response["embeddings"]
    else:
        raise ValueError("embedding response must contain data or embeddings")
    if len(vectors) != expected_count:
        raise ValueError(f"embedding response count {len(vectors)} does not match {expected_count}")
    return [[float(value) for value in vector] for vector in vectors]
