"""Embedding service abstraction with deterministic fallback vectors."""

from __future__ import annotations

import hashlib
import math

from retrieval.embedding_profile import (
    DOCUMENT_KIND,
    INTERACTIVE_ROUTING_MODE,
    LOCAL_ONLY_ROUTING_MODE,
    QUERY_KIND,
    EmbeddingProfile,
)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional runtime dependency
    SentenceTransformer = None

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover - optional runtime dependency
    Llama = None


class EmbeddingService:
    def __init__(
        self,
        model_name: str = "jina-embeddings-v5-text-small-retrieval-GGUF",
        dimensions: int = 1024,
        model_path: str = "",
        normalized: bool = True,
        backend_router=None,
        profile: EmbeddingProfile | None = None,
    ) -> None:
        if "XXS" in model_name.upper():
            raise ValueError("XXS Jina variants are disabled for this project")
        self.model_name = model_name
        self.dimensions = dimensions
        self.model_path = model_path
        self.normalized = normalized
        self.vector_field_name = "embedding_v1"
        self._model = None
        self.query_prefix = "Query: "
        self.passage_prefix = "Document: "
        self.backend_router = backend_router
        self.profile = profile
        self.last_result_metadata = {
            "backend_name": "fallback-hash-v1",
            "routing_mode": LOCAL_ONLY_ROUTING_MODE,
            "runtime_metadata": {},
        }

    def _load_model(self):
        if self.model_name == "fallback-hash-v1":
            return None
        if "GGUF" in self.model_name.upper():
            if Llama is None or not self.model_path:
                return None
            if self._model is None:
                self._model = Llama(model_path=self.model_path, embedding=True, verbose=False)
            return self._model
        if SentenceTransformer is None:
            return None
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self._model

    def encode(self, text: str) -> list[float]:
        return self.encode_query(text)

    def encode_query(self, text: str) -> list[float]:
        return self.encode_query_with_metadata(text)["embedding"]

    def encode_passage(self, text: str) -> list[float]:
        return self.encode_passage_with_metadata(text)["embedding"]

    def encode_text(
        self,
        text: str,
        *,
        kind: str,
        routing_mode: str,
    ) -> dict[str, object]:
        prefix = self.query_prefix if kind == QUERY_KIND else self.passage_prefix
        if self.backend_router is not None and self.profile is not None:
            result = self.backend_router.embed(
                [f"{prefix}{text}"],
                kind=kind,
                routing_mode=routing_mode,
                profile=self.profile,
            )
            self.last_result_metadata = {
                "backend_name": result.backend_name,
                "routing_mode": result.routing_mode,
                "runtime_metadata": result.runtime_metadata,
            }
            return {"embedding": self._normalize(result.embeddings[0]), **self.last_result_metadata}
        return {
            "embedding": self._encode_with_prefix(prefix, text),
            "backend_name": self.last_result_metadata["backend_name"],
            "routing_mode": self.last_result_metadata["routing_mode"],
            "runtime_metadata": self.last_result_metadata["runtime_metadata"],
        }

    def encode_query_with_metadata(self, text: str) -> dict[str, object]:
        return self.encode_text(
            text,
            kind=QUERY_KIND,
            routing_mode=INTERACTIVE_ROUTING_MODE,
        )

    def encode_passage_with_metadata(self, text: str) -> dict[str, object]:
        return self.encode_text(
            text,
            kind=DOCUMENT_KIND,
            routing_mode=LOCAL_ONLY_ROUTING_MODE,
        )

    def _encode_with_prefix(self, prefix: str, text: str) -> list[float]:
        payload_text = f"{prefix}{text}"
        model = self._load_model()
        if model is not None:
            if "GGUF" in self.model_name.upper():
                payload = model.create_embedding(payload_text)
                vector = payload["data"][0]["embedding"]
            else:
                vector = model.encode(payload_text)
            vector = [float(value) for value in vector[: self.dimensions]]
            if len(vector) < self.dimensions:
                vector.extend([0.0] * (self.dimensions - len(vector)))
            self.last_result_metadata = {
                "backend_name": self.model_name,
                "routing_mode": LOCAL_ONLY_ROUTING_MODE,
                "runtime_metadata": {"model_path": self.model_path},
            }
            return self._normalize(vector)
        digest = hashlib.sha256(payload_text.encode("utf-8")).digest()
        values = []
        for idx in range(self.dimensions):
            byte = digest[idx % len(digest)]
            values.append(round((byte / 255.0) * 2 - 1, 6))
        self.last_result_metadata = {
            "backend_name": "fallback-hash-v1",
            "routing_mode": LOCAL_ONLY_ROUTING_MODE,
            "runtime_metadata": {},
        }
        return self._normalize(values)

    def _normalize(self, vector: list[float]) -> list[float]:
        if not self.normalized or not vector:
            return vector
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
