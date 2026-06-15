"""Embedding orchestration with profile validation and fail-fast policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from retrieval.embedding_backend import EmbeddingBackend
from retrieval.embedding_profile import EmbeddingProfile, validate_vector


MAX_LOCAL_EMBEDDING_BATCH_SIZE = 16


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
    def __init__(
        self,
        *,
        profile: EmbeddingProfile,
        backend: EmbeddingBackend,
        batch_size: int = MAX_LOCAL_EMBEDDING_BATCH_SIZE,
    ) -> None:
        if not 1 <= batch_size <= MAX_LOCAL_EMBEDDING_BATCH_SIZE:
            raise ValueError(
                f"batch_size must be between 1 and {MAX_LOCAL_EMBEDDING_BATCH_SIZE}"
            )
        self.profile = profile.validate()
        self.backend = backend
        self.batch_size = batch_size

    def preflight(self) -> None:
        self.backend.preflight()

    def embed_inputs(
        self,
        inputs: list[EmbeddingInput],
        *,
        progress_callback: Callable[[str, int, int, str], None] | None = None,
    ) -> list[EmbeddingRecord]:
        if progress_callback is not None:
            progress_callback("embedding_preflight", 0, 1, "")
        self.preflight()
        if progress_callback is not None:
            progress_callback("embedding_preflight", 1, 1, "")
        records: list[EmbeddingRecord] = []
        batch_count = (len(inputs) + self.batch_size - 1) // self.batch_size
        for batch_index, start in enumerate(range(0, len(inputs), self.batch_size), start=1):
            batch = inputs[start : start + self.batch_size]
            prefixed = [self.profile.prefix_text(item.text, kind="document") for item in batch]
            vectors = self.backend.embed(prefixed)
            for item, vector in zip(batch, vectors, strict=True):
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
            if progress_callback is not None:
                progress_callback(
                    "embedding_http_batches",
                    len(records),
                    len(inputs),
                    f"batch={batch_index}/{batch_count} size={len(batch)}",
                )
        return records
