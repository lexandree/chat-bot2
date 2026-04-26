"""Embedding profile policy for source and query vectors."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Literal, Sequence


QUERY_PREFIX = "Query: "
DOCUMENT_PREFIX = "Document: "
LOCAL_ONLY_ROUTING_MODE = "local_only"
VECTOR_FIELD = "embedding_v1"


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    embedding_profile_id: str
    provider: str = "jina"
    model_id: str = "jina-embeddings-v5-text-small-retrieval-GGUF"
    variant: str = "Q8"
    dimensions: int = 1024
    normalized: bool = True
    query_prefix: str = QUERY_PREFIX
    document_prefix: str = DOCUMENT_PREFIX
    query_task: str = "retrieval.query"
    document_task: str = "retrieval.passage"
    routing_mode: str = LOCAL_ONLY_ROUTING_MODE
    vector_field: str = VECTOR_FIELD

    def validate(self) -> "EmbeddingProfile":
        if not self.embedding_profile_id:
            raise ValueError("embedding_profile_id is required")
        if self.dimensions <= 0:
            raise ValueError("dimensions must be positive")
        if self.query_prefix != QUERY_PREFIX:
            raise ValueError("query_prefix must preserve 'Query: '")
        if self.document_prefix != DOCUMENT_PREFIX:
            raise ValueError("document_prefix must preserve 'Document: '")
        if self.routing_mode != LOCAL_ONLY_ROUTING_MODE:
            raise ValueError("graph-write embeddings must use local_only routing")
        return self

    def prefix_text(self, text: str, *, kind: Literal["query", "document"]) -> str:
        self.validate()
        prefix = self.query_prefix if kind == "query" else self.document_prefix
        return text if text.startswith(prefix) else f"{prefix}{text}"

    def as_record(self) -> dict[str, object]:
        self.validate()
        return {
            "embedding_profile_id": self.embedding_profile_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "variant": self.variant,
            "dimensions": self.dimensions,
            "normalized": self.normalized,
            "query_prefix": self.query_prefix,
            "document_prefix": self.document_prefix,
            "query_task": self.query_task,
            "document_task": self.document_task,
            "routing_mode": self.routing_mode,
            "vector_field": self.vector_field,
        }


def validate_vector(vector: Sequence[float], profile: EmbeddingProfile, *, tolerance: float = 0.02) -> None:
    profile.validate()
    if len(vector) != profile.dimensions:
        raise ValueError(f"vector dimensions {len(vector)} do not match {profile.dimensions}")
    if profile.normalized:
        norm = sqrt(sum(float(value) * float(value) for value in vector))
        if abs(norm - 1.0) > tolerance:
            raise ValueError(f"vector norm {norm:.4f} violates normalized profile")
