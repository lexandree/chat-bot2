"""Load, verify, and delete legal preview corpora in Neo4j."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from app.settings import load_settings
from graph.schema import build_schema_queries
from ingestion.verification import assert_embedding_profile, assert_local_only_metadata
from retrieval.backend_health import InteractiveBackendState
from retrieval.embedding_backend import EmbeddingBackendRouter
from retrieval.embedding_profile import (
    DOCUMENT_KIND,
    LOCAL_ONLY_ROUTING_MODE,
    EmbeddingBackendConfig,
    EmbeddingProfile,
)
from retrieval.embedding_service import EmbeddingService
from retrieval.llama_server_client import LlamaServerClient

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - depends on local environment
    GraphDatabase = None


def load_preview_payload(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def select_documents(payload: dict[str, Any], law_codes: set[str] | None = None) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for source in payload.get("imported_sources", []):
        if law_codes and str(source.get("law_code")) not in law_codes:
            continue
        documents.extend(source.get("documents", []))
    return documents


def _fragment_payload(document: dict[str, Any]) -> dict[str, Any]:
    source_id = str(document["source_id"])
    body_text = str(document.get("body_text", "")).strip()
    return {
        "fragment_id": f"{source_id}:fragment:1",
        "source_id": source_id,
        "ordinal": 1,
        "text": body_text,
        "start_ref": str(document.get("section_ref", "")),
        "end_ref": str(document.get("section_ref", "")),
        "language": str(document.get("language", "de")),
        "checksum": f"{source_id}:fragment:1",
    }


def _document_embedding_text(document: dict[str, Any]) -> str:
    parts = [
        str(document.get("law_code", "")).strip(),
        str(document.get("section_ref", "")).strip(),
        str(document.get("title", "")).strip(),
        str(document.get("body_text", "")).strip(),
    ]
    return "\n".join(part for part in parts if part)


def _law_progress_summary(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_law: dict[str, dict[str, Any]] = {}
    for document in documents:
        law_code = str(document.get("law_code", ""))
        source_id = str(document.get("source_id", ""))
        entry = by_law.setdefault(
            law_code,
            {
                "law_code": law_code,
                "source_document_count": 0,
                "first_source_id": source_id,
                "last_source_id": source_id,
            },
        )
        entry["source_document_count"] += 1
        if source_id < entry["first_source_id"]:
            entry["first_source_id"] = source_id
        if source_id > entry["last_source_id"]:
            entry["last_source_id"] = source_id
    return [by_law[law_code] for law_code in sorted(by_law)]


def _preview_section_ranges(documents: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    ranges: dict[str, dict[str, str]] = {}
    for document in documents:
        law_code = str(document.get("law_code", ""))
        if law_code in ranges:
            continue
        ranges[law_code] = {
            "first_section_ref": str(document.get("section_ref", "")),
            "last_section_ref": str(document.get("section_ref", "")),
            "first_source_id": str(document.get("source_id", "")),
            "last_source_id": str(document.get("source_id", "")),
        }
    for document in documents:
        law_code = str(document.get("law_code", ""))
        if law_code not in ranges:
            continue
        ranges[law_code]["last_section_ref"] = str(document.get("section_ref", ""))
        ranges[law_code]["last_source_id"] = str(document.get("source_id", ""))
    return ranges


def _build_local_passage_embedder(settings) -> EmbeddingService:
    profile = EmbeddingProfile(
        profile_id=settings.embedding_profile_id,
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        variant=settings.embedding_variant,
        dim=settings.embedding_vector_dimensions,
        normalized=settings.embedding_normalized,
        query_task=settings.embedding_query_task,
        document_task=settings.embedding_document_task,
    )
    router = EmbeddingBackendRouter(
        local_client=LlamaServerClient(settings.llama_server_url, settings.embedding_model),
        hosted_client=None,
        local_config=EmbeddingBackendConfig(
            backend_name="llama_server_local",
            routing_mode=LOCAL_ONLY_ROUTING_MODE,
            base_url=settings.llama_server_url,
            model_name_or_alias=settings.embedding_model,
        ),
        hosted_config=None,
        health_state=InteractiveBackendState(
            healthcheck_seconds=settings.backend_healthcheck_seconds,
            recovery_successes=settings.backend_recovery_successes,
            failure_threshold=settings.backend_failure_threshold,
        ),
    )
    return EmbeddingService(
        settings.embedding_model,
        dimensions=settings.embedding_vector_dimensions,
        model_path=settings.embedding_model_path,
        normalized=settings.embedding_normalized,
        backend_router=router,
        profile=profile,
    )


def _progress_line(current: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "[------------------------] 0/0 0.0%"
    ratio = min(max(current / total, 0.0), 1.0)
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {current}/{total} {ratio * 100:5.1f}%"


def _upsert_embedding_profile(session, profile: EmbeddingProfile) -> None:
    session.run(
        "MERGE (p:EmbeddingProfile {profile_id: $payload.profile_id}) SET p += $payload",
        payload=profile.as_payload(),
    )


def _upsert_node_embedding(
    session,
    *,
    label: str,
    key_field: str,
    key_value: str,
    vector: list[float],
    profile_id: str,
    backend_name: str,
    routing_mode: str,
    model_id: str,
) -> None:
    payload = {
        "embedding_v1": vector,
        "embedding_profile_id": profile_id,
        "embedding_backend_used": backend_name,
        "embedding_routing_mode": routing_mode,
        "embedding_model_id": model_id,
    }
    session.run(
        f"MERGE (n:{label} {{{key_field}: $key_value}}) "
        "SET n += $payload "
        "WITH n "
        "MATCH (p:EmbeddingProfile {profile_id: $profile_id}) "
        "MERGE (n)-[:EMBEDDED_WITH]->(p)",
        key_value=key_value,
        payload=payload,
        profile_id=profile_id,
    )


def load_documents(session, documents: list[dict[str, Any]], settings, progress_every: int = 25) -> dict[str, Any]:
    for query in build_schema_queries():
        session.run(query)
    embedder = _build_local_passage_embedder(settings)
    profile = embedder.profile
    if profile is None:
        raise RuntimeError("Embedding profile is required for legal preview load")
    _upsert_embedding_profile(session, profile)
    total = len(documents)
    last_backend_name = ""
    for index, document in enumerate(documents, start=1):
        source_payload = {
            "source_id": str(document["source_id"]),
            "law_code": str(document.get("law_code", "")),
            "source_type": str(document.get("source_type", "law")),
            "title": str(document.get("title", "")),
            "section_ref": str(document.get("section_ref", "")),
            "law_name": str(document.get("law_name", "")),
            "jurisdiction": str(document.get("jurisdiction", "DE")),
            "language": str(document.get("language", "de")),
            "source_uri_or_ref": str(document.get("source_uri_or_ref", "")),
            "published_at": str(document.get("published_at", "")),
            "effective_from": str(document.get("effective_from", "")),
            "retrieved_at": str(document.get("retrieved_at", "")),
            "freshness_note": str(document.get("freshness_note", "")),
            "checksum": str(document.get("checksum", document["source_id"])),
            "body_text": str(document.get("body_text", "")),
        }
        fragment_payload = _fragment_payload(document)
        session.run(
            "MERGE (s:SourceDocument {source_id: $payload.source_id}) "
            "SET s += $payload",
            payload=source_payload,
        )
        session.run(
            "MERGE (f:SourceFragment {fragment_id: $fragment.fragment_id}) "
            "SET f += $fragment "
            "WITH f "
            "MATCH (s:SourceDocument {source_id: $fragment.source_id}) "
            "MERGE (s)-[:HAS_FRAGMENT]->(f)",
            fragment=fragment_payload,
        )
        embedding_payload = embedder.encode_text(
            _document_embedding_text(document),
            kind=DOCUMENT_KIND,
            routing_mode=LOCAL_ONLY_ROUTING_MODE,
        )
        assert_local_only_metadata(embedding_payload)
        assert_embedding_profile(
            embedding_payload["embedding"],
            embedder.dimensions,
            profile.profile_id,
        )
        vector = [float(value) for value in embedding_payload["embedding"]]
        last_backend_name = str(embedding_payload["backend_name"])
        _upsert_node_embedding(
            session,
            label="SourceDocument",
            key_field="source_id",
            key_value=str(document["source_id"]),
            vector=vector,
            profile_id=profile.profile_id,
            backend_name=last_backend_name,
            routing_mode=str(embedding_payload["routing_mode"]),
            model_id=embedder.model_name,
        )
        _upsert_node_embedding(
            session,
            label="SourceFragment",
            key_field="fragment_id",
            key_value=str(fragment_payload["fragment_id"]),
            vector=vector,
            profile_id=profile.profile_id,
            backend_name=last_backend_name,
            routing_mode=str(embedding_payload["routing_mode"]),
            model_id=embedder.model_name,
        )
        if progress_every > 0 and (index % progress_every == 0 or index == total):
            line = _progress_line(index, total)
            end = "\n" if index == total else "\r"
            print(f"[load_legal_preview] {line}", file=sys.stderr, end=end, flush=True)
    return {
        "mode": "load",
        "write_semantics": "upsert",
        "idempotent_source_layer": True,
        "embedding_profile_id": profile.profile_id,
        "embedding_dimension": profile.dim,
        "effective_embedding_backend": last_backend_name or "unknown",
        "source_document_count": total,
        "source_fragment_count": total,
        "embedded_source_document_count": total,
        "embedded_source_fragment_count": total,
        "by_law": _law_progress_summary(documents),
    }


def verify_documents(
    session,
    law_codes: list[str],
    preview_ranges: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    rows = session.run(
        """
        MATCH (s:SourceDocument)
        WHERE s.law_code IN $law_codes
        OPTIONAL MATCH (s)-[:HAS_FRAGMENT]->(f:SourceFragment)
        RETURN s.law_code AS law_code,
               count(DISTINCT s) AS source_document_count,
               count(DISTINCT f) AS source_fragment_count,
               count(DISTINCT CASE WHEN s.embedding_profile_id IS NOT NULL THEN s END)
                 AS embedded_source_document_count,
               count(DISTINCT CASE WHEN f.embedding_profile_id IS NOT NULL THEN f END)
                 AS embedded_source_fragment_count
        ORDER BY law_code
        """,
        law_codes=law_codes,
    )
    verification: list[dict[str, Any]] = []
    preview_ranges = preview_ranges or {}
    for row in rows:
        item = dict(row)
        range_info = preview_ranges.get(str(item["law_code"]), {})
        item.update(range_info)
        verification.append(item)
    return verification


def verify_embedding_metadata(session, source_ids: list[str]) -> dict[str, Any]:
    row = session.run(
        """
        MATCH (s:SourceDocument)
        WHERE s.source_id IN $source_ids
        OPTIONAL MATCH (f:SourceFragment)
        WHERE f.source_id IN $source_ids
        RETURN collect(DISTINCT s.embedding_profile_id) AS document_profile_ids,
               collect(DISTINCT f.embedding_profile_id) AS fragment_profile_ids,
               collect(DISTINCT size(s.embedding_v1)) AS document_dimensions,
               collect(DISTINCT size(f.embedding_v1)) AS fragment_dimensions,
               collect(DISTINCT s.embedding_backend_used) AS document_backends,
               collect(DISTINCT f.embedding_backend_used) AS fragment_backends
        """,
        source_ids=source_ids,
    ).single()
    if row is None:
        return {}
    document_profile_ids = sorted(
        profile_id for profile_id in row["document_profile_ids"] if profile_id
    )
    fragment_profile_ids = sorted(
        profile_id for profile_id in row["fragment_profile_ids"] if profile_id
    )
    document_dimensions = sorted(
        int(value) for value in row["document_dimensions"] if isinstance(value, (int, float))
    )
    fragment_dimensions = sorted(
        int(value) for value in row["fragment_dimensions"] if isinstance(value, (int, float))
    )
    document_backends = sorted(backend for backend in row["document_backends"] if backend)
    fragment_backends = sorted(backend for backend in row["fragment_backends"] if backend)
    return {
        "document_profile_ids": document_profile_ids,
        "fragment_profile_ids": fragment_profile_ids,
        "document_dimensions": document_dimensions,
        "fragment_dimensions": fragment_dimensions,
        "document_backends": document_backends,
        "fragment_backends": fragment_backends,
    }


def delete_documents(session, source_ids: list[str]) -> dict[str, int]:
    fragment_result = session.run(
        """
        MATCH (f:SourceFragment)
        WHERE f.source_id IN $source_ids
        WITH count(f) AS count
        DETACH DELETE f
        RETURN count
        """,
        source_ids=source_ids,
    ).single()
    source_result = session.run(
        """
        MATCH (s:SourceDocument)
        WHERE s.source_id IN $source_ids
        WITH count(s) AS count
        DETACH DELETE s
        RETURN count
        """,
        source_ids=source_ids,
    ).single()
    return {
        "mode": "delete",
        "deleted_source_fragments": int(fragment_result["count"]) if fragment_result else 0,
        "deleted_source_documents": int(source_result["count"]) if source_result else 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load, verify, or delete legal preview corpus in Neo4j")
    parser.add_argument(
        "--preview",
        default="data/import_preview/legal_xml_import_preview.json",
        help="Path to normalized legal preview JSON",
    )
    parser.add_argument(
        "--mode",
        choices=("load", "verify", "delete"),
        required=True,
        help="Operation to perform",
    )
    parser.add_argument(
        "--law-code",
        action="append",
        dest="law_codes",
        default=[],
        help="Optional law code filter, repeatable",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Emit load progress every N documents; set 0 to disable",
    )
    args = parser.parse_args(argv)

    if GraphDatabase is None:
        raise SystemExit("neo4j driver is not installed. Install project dependencies first.")

    settings = load_settings()
    payload = load_preview_payload(args.preview)
    selected_codes = set(args.law_codes) if args.law_codes else None
    documents = select_documents(payload, selected_codes)
    if not documents:
        raise SystemExit("No documents matched the selected preview corpus or law codes.")

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with driver.session() as session:
            if args.mode == "load":
                result = load_documents(
                    session,
                    documents,
                    settings,
                    progress_every=args.progress_every,
                )
            elif args.mode == "verify":
                law_codes = sorted({str(document["law_code"]) for document in documents})
                preview_ranges = _preview_section_ranges(documents)
                source_ids = [str(document["source_id"]) for document in documents]
                result = {
                    "mode": "verify",
                    "selected_law_codes": law_codes,
                    "verification": verify_documents(session, law_codes, preview_ranges),
                    "embedding_verification": verify_embedding_metadata(session, source_ids),
                }
            else:
                source_ids = [str(document["source_id"]) for document in documents]
                result = delete_documents(session, source_ids)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        driver.close()


if __name__ == "__main__":  # pragma: no cover - CLI helper
    raise SystemExit(main())
