"""Typed runtime settings for the database-first foundation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


DEFAULT_EMBEDDING_ENDPOINT_URL = "http://127.0.0.1:18080/v1/embeddings"
DEFAULT_EMBEDDING_MODEL = "jina-embeddings-v5-text-small-retrieval-GGUF"
DEFAULT_EMBEDDING_PROFILE_ID = "jina_v5_q8_1024_norm_v1"


def _as_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class MissingSettingError(ValueError):
    missing: tuple[str, ...]

    def __str__(self) -> str:
        return f"Missing required settings: {', '.join(self.missing)}"


class FoundationSettings(BaseModel):
    """Configuration profile for graph, corpus, embedding, and tests."""

    model_config = ConfigDict(extra="forbid")

    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    neo4j_database: str = ""
    corpus_manifest_path: str = "tests/fixtures/legal_xml_import_manifest.json"
    preview_output_path: str = "data/import_preview/legal_xml_preview.json"
    embedding_profile_id: str = DEFAULT_EMBEDDING_PROFILE_ID
    embedding_model_id: str = DEFAULT_EMBEDDING_MODEL
    embedding_provider: str = "jina"
    embedding_vector_dimensions: int = 1024
    embedding_normalized: bool = True
    embedding_variant: str = "Q8"
    embedding_query_prefix: str = "Query: "
    embedding_document_prefix: str = "Document: "
    embedding_routing_mode: str = "local_only"
    embedding_endpoint_url: str = DEFAULT_EMBEDDING_ENDPOINT_URL
    run_live_neo4j_tests: bool = False
    run_live_embedding_tests: bool = False
    default_temporal_mode: str = "current_default"

    @field_validator("embedding_vector_dimensions")
    @classmethod
    def validate_dimensions(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("embedding_vector_dimensions must be positive")
        return value

    @field_validator("embedding_routing_mode")
    @classmethod
    def validate_routing_mode(cls, value: str) -> str:
        if value != "local_only":
            raise ValueError("embedding_routing_mode must be local_only for graph writes")
        return value

    @field_validator("embedding_query_prefix")
    @classmethod
    def validate_query_prefix(cls, value: str) -> str:
        if value != "Query: ":
            raise ValueError("embedding_query_prefix must be 'Query: '")
        return value

    @field_validator("embedding_document_prefix")
    @classmethod
    def validate_document_prefix(cls, value: str) -> str:
        if value != "Document: ":
            raise ValueError("embedding_document_prefix must be 'Document: '")
        return value

    def require_neo4j(self) -> None:
        missing = []
        if not self.neo4j_uri:
            missing.append("NEO4J_URI")
        if not self.neo4j_username:
            missing.append("NEO4J_USERNAME")
        if not self.neo4j_password.get_secret_value():
            missing.append("NEO4J_PASSWORD")
        if missing:
            raise MissingSettingError(tuple(missing))

    def redacted_summary(self) -> dict[str, Any]:
        return {
            "neo4j_uri": self.neo4j_uri,
            "neo4j_username": self.neo4j_username,
            "neo4j_password": "***" if self.neo4j_password.get_secret_value() else "",
            "neo4j_database": self.neo4j_database,
            "embedding_profile_id": self.embedding_profile_id,
            "embedding_model_id": self.embedding_model_id,
            "embedding_provider": self.embedding_provider,
            "embedding_vector_dimensions": self.embedding_vector_dimensions,
            "embedding_normalized": self.embedding_normalized,
            "embedding_variant": self.embedding_variant,
            "embedding_routing_mode": self.embedding_routing_mode,
            "embedding_endpoint_url": self.embedding_endpoint_url,
            "run_live_neo4j_tests": self.run_live_neo4j_tests,
            "run_live_embedding_tests": self.run_live_embedding_tests,
            "default_temporal_mode": self.default_temporal_mode,
        }


def load_settings(env: Mapping[str, str] | None = None) -> FoundationSettings:
    source = os.environ if env is None else env
    return FoundationSettings(
        neo4j_uri=source.get("NEO4J_URI", ""),
        neo4j_username=source.get("NEO4J_USERNAME", ""),
        neo4j_password=SecretStr(source.get("NEO4J_PASSWORD", "")),
        neo4j_database=source.get("NEO4J_DATABASE", ""),
        corpus_manifest_path=source.get(
            "CORPUS_MANIFEST_PATH",
            "tests/fixtures/legal_xml_import_manifest.json",
        ),
        preview_output_path=source.get(
            "PREVIEW_OUTPUT_PATH",
            "data/import_preview/legal_xml_preview.json",
        ),
        embedding_profile_id=source.get("EMBEDDING_PROFILE_ID", DEFAULT_EMBEDDING_PROFILE_ID),
        embedding_model_id=source.get(
            "EMBEDDING_MODEL_ID",
            source.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        ),
        embedding_provider=source.get("EMBEDDING_PROVIDER", "jina"),
        embedding_vector_dimensions=int(source.get("EMBEDDING_VECTOR_DIMENSIONS", "1024")),
        embedding_normalized=_as_bool(source.get("EMBEDDING_NORMALIZED"), default=True),
        embedding_variant=source.get("EMBEDDING_VARIANT", "Q8"),
        embedding_query_prefix=source.get("EMBEDDING_QUERY_PREFIX", "Query: "),
        embedding_document_prefix=source.get("EMBEDDING_DOCUMENT_PREFIX", "Document: "),
        embedding_routing_mode=source.get("EMBEDDING_ROUTING_MODE", "local_only"),
        embedding_endpoint_url=source.get(
            "EMBEDDING_ENDPOINT_URL",
            source.get("LLAMA_SERVER_URL", DEFAULT_EMBEDDING_ENDPOINT_URL),
        ),
        run_live_neo4j_tests=_as_bool(source.get("RUN_LIVE_NEO4J_TESTS")),
        run_live_embedding_tests=_as_bool(source.get("RUN_LIVE_EMBEDDING_TESTS")),
        default_temporal_mode=source.get("DEFAULT_TEMPORAL_MODE", "current_default"),
    )
