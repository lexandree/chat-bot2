"""Policy-aware routing between local and hosted embedding providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from retrieval.backend_health import InteractiveBackendState
from retrieval.embedding_profile import (
    DOCUMENT_KIND,
    INTERACTIVE_ROUTING_MODE,
    LOCAL_ONLY_ROUTING_MODE,
    QUERY_KIND,
    EmbeddingBackendConfig,
    EmbeddingProfile,
)


@dataclass(slots=True)
class EmbeddingRunResult:
    embeddings: list[list[float]]
    backend_name: str
    routing_mode: str
    runtime_metadata: dict[str, Any]


class EmbeddingBackendRouter:
    def __init__(
        self,
        local_client: Any,
        hosted_client: Any | None,
        local_config: EmbeddingBackendConfig,
        hosted_config: EmbeddingBackendConfig | None,
        health_state: InteractiveBackendState | None = None,
    ) -> None:
        self.local_client = local_client
        self.hosted_client = hosted_client
        self.local_config = local_config.validate()
        self.hosted_config = hosted_config.validate() if hosted_config is not None else None
        self.health_state = health_state or InteractiveBackendState()

    def embed(
        self,
        texts: list[str],
        *,
        kind: str,
        routing_mode: str,
        profile: EmbeddingProfile,
    ) -> EmbeddingRunResult:
        profile.validate()
        if kind not in {QUERY_KIND, DOCUMENT_KIND}:
            raise ValueError(f"Unsupported embedding kind: {kind}")
        if routing_mode == LOCAL_ONLY_ROUTING_MODE:
            return self._run_local(texts, routing_mode)
        if routing_mode != INTERACTIVE_ROUTING_MODE or kind != QUERY_KIND:
            raise ValueError(f"Unsupported routing/kind combination: {routing_mode} + {kind}")
        return self._run_interactive_query(texts)

    def _run_local(self, texts: list[str], routing_mode: str) -> EmbeddingRunResult:
        try:
            vectors = self.local_client.embed(texts)
        except Exception as exc:
            self.health_state.mark_local_failure()
            raise RuntimeError(f"Local backend unavailable for {routing_mode}: {exc}") from exc
        self.health_state.mark_local_success()
        return EmbeddingRunResult(
            embeddings=vectors,
            backend_name="llama_server_local",
            routing_mode=routing_mode,
            runtime_metadata=self.local_client.runtime_metadata(),
        )

    def _run_interactive_query(self, texts: list[str]) -> EmbeddingRunResult:
        if self.health_state.effective_backend == "llama_server_local":
            try:
                return self._run_local(texts, INTERACTIVE_ROUTING_MODE)
            except RuntimeError:
                pass
        if self.hosted_client is None or self.hosted_config is None:
            raise RuntimeError("Hosted backend is not configured for interactive failover")
        if self.health_state.should_probe_local():
            recovered = self.local_client.healthcheck()
            self.health_state.observe_recovery_probe(recovered)
            if recovered and self.health_state.effective_backend == "llama_server_local":
                return self._run_local(texts, INTERACTIVE_ROUTING_MODE)
        vectors = self.hosted_client.embed(texts, task="retrieval.query")
        return EmbeddingRunResult(
            embeddings=vectors,
            backend_name="jina_api",
            routing_mode=INTERACTIVE_ROUTING_MODE,
            runtime_metadata=self.hosted_client.runtime_metadata(),
        )
