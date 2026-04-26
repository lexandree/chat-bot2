"""Embedding orchestration with profile validation and fail-fast policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from retrieval.embedding_backend import EmbeddingBackend
from retrieval.embedding_profile import EmbeddingProfile, validate_vector


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    entity_kind: Literal["source_document", "source_fragment"]
    entity_id: str
    text: str
    law_code: str = ""


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    entity_kind: str
    entity_id: str
    law_code: str
    vector: list[float]
    embedding_profile_id: str
    model_id: str
    backend_name: str
    routing_mode: str
    vector_dimensions: int
    normalized: bool


class EmbeddingService:
    def __init__(self, *, profile: EmbeddingProfile, backend: EmbeddingBackend) -> None:
        self.profile = profile.validate()
        self.backend = backend

    def preflight(self) -> None:
        self.backend.preflight()

    def embed_inputs(self, inputs: list[EmbeddingInput]) -> list[EmbeddingRecord]:
        self.preflight()
        prefixed = [self.profile.prefix_text(item.text, kind="document") for item in inputs]
        vectors = self.backend.embed(prefixed)
        records: list[EmbeddingRecord] = []
        for item, vector in zip(inputs, vectors, strict=True):
            validate_vector(vector, self.profile)
            records.append(
                EmbeddingRecord(
                    entity_kind=item.entity_kind,
                    entity_id=item.entity_id,
                    law_code=item.law_code,
                    vector=list(vector),
                    embedding_profile_id=self.profile.embedding_profile_id,
                    model_id=self.profile.model_id,
                    backend_name=self.backend.backend_name,
                    routing_mode=self.profile.routing_mode,
                    vector_dimensions=self.profile.dimensions,
                    normalized=self.profile.normalized,
                )
            )
        return records
