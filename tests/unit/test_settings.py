from __future__ import annotations

import pytest

from app.settings import MissingSettingError, load_settings


def test_settings_redacts_secret_and_defaults_embedding_contract() -> None:
    settings = load_settings(
        {
            "NEO4J_URI": "neo4j://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "secret-value",
        }
    )

    summary = settings.redacted_summary()

    assert summary["neo4j_password"] == "***"
    assert "secret-value" not in str(summary)
    assert settings.neo4j_database == ""
    assert settings.embedding_query_prefix == "Query: "
    assert settings.embedding_document_prefix == "Document: "
    assert settings.embedding_routing_mode == "local_only"


def test_settings_fail_before_graph_operations_when_neo4j_missing() -> None:
    settings = load_settings({})

    with pytest.raises(MissingSettingError) as exc_info:
        settings.require_neo4j()

    assert "NEO4J_URI" in str(exc_info.value)
    assert "NEO4J_PASSWORD" in str(exc_info.value)


def test_settings_accepts_embedding_endpoint_alias_without_live_service() -> None:
    settings = load_settings({"LLAMA_SERVER_URL": "http://embedding-box:18080/v1/embeddings"})

    assert settings.embedding_endpoint_url == "http://embedding-box:18080/v1/embeddings"
    assert settings.run_live_embedding_tests is False
