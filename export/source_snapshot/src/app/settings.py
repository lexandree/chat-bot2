"""Environment-driven settings for the chatbot application."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


SUPPORTED_BACKENDS = {"jina_api", "llama_server_local"}
SUPPORTED_ROUTING_MODES = {"prefer_local_with_api_failover", "local_only"}
SUPPORTED_RUNTIME_CONTOURS = {"managed_paid", "operator_managed"}
SUPPORTED_SOURCE_TYPES = {"law", "official_guidance"}
SUPPORTED_CANDIDATE_REVIEW_STATES = {"pending", "approved", "rejected", "deprecated"}


def _dotenv_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv_values() -> dict[str, str]:
    dotenv_path = _dotenv_path()
    if not dotenv_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@dataclass(slots=True)
class AppSettings:
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: tuple[int, ...] = ()
    openai_api_key: str = ""
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/graph_chatbot"
    embedding_model: str = "jina-embeddings-v5-text-small-retrieval-GGUF"
    embedding_model_path: str = ""
    enable_embedding_router: bool = False
    embedding_vector_dimensions: int = 1024
    embedding_normalized: bool = True
    embedding_variant: str = "Q8"
    embedding_profile_id: str = "jina_v5_q8_1024_norm_v1"
    embedding_provider: str = "jina_local"
    embedding_query_task: str = "retrieval.query"
    embedding_document_task: str = "retrieval.passage"
    jina_api_base_url: str = "https://api.jina.ai/v1/embeddings"
    jina_api_key: str = ""
    llama_server_url: str = "http://127.0.0.1:18080/v1/embeddings"
    interactive_routing_mode: str = "prefer_local_with_api_failover"
    graph_write_routing_mode: str = "local_only"
    backend_healthcheck_seconds: int = 15
    backend_recovery_successes: int = 2
    backend_failure_threshold: int = 1
    bulk_runtime_contour: str = "operator_managed"
    bulk_allowed_source_types: tuple[str, ...] = ("law", "official_guidance")
    bulk_extraction_policy_version: str = "bulk_enrichment_v1"
    bulk_validation_fixture_path: str = "tests/fixtures/legal_enrichment_validation_cases.json"
    bulk_candidate_review_state: str = "pending"
    bulk_managed_llm_backend: str = "paid_api"
    bulk_operator_llm_backend: str = "operator_remote"
    bulk_managed_embedding_backend: str = "jina_api"
    bulk_operator_embedding_backend: str = "llama_server_local"
    legal_runtime_contour: str = "operator_managed"
    legal_extraction_policy_version: str = "legal_extraction_v1"
    legal_managed_llm_backend: str = "paid_api"
    legal_operator_llm_backend: str = "operator_remote"
    legal_managed_embedding_backend: str = "jina_api"
    legal_operator_embedding_backend: str = "llama_server_local"
    legal_validation_fixture_path: str = "tests/fixtures/legal_extraction_validation_cases.json"
    legal_managed_smoke_limit: int = 5
    legal_default_temporal_mode: str = "current_default"
    memory_retention_days: int = 30
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppSettings":
        dotenv_values = _load_dotenv_values()

        def getenv(name: str, default: str = "") -> str:
            return os.getenv(name, dotenv_values.get(name, default))

        allowed = tuple(
            int(chat_id) for chat_id in _split_csv(getenv("TELEGRAM_ALLOWED_CHAT_IDS", ""))
        )
        return cls(
            telegram_bot_token=getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_allowed_chat_ids=allowed,
            openai_api_key=getenv("OPENAI_API_KEY", ""),
            neo4j_uri=getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_username=getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=getenv("NEO4J_PASSWORD", ""),
            postgres_dsn=getenv(
                "POSTGRES_DSN",
                "postgresql://postgres:postgres@localhost:5432/graph_chatbot",
            ),
            embedding_model=getenv(
                "EMBEDDING_MODEL", "jina-embeddings-v5-text-small-retrieval-GGUF"
            ),
            embedding_model_path=getenv("EMBEDDING_MODEL_PATH", ""),
            enable_embedding_router=getenv("ENABLE_EMBEDDING_ROUTER", "false").strip().lower()
            in {"1", "true", "yes", "on"},
            embedding_vector_dimensions=int(getenv("EMBEDDING_VECTOR_DIMENSIONS", "1024")),
            embedding_normalized=getenv("EMBEDDING_NORMALIZED", "true").strip().lower()
            in {"1", "true", "yes", "on"},
            embedding_variant=getenv("EMBEDDING_VARIANT", "Q8"),
            embedding_profile_id=getenv(
                "EMBEDDING_PROFILE_ID", "jina_v5_q8_1024_norm_v1"
            ),
            embedding_provider=getenv("EMBEDDING_PROVIDER", "jina_local"),
            embedding_query_task=getenv("EMBEDDING_QUERY_TASK", "retrieval.query"),
            embedding_document_task=getenv(
                "EMBEDDING_DOCUMENT_TASK", "retrieval.passage"
            ),
            jina_api_base_url=getenv(
                "JINA_API_BASE_URL", "https://api.jina.ai/v1/embeddings"
            ),
            jina_api_key=getenv("JINA_API_KEY", ""),
            llama_server_url=getenv(
                "LLAMA_SERVER_URL", "http://127.0.0.1:18080/v1/embeddings"
            ),
            interactive_routing_mode=getenv(
                "INTERACTIVE_EMBEDDING_ROUTING_MODE", "prefer_local_with_api_failover"
            ),
            graph_write_routing_mode=getenv(
                "GRAPH_WRITE_EMBEDDING_ROUTING_MODE", "local_only"
            ),
            backend_healthcheck_seconds=int(getenv("BACKEND_HEALTHCHECK_SECONDS", "15")),
            backend_recovery_successes=int(getenv("BACKEND_RECOVERY_SUCCESSES", "2")),
            backend_failure_threshold=int(getenv("BACKEND_FAILURE_THRESHOLD", "1")),
            bulk_runtime_contour=getenv("BULK_RUNTIME_CONTOUR", "operator_managed"),
            bulk_allowed_source_types=tuple(
                _split_csv(getenv("BULK_ALLOWED_SOURCE_TYPES", "law,official_guidance"))
            ),
            bulk_extraction_policy_version=getenv(
                "BULK_EXTRACTION_POLICY_VERSION", "bulk_enrichment_v1"
            ),
            bulk_validation_fixture_path=getenv(
                "BULK_VALIDATION_FIXTURE_PATH",
                "tests/fixtures/legal_enrichment_validation_cases.json",
            ),
            bulk_candidate_review_state=getenv("BULK_CANDIDATE_REVIEW_STATE", "pending"),
            bulk_managed_llm_backend=getenv("BULK_MANAGED_LLM_BACKEND", "paid_api"),
            bulk_operator_llm_backend=getenv("BULK_OPERATOR_LLM_BACKEND", "operator_remote"),
            bulk_managed_embedding_backend=getenv(
                "BULK_MANAGED_EMBEDDING_BACKEND", "jina_api"
            ),
            bulk_operator_embedding_backend=getenv(
                "BULK_OPERATOR_EMBEDDING_BACKEND", "llama_server_local"
            ),
            legal_runtime_contour=getenv(
                "LEGAL_RUNTIME_CONTOUR",
                getenv("BULK_RUNTIME_CONTOUR", "operator_managed"),
            ),
            legal_extraction_policy_version=getenv(
                "LEGAL_EXTRACTION_POLICY_VERSION",
                "legal_extraction_v1",
            ),
            legal_managed_llm_backend=getenv(
                "LEGAL_MANAGED_LLM_BACKEND",
                getenv("BULK_MANAGED_LLM_BACKEND", "paid_api"),
            ),
            legal_operator_llm_backend=getenv(
                "LEGAL_OPERATOR_LLM_BACKEND",
                getenv("BULK_OPERATOR_LLM_BACKEND", "operator_remote"),
            ),
            legal_managed_embedding_backend=getenv(
                "LEGAL_MANAGED_EMBEDDING_BACKEND",
                getenv("BULK_MANAGED_EMBEDDING_BACKEND", "jina_api"),
            ),
            legal_operator_embedding_backend=getenv(
                "LEGAL_OPERATOR_EMBEDDING_BACKEND",
                getenv("BULK_OPERATOR_EMBEDDING_BACKEND", "llama_server_local"),
            ),
            legal_validation_fixture_path=getenv(
                "LEGAL_VALIDATION_FIXTURE_PATH",
                "tests/fixtures/legal_extraction_validation_cases.json",
            ),
            legal_managed_smoke_limit=int(getenv("LEGAL_MANAGED_SMOKE_LIMIT", "5")),
            legal_default_temporal_mode=getenv(
                "LEGAL_DEFAULT_TEMPORAL_MODE", "current_default"
            ),
            memory_retention_days=int(getenv("MEMORY_RETENTION_DAYS", "30")),
            log_level=getenv("LOG_LEVEL", "INFO"),
        ).validated()

    def validated(self) -> "AppSettings":
        if self.embedding_variant.upper() == "XXS":
            raise ValueError("XXS Jina variants are disabled for this project")
        if self.interactive_routing_mode not in SUPPORTED_ROUTING_MODES:
            raise ValueError(
                f"Unsupported interactive routing mode: {self.interactive_routing_mode}"
            )
        if self.graph_write_routing_mode != "local_only":
            raise ValueError("Graph-write workflows must use local_only routing")
        if self.embedding_provider not in {"jina_local", "jina_api"}:
            raise ValueError(f"Unsupported embedding provider: {self.embedding_provider}")
        if self.embedding_vector_dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        if self.backend_healthcheck_seconds <= 0:
            raise ValueError("Healthcheck interval must be positive")
        if self.backend_recovery_successes <= 0:
            raise ValueError("Recovery success threshold must be positive")
        if self.backend_failure_threshold <= 0:
            raise ValueError("Failure threshold must be positive")
        if self.bulk_runtime_contour not in SUPPORTED_RUNTIME_CONTOURS:
            raise ValueError(f"Unsupported bulk runtime contour: {self.bulk_runtime_contour}")
        if self.legal_runtime_contour not in SUPPORTED_RUNTIME_CONTOURS:
            raise ValueError(f"Unsupported legal runtime contour: {self.legal_runtime_contour}")
        if not self.bulk_allowed_source_types:
            raise ValueError("At least one bulk source type must be configured")
        invalid_source_types = set(self.bulk_allowed_source_types) - SUPPORTED_SOURCE_TYPES
        if invalid_source_types:
            raise ValueError(f"Unsupported bulk source types: {sorted(invalid_source_types)}")
        if self.bulk_candidate_review_state not in SUPPORTED_CANDIDATE_REVIEW_STATES:
            raise ValueError(
                f"Unsupported bulk candidate review state: {self.bulk_candidate_review_state}"
            )
        if self.legal_managed_smoke_limit <= 0:
            raise ValueError("Legal managed smoke limit must be positive")
        if self.legal_default_temporal_mode not in {"current_default", "as_of_date"}:
            raise ValueError(
                f"Unsupported legal default temporal mode: {self.legal_default_temporal_mode}"
            )
        if not self.legal_validation_fixture_path.strip():
            raise ValueError("Legal validation fixture path must not be empty")
        if not self.legal_extraction_policy_version.strip():
            raise ValueError("Legal extraction policy version must not be empty")
        if not self.bulk_extraction_policy_version.strip():
            raise ValueError("Bulk extraction policy version must not be empty")
        if not self.bulk_validation_fixture_path.strip():
            raise ValueError("Bulk validation fixture path must not be empty")
        return self


def load_settings() -> AppSettings:
    """Load application settings from environment variables."""

    return AppSettings.from_env()
