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
from evaluation.tg_qa_dataset import (
    build_final_tg_qa_dataset,
    build_tg_qa_dataset_corpus_coverage_report,
    build_tg_qa_manual_review_queue,
    cluster_tg_qa_candidates,
    emit_tg_qa_cluster_llm_batch,
    emit_tg_qa_dataset_corpus_coverage_embedding_batch,
    extract_tg_qa_dataset,
    export_tg_qa_human_review,
    import_tg_qa_embedding_records,
    import_tg_qa_dataset_corpus_coverage_embeddings,
    import_tg_qa_llm_results,
    import_tg_qa_manual_review_decisions,
    filter_tg_qa_llm_batch_by_results,
    merge_final_tg_qa_datasets,
    merge_tg_qa_llm_results,
    run_tg_qa_llm_batch,
    run_tg_qa_similarity,
    select_tg_qa_clusters,
    vectorize_tg_qa_embedding_batch,
    verify_tg_qa_boundaries,
)
from evaluation.tg_question_canonicalization import (
    build_tg_qa_canonicalization_adjudication_batch,
    build_tg_qa_canonicalization_retry_batch_from_adjudication,
    build_tg_qa_canonical_coverage_report,
    build_tg_qa_canonicalization_routing,
    build_tg_qa_issue_final_case_candidates,
    build_tg_qa_legal_intent_equivalence_report,
    build_tg_qa_legal_intent_pair_benchmark,
    build_tg_qa_question_bank,
    build_tg_qa_reviewed_evaluation_dataset,
    cluster_tg_qa_legal_issues,
    emit_tg_qa_canonical_embedding_batch,
    emit_tg_qa_canonicalization_batch,
    export_tg_qa_legal_intent_pair_review_html,
    export_tg_qa_canonicalization_review_cards,
    import_tg_qa_canonical_embedding_records,
    import_tg_qa_canonicalization_results,
    import_tg_qa_canonicalization_review_decisions,
    import_tg_qa_cluster_review_decisions,
    import_tg_qa_legal_intent_candidates,
    import_tg_qa_legal_intent_pair_decisions,
    import_tg_qa_legal_intent_pair_review_labels,
    run_tg_qa_canonicalization_adjudication_batch,
    run_tg_qa_canonicalization_llm_batch,
    run_tg_qa_canonicalization_deepseek_batch,
    run_tg_qa_canonicalization_verifier_batch,
    sample_tg_qa_canonicalization_batch,
    verify_tg_question_canonicalization_boundaries,
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
    tg_qa_parser.add_argument("--candidate-offset", type=int, default=0)
    tg_qa_parser.add_argument("--min-attention-score", type=int, default=6)
    tg_qa_embeddings_parser = evaluation_subparsers.add_parser("tg-qa-embeddings-import")
    tg_qa_embeddings_parser.add_argument("--embedding-batch", required=True)
    tg_qa_embeddings_parser.add_argument("--external-vectors", required=True)
    tg_qa_embeddings_parser.add_argument("--output", required=True)
    tg_qa_embeddings_parser.add_argument("--summary-output", required=True)
    tg_qa_embeddings_parser.add_argument("--embedding-profile-id", default="")
    tg_qa_embeddings_parser.add_argument("--dimensions", type=int, default=0)
    tg_qa_embeddings_parser.add_argument("--model-id", default="")
    tg_qa_embed_batch_parser = evaluation_subparsers.add_parser("tg-qa-embed-batch")
    tg_qa_embed_batch_parser.add_argument("--embedding-batch", required=True)
    tg_qa_embed_batch_parser.add_argument("--output", required=True)
    tg_qa_embed_batch_parser.add_argument("--summary-output", required=True)
    tg_qa_embed_batch_parser.add_argument("--endpoint-url", default="")
    tg_qa_embed_batch_parser.add_argument("--model-id", default="")
    tg_qa_embed_batch_parser.add_argument("--batch-size", type=int, default=16)
    tg_qa_embed_batch_parser.add_argument("--timeout-seconds", type=int, default=60)
    tg_qa_embed_batch_parser.add_argument("--no-progress", action="store_true")
    tg_qa_similarity_parser = evaluation_subparsers.add_parser("tg-qa-similarity")
    tg_qa_similarity_parser.add_argument("--embedding-records", required=True)
    tg_qa_similarity_parser.add_argument("--output", required=True)
    tg_qa_similarity_parser.add_argument("--summary-output", required=True)
    tg_qa_clusters_parser = evaluation_subparsers.add_parser("tg-qa-clusters")
    tg_qa_clusters_parser.add_argument("--candidates", required=True)
    tg_qa_clusters_parser.add_argument("--neighbors", required=True)
    tg_qa_clusters_parser.add_argument("--question-clusters-output", required=True)
    tg_qa_clusters_parser.add_argument("--answer-clusters-output", required=True)
    tg_qa_clusters_parser.add_argument("--qa-clusters-output", required=True)
    tg_qa_clusters_parser.add_argument("--summary-output", required=True)
    tg_qa_selection_parser = evaluation_subparsers.add_parser("tg-qa-selection")
    tg_qa_selection_parser.add_argument("--candidates", required=True)
    tg_qa_selection_parser.add_argument("--qa-clusters", required=True)
    tg_qa_selection_parser.add_argument("--answer-clusters", default="")
    tg_qa_selection_parser.add_argument("--output", required=True)
    tg_qa_selection_parser.add_argument("--summary-output", required=True)
    tg_qa_cluster_llm_parser = evaluation_subparsers.add_parser("tg-qa-cluster-llm-batch")
    tg_qa_cluster_llm_parser.add_argument("--candidates", required=True)
    tg_qa_cluster_llm_parser.add_argument("--selection", required=True)
    tg_qa_cluster_llm_parser.add_argument("--output", required=True)
    tg_qa_cluster_llm_parser.add_argument("--prompt-profile", choices=["full", "compact"], default="full")
    tg_qa_cluster_llm_parser.add_argument("--input-char-budget", type=int, default=0)
    tg_qa_cluster_llm_parser.add_argument("--overflow-output", default="")
    tg_qa_cluster_llm_parser.add_argument("--skip-over-budget", action="store_true")
    tg_qa_cluster_llm_parser.add_argument("--manual-review-overlay", default="")
    tg_qa_llm_run_parser = evaluation_subparsers.add_parser("tg-qa-llm-run")
    tg_qa_llm_run_parser.add_argument("--batch", required=True)
    tg_qa_llm_run_parser.add_argument("--output", required=True)
    tg_qa_llm_run_parser.add_argument("--summary-output", required=True)
    tg_qa_llm_run_parser.add_argument("--endpoint-url", required=True)
    tg_qa_llm_run_parser.add_argument("--model-id", required=True)
    tg_qa_llm_run_parser.add_argument("--llm-run-id", required=True)
    tg_qa_llm_run_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_llm_run_parser.add_argument("--timeout-seconds", type=int, default=120)
    tg_qa_llm_run_parser.add_argument("--max-tokens", type=int, default=512)
    tg_qa_llm_run_parser.add_argument("--no-response-format-json", action="store_true")
    tg_qa_llm_run_parser.add_argument("--reasoning-effort", default="")
    tg_qa_llm_run_parser.add_argument("--thinking-type", choices=["", "disabled", "enabled"], default="")
    tg_qa_llm_run_parser.add_argument("--omit-temperature", action="store_true")
    tg_qa_llm_run_parser.add_argument("--extra-body-json", default="")
    tg_qa_llm_run_parser.add_argument("--runtime-contour", default="operator_managed_llama_server_openai_compatible")
    tg_qa_llm_run_parser.add_argument("--backend", default="llama-server")
    tg_qa_llm_run_parser.add_argument("--model-file", default="")
    tg_qa_llm_run_parser.add_argument("--quantization", default="")
    tg_qa_llm_run_parser.add_argument("--api-key-env", default="")
    tg_qa_llm_run_parser.add_argument("--http-user-agent", default="chat_bot2-evaluation-runner/006")
    tg_qa_llm_run_parser.add_argument("--no-progress", action="store_true")
    tg_qa_llm_import_parser = evaluation_subparsers.add_parser("tg-qa-llm-import")
    tg_qa_llm_import_parser.add_argument("--batch", required=True)
    tg_qa_llm_import_parser.add_argument("--results", required=True)
    tg_qa_llm_import_parser.add_argument("--evidence-output", required=True)
    tg_qa_llm_import_parser.add_argument("--manifest-output", required=True)
    tg_qa_llm_import_parser.add_argument("--llm-run-id", default="")
    tg_qa_llm_import_parser.add_argument("--runtime-summary", default="")
    tg_qa_llm_retry_parser = evaluation_subparsers.add_parser("tg-qa-llm-retry-batch")
    tg_qa_llm_retry_parser.add_argument("--batch", required=True)
    tg_qa_llm_retry_parser.add_argument("--results", required=True)
    tg_qa_llm_retry_parser.add_argument("--output", required=True)
    tg_qa_llm_retry_parser.add_argument("--status", default="failed")
    tg_qa_llm_merge_parser = evaluation_subparsers.add_parser("tg-qa-llm-merge-results")
    tg_qa_llm_merge_parser.add_argument("--primary-results", required=True)
    tg_qa_llm_merge_parser.add_argument("--retry-results", required=True)
    tg_qa_llm_merge_parser.add_argument("--output", required=True)
    tg_qa_review_queue_parser = evaluation_subparsers.add_parser("tg-qa-review-queue")
    tg_qa_review_queue_parser.add_argument("--candidates", required=True)
    tg_qa_review_queue_parser.add_argument("--selection", required=True)
    tg_qa_review_queue_parser.add_argument("--llm-evidence", default="")
    tg_qa_review_queue_parser.add_argument("--output", required=True)
    tg_qa_review_queue_parser.add_argument("--summary-output", required=True)
    tg_qa_review_export_parser = evaluation_subparsers.add_parser("tg-qa-review-export")
    tg_qa_review_export_parser.add_argument("--review-queue", required=True)
    tg_qa_review_export_parser.add_argument("--markdown-output", required=True)
    tg_qa_review_export_parser.add_argument("--tsv-output", required=True)
    tg_qa_review_export_parser.add_argument("--summary-output", required=True)
    tg_qa_review_export_parser.add_argument("--max-text-chars", type=int, default=900)
    tg_qa_review_import_parser = evaluation_subparsers.add_parser("tg-qa-review-import")
    tg_qa_review_import_parser.add_argument("--review-queue", required=True)
    tg_qa_review_import_parser.add_argument("--decisions", required=True)
    tg_qa_review_import_parser.add_argument("--output", required=True)
    tg_qa_review_import_parser.add_argument("--summary-output", required=True)
    tg_qa_final_parser = evaluation_subparsers.add_parser("tg-qa-final")
    tg_qa_final_parser.add_argument("--candidates", required=True)
    tg_qa_final_parser.add_argument("--selection", required=True)
    tg_qa_final_parser.add_argument("--review-decisions", default="")
    tg_qa_final_parser.add_argument("--output", required=True)
    tg_qa_final_parser.add_argument("--manifest-output", required=True)
    tg_qa_final_parser.add_argument("--quality-output", required=True)
    tg_qa_final_merge_parser = evaluation_subparsers.add_parser("tg-qa-final-merge")
    tg_qa_final_merge_parser.add_argument("--cases", nargs="+", required=True)
    tg_qa_final_merge_parser.add_argument("--source-manifests", nargs="*", default=[])
    tg_qa_final_merge_parser.add_argument("--output", required=True)
    tg_qa_final_merge_parser.add_argument("--manifest-output", required=True)
    tg_qa_final_merge_parser.add_argument("--quality-output", required=True)
    tg_qa_coverage_batch_parser = evaluation_subparsers.add_parser("tg-qa-coverage-batch")
    tg_qa_coverage_batch_parser.add_argument("--final-cases", required=True)
    tg_qa_coverage_batch_parser.add_argument("--candidates", required=True)
    tg_qa_coverage_batch_parser.add_argument("--output", required=True)
    tg_qa_coverage_batch_parser.add_argument("--summary-output", required=True)
    tg_qa_coverage_batch_parser.add_argument(
        "--corpus-filter",
        choices=["all", "law_or_topic", "legalish"],
        default="all",
    )
    tg_qa_coverage_batch_parser.add_argument("--skip-corpus-answers", action="store_true")
    tg_qa_coverage_import_parser = evaluation_subparsers.add_parser("tg-qa-coverage-embeddings-import")
    tg_qa_coverage_import_parser.add_argument("--embedding-batch", required=True)
    tg_qa_coverage_import_parser.add_argument("--external-vectors", required=True)
    tg_qa_coverage_import_parser.add_argument("--output", required=True)
    tg_qa_coverage_import_parser.add_argument("--summary-output", required=True)
    tg_qa_coverage_import_parser.add_argument("--embedding-profile-id", default="")
    tg_qa_coverage_import_parser.add_argument("--dimensions", type=int, default=0)
    tg_qa_coverage_import_parser.add_argument("--model-id", default="")
    tg_qa_coverage_report_parser = evaluation_subparsers.add_parser("tg-qa-coverage-report")
    tg_qa_coverage_report_parser.add_argument("--embedding-records", required=True)
    tg_qa_coverage_report_parser.add_argument("--output", required=True)
    tg_qa_coverage_report_parser.add_argument("--summary-output", required=True)
    tg_qa_coverage_report_parser.add_argument("--chunk-size", type=int, default=4096)
    tg_qa_coverage_report_parser.add_argument("--max-samples-per-bucket", type=int, default=20)
    evaluation_subparsers.add_parser("tg-qa-boundary-check")
    tg_qa_canonical_batch_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-batch")
    tg_qa_canonical_batch_parser.add_argument("--candidates", required=True)
    tg_qa_canonical_batch_parser.add_argument("--output", required=True)
    tg_qa_canonical_batch_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_batch_parser.add_argument(
        "--filter-mode",
        choices=["all", "law_or_topic", "legalish"],
        default="all",
    )
    tg_qa_canonical_batch_parser.add_argument("--max-candidates", type=int, default=0)
    tg_qa_canonical_batch_parser.add_argument("--candidate-offset", type=int, default=0)
    tg_qa_canonical_sample_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-sample")
    tg_qa_canonical_sample_parser.add_argument("--batch", required=True)
    tg_qa_canonical_sample_parser.add_argument("--output", required=True)
    tg_qa_canonical_sample_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_sample_parser.add_argument("--sample-size", type=int, default=50)
    tg_qa_canonical_review_cards_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-review-cards")
    tg_qa_canonical_review_cards_parser.add_argument("--batch", required=True)
    tg_qa_canonical_review_cards_parser.add_argument("--html-output", required=True)
    tg_qa_canonical_review_cards_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_review_cards_parser.add_argument("--qwen-results", default="")
    tg_qa_canonical_review_cards_parser.add_argument("--verifier-results", default="")
    tg_qa_canonical_review_cards_parser.add_argument("--max-cards", type=int, default=0)
    tg_qa_canonical_llm_run_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-llm-run")
    tg_qa_canonical_llm_run_parser.add_argument("--batch", required=True)
    tg_qa_canonical_llm_run_parser.add_argument("--output", required=True)
    tg_qa_canonical_llm_run_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_llm_run_parser.add_argument("--endpoint-url", required=True)
    tg_qa_canonical_llm_run_parser.add_argument("--model-id", required=True)
    tg_qa_canonical_llm_run_parser.add_argument("--canonicalization-run-id", required=True)
    tg_qa_canonical_llm_run_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_canonical_llm_run_parser.add_argument("--timeout-seconds", type=int, default=180)
    tg_qa_canonical_llm_run_parser.add_argument("--max-tokens", type=int, default=1200)
    tg_qa_canonical_llm_run_parser.add_argument(
        "--structured-output-method",
        choices=["function_calling", "json_mode", "json_schema"],
        default="json_mode",
    )
    tg_qa_canonical_llm_run_parser.add_argument("--extra-body-json", default="")
    tg_qa_canonical_llm_run_parser.add_argument("--stop-on-failure", action="store_true")
    tg_qa_canonical_llm_run_parser.add_argument("--runtime-contour", default="opencode_go_openai_compatible_chat_completion")
    tg_qa_canonical_llm_run_parser.add_argument("--backend", default="opencode")
    tg_qa_canonical_llm_run_parser.add_argument("--api-key-env", default="")
    tg_qa_canonical_llm_run_parser.add_argument("--provider-max-attempts", type=int, default=3)
    tg_qa_canonical_llm_run_parser.add_argument("--provider-retry-delay-seconds", type=float, default=2.0)
    tg_qa_canonical_llm_run_parser.add_argument("--no-resume", action="store_true")
    tg_qa_canonical_llm_run_parser.add_argument("--no-progress", action="store_true")
    tg_qa_canonical_verifier_run_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-verifier-run")
    tg_qa_canonical_verifier_run_parser.add_argument("--evidence", required=True)
    tg_qa_canonical_verifier_run_parser.add_argument("--output", required=True)
    tg_qa_canonical_verifier_run_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_verifier_run_parser.add_argument("--endpoint-url", required=True)
    tg_qa_canonical_verifier_run_parser.add_argument("--model-id", required=True)
    tg_qa_canonical_verifier_run_parser.add_argument("--verifier-run-id", required=True)
    tg_qa_canonical_verifier_run_parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    tg_qa_canonical_verifier_run_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_canonical_verifier_run_parser.add_argument("--timeout-seconds", type=int, default=180)
    tg_qa_canonical_verifier_run_parser.add_argument("--max-tokens", type=int, default=1024)
    tg_qa_canonical_verifier_run_parser.add_argument(
        "--structured-output-method",
        choices=["function_calling", "json_mode", "json_schema"],
        default="function_calling",
    )
    tg_qa_canonical_verifier_run_parser.add_argument("--extra-body-json", default="")
    tg_qa_canonical_verifier_run_parser.add_argument("--stop-on-failure", action="store_true")
    tg_qa_canonical_verifier_run_parser.add_argument("--runtime-contour", default="minimax_anthropic_compatible_tool_use")
    tg_qa_canonical_verifier_run_parser.add_argument("--backend", default="minimax")
    tg_qa_canonical_verifier_run_parser.add_argument("--api-key-env", default="")
    tg_qa_canonical_verifier_run_parser.add_argument("--provider-max-attempts", type=int, default=3)
    tg_qa_canonical_verifier_run_parser.add_argument("--provider-retry-delay-seconds", type=float, default=2.0)
    tg_qa_canonical_verifier_run_parser.add_argument("--no-resume", action="store_true")
    tg_qa_canonical_verifier_run_parser.add_argument("--no-progress", action="store_true")
    tg_qa_canonical_adjudication_batch_parser = evaluation_subparsers.add_parser(
        "tg-qa-canonicalization-adjudication-batch"
    )
    tg_qa_canonical_adjudication_batch_parser.add_argument("--batch", required=True)
    tg_qa_canonical_adjudication_batch_parser.add_argument(
        "--candidate-results",
        action="append",
        default=[],
        help="Candidate result spec key=path.",
    )
    tg_qa_canonical_adjudication_batch_parser.add_argument(
        "--verifier-results",
        action="append",
        default=[],
        help="Verifier result spec candidate:verifier=path.",
    )
    tg_qa_canonical_adjudication_batch_parser.add_argument("--output", required=True)
    tg_qa_canonical_adjudication_batch_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_adjudication_batch_parser.add_argument("--review-decisions", default="")
    tg_qa_canonical_adjudication_batch_parser.add_argument(
        "--mode",
        choices=["all", "non_unanimous", "unanimous_only"],
        default="non_unanimous",
    )
    tg_qa_canonical_adjudication_batch_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_canonical_adjudication_retry_batch_parser = evaluation_subparsers.add_parser(
        "tg-qa-canonicalization-adjudication-retry-batch"
    )
    tg_qa_canonical_adjudication_retry_batch_parser.add_argument("--batch", required=True)
    tg_qa_canonical_adjudication_retry_batch_parser.add_argument("--adjudication-batch", required=True)
    tg_qa_canonical_adjudication_retry_batch_parser.add_argument(
        "--adjudication-results",
        action="append",
        required=True,
        help="Adjudication result path or key=path. Repeat to pass all judge decisions.",
    )
    tg_qa_canonical_adjudication_retry_batch_parser.add_argument("--output", required=True)
    tg_qa_canonical_adjudication_retry_batch_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_adjudication_retry_batch_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_canonical_adjudication_run_parser = evaluation_subparsers.add_parser(
        "tg-qa-canonicalization-adjudication-run"
    )
    tg_qa_canonical_adjudication_run_parser.add_argument("--batch", required=True)
    tg_qa_canonical_adjudication_run_parser.add_argument("--output", required=True)
    tg_qa_canonical_adjudication_run_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_adjudication_run_parser.add_argument("--endpoint-url", required=True)
    tg_qa_canonical_adjudication_run_parser.add_argument("--model-id", required=True)
    tg_qa_canonical_adjudication_run_parser.add_argument("--adjudication-run-id", required=True)
    tg_qa_canonical_adjudication_run_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_canonical_adjudication_run_parser.add_argument("--timeout-seconds", type=int, default=180)
    tg_qa_canonical_adjudication_run_parser.add_argument("--max-tokens", type=int, default=1024)
    tg_qa_canonical_adjudication_run_parser.add_argument(
        "--structured-output-method",
        choices=["function_calling", "json_mode", "json_schema"],
        default="json_mode",
    )
    tg_qa_canonical_adjudication_run_parser.add_argument("--extra-body-json", default="")
    tg_qa_canonical_adjudication_run_parser.add_argument("--stop-on-failure", action="store_true")
    tg_qa_canonical_adjudication_run_parser.add_argument(
        "--runtime-contour",
        default="opencode_go_openai_compatible_chat_completion",
    )
    tg_qa_canonical_adjudication_run_parser.add_argument("--backend", default="opencode")
    tg_qa_canonical_adjudication_run_parser.add_argument("--api-key-env", default="")
    tg_qa_canonical_adjudication_run_parser.add_argument("--provider", choices=["anthropic", "openai"], default="openai")
    tg_qa_canonical_adjudication_run_parser.add_argument("--provider-max-attempts", type=int, default=3)
    tg_qa_canonical_adjudication_run_parser.add_argument("--provider-retry-delay-seconds", type=float, default=2.0)
    tg_qa_canonical_adjudication_run_parser.add_argument("--no-resume", action="store_true")
    tg_qa_canonical_adjudication_run_parser.add_argument("--no-progress", action="store_true")
    tg_qa_canonical_deepseek_run_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-deepseek-run")
    tg_qa_canonical_deepseek_run_parser.add_argument("--batch", required=True)
    tg_qa_canonical_deepseek_run_parser.add_argument("--output", required=True)
    tg_qa_canonical_deepseek_run_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_deepseek_run_parser.add_argument("--endpoint-url", required=True)
    tg_qa_canonical_deepseek_run_parser.add_argument("--model-id", required=True)
    tg_qa_canonical_deepseek_run_parser.add_argument("--adjudication-run-id", required=True)
    tg_qa_canonical_deepseek_run_parser.add_argument("--max-items", type=int, default=0)
    tg_qa_canonical_deepseek_run_parser.add_argument("--timeout-seconds", type=int, default=180)
    tg_qa_canonical_deepseek_run_parser.add_argument("--max-tokens", type=int, default=1024)
    tg_qa_canonical_deepseek_run_parser.add_argument(
        "--structured-output-method",
        choices=["function_calling", "json_mode", "json_schema"],
        default="json_mode",
    )
    tg_qa_canonical_deepseek_run_parser.add_argument("--extra-body-json", default="")
    tg_qa_canonical_deepseek_run_parser.add_argument("--stop-on-failure", action="store_true")
    tg_qa_canonical_deepseek_run_parser.add_argument(
        "--runtime-contour",
        default="opencode_go_openai_compatible_chat_completion",
    )
    tg_qa_canonical_deepseek_run_parser.add_argument("--backend", default="opencode")
    tg_qa_canonical_deepseek_run_parser.add_argument("--api-key-env", default="")
    tg_qa_canonical_deepseek_run_parser.add_argument("--provider-max-attempts", type=int, default=3)
    tg_qa_canonical_deepseek_run_parser.add_argument("--provider-retry-delay-seconds", type=float, default=2.0)
    tg_qa_canonical_deepseek_run_parser.add_argument("--no-resume", action="store_true")
    tg_qa_canonical_deepseek_run_parser.add_argument("--no-progress", action="store_true")
    tg_qa_canonical_review_decisions_parser = evaluation_subparsers.add_parser(
        "tg-qa-canonicalization-review-decisions-import"
    )
    tg_qa_canonical_review_decisions_parser.add_argument("--batch", required=True)
    tg_qa_canonical_review_decisions_parser.add_argument("--qwen-results", required=True)
    tg_qa_canonical_review_decisions_parser.add_argument("--decisions", required=True)
    tg_qa_canonical_review_decisions_parser.add_argument("--output", required=True)
    tg_qa_canonical_review_decisions_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_review_decisions_parser.add_argument("--verifier-results", default="")
    tg_qa_canonical_routing_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-routing")
    tg_qa_canonical_routing_parser.add_argument("--batch", required=True)
    tg_qa_canonical_routing_parser.add_argument("--qwen-results", required=True)
    tg_qa_canonical_routing_parser.add_argument("--output", required=True)
    tg_qa_canonical_routing_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_routing_parser.add_argument("--review-decisions", default="")
    tg_qa_canonical_routing_parser.add_argument("--verifier-results", default="")
    tg_qa_canonical_routing_parser.add_argument("--decision-ledger-output", default="")
    tg_qa_canonical_routing_parser.add_argument("--retry-qwen-batch-output", default="")
    tg_qa_canonical_routing_parser.add_argument("--send-deepseek-batch-output", default="")
    tg_qa_canonical_routing_parser.add_argument("--backlog-output", default="")
    tg_qa_canonical_import_parser = evaluation_subparsers.add_parser("tg-qa-canonicalization-import")
    tg_qa_canonical_import_parser.add_argument("--batch", required=True)
    tg_qa_canonical_import_parser.add_argument("--results", required=True)
    tg_qa_canonical_import_parser.add_argument("--output", required=True)
    tg_qa_canonical_import_parser.add_argument("--manifest-output", required=True)
    tg_qa_canonical_import_parser.add_argument("--canonicalization-run-id", default="")
    tg_qa_canonical_import_parser.add_argument("--only-results-task-ids", action="store_true")
    tg_qa_canonical_embedding_batch_parser = evaluation_subparsers.add_parser("tg-qa-canonical-embedding-batch")
    tg_qa_canonical_embedding_batch_parser.add_argument("--canonicalization-evidence", required=True)
    tg_qa_canonical_embedding_batch_parser.add_argument("--output", required=True)
    tg_qa_canonical_embedding_batch_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_embedding_import_parser = evaluation_subparsers.add_parser("tg-qa-canonical-embeddings-import")
    tg_qa_canonical_embedding_import_parser.add_argument("--embedding-batch", required=True)
    tg_qa_canonical_embedding_import_parser.add_argument("--external-vectors", required=True)
    tg_qa_canonical_embedding_import_parser.add_argument("--output", required=True)
    tg_qa_canonical_embedding_import_parser.add_argument("--summary-output", required=True)
    tg_qa_canonical_embedding_import_parser.add_argument("--embedding-profile-id", default="")
    tg_qa_canonical_embedding_import_parser.add_argument("--dimensions", type=int, default=0)
    tg_qa_canonical_embedding_import_parser.add_argument("--model-id", default="")
    tg_qa_issue_clusters_parser = evaluation_subparsers.add_parser("tg-qa-issue-clusters")
    tg_qa_issue_clusters_parser.add_argument("--canonicalization-evidence", required=True)
    tg_qa_issue_clusters_parser.add_argument("--embedding-records", default="")
    tg_qa_issue_clusters_parser.add_argument("--output", required=True)
    tg_qa_issue_clusters_parser.add_argument("--summary-output", required=True)
    tg_qa_issue_clusters_parser.add_argument("--manifest-output", default="")
    tg_qa_canonical_coverage_parser = evaluation_subparsers.add_parser("tg-qa-canonical-coverage")
    tg_qa_canonical_coverage_parser.add_argument("--issue-clusters", required=True)
    tg_qa_canonical_coverage_parser.add_argument("--reviewed-final-cases", required=True)
    tg_qa_canonical_coverage_parser.add_argument("--question-bank", default="")
    tg_qa_canonical_coverage_parser.add_argument("--output", required=True)
    tg_qa_canonical_coverage_parser.add_argument("--summary-output", required=True)
    tg_qa_cluster_review_import_parser = evaluation_subparsers.add_parser("tg-qa-cluster-review-import")
    tg_qa_cluster_review_import_parser.add_argument("--issue-clusters", required=True)
    tg_qa_cluster_review_import_parser.add_argument("--decisions", required=True)
    tg_qa_cluster_review_import_parser.add_argument("--output", required=True)
    tg_qa_cluster_review_import_parser.add_argument("--summary-output", required=True)
    tg_qa_question_bank_parser = evaluation_subparsers.add_parser("tg-qa-question-bank-build")
    tg_qa_question_bank_parser.add_argument("--issue-clusters", required=True)
    tg_qa_question_bank_parser.add_argument("--review-decisions", required=True)
    tg_qa_question_bank_parser.add_argument("--output", required=True)
    tg_qa_question_bank_parser.add_argument("--summary-output", required=True)
    tg_qa_question_bank_parser.add_argument("--manifest-output", default="")
    tg_qa_issue_final_candidates_parser = evaluation_subparsers.add_parser("tg-qa-issue-final-candidates")
    tg_qa_issue_final_candidates_parser.add_argument("--question-bank", required=True)
    tg_qa_issue_final_candidates_parser.add_argument("--review-decisions", required=True)
    tg_qa_issue_final_candidates_parser.add_argument("--output", required=True)
    tg_qa_issue_final_candidates_parser.add_argument("--summary-output", required=True)
    tg_qa_issue_final_candidates_parser.add_argument("--manifest-output", default="")
    tg_qa_reviewed_dataset_parser = evaluation_subparsers.add_parser("tg-qa-reviewed-evaluation-dataset-build")
    tg_qa_reviewed_dataset_parser.add_argument("--final-case-candidates", required=True)
    tg_qa_reviewed_dataset_parser.add_argument("--output", required=True)
    tg_qa_reviewed_dataset_parser.add_argument("--manifest-output", required=True)
    tg_qa_reviewed_dataset_parser.add_argument("--quality-output", required=True)
    tg_qa_legal_pair_benchmark_parser = evaluation_subparsers.add_parser("tg-qa-legal-intent-pair-benchmark")
    tg_qa_legal_pair_benchmark_parser.add_argument("--canonicalization-evidence", required=True)
    tg_qa_legal_pair_benchmark_parser.add_argument("--similarity-pairs", default="")
    tg_qa_legal_pair_benchmark_parser.add_argument("--max-random-negatives", type=int, default=0)
    tg_qa_legal_pair_benchmark_parser.add_argument("--output", required=True)
    tg_qa_legal_pair_benchmark_parser.add_argument("--summary-output", required=True)
    tg_qa_legal_intent_import_parser = evaluation_subparsers.add_parser("tg-qa-legal-intent-candidates-import")
    tg_qa_legal_intent_import_parser.add_argument("--canonicalization-evidence", required=True)
    tg_qa_legal_intent_import_parser.add_argument("--candidates", required=True)
    tg_qa_legal_intent_import_parser.add_argument("--output", required=True)
    tg_qa_legal_intent_import_parser.add_argument("--summary-output", required=True)
    tg_qa_legal_pair_decision_import_parser = evaluation_subparsers.add_parser("tg-qa-legal-intent-pair-decisions-import")
    tg_qa_legal_pair_decision_import_parser.add_argument("--pair-benchmark", required=True)
    tg_qa_legal_pair_decision_import_parser.add_argument("--decisions", required=True)
    tg_qa_legal_pair_decision_import_parser.add_argument("--output", required=True)
    tg_qa_legal_pair_decision_import_parser.add_argument("--summary-output", required=True)
    tg_qa_legal_pair_review_parser = evaluation_subparsers.add_parser("tg-qa-legal-intent-pair-review-html")
    tg_qa_legal_pair_review_parser.add_argument("--pair-benchmark", required=True)
    tg_qa_legal_pair_review_parser.add_argument("--pair-decisions", default="")
    tg_qa_legal_pair_review_parser.add_argument("--output", required=True)
    tg_qa_legal_pair_review_parser.add_argument("--summary-output", required=True)
    tg_qa_legal_pair_label_import_parser = evaluation_subparsers.add_parser("tg-qa-legal-intent-pair-labels-import")
    tg_qa_legal_pair_label_import_parser.add_argument("--pair-benchmark", required=True)
    tg_qa_legal_pair_label_import_parser.add_argument("--labels", required=True)
    tg_qa_legal_pair_label_import_parser.add_argument("--output", required=True)
    tg_qa_legal_pair_label_import_parser.add_argument("--summary-output", required=True)
    tg_qa_legal_eval_parser = evaluation_subparsers.add_parser("tg-qa-legal-intent-equivalence-report")
    tg_qa_legal_eval_parser.add_argument("--pair-benchmark", required=True)
    tg_qa_legal_eval_parser.add_argument("--pair-decisions", required=True)
    tg_qa_legal_eval_parser.add_argument("--review-labels", required=True)
    tg_qa_legal_eval_parser.add_argument("--output", required=True)
    tg_qa_legal_eval_parser.add_argument("--summary-output", required=True)
    evaluation_subparsers.add_parser("tg-qa-canonical-boundary-check")

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


def handle_evaluation_command(args: argparse.Namespace, settings: FoundationSettings) -> tuple[int, dict[str, object]]:
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
            candidate_offset=args.candidate_offset,
            min_attention_score=args.min_attention_score,
        )
        payload = dict(result.summary)
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-embeddings-import":
        profile_metadata = {}
        if args.embedding_profile_id:
            profile_metadata["embedding_profile_id"] = args.embedding_profile_id
        if args.dimensions:
            profile_metadata["dimensions"] = args.dimensions
        if args.model_id:
            profile_metadata["model_id"] = args.model_id
        result = import_tg_qa_embedding_records(
            embedding_batch_path=args.embedding_batch,
            external_vectors_path=args.external_vectors,
            output_path=args.output,
            summary_output_path=args.summary_output,
            profile_metadata=profile_metadata or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-embed-batch":
        result = vectorize_tg_qa_embedding_batch(
            embedding_batch_path=args.embedding_batch,
            output_path=args.output,
            summary_output_path=args.summary_output,
            endpoint_url=args.endpoint_url or settings.embedding_endpoint_url,
            model_id=args.model_id or settings.embedding_model_id,
            batch_size=args.batch_size,
            timeout_seconds=args.timeout_seconds,
            progress=not args.no_progress,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-similarity":
        result = run_tg_qa_similarity(
            embedding_records_path=args.embedding_records,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-clusters":
        result = cluster_tg_qa_candidates(
            candidates_path=args.candidates,
            neighbors_path=args.neighbors,
            question_clusters_output_path=args.question_clusters_output,
            answer_clusters_output_path=args.answer_clusters_output,
            qa_clusters_output_path=args.qa_clusters_output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-selection":
        result = select_tg_qa_clusters(
            candidates_path=args.candidates,
            qa_clusters_path=args.qa_clusters,
            answer_clusters_path=args.answer_clusters or None,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-cluster-llm-batch":
        result = emit_tg_qa_cluster_llm_batch(
            candidates_path=args.candidates,
            selection_path=args.selection,
            output_path=args.output,
            prompt_profile=args.prompt_profile,
            input_char_budget=args.input_char_budget,
            overflow_output_path=args.overflow_output or None,
            skip_over_budget=args.skip_over_budget,
            manual_review_path=args.manual_review_overlay or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-llm-run":
        result = run_tg_qa_llm_batch(
            batch_path=args.batch,
            output_path=args.output,
            summary_output_path=args.summary_output,
            endpoint_url=args.endpoint_url,
            model_id=args.model_id,
            llm_run_id=args.llm_run_id,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            response_format_json=not args.no_response_format_json,
            reasoning_effort=args.reasoning_effort,
            thinking_type=args.thinking_type,
            omit_temperature=args.omit_temperature,
            extra_body=json.loads(args.extra_body_json) if args.extra_body_json else None,
            runtime_contour=args.runtime_contour,
            backend=args.backend,
            model_file=args.model_file,
            quantization=args.quantization,
            api_key_env=args.api_key_env,
            http_user_agent=args.http_user_agent,
            progress=not args.no_progress,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-llm-retry-batch":
        result = filter_tg_qa_llm_batch_by_results(
            batch_path=args.batch,
            results_path=args.results,
            output_path=args.output,
            status=args.status,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-llm-merge-results":
        result = merge_tg_qa_llm_results(
            primary_results_path=args.primary_results,
            retry_results_path=args.retry_results,
            output_path=args.output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-llm-import":
        runtime_metadata = (
            json.loads(Path(args.runtime_summary).read_text(encoding="utf-8"))
            if args.runtime_summary
            else None
        )
        result = import_tg_qa_llm_results(
            batch_path=args.batch,
            result_path=args.results,
            evidence_output_path=args.evidence_output,
            manifest_output_path=args.manifest_output,
            llm_run_id=args.llm_run_id,
            runtime_metadata=runtime_metadata,
        )
        payload = dict(result["manifest"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-review-queue":
        result = build_tg_qa_manual_review_queue(
            candidates_path=args.candidates,
            selection_path=args.selection,
            llm_evidence_path=args.llm_evidence or None,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-review-export":
        result = export_tg_qa_human_review(
            review_queue_path=args.review_queue,
            markdown_output_path=args.markdown_output,
            tsv_output_path=args.tsv_output,
            summary_output_path=args.summary_output,
            max_text_chars=args.max_text_chars,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-review-import":
        result = import_tg_qa_manual_review_decisions(
            review_queue_path=args.review_queue,
            decisions_path=args.decisions,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-final":
        result = build_final_tg_qa_dataset(
            candidates_path=args.candidates,
            selection_path=args.selection,
            review_decisions_path=args.review_decisions or None,
            output_path=args.output,
            manifest_output_path=args.manifest_output,
            quality_output_path=args.quality_output,
        )
        payload = dict(result["manifest"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-final-merge":
        result = merge_final_tg_qa_datasets(
            case_paths=args.cases,
            manifest_paths=args.source_manifests or None,
            output_path=args.output,
            manifest_output_path=args.manifest_output,
            quality_output_path=args.quality_output,
        )
        payload = dict(result["manifest"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-coverage-batch":
        result = emit_tg_qa_dataset_corpus_coverage_embedding_batch(
            final_cases_path=args.final_cases,
            candidates_path=args.candidates,
            output_path=args.output,
            summary_output_path=args.summary_output,
            corpus_filter_mode=args.corpus_filter,
            include_corpus_answers=not args.skip_corpus_answers,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-coverage-embeddings-import":
        result = import_tg_qa_dataset_corpus_coverage_embeddings(
            embedding_batch_path=args.embedding_batch,
            external_vectors_path=args.external_vectors,
            output_path=args.output,
            summary_output_path=args.summary_output,
            profile_metadata={
                "embedding_profile_id": args.embedding_profile_id or settings.embedding_profile_id,
                "provider": settings.embedding_provider,
                "model_id": args.model_id or settings.embedding_model_id,
                "variant": settings.embedding_variant,
                "dimensions": args.dimensions or settings.embedding_vector_dimensions,
                "normalized": settings.embedding_normalized,
                "query_prefix": settings.embedding_query_prefix,
                "document_prefix": settings.embedding_document_prefix,
                "routing_mode": settings.embedding_routing_mode,
            },
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-coverage-report":
        result = build_tg_qa_dataset_corpus_coverage_report(
            embedding_records_path=args.embedding_records,
            output_path=args.output,
            summary_output_path=args.summary_output,
            chunk_size=args.chunk_size,
            max_samples_per_bucket=args.max_samples_per_bucket,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-batch":
        result = emit_tg_qa_canonicalization_batch(
            candidates_path=args.candidates,
            output_path=args.output,
            summary_output_path=args.summary_output,
            filter_mode=args.filter_mode,
            max_candidates=args.max_candidates,
            candidate_offset=args.candidate_offset,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-sample":
        result = sample_tg_qa_canonicalization_batch(
            batch_path=args.batch,
            output_path=args.output,
            summary_output_path=args.summary_output,
            sample_size=args.sample_size,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-review-cards":
        result = export_tg_qa_canonicalization_review_cards(
            batch_path=args.batch,
            html_output_path=args.html_output,
            summary_output_path=args.summary_output,
            qwen_results_path=args.qwen_results,
            verifier_results_path=args.verifier_results,
            max_cards=args.max_cards,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-llm-run":
        result = run_tg_qa_canonicalization_llm_batch(
            batch_path=args.batch,
            output_path=args.output,
            summary_output_path=args.summary_output,
            endpoint_url=args.endpoint_url,
            model_id=args.model_id,
            canonicalization_run_id=args.canonicalization_run_id,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            structured_output_method=args.structured_output_method,
            api_key_env=args.api_key_env,
            extra_body=json.loads(args.extra_body_json) if args.extra_body_json else None,
            stop_on_failure=args.stop_on_failure,
            runtime_contour=args.runtime_contour,
            backend=args.backend,
            resume=not args.no_resume,
            provider_max_attempts=args.provider_max_attempts,
            provider_retry_delay_seconds=args.provider_retry_delay_seconds,
            progress=not args.no_progress,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-canonicalization-verifier-run":
        result = run_tg_qa_canonicalization_verifier_batch(
            evidence_path=args.evidence,
            output_path=args.output,
            summary_output_path=args.summary_output,
            endpoint_url=args.endpoint_url,
            model_id=args.model_id,
            verifier_run_id=args.verifier_run_id,
            provider=args.provider,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            structured_output_method=args.structured_output_method,
            api_key_env=args.api_key_env,
            extra_body=json.loads(args.extra_body_json) if args.extra_body_json else None,
            stop_on_failure=args.stop_on_failure,
            runtime_contour=args.runtime_contour,
            backend=args.backend,
            resume=not args.no_resume,
            provider_max_attempts=args.provider_max_attempts,
            provider_retry_delay_seconds=args.provider_retry_delay_seconds,
            progress=not args.no_progress,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-canonicalization-adjudication-batch":
        result = build_tg_qa_canonicalization_adjudication_batch(
            batch_path=args.batch,
            candidate_result_specs=args.candidate_results,
            verifier_result_specs=args.verifier_results,
            output_path=args.output,
            summary_output_path=args.summary_output,
            review_decisions_path=args.review_decisions or None,
            mode=args.mode,
            max_items=args.max_items,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-adjudication-retry-batch":
        result = build_tg_qa_canonicalization_retry_batch_from_adjudication(
            batch_path=args.batch,
            adjudication_batch_path=args.adjudication_batch,
            adjudication_results_paths=args.adjudication_results,
            output_path=args.output,
            summary_output_path=args.summary_output,
            max_items=args.max_items,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-adjudication-run":
        result = run_tg_qa_canonicalization_adjudication_batch(
            batch_path=args.batch,
            output_path=args.output,
            summary_output_path=args.summary_output,
            endpoint_url=args.endpoint_url,
            model_id=args.model_id,
            adjudication_run_id=args.adjudication_run_id,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            structured_output_method=args.structured_output_method,
            api_key_env=args.api_key_env,
            provider=args.provider,
            extra_body=json.loads(args.extra_body_json) if args.extra_body_json else None,
            stop_on_failure=args.stop_on_failure,
            runtime_contour=args.runtime_contour,
            backend=args.backend,
            resume=not args.no_resume,
            provider_max_attempts=args.provider_max_attempts,
            provider_retry_delay_seconds=args.provider_retry_delay_seconds,
            progress=not args.no_progress,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-canonicalization-deepseek-run":
        result = run_tg_qa_canonicalization_deepseek_batch(
            batch_path=args.batch,
            output_path=args.output,
            summary_output_path=args.summary_output,
            endpoint_url=args.endpoint_url,
            model_id=args.model_id,
            adjudication_run_id=args.adjudication_run_id,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            structured_output_method=args.structured_output_method,
            api_key_env=args.api_key_env,
            extra_body=json.loads(args.extra_body_json) if args.extra_body_json else None,
            stop_on_failure=args.stop_on_failure,
            runtime_contour=args.runtime_contour,
            backend=args.backend,
            resume=not args.no_resume,
            provider_max_attempts=args.provider_max_attempts,
            provider_retry_delay_seconds=args.provider_retry_delay_seconds,
            progress=not args.no_progress,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-canonicalization-review-decisions-import":
        result = import_tg_qa_canonicalization_review_decisions(
            batch_path=args.batch,
            qwen_results_path=args.qwen_results,
            decisions_path=args.decisions,
            output_path=args.output,
            summary_output_path=args.summary_output,
            verifier_results_path=args.verifier_results or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-canonicalization-routing":
        result = build_tg_qa_canonicalization_routing(
            batch_path=args.batch,
            qwen_results_path=args.qwen_results,
            output_path=args.output,
            summary_output_path=args.summary_output,
            review_decisions_path=args.review_decisions or None,
            verifier_results_path=args.verifier_results or None,
            decision_ledger_output_path=args.decision_ledger_output or None,
            retry_qwen_batch_output_path=args.retry_qwen_batch_output or None,
            send_deepseek_batch_output_path=args.send_deepseek_batch_output or None,
            backlog_output_path=args.backlog_output or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonicalization-import":
        result = import_tg_qa_canonicalization_results(
            batch_path=args.batch,
            result_path=args.results,
            output_path=args.output,
            manifest_output_path=args.manifest_output,
            canonicalization_run_id=args.canonicalization_run_id,
            only_results_task_ids=args.only_results_task_ids,
        )
        payload = dict(result["manifest"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-canonical-embedding-batch":
        result = emit_tg_qa_canonical_embedding_batch(
            canonicalization_evidence_path=args.canonicalization_evidence,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonical-embeddings-import":
        result = import_tg_qa_canonical_embedding_records(
            embedding_batch_path=args.embedding_batch,
            external_vectors_path=args.external_vectors,
            output_path=args.output,
            summary_output_path=args.summary_output,
            profile_metadata={
                "embedding_profile_id": args.embedding_profile_id or settings.embedding_profile_id,
                "provider": settings.embedding_provider,
                "model_id": args.model_id or settings.embedding_model_id,
                "variant": settings.embedding_variant,
                "dimensions": args.dimensions or settings.embedding_vector_dimensions,
                "normalized": settings.embedding_normalized,
                "query_prefix": settings.embedding_query_prefix,
                "document_prefix": settings.embedding_document_prefix,
                "routing_mode": settings.embedding_routing_mode,
            },
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-issue-clusters":
        result = cluster_tg_qa_legal_issues(
            canonicalization_evidence_path=args.canonicalization_evidence,
            embedding_records_path=args.embedding_records or None,
            output_path=args.output,
            summary_output_path=args.summary_output,
            manifest_output_path=args.manifest_output or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-canonical-coverage":
        result = build_tg_qa_canonical_coverage_report(
            issue_clusters_path=args.issue_clusters,
            reviewed_final_cases_path=args.reviewed_final_cases,
            question_bank_path=args.question_bank or None,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-cluster-review-import":
        result = import_tg_qa_cluster_review_decisions(
            issue_clusters_path=args.issue_clusters,
            decisions_path=args.decisions,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-question-bank-build":
        result = build_tg_qa_question_bank(
            issue_clusters_path=args.issue_clusters,
            review_decisions_path=args.review_decisions,
            output_path=args.output,
            summary_output_path=args.summary_output,
            manifest_output_path=args.manifest_output or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-issue-final-candidates":
        result = build_tg_qa_issue_final_case_candidates(
            question_bank_path=args.question_bank,
            review_decisions_path=args.review_decisions,
            output_path=args.output,
            summary_output_path=args.summary_output,
            manifest_output_path=args.manifest_output or None,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-reviewed-evaluation-dataset-build":
        result = build_tg_qa_reviewed_evaluation_dataset(
            final_case_candidates_path=args.final_case_candidates,
            output_path=args.output,
            manifest_output_path=args.manifest_output,
            quality_output_path=args.quality_output,
        )
        payload = dict(result["manifest"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-legal-intent-pair-benchmark":
        result = build_tg_qa_legal_intent_pair_benchmark(
            canonicalization_evidence_path=args.canonicalization_evidence,
            similarity_pairs_path=args.similarity_pairs or None,
            max_random_negatives=args.max_random_negatives,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-legal-intent-candidates-import":
        result = import_tg_qa_legal_intent_candidates(
            canonicalization_evidence_path=args.canonicalization_evidence,
            candidates_path=args.candidates,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-legal-intent-pair-decisions-import":
        result = import_tg_qa_legal_intent_pair_decisions(
            pair_benchmark_path=args.pair_benchmark,
            decisions_path=args.decisions,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-legal-intent-pair-review-html":
        result = export_tg_qa_legal_intent_pair_review_html(
            pair_benchmark_path=args.pair_benchmark,
            pair_decisions_path=args.pair_decisions or None,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-legal-intent-pair-labels-import":
        result = import_tg_qa_legal_intent_pair_review_labels(
            pair_benchmark_path=args.pair_benchmark,
            labels_path=args.labels,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed" if payload.get("failed_count") == 0 else "completed_with_failures"
        return 0, payload
    if args.action == "tg-qa-legal-intent-equivalence-report":
        result = build_tg_qa_legal_intent_equivalence_report(
            pair_benchmark_path=args.pair_benchmark,
            pair_decisions_path=args.pair_decisions,
            review_labels_path=args.review_labels,
            output_path=args.output,
            summary_output_path=args.summary_output,
        )
        payload = dict(result["summary"])
        payload["status"] = "completed"
        return 0, payload
    if args.action == "tg-qa-boundary-check":
        payload = verify_tg_qa_boundaries()
        return (0 if payload["status"] == "passed" else 1), payload
    if args.action == "tg-qa-canonical-boundary-check":
        payload = verify_tg_question_canonicalization_boundaries()
        return (0 if payload["status"] == "passed" else 1), payload
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
        return handle_evaluation_command(args, effective_settings)
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
