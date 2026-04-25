"""Typed embedding profile and backend configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass


FORBIDDEN_VARIANTS = {"XXS"}
INTERACTIVE_ROUTING_MODE = "prefer_local_with_api_failover"
LOCAL_ONLY_ROUTING_MODE = "local_only"
QUERY_KIND = "query"
DOCUMENT_KIND = "document"


@dataclass(slots=True)
class EmbeddingProfile:
    profile_id: str
    provider: str
    model: str
    variant: str
    dim: int
    normalized: bool
    query_prefix: str = "Query: "
    document_prefix: str = "Document: "
    query_task: str = "retrieval.query"
    document_task: str = "retrieval.passage"
    active: bool = True

    def validate(self) -> "EmbeddingProfile":
        if self.variant.upper() in FORBIDDEN_VARIANTS:
            raise ValueError(f"Embedding variant is forbidden: {self.variant}")
        if self.dim <= 0:
            raise ValueError("Embedding profile dimension must be positive")
        if not self.profile_id:
            raise ValueError("Embedding profile id is required")
        return self

    def as_payload(self) -> dict[str, object]:
        self.validate()
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "model": self.model,
            "variant": self.variant,
            "dim": self.dim,
            "normalized": self.normalized,
            "query_prefix": self.query_prefix,
            "document_prefix": self.document_prefix,
            "query_task": self.query_task,
            "document_task": self.document_task,
            "active": self.active,
        }


@dataclass(slots=True)
class EmbeddingBackendConfig:
    backend_name: str
    routing_mode: str
    base_url: str
    model_name_or_alias: str
    timeout_seconds: int = 30
    batch_size: int = 1
    enabled: bool = True

    def validate(self) -> "EmbeddingBackendConfig":
        if self.routing_mode not in {INTERACTIVE_ROUTING_MODE, LOCAL_ONLY_ROUTING_MODE}:
            raise ValueError(f"Unsupported routing mode: {self.routing_mode}")
        if self.backend_name not in {"jina_api", "llama_server_local"}:
            raise ValueError(f"Unsupported backend: {self.backend_name}")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        return self
