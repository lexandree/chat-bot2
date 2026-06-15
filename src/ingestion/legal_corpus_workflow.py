"""Offline validation helpers for controlled legal-corpus expansion."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from graph.types import CLASSIFIER_POLICY_VERSION
from ingestion.legal_preview_loader import (
    build_preview_from_manifest_path,
    load_manifest,
    write_preview_artifact,
)
from ingestion.legal_structure_builder import build_relationship_evidence_from_preview


def build_new_law_preflight(
    *,
    manifest_path: str | Path,
    new_law_code: str,
    preview_output_path: str | Path,
    classifier_policy_version: str = CLASSIFIER_POLICY_VERSION,
) -> dict[str, Any]:
    """Validate an active-corpus manifest and build cross-corpus relationship evidence offline."""

    manifest = load_manifest(manifest_path)
    active_law_codes = _active_manifest_law_codes(manifest)
    if new_law_code not in active_law_codes:
        raise ValueError(f"new law code is absent from active corpus manifest: {new_law_code}")

    preview = build_preview_from_manifest_path(manifest_path, law_codes=active_law_codes)
    if preview.get("missing_inputs"):
        raise ValueError("active corpus manifest contains missing optional inputs")
    write_preview_artifact(preview_output_path, preview)

    fragment_counts = Counter(
        str(item.get("law_code", ""))
        for item in preview.get("source_fragments", [])
        if item.get("law_code")
    )
    if fragment_counts.get(new_law_code, 0) == 0:
        raise ValueError(f"new law has no parsed source fragments: {new_law_code}")

    relationships = build_relationship_evidence_from_preview(
        preview,
        law_codes=active_law_codes,
        classifier_policy_version=classifier_policy_version,
    )
    incoming = [
        item
        for item in relationships
        if str(item.get("target_law_code", "")) == new_law_code
        and str(item.get("law_code", "")) != new_law_code
    ]
    outgoing = [item for item in relationships if str(item.get("law_code", "")) == new_law_code]
    unresolved_incoming = [
        item for item in incoming if str(item.get("resolution_status", "")) != "resolved"
    ]

    return {
        "artifact_type": "legal_corpus_new_law_preflight",
        "status": "ready" if not unresolved_incoming else "needs_review",
        "manifest_path": str(manifest_path),
        "preview_output_path": str(preview_output_path),
        "preview_id": str(preview.get("preview_id", "")),
        "new_law_code": new_law_code,
        "active_law_codes": active_law_codes,
        "source_document_count": len(preview.get("source_documents", [])),
        "source_fragment_count": len(preview.get("source_fragments", [])),
        "source_fragment_counts_by_law_code": dict(sorted(fragment_counts.items())),
        "relationship_reference_count": len(relationships),
        "counts_by_resolution_status": _counts(relationships, "resolution_status"),
        "counts_by_unresolved_reason": _counts(relationships, "unresolved_reason", include_empty=False),
        "new_law_incoming_reference_count": len(incoming),
        "new_law_resolved_incoming_reference_count": sum(
            str(item.get("resolution_status", "")) == "resolved" for item in incoming
        ),
        "new_law_unresolved_incoming_reference_count": len(unresolved_incoming),
        "new_law_full_name_alias_reference_count": sum(
            new_law_code not in str(item.get("raw_reference_text", "")) for item in incoming
        ),
        "new_law_outgoing_reference_count": len(outgoing),
        "new_law_incoming_reference_samples": [
            _reference_sample(item) for item in incoming[:10]
        ],
        "new_law_unresolved_incoming_reference_samples": [
            _reference_sample(item) for item in unresolved_incoming[:10]
        ],
        "classifier_policy_version": classifier_policy_version,
        "graph_writes_performed": False,
        "known_limitations": [
            "preflight validates files, parsing, and in-memory relationship resolution only",
            "live graph state, embedding backend, and graph writes are checked by later guarded stages",
            "the structural parser can resolve only the reference items it extracts from lists or ranges",
            "semantic retrieval artifacts must be rebuilt separately after corpus expansion",
        ],
    }


def _active_manifest_law_codes(manifest: dict[str, Any]) -> list[str]:
    inputs = manifest.get("inputs", [])
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("active corpus manifest must contain at least one input")

    law_codes: list[str] = []
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("active corpus manifest inputs must be objects")
        law_code = str(item.get("law_code", "")).strip()
        if not law_code:
            raise ValueError("active corpus manifest input is missing law_code")
        if not bool(item.get("required", True)):
            raise ValueError(f"active corpus manifest inputs must be required: {law_code}")
        law_codes.append(law_code)

    duplicates = sorted(code for code, count in Counter(law_codes).items() if count > 1)
    if duplicates:
        raise ValueError(f"active corpus manifest contains duplicate law codes: {duplicates}")
    return sorted(law_codes)


def _counts(records: list[dict[str, Any]], field: str, *, include_empty: bool = True) -> dict[str, int]:
    values = (
        str(item.get(field, ""))
        for item in records
        if include_empty or str(item.get(field, ""))
    )
    return dict(sorted(Counter(values).items()))


def _reference_sample(record: dict[str, Any]) -> dict[str, str]:
    return {
        "source_legal_section_id": str(record.get("source_legal_section_id", "")),
        "source_law_code": str(record.get("law_code", "")),
        "raw_reference_text": str(record.get("raw_reference_text", "")),
        "target_law_code": str(record.get("target_law_code", "")),
        "target_section_reference": str(record.get("target_section_reference", "")),
        "target_legal_section_id": str(record.get("target_legal_section_id", "")),
        "resolution_status": str(record.get("resolution_status", "")),
        "unresolved_reason": str(record.get("unresolved_reason", "")),
    }
