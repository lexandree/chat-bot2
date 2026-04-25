"""Hosted Jina API client for retrieval embeddings."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class JinaApiClient:
    def __init__(self, base_url: str, api_key: str, model_name: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str], *, task: str = "retrieval.query") -> list[list[float]]:
        payload = json.dumps(
            {
                "model": self.model_name,
                "input": texts,
                "task": task,
                "embedding_type": "float",
                "normalized": True,
            }
        ).encode("utf-8")
        req = request.Request(
            self.base_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:  # pragma: no cover - network-bound
            raise RuntimeError(f"Jina API unavailable: {exc}") from exc
        return [[float(value) for value in item["embedding"]] for item in data.get("data", [])]

    def healthcheck(self) -> bool:
        return True

    def runtime_metadata(self) -> dict[str, Any]:
        return {"base_url": self.base_url, "model": self.model_name}
