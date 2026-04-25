"""Local llama-server client for embeddings."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class LlamaServerClient:
    def __init__(self, base_url: str, model_name: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model_name, "input": texts}).encode("utf-8")
        req = request.Request(
            self.base_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:  # pragma: no cover - network-bound
            raise RuntimeError(f"Local llama-server unavailable: {exc}") from exc
        return [[float(value) for value in item["embedding"]] for item in data.get("data", [])]

    def healthcheck(self) -> bool:
        health_url = self.base_url.replace("/v1/embeddings", "/health")
        try:
            with request.urlopen(health_url, timeout=self.timeout_seconds):
                return True
        except Exception:  # pragma: no cover - network-bound
            try:
                self.embed(["Query: healthcheck"])
            except Exception:
                return False
            return True

    def runtime_metadata(self) -> dict[str, Any]:
        return {"base_url": self.base_url, "model": self.model_name}
