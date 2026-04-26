"""Report builders for load, verify, and delete workflows."""

from __future__ import annotations

from typing import Any

from graph.types import DeletionReport, EmbeddingRunReport, LoadRunReport, VerificationReport
from retrieval.embedding_profile import EmbeddingProfile


def build_load_report(
    preview: dict[str, Any],
    structural_graph: dict[str, list[dict[str, Any]]],
    *,
    law_codes: list[str] | None = None,
) -> LoadRunReport:
    selected_scope = {"law_codes": law_codes or preview.get("source_scope", {}).get("law_codes", [])}
    references = structural_graph.get("legal_references", [])
    return LoadRunReport(
        load_run_id=f"load:{preview.get('preview_id', 'preview')}",
        selected_scope=selected_scope,
        processed_count=len(preview.get("source_fragments", [])),
        source_document_count=len(structural_graph.get("source_documents", [])),
        source_fragment_count=len(structural_graph.get("source_fragments", [])),
        legal_section_count=len(structural_graph.get("legal_sections", [])),
        legal_reference_count=len(references),
        unresolved_reference_count=sum(1 for item in references if item.get("resolution_status") != "resolved"),
    )


def build_verification_report(
    *,
    selected_scope: dict[str, Any],
    counts: dict[str, int],
    embedding: dict[str, Any] | None = None,
) -> VerificationReport:
    embedding = embedding or {}
    return VerificationReport(
        selected_scope=selected_scope,
        source_document_count=counts.get("SourceDocument", 0),
        source_fragment_count=counts.get("SourceFragment", 0),
        legal_act_count=counts.get("LegalAct", 0),
        legal_section_count=counts.get("LegalSection", 0),
        legal_fragment_count=counts.get("LegalFragment", 0),
        legal_reference_count=counts.get("LegalReference", 0),
        unresolved_reference_count=counts.get("UnresolvedLegalReference", 0),
        embedding_count=int(embedding.get("embedding_count", 0) or 0),
        embedding_profile_ids=[item for item in embedding.get("profile_ids", []) if item],
        vector_dimensions=[int(item) for item in embedding.get("vector_dimensions", []) if item],
        backend_names=[item for item in embedding.get("backend_names", []) if item],
        candidate_review_placeholders_present=True,
    )


def build_deletion_report(
    *,
    selected_scope: dict[str, Any],
    matched_records: int,
    removed_records: int | None = None,
    skipped_records: int = 0,
    retained_related_records: int = 0,
) -> DeletionReport:
    return DeletionReport(
        selected_scope=selected_scope,
        matched_records=matched_records,
        removed_records=matched_records if removed_records is None else removed_records,
        skipped_records=skipped_records,
        retained_related_records=retained_related_records,
    )


def build_embedding_run_report(
    *,
    selected_scope: dict[str, Any],
    processed_count: int,
    skipped_count: int,
    failed_count: int,
    profile: EmbeddingProfile,
    backend_name: str,
    failure_reason: str | None = None,
) -> EmbeddingRunReport:
    return EmbeddingRunReport(
        embedding_run_id=f"embedding:{profile.embedding_profile_id}",
        selected_scope=selected_scope,
        embedding_profile_id=profile.embedding_profile_id,
        model_id=profile.model_id,
        backend_name=backend_name,
        routing_mode=profile.routing_mode,
        vector_dimensions=profile.dimensions,
        normalized=profile.normalized,
        processed_count=processed_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        failure_reason=failure_reason,
    )
