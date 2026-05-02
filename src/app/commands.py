"""Thin operator command dispatch for foundation workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.settings import FoundationSettings, load_settings
from graph.client import Neo4jGraphClient
from graph.repositories import GraphDataRepository, GraphFoundationRepository
from graph.types import to_plain_dict
from evaluation.load_cases import (
    build_snapshot_comparison_report,
    write_json_artifact,
)
from ingestion.legal_preview_loader import build_preview_from_manifest_path, write_preview_artifact
from ingestion.verification import build_embedding_run_report
from retrieval.embedding_backend import build_local_embedding_backend
from retrieval.embedding_profile import EmbeddingProfile
from retrieval.embedding_service import EmbeddingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundation")
    subparsers = parser.add_subparsers(dest="group")

    settings_parser = subparsers.add_parser("settings")
    settings_subparsers = settings_parser.add_subparsers(dest="action")
    settings_subparsers.add_parser("validate")

    schema_parser = subparsers.add_parser("schema")
    schema_subparsers = schema_parser.add_subparsers(dest="action")
    schema_subparsers.add_parser("bootstrap")

    preview_parser = subparsers.add_parser("preview")
    preview_subparsers = preview_parser.add_subparsers(dest="action")
    legal_xml_parser = preview_subparsers.add_parser("legal-xml")
    legal_xml_parser.add_argument("--manifest", default=None)
    legal_xml_parser.add_argument("--output", default=None)
    legal_xml_parser.add_argument("--law-code", action="append", dest="law_codes")

    graph_parser = subparsers.add_parser("graph")
    graph_subparsers = graph_parser.add_subparsers(dest="action")
    load_parser = graph_subparsers.add_parser("load")
    load_parser.add_argument("--preview", required=True)
    load_parser.add_argument("--law-code", action="append", dest="law_codes")
    verify_parser = graph_subparsers.add_parser("verify")
    verify_parser.add_argument("--law-code", action="append", dest="law_codes")
    delete_parser = graph_subparsers.add_parser("delete")
    delete_parser.add_argument("--law-code", action="append", required=True, dest="law_codes")
    delete_parser.add_argument("--confirm", action="store_true")
    snapshot_parser = graph_subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--law-code", action="append", dest="law_codes", required=True)
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.add_argument("--read-only-baseline", action="store_true")
    compare_parser = graph_subparsers.add_parser("compare")
    compare_parser.add_argument("--new", required=True)
    compare_parser.add_argument("--baseline", required=True)
    compare_parser.add_argument("--output", required=True)

    references_parser = subparsers.add_parser("references")
    references_subparsers = references_parser.add_subparsers(dest="action")
    resolve_parser = references_subparsers.add_parser("resolve")
    resolve_parser.add_argument("--law-code", required=True)
    resolve_parser.add_argument("--section-reference", required=True)
    resolve_parser.add_argument("--temporal-mode", default="current_default")
    resolve_parser.add_argument("--as-of-date", default="")

    traversal_parser = subparsers.add_parser("traversal")
    traversal_subparsers = traversal_parser.add_subparsers(dest="action")
    run_parser = traversal_subparsers.add_parser("run")
    run_parser.add_argument("--legal-section-id", required=True)
    run_parser.add_argument("--relation-type", action="append", dest="relation_types", default=["CITES"])
    run_parser.add_argument("--depth", type=int, default=1)
    run_parser.add_argument("--fanout", type=int, default=25)
    run_parser.add_argument("--node-limit", type=int, default=100)

    relationships_parser = subparsers.add_parser("relationships")
    relationships_subparsers = relationships_parser.add_subparsers(dest="action")
    refresh_parser = relationships_subparsers.add_parser("refresh")
    refresh_parser.add_argument("--law-code", action="append", required=True, dest="law_codes")
    refresh_parser.add_argument("--classifier-policy", default="legal-ref-context-v1")
    relationship_verify_parser = relationships_subparsers.add_parser("verify")
    relationship_verify_parser.add_argument("--law-code", action="append", required=True, dest="law_codes")
    relationship_verify_parser.add_argument("--classifier-policy", default="")
    quality_parser = relationships_subparsers.add_parser("quality")
    quality_parser.add_argument("--law-code", action="append", required=True, dest="law_codes")
    quality_parser.add_argument("--classifier-policy", default="")
    quality_parser.add_argument("--output", required=True)

    corpus_parser = subparsers.add_parser("corpus")
    corpus_subparsers = corpus_parser.add_subparsers(dest="action")
    readiness_parser = corpus_subparsers.add_parser("readiness")
    readiness_parser.add_argument("--law-code", action="append", required=True, dest="law_codes")
    readiness_parser.add_argument("--output", required=True)

    embeddings_parser = subparsers.add_parser("embeddings")
    embeddings_subparsers = embeddings_parser.add_subparsers(dest="action")
    write_parser = embeddings_subparsers.add_parser("write")
    write_parser.add_argument("--law-code", action="append", required=True, dest="law_codes")

    return parser


def handle_settings_validate(settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    return 0, {
        "status": "valid",
        "configuration": settings.redacted_summary(),
    }


def handle_schema_bootstrap(settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    settings.require_neo4j()
    client = Neo4jGraphClient(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    try:
        report = GraphFoundationRepository(client, database_name=settings.neo4j_database).prepare_foundation(
            embedding_dimensions=settings.embedding_vector_dimensions,
        )
    finally:
        client.close()
    return (0 if report.status == "ready" else 1), to_plain_dict(report)


def handle_preview_legal_xml(args: argparse.Namespace, settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    preview = build_preview_from_manifest_path(
        args.manifest or settings.corpus_manifest_path,
        law_codes=args.law_codes,
    )
    output_path = write_preview_artifact(args.output or settings.preview_output_path, preview)
    return 0, {
        "status": "previewed",
        "preview_artifact_path": str(output_path),
        "source_document_count": len(preview["source_documents"]),
        "source_fragment_count": len(preview["source_fragments"]),
        "missing_inputs": preview["missing_inputs"],
        "preview": preview,
    }


def _graph_client_from_settings(settings: FoundationSettings) -> Neo4jGraphClient:
    settings.require_neo4j()
    return Neo4jGraphClient(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )


def handle_graph_command(args: argparse.Namespace, settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    if args.action == "compare":
        new_snapshot = json.loads(Path(args.new).read_text(encoding="utf-8"))
        baseline_snapshot = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        report = build_snapshot_comparison_report(
            new_snapshot,
            baseline_snapshot,
            notes=[
                "comparison artifacts are file-based",
                "legacy AufenthG baseline graph snapshot remains read-only",
            ],
        )
        output_path = write_json_artifact(args.output, report)
        payload = report.as_dict()
        payload["comparison_artifact_path"] = str(output_path)
        return 0, payload
    client = _graph_client_from_settings(settings)
    try:
        repo = GraphDataRepository(client)
        if args.action == "load":
            preview = json.loads(Path(args.preview).read_text(encoding="utf-8"))
            report = repo.load_preview(preview, law_codes=args.law_codes)
        elif args.action == "verify":
            report = repo.verify_scope(law_codes=args.law_codes)
        elif args.action == "delete":
            report = repo.delete_scope(law_codes=args.law_codes, confirm=args.confirm)
        elif args.action == "snapshot":
            artifact = repo.snapshot_scope(
                law_codes=args.law_codes,
                read_only_baseline=args.read_only_baseline,
            )
            output_path = write_json_artifact(args.output, artifact)
            payload = artifact.as_dict()
            payload["snapshot_artifact_path"] = str(output_path)
            return 0, payload
        else:
            raise ValueError(f"unknown graph action: {args.action}")
    finally:
        client.close()
    return 0, to_plain_dict(report)


def _embedding_profile_from_settings(settings: FoundationSettings) -> EmbeddingProfile:
    return EmbeddingProfile(
        embedding_profile_id=settings.embedding_profile_id,
        provider=settings.embedding_provider,
        model_id=settings.embedding_model_id,
        variant=settings.embedding_variant,
        dimensions=settings.embedding_vector_dimensions,
        normalized=settings.embedding_normalized,
        query_prefix=settings.embedding_query_prefix,
        document_prefix=settings.embedding_document_prefix,
        routing_mode=settings.embedding_routing_mode,
    )


def handle_embeddings_command(args: argparse.Namespace, settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    profile = _embedding_profile_from_settings(settings)
    backend = build_local_embedding_backend(endpoint_url=settings.embedding_endpoint_url, profile=profile)
    client = _graph_client_from_settings(settings)
    try:
        repo = GraphDataRepository(client)
        report = repo.write_embeddings(
            law_codes=args.law_codes,
            embedding_service=EmbeddingService(profile=profile, backend=backend),
        )
    except Exception as exc:
        report = build_embedding_run_report(
            selected_scope={"law_codes": args.law_codes},
            processed_count=0,
            skipped_count=0,
            failed_count=0,
            profile=profile,
            backend_name=backend.backend_name,
            failure_reason=str(exc),
        )
        return 1, to_plain_dict(report)
    finally:
        client.close()
    return 0, to_plain_dict(report)


def handle_references_command(args: argparse.Namespace, settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    client = _graph_client_from_settings(settings)
    try:
        report = GraphDataRepository(client).resolve_reference(
            law_code=args.law_code,
            section_reference=args.section_reference,
            temporal_mode=args.temporal_mode,
            as_of_date=args.as_of_date,
        )
    finally:
        client.close()
    return 0, report.as_dict()


def handle_traversal_command(args: argparse.Namespace, settings: FoundationSettings) -> tuple[int, dict[str, object]]:
    client = _graph_client_from_settings(settings)
    try:
        report = GraphDataRepository(client).traverse(
            legal_section_id=args.legal_section_id,
            allowed_relation_types=args.relation_types,
            depth_limit=args.depth,
            fanout_limit=args.fanout,
            node_limit=args.node_limit,
        )
    finally:
        client.close()
    return 0, report.as_dict()


def handle_relationships_command(
    args: argparse.Namespace,
    settings: FoundationSettings,
    *,
    repository_factory=None,
) -> tuple[int, dict[str, object]]:
    client = None
    if repository_factory is not None:
        repo = repository_factory(settings)
    else:
        client = _graph_client_from_settings(settings)
        repo = GraphDataRepository(client)
    try:
        if args.action == "refresh":
            report = repo.refresh_relationships(
                law_codes=args.law_codes,
                classifier_policy_version=args.classifier_policy,
            )
            return (0 if report.status == "completed" else 1), to_plain_dict(report)
        if args.action == "verify":
            report = repo.verify_relationships(
                law_codes=args.law_codes,
                classifier_policy_version=args.classifier_policy,
            )
            return 0, to_plain_dict(report)
        if args.action == "quality":
            artifact = repo.relationship_quality_artifact(
                law_codes=args.law_codes,
                classifier_policy_version=args.classifier_policy,
            )
            output_path = write_json_artifact(args.output, artifact)
            payload = artifact.as_dict()
            payload["relationship_quality_artifact_path"] = str(output_path)
            return 0, payload
        raise ValueError(f"unknown relationships action: {args.action}")
    finally:
        if client is not None:
            client.close()


def handle_corpus_command(
    args: argparse.Namespace,
    settings: FoundationSettings,
    *,
    repository_factory=None,
) -> tuple[int, dict[str, object]]:
    client = None
    if repository_factory is not None:
        repo = repository_factory(settings)
    else:
        client = _graph_client_from_settings(settings)
        repo = GraphDataRepository(client)
    try:
        if args.action == "readiness":
            artifact = repo.corpus_readiness_artifact(law_codes=args.law_codes)
            output_path = write_json_artifact(args.output, artifact)
            payload = artifact.as_dict()
            payload["corpus_readiness_artifact_path"] = str(output_path)
            return 0, payload
        raise ValueError(f"unknown corpus action: {args.action}")
    finally:
        if client is not None:
            client.close()


def dispatch(
    argv: Sequence[str] | None = None,
    *,
    settings: FoundationSettings | None = None,
    graph_repository_factory=None,
) -> tuple[int, dict[str, object]]:
    parser = build_parser()
    args = parser.parse_args(argv)
    effective_settings = settings or load_settings()
    if args.group == "settings" and args.action == "validate":
        return handle_settings_validate(effective_settings)
    if args.group == "schema" and args.action == "bootstrap":
        return handle_schema_bootstrap(effective_settings)
    if args.group == "preview" and args.action == "legal-xml":
        return handle_preview_legal_xml(args, effective_settings)
    if args.group == "graph":
        return handle_graph_command(args, effective_settings)
    if args.group == "embeddings" and args.action == "write":
        return handle_embeddings_command(args, effective_settings)
    if args.group == "references" and args.action == "resolve":
        return handle_references_command(args, effective_settings)
    if args.group == "traversal" and args.action == "run":
        return handle_traversal_command(args, effective_settings)
    if args.group == "relationships":
        return handle_relationships_command(
            args,
            effective_settings,
            repository_factory=graph_repository_factory,
        )
    if args.group == "corpus":
        return handle_corpus_command(
            args,
            effective_settings,
            repository_factory=graph_repository_factory,
        )
    parser.error("unknown command")
    raise AssertionError("unreachable")


def main(argv: Sequence[str] | None = None) -> int:
    exit_code, payload = dispatch(argv)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code
