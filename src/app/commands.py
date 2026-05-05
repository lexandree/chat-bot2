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
from evaluation.tg_qa_dataset import extract_tg_qa_dataset
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
    neighborhood_parser = traversal_subparsers.add_parser("neighborhood")
    neighborhood_parser.add_argument(
        "--workflow-mode",
        choices=["seed_neighborhood", "law_scope_overview"],
        required=True,
    )
    neighborhood_parser.add_argument("--law-code", action="append", dest="law_codes")
    neighborhood_parser.add_argument("--seed-section-id", action="append", dest="seed_section_ids")
    neighborhood_parser.add_argument("--relation-type", action="append", dest="relation_types", required=True)
    neighborhood_parser.add_argument("--direction", choices=["outgoing", "incoming", "both"], default="outgoing")
    neighborhood_parser.add_argument("--depth", type=int, default=1)
    neighborhood_parser.add_argument("--fanout", type=int, default=25)
    neighborhood_parser.add_argument("--node-limit", type=int, default=100)
    neighborhood_parser.add_argument("--edge-limit", type=int, default=500)
    neighborhood_parser.add_argument("--source-sample-limit", type=int, default=5)
    neighborhood_parser.add_argument("--output", required=True)
    neighborhood_parser.add_argument("--missing-target-inventory", default="")
    neighborhood_parser.add_argument("--source-relationship-quality-artifact", default="")
    neighborhood_parser.add_argument("--include-boundary-stops", action="store_true", default=True)
    neighborhood_parser.add_argument("--include-inactive-sections", action="store_true", default=True)

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

    evaluation_parser = subparsers.add_parser("evaluation")
    evaluation_subparsers = evaluation_parser.add_subparsers(dest="action")
    tg_qa_parser = evaluation_subparsers.add_parser("tg-qa")
    tg_qa_parser.add_argument("--input", action="append", dest="inputs", required=True)
    tg_qa_parser.add_argument("--bot-catalog", default="")
    tg_qa_parser.add_argument("--output", required=True)
    tg_qa_parser.add_argument("--summary-output", required=True)
    tg_qa_parser.add_argument("--embedding-batch-output", default="")
    tg_qa_parser.add_argument("--llm-batch-output", default="")
    tg_qa_parser.add_argument("--max-messages-per-export", type=int, default=0)
    tg_qa_parser.add_argument("--max-candidates", type=int, default=500)
    tg_qa_parser.add_argument("--min-attention-score", type=int, default=6)

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


def handle_traversal_command(
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
        if args.action == "run":
            report = repo.traverse(
                legal_section_id=args.legal_section_id,
                allowed_relation_types=args.relation_types,
                depth_limit=args.depth,
                fanout_limit=args.fanout,
                node_limit=args.node_limit,
            )
            return 0, report.as_dict()
        if args.action == "neighborhood":
            inventory_reference = _missing_target_inventory_reference(
                args.missing_target_inventory,
                law_codes=args.law_codes or [],
            )
            artifact = repo.structural_workflow_artifact(
                workflow_mode=args.workflow_mode,
                seed_legal_section_ids=args.seed_section_ids or [],
                law_codes=args.law_codes or [],
                allowed_relation_types=args.relation_types,
                direction=args.direction,
                max_depth=args.depth,
                fanout_limit=args.fanout,
                node_limit=args.node_limit,
                edge_limit=args.edge_limit,
                source_sample_limit=args.source_sample_limit,
                include_boundary_stops=args.include_boundary_stops,
                include_inactive_sections=args.include_inactive_sections,
                missing_target_inventory_reference=inventory_reference,
                source_relationship_quality_artifact=args.source_relationship_quality_artifact,
            )
            output_path = write_json_artifact(args.output, artifact)
            payload = _structural_workflow_cli_payload(artifact.as_dict(), output_path)
            return 0, payload
        raise ValueError(f"unknown traversal action: {args.action}")
    finally:
        if client is not None:
            client.close()


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


def handle_evaluation_command(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    if args.action == "tg-qa":
        result = extract_tg_qa_dataset(
            input_paths=args.inputs,
            bot_catalog_path=args.bot_catalog or None,
            output_path=args.output,
            summary_output_path=args.summary_output,
            embedding_batch_output_path=args.embedding_batch_output or None,
            llm_batch_output_path=args.llm_batch_output or None,
            max_messages_per_export=args.max_messages_per_export,
            max_candidates=args.max_candidates,
            min_attention_score=args.min_attention_score,
        )
        payload = dict(result.summary)
        payload["status"] = "completed"
        return 0, payload
    raise ValueError(f"unknown evaluation action: {args.action}")


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
    if args.group == "traversal":
        return handle_traversal_command(
            args,
            effective_settings,
            repository_factory=graph_repository_factory,
        )
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
    if args.group == "evaluation":
        return handle_evaluation_command(args)
    parser.error("unknown command")
    raise AssertionError("unreachable")


def main(argv: Sequence[str] | None = None) -> int:
    exit_code, payload = dispatch(argv)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


def _missing_target_inventory_reference(path: str, *, law_codes: list[str]) -> dict[str, object]:
    if not path:
        return {"status": "not_provided", "path": "", "law_codes": law_codes, "targets": []}
    inventory_path = Path(path)
    if not inventory_path.exists():
        return {"status": "missing_file", "path": str(inventory_path), "law_codes": law_codes, "targets": []}
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "stale", "path": str(inventory_path), "law_codes": law_codes, "targets": []}
    selected_scope = payload.get("selected_scope", {}) if isinstance(payload, dict) else {}
    inventory_law_codes = selected_scope.get("law_codes", []) if isinstance(selected_scope, dict) else []
    if not inventory_law_codes and isinstance(payload, dict):
        inventory_law_codes = payload.get("law_codes", [])
    targets = []
    if isinstance(payload, dict):
        raw_targets = (
            payload.get("items")
            or payload.get("top_missing_targets")
            or payload.get("targets")
            or payload.get("missing_targets")
            or []
        )
        if isinstance(raw_targets, list):
            for item in raw_targets:
                if not isinstance(item, dict):
                    continue
                targets.append(
                    {
                        "reason": item.get("reason") or item.get("unresolved_reason") or "missing_target_in_corpus",
                        "target_law_code": item.get("target_law_code", ""),
                        "target_section_reference": item.get("target_section_reference", ""),
                    }
                )
    return {
        "status": "available",
        "path": str(inventory_path),
        "generated_at": payload.get("generated_at", "") if isinstance(payload, dict) else "",
        "law_codes": inventory_law_codes or law_codes,
        "targets": targets,
    }


def _structural_workflow_cli_payload(artifact: dict[str, object], output_path: Path) -> dict[str, object]:
    summary = artifact.get("quality_summary", {})
    summary = summary if isinstance(summary, dict) else {}
    return {
        "status": "completed",
        "workflow_mode": artifact.get("workflow_request", {}).get("workflow_mode", "")
        if isinstance(artifact.get("workflow_request"), dict)
        else "",
        "structural_workflow_artifact_path": str(output_path),
        "selected_scope": artifact.get("selected_scope", {}),
        "visited_section_count": summary.get("visited_section_count", 0),
        "resolved_edge_count": summary.get("resolved_edge_count", 0),
        "boundary_stop_count": summary.get("boundary_stop_count", 0),
        "boundary_stops_by_reason": summary.get("boundary_stops_by_reason", {}),
        "missing_target_inventory_status": summary.get("missing_target_inventory_status", "not_provided"),
        "warnings": artifact.get("warnings", []),
    }
