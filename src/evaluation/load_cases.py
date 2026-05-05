"""Report serialization and snapshot-comparison helpers."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from graph.types import (
    CorpusReadinessArtifact,
    DEFERRED_RELATION_TYPES,
    GraphSnapshotArtifact,
    INVENTORY_MATCH_STATUSES,
    LegacyAufenthGBaselineGraphSnapshotArtifact,
    MISSING_TARGET_INVENTORY_STATUSES,
    RELATION_TYPES,
    RESOLUTION_STATUSES,
    RelationshipQualityArtifact,
    STRUCTURE_CLASSES,
    STRUCTURE_CLASS_RULES_VERSION,
    STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS,
    STRUCTURAL_WORKFLOW_DIRECTIONS,
    STRUCTURAL_WORKFLOW_MAX_BOUNDS,
    STRUCTURAL_WORKFLOW_MODES,
    STRUCTURAL_WORKFLOW_SECTION_ROLES,
    StructuralWorkflowArtifact,
    StructuralWorkflowRequest,
    TARGET_UNIT_STATUSES,
    TEMPORAL_EVIDENCE_STATUSES,
    UNIT_STATUSES,
    UNRESOLVED_REASONS,
    SnapshotComparisonReport,
    to_plain_dict,
)


FORBIDDEN_ANSWER_FIELDS = {"answer_text", "answer", "generated_answer"}
SNAPSHOT_SECTIONS = (
    "counts",
    "labels",
    "relation_types",
    "sample_ids",
    "source_coverage",
    "embedding_profile_metadata",
    "unresolved_reference_evidence",
)


def to_artifact_dict(record: Any) -> dict[str, Any]:
    payload = to_plain_dict(record)
    if not isinstance(payload, dict):
        raise TypeError("artifact payload must be a mapping")
    return payload


def ensure_no_answer_fields(payload: Mapping[str, Any]) -> None:
    present = _find_forbidden_answer_fields(payload)
    if present:
        raise ValueError(f"structural retrieval artifact contains forbidden answer fields: {sorted(present)}")


def structural_retrieval_artifact(record: Any) -> dict[str, Any]:
    payload = to_artifact_dict(record)
    ensure_no_answer_fields(payload)
    return payload


def relationship_quality_artifact(record: Any) -> dict[str, Any]:
    payload = to_artifact_dict(record)
    ensure_no_answer_fields(payload)
    return payload


def corpus_readiness_artifact(record: Any) -> dict[str, Any]:
    payload = to_artifact_dict(record)
    ensure_no_answer_fields(payload)
    return payload


def structural_workflow_artifact(record: Any) -> dict[str, Any]:
    payload = to_artifact_dict(record)
    ensure_no_answer_fields(payload)
    return payload


def build_relationship_quality_artifact(
    *,
    selected_scope: dict[str, Any],
    classifier_policy_version: str,
    generated_at: str,
    counts_by_relation_type: dict[str, int],
    counts_by_resolution_status: dict[str, int],
    sample_edges_by_relation_type: dict[str, list[dict[str, Any]]],
    sample_reference_evidence: list[dict[str, Any]],
    top_unresolved_targets: list[dict[str, Any]],
    source_to_relation_coverage: dict[str, Any],
    fanout_summary: dict[str, Any],
    temporal_metadata_completeness: dict[str, Any],
    counts_by_source_unit_status: dict[str, int] | None = None,
    counts_by_target_unit_status: dict[str, int] | None = None,
    counts_by_unresolved_reason: dict[str, int] | None = None,
    top_missing_targets: list[dict[str, Any]] | None = None,
    deferred_relation_strategy: dict[str, Any] | None = None,
) -> RelationshipQualityArtifact:
    normalized_payload = {
        "selected_scope": _sorted_mapping(selected_scope),
        "classifier_policy_version": classifier_policy_version,
        "counts_by_relation_type": _complete_counts(counts_by_relation_type, RELATION_TYPES),
        "counts_by_source_unit_status": _complete_counts(counts_by_source_unit_status or {}, UNIT_STATUSES),
        "counts_by_target_unit_status": _complete_counts(counts_by_target_unit_status or {}, TARGET_UNIT_STATUSES),
        "counts_by_resolution_status": _complete_counts(counts_by_resolution_status, RESOLUTION_STATUSES),
        "counts_by_unresolved_reason": _complete_counts(counts_by_unresolved_reason or {}, UNRESOLVED_REASONS),
        "sample_edges_by_relation_type": _normalize_samples_by_relation(sample_edges_by_relation_type),
        "sample_reference_evidence": _normalize_sample_list(sample_reference_evidence),
        "top_unresolved_targets": _normalize_sample_list(top_unresolved_targets),
        "top_missing_targets": _normalize_top_missing_targets(top_missing_targets or []),
        "source_to_relation_coverage": _sorted_mapping(source_to_relation_coverage),
        "fanout_summary": _sorted_mapping(fanout_summary),
        "temporal_metadata_completeness": _normalize_temporal_completeness(
            temporal_metadata_completeness,
            selected_scope=selected_scope,
        ),
        "deferred_relation_strategy": _deferred_relation_strategy(deferred_relation_strategy),
    }
    ensure_no_answer_fields(normalized_payload)
    artifact_id = _stable_digest(normalized_payload, prefix="relationship-quality")
    return RelationshipQualityArtifact(
        artifact_id=artifact_id,
        generated_at=generated_at,
        **normalized_payload,
    )


def build_corpus_readiness_artifact(
    *,
    selected_scope: dict[str, Any],
    generated_at: str,
    counts_by_unit_status: dict[str, int],
    counts_by_structure_class: dict[str, int],
    active_unit_samples: list[dict[str, Any]],
    inactive_unit_samples: list[dict[str, Any]],
    complexity_summary: dict[str, Any],
    excluded_semantic_candidates: dict[str, Any] | None = None,
    structure_class_rules_version: str = STRUCTURE_CLASS_RULES_VERSION,
) -> CorpusReadinessArtifact:
    normalized_payload = {
        "selected_scope": _sorted_mapping(selected_scope),
        "structure_class_rules_version": structure_class_rules_version,
        "counts_by_unit_status": _complete_counts(counts_by_unit_status, UNIT_STATUSES),
        "counts_by_structure_class": _complete_counts(counts_by_structure_class, STRUCTURE_CLASSES),
        "active_unit_samples": _normalize_sample_list(active_unit_samples),
        "inactive_unit_samples": _normalize_sample_list(inactive_unit_samples),
        "complexity_summary": _sorted_mapping(
            {
                "structure_class_rules_version": structure_class_rules_version,
                **dict(complexity_summary),
            }
        ),
        "excluded_semantic_candidates": _sorted_mapping(
            excluded_semantic_candidates
            or {
                "LegalNorm": 0,
                "Condition": 0,
                "LegalEffect": 0,
                "Exception": 0,
            }
        ),
    }
    ensure_no_answer_fields(normalized_payload)
    artifact_id = _stable_digest(normalized_payload, prefix="corpus-readiness")
    return CorpusReadinessArtifact(
        artifact_id=artifact_id,
        generated_at=generated_at,
        **normalized_payload,
    )


def build_structural_workflow_artifact(
    *,
    workflow_request: StructuralWorkflowRequest | Mapping[str, Any],
    generated_at: str,
    sections: list[dict[str, Any]],
    resolved_edges: list[dict[str, Any]],
    unresolved_references: list[dict[str, Any]] | None = None,
    selected_scope: dict[str, Any] | None = None,
    traversal_metadata: dict[str, Any] | None = None,
    missing_target_inventory_reference: dict[str, Any] | None = None,
    source_relationship_quality_artifact: str = "",
    warnings: list[str] | None = None,
) -> StructuralWorkflowArtifact:
    ensure_no_answer_fields(
        {
            "workflow_request": to_plain_dict(workflow_request),
            "sections": sections,
            "resolved_edges": resolved_edges,
            "unresolved_references": unresolved_references or [],
            "missing_target_inventory_reference": missing_target_inventory_reference or {},
        }
    )
    request = _normalize_workflow_request(workflow_request)
    scope = _normalize_workflow_scope(selected_scope, request)
    inventory_reference = _normalize_inventory_reference(missing_target_inventory_reference, scope)
    normalized_sections, section_truncations = _normalize_workflow_sections(
        sections,
        node_limit=int(request["node_limit"]),
        include_inactive_sections=bool(request["include_inactive_sections"]),
    )
    normalized_edges, edge_truncations = _normalize_workflow_edges(
        resolved_edges,
        allowed_relation_types=set(request["allowed_relation_types"]),
        edge_limit=int(request["edge_limit"]),
        emitted_section_ids={item["legal_section_id"] for item in normalized_sections},
    )
    boundary_stops = _normalize_boundary_stops(
        unresolved_references or [],
        selected_scope=scope,
        source_sample_limit=int(request["source_sample_limit"]),
        inventory_reference=inventory_reference,
    )
    emitted_boundary_stops = boundary_stops if request["include_boundary_stops"] else []
    metadata = dict(traversal_metadata or {})
    truncation_count = (
        int(metadata.get("truncation_count", 0) or 0)
        + section_truncations
        + edge_truncations
        + sum(1 for item in normalized_edges if item.get("truncated"))
    )
    cycle_boundary_count = max(
        int(metadata.get("cycle_boundary_count", 0) or 0),
        sum(1 for item in normalized_edges if item.get("cycle_boundary")),
    )
    quality_summary = _build_workflow_quality_summary(
        workflow_mode=str(request["workflow_mode"]),
        sections=normalized_sections,
        resolved_edges=normalized_edges,
        boundary_stops=emitted_boundary_stops,
        truncation_count=truncation_count,
        cycle_boundary_count=cycle_boundary_count,
        skipped_path_count=int(metadata.get("skipped_path_count", 0) or 0),
        missing_target_inventory_status=str(inventory_reference["status"]),
    )
    normalized_payload = {
        "artifact_type": "structural_workflow",
        "workflow_request": request,
        "selected_scope": scope,
        "sections": normalized_sections,
        "resolved_edges": normalized_edges,
        "coverage_boundary_stops": emitted_boundary_stops,
        "quality_summary": quality_summary,
        "ordering_policy": _structural_workflow_ordering_policy(),
        "source_relationship_quality_artifact": str(source_relationship_quality_artifact or ""),
        "missing_target_inventory_reference": inventory_reference,
        "warnings": sorted(str(item) for item in (warnings or []) if item),
    }
    ensure_no_answer_fields(normalized_payload)
    stable_identity_payload = {
        key: value
        for key, value in normalized_payload.items()
        if key not in {"warnings"}
    }
    artifact_id = _stable_digest(stable_identity_payload, prefix="structural-workflow")
    workflow_id = _stable_digest(
        {
            "workflow_request": request,
            "selected_scope": scope,
            "section_ids": [item["legal_section_id"] for item in normalized_sections],
        },
        prefix="structural-workflow-run",
    )
    return StructuralWorkflowArtifact(
        artifact_id=artifact_id,
        generated_at=generated_at,
        workflow_id=workflow_id,
        **normalized_payload,
    )


def build_graph_snapshot_artifact(
    *,
    selected_scope: dict[str, Any],
    source_scope: dict[str, Any],
    counts: dict[str, int],
    labels: dict[str, int],
    relation_types: dict[str, int],
    sample_ids: dict[str, list[str]],
    source_coverage: dict[str, Any],
    embedding_profile_metadata: dict[str, Any],
    unresolved_reference_evidence: list[dict[str, Any]],
) -> GraphSnapshotArtifact:
    payload = {
        "selected_scope": selected_scope,
        "source_scope": source_scope,
        "counts": counts,
        "labels": labels,
        "relation_types": relation_types,
        "sample_ids": sample_ids,
        "source_coverage": source_coverage,
        "embedding_profile_metadata": embedding_profile_metadata,
        "unresolved_reference_evidence": unresolved_reference_evidence,
    }
    snapshot_id = _stable_digest(payload, prefix="snapshot")
    return GraphSnapshotArtifact(snapshot_id=snapshot_id, **payload)


def build_legacy_baseline_graph_snapshot_artifact(
    *,
    selected_scope: dict[str, Any],
    source_scope: dict[str, Any],
    counts: dict[str, int],
    labels: dict[str, int],
    relation_types: dict[str, int],
    sample_ids: dict[str, list[str]],
    source_coverage: dict[str, Any],
    embedding_profile_metadata: dict[str, Any],
    unresolved_reference_evidence: list[dict[str, Any]],
    baseline_scope: dict[str, Any],
    baseline_origin: str = "legacy_aufenthg_graph_scope",
) -> LegacyAufenthGBaselineGraphSnapshotArtifact:
    payload = {
        "selected_scope": selected_scope,
        "source_scope": source_scope,
        "counts": counts,
        "labels": labels,
        "relation_types": relation_types,
        "sample_ids": sample_ids,
        "source_coverage": source_coverage,
        "embedding_profile_metadata": embedding_profile_metadata,
        "unresolved_reference_evidence": unresolved_reference_evidence,
        "baseline_scope": baseline_scope,
        "baseline_origin": baseline_origin,
    }
    snapshot_id = _stable_digest(payload, prefix="snapshot")
    return LegacyAufenthGBaselineGraphSnapshotArtifact(snapshot_id=snapshot_id, **payload)


def build_snapshot_comparison_report(
    new_snapshot: Mapping[str, Any] | GraphSnapshotArtifact,
    baseline_snapshot: Mapping[str, Any] | GraphSnapshotArtifact,
    *,
    notes: list[str] | None = None,
) -> SnapshotComparisonReport:
    new_payload = to_artifact_dict(new_snapshot)
    baseline_payload = to_artifact_dict(baseline_snapshot)
    matching: dict[str, Any] = {}
    missing: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for section in SNAPSHOT_SECTIONS:
        section_matching, section_missing, section_extra = _diff_value(
            new_payload.get(section),
            baseline_payload.get(section),
        )
        if section_matching not in ({}, [], None):
            matching[section] = section_matching
        if section_missing not in ({}, [], None):
            missing[section] = section_missing
        if section_extra not in ({}, [], None):
            extra[section] = section_extra
    comparison_payload = {
        "new_snapshot_id": new_payload.get("snapshot_id", ""),
        "baseline_snapshot_id": baseline_payload.get("snapshot_id", ""),
        "matching": matching,
        "missing": missing,
        "extra": extra,
        "summary_counts": {
            "matching_sections": len(matching),
            "missing_sections": len(missing),
            "extra_sections": len(extra),
            "matching_items": _count_value(matching),
            "missing_items": _count_value(missing),
            "extra_items": _count_value(extra),
        },
        "notes": list(notes or []),
    }
    comparison_payload["comparison_id"] = _stable_digest(comparison_payload, prefix="comparison")
    return SnapshotComparisonReport(**comparison_payload)


def write_json_artifact(path: str | Path, payload: Mapping[str, Any] | Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    serializable = to_artifact_dict(payload) if not isinstance(payload, Mapping) else dict(payload)
    output.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _find_forbidden_answer_fields(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        found.update(FORBIDDEN_ANSWER_FIELDS.intersection(str(key) for key in value.keys()))
        for child in value.values():
            found.update(_find_forbidden_answer_fields(child))
    elif isinstance(value, list | tuple):
        for child in value:
            found.update(_find_forbidden_answer_fields(child))
    return found


def _complete_counts(counts: Mapping[str, int], keys: tuple[str, ...]) -> dict[str, int]:
    return {key: int(counts.get(key, 0) or 0) for key in keys}


def _normalize_samples_by_relation(
    samples: Mapping[str, list[dict[str, Any]]],
    *,
    limit: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    return {
        relation_type: _normalize_sample_list(samples.get(relation_type, []), limit=limit)
        for relation_type in RELATION_TYPES
    }


def _normalize_sample_list(samples: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    return [
        _sorted_mapping(item)
        for item in sorted(samples, key=_stable_item)[:limit]
    ]


def _normalize_top_missing_targets(samples: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    normalized = []
    for item in samples:
        if str(item.get("reason", "")) != "missing_target_in_corpus":
            continue
        normalized.append(
            _sorted_mapping(
                {
                    "target_law_code": str(item.get("target_law_code", "")),
                    "target_section_reference": str(item.get("target_section_reference", "")),
                    "reason": "missing_target_in_corpus",
                    "count": int(item.get("count", 0) or 0),
                    "source_samples": _normalize_sample_list(
                        list(item.get("source_samples", [])) if isinstance(item.get("source_samples"), list) else [],
                        limit=5,
                    ),
                }
            )
        )
    return sorted(
        normalized,
        key=lambda item: (
            -int(item["count"]),
            item["target_law_code"],
            item["target_section_reference"],
        ),
    )[:limit]


def _normalize_workflow_request(request: StructuralWorkflowRequest | Mapping[str, Any]) -> dict[str, Any]:
    raw = to_artifact_dict(request) if not isinstance(request, Mapping) else dict(request)
    defaults = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS
    workflow_mode = str(raw.get("workflow_mode") or "")
    if workflow_mode not in STRUCTURAL_WORKFLOW_MODES:
        raise ValueError(f"unsupported structural workflow mode: {workflow_mode}")
    direction = str(raw.get("direction") or defaults["direction"])
    if direction not in STRUCTURAL_WORKFLOW_DIRECTIONS:
        raise ValueError(f"unsupported structural workflow direction: {direction}")
    relation_types = raw.get("allowed_relation_types", RELATION_TYPES)
    if not isinstance(relation_types, list | tuple | set):
        raise ValueError("allowed_relation_types must be a list")
    normalized_relation_types = sorted({str(item) for item in relation_types if str(item)})
    unsupported = set(normalized_relation_types).difference(RELATION_TYPES)
    if unsupported:
        raise ValueError(f"unsupported structural relation type: {sorted(unsupported)}")
    if not normalized_relation_types:
        normalized_relation_types = list(RELATION_TYPES)
    seed_ids = _normalize_string_list(raw.get("seed_legal_section_ids", []))
    law_codes = _normalize_string_list(raw.get("law_codes", []))
    if workflow_mode == "seed_neighborhood" and not seed_ids:
        raise ValueError("seed_neighborhood requires at least one seed legal section id")
    if workflow_mode == "law_scope_overview" and not law_codes:
        raise ValueError("law_scope_overview requires at least one law code")
    max_depth = _bounded_positive_int(raw, "max_depth", defaults["max_depth"])
    fanout_limit = _bounded_positive_int(raw, "fanout_limit", defaults["fanout_limit"])
    node_limit = _bounded_positive_int(raw, "node_limit", defaults["node_limit"], minimum=1)
    edge_limit = _bounded_positive_int(raw, "edge_limit", defaults["edge_limit"], minimum=1)
    source_sample_limit = _bounded_positive_int(
        raw,
        "source_sample_limit",
        defaults["source_sample_limit"],
        minimum=1,
    )
    maximums = STRUCTURAL_WORKFLOW_MAX_BOUNDS
    for key, value in (
        ("max_depth", max_depth),
        ("fanout_limit", fanout_limit),
        ("node_limit", node_limit),
        ("edge_limit", edge_limit),
        ("source_sample_limit", source_sample_limit),
    ):
        if value > maximums[key]:
            raise ValueError(f"{key} exceeds maximum {maximums[key]}")
    return {
        "workflow_mode": workflow_mode,
        "seed_legal_section_ids": seed_ids,
        "law_codes": law_codes,
        "direction": direction,
        "max_depth": max_depth,
        "allowed_relation_types": normalized_relation_types,
        "fanout_limit": fanout_limit,
        "node_limit": node_limit,
        "edge_limit": edge_limit,
        "source_sample_limit": source_sample_limit,
        "include_boundary_stops": bool(raw.get("include_boundary_stops", True)),
        "include_inactive_sections": bool(raw.get("include_inactive_sections", True)),
    }


def _bounded_positive_int(
    raw: Mapping[str, Any],
    key: str,
    default: int,
    *,
    minimum: int = 0,
) -> int:
    value = int(raw.get(key, default) if raw.get(key, None) is not None else default)
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


def _normalize_workflow_scope(selected_scope: dict[str, Any] | None, request: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(selected_scope or {})
    law_codes = _normalize_string_list(raw.get("law_codes", request.get("law_codes", [])))
    scope = {"source_families": _normalize_string_list(raw.get("source_families", ["law"])) or ["law"]}
    if law_codes:
        scope["law_codes"] = law_codes
    if request.get("seed_legal_section_ids"):
        scope["seed_legal_section_ids"] = list(request["seed_legal_section_ids"])
    return _sorted_mapping(scope)


def _normalize_workflow_sections(
    sections: list[dict[str, Any]],
    *,
    node_limit: int,
    include_inactive_sections: bool,
) -> tuple[list[dict[str, Any]], int]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in sections:
        section_id = str(item.get("legal_section_id") or "")
        if not section_id:
            continue
        unit_status = str(item.get("unit_status") or "active")
        if unit_status not in UNIT_STATUSES:
            unit_status = "active"
        if unit_status == "inactive" and not include_inactive_sections and item.get("role") != "seed":
            continue
        role = str(item.get("role") or "resolved_neighbor")
        if role not in STRUCTURAL_WORKFLOW_SECTION_ROLES:
            role = "resolved_neighbor"
        normalized = {
            "legal_section_id": section_id,
            "law_code": str(item.get("law_code") or ""),
            "section_reference": str(item.get("section_reference") or ""),
            "unit_status": unit_status,
            "depth": int(item.get("depth", 0) or 0),
            "role": role,
            "legal_act_id": str(item.get("legal_act_id") or ""),
            "normalized_reference": str(item.get("normalized_reference") or ""),
            "title": str(item.get("title") or ""),
            "status_marker_text": str(item.get("status_marker_text") or ""),
            "source_document_id": str(item.get("source_document_id") or ""),
            "source_fragment_id": str(item.get("source_fragment_id") or ""),
            "source_version_id": str(item.get("source_version_id") or ""),
            "source_revision_marker": str(item.get("source_revision_marker") or ""),
            "build_date": str(item.get("build_date") or ""),
            "content_checksum": str(item.get("content_checksum") or ""),
        }
        current = by_id.get(section_id)
        if current is None or _section_sort_key(normalized) < _section_sort_key(current):
            by_id[section_id] = normalized
    ordered = sorted(by_id.values(), key=_section_sort_key)
    truncations = max(0, len(ordered) - node_limit)
    return [_sorted_mapping(item) for item in ordered[:node_limit]], truncations


def _normalize_workflow_edges(
    edges: list[dict[str, Any]],
    *,
    allowed_relation_types: set[str],
    edge_limit: int,
    emitted_section_ids: set[str],
) -> tuple[list[dict[str, Any]], int]:
    grouped: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for item in edges:
        relation_type = str(item.get("relation_type") or "")
        if relation_type not in allowed_relation_types or relation_type not in RELATION_TYPES:
            continue
        source_id = str(item.get("source_legal_section_id") or "")
        target_id = str(item.get("target_legal_section_id") or "")
        if not source_id or not target_id:
            continue
        if emitted_section_ids and (source_id not in emitted_section_ids or target_id not in emitted_section_ids):
            continue
        depth = int(item.get("depth", 1) or 1)
        key = (source_id, target_id, relation_type, depth)
        legal_reference_ids = _normalize_string_list(item.get("legal_reference_ids", []))
        if not legal_reference_ids and item.get("legal_reference_id"):
            legal_reference_ids = [str(item["legal_reference_id"])]
        source_fragment_ids = _normalize_string_list(item.get("source_fragment_ids", []))
        if not source_fragment_ids and item.get("source_fragment_id"):
            source_fragment_ids = [str(item["source_fragment_id"])]
        normalized = grouped.setdefault(
            key,
            {
                "source_legal_section_id": source_id,
                "target_legal_section_id": target_id,
                "relation_type": relation_type,
                "depth": depth,
                "legal_reference_ids": [],
                "source_fragment_ids": [],
                "target_law_code": str(item.get("target_law_code") or ""),
                "target_section_reference": str(item.get("target_section_reference") or ""),
                "target_unit_status": str(item.get("target_unit_status") or ""),
                "classifier_policy_version": str(item.get("classifier_policy_version") or ""),
                "effective_from": str(item.get("effective_from") or ""),
                "effective_until": str(item.get("effective_until") or ""),
                "publication_date": str(item.get("publication_date") or ""),
                "source_version_id": str(item.get("source_version_id") or ""),
                "source_revision_marker": str(item.get("source_revision_marker") or ""),
                "build_date": str(item.get("build_date") or ""),
                "temporal_evidence_status": str(item.get("temporal_evidence_status") or ""),
                "cycle_boundary": bool(item.get("cycle_boundary", False)),
                "truncated": bool(item.get("truncated", False)),
            },
        )
        normalized["legal_reference_ids"] = sorted(set(normalized["legal_reference_ids"]) | set(legal_reference_ids))
        normalized["source_fragment_ids"] = sorted(set(normalized["source_fragment_ids"]) | set(source_fragment_ids))
        normalized["cycle_boundary"] = bool(normalized["cycle_boundary"] or item.get("cycle_boundary", False))
        normalized["truncated"] = bool(normalized["truncated"] or item.get("truncated", False))
    ordered = sorted(grouped.values(), key=_edge_sort_key)
    truncations = max(0, len(ordered) - edge_limit)
    return [_sorted_mapping(item) for item in ordered[:edge_limit]], truncations


def _normalize_boundary_stops(
    unresolved_references: list[dict[str, Any]],
    *,
    selected_scope: Mapping[str, Any],
    source_sample_limit: int,
    inventory_reference: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scope_key = ",".join(_normalize_string_list(selected_scope.get("law_codes", [])))
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in unresolved_references:
        reason = str(item.get("reason") or item.get("unresolved_reason") or "unresolved")
        target_law_code = str(item.get("target_law_code") or "")
        target_section_reference = str(item.get("target_section_reference") or "")
        if reason == "missing_target_in_corpus" and (not target_law_code or not target_section_reference):
            continue
        key = (reason, target_law_code, target_section_reference, scope_key)
        grouped.setdefault(key, []).append(
            {
                "legal_reference_id": str(item.get("legal_reference_id") or ""),
                "source_legal_section_id": str(item.get("source_legal_section_id") or ""),
                "source_fragment_id": str(item.get("source_fragment_id") or ""),
                "raw_reference_text": str(item.get("raw_reference_text") or ""),
                "normalized_reference_text": item.get("normalized_reference_text"),
                "target_law_code": target_law_code,
                "target_section_reference": target_section_reference,
                "reason": reason,
            }
        )
    stops: list[dict[str, Any]] = []
    for (reason, target_law_code, target_section_reference, _scope_key), samples in grouped.items():
        ordered_samples = sorted(samples, key=_boundary_sample_sort_key)
        visible_samples = [
            _sorted_mapping(
                {
                    "legal_reference_id": sample["legal_reference_id"],
                    "source_legal_section_id": sample["source_legal_section_id"],
                    "source_fragment_id": sample["source_fragment_id"],
                    "raw_reference_text": sample["raw_reference_text"],
                    "normalized_reference_text": sample["normalized_reference_text"],
                }
            )
            for sample in ordered_samples[:source_sample_limit]
        ]
        first = ordered_samples[0]
        boundary_key = {
            "reason": reason,
            "target_law_code": target_law_code,
            "target_section_reference": target_section_reference,
            "scope": _scope_key,
        }
        stops.append(
            _sorted_mapping(
                {
                    "boundary_id": _stable_digest(boundary_key, prefix="coverage-boundary"),
                    "source_legal_section_id": first["source_legal_section_id"],
                    "source_fragment_id": first["source_fragment_id"],
                    "legal_reference_id": first["legal_reference_id"],
                    "raw_reference_text": first["raw_reference_text"],
                    "normalized_reference_text": first["normalized_reference_text"],
                    "target_law_code": target_law_code,
                    "target_section_reference": target_section_reference,
                    "reason": reason,
                    "count": len(ordered_samples),
                    "source_samples": visible_samples,
                    "inventory_match": _inventory_match_status(
                        inventory_reference,
                        reason=reason,
                        target_law_code=target_law_code,
                        target_section_reference=target_section_reference,
                    ),
                }
            )
        )
    return sorted(stops, key=_boundary_sort_key)


def _build_workflow_quality_summary(
    *,
    workflow_mode: str,
    sections: list[dict[str, Any]],
    resolved_edges: list[dict[str, Any]],
    boundary_stops: list[dict[str, Any]],
    truncation_count: int,
    cycle_boundary_count: int,
    skipped_path_count: int,
    missing_target_inventory_status: str,
) -> dict[str, Any]:
    resolved_edges_by_relation_type = _complete_counts({}, RELATION_TYPES)
    for edge in resolved_edges:
        relation_type = str(edge.get("relation_type") or "")
        if relation_type in resolved_edges_by_relation_type:
            resolved_edges_by_relation_type[relation_type] += 1
    boundary_stops_by_reason = _complete_counts({}, UNRESOLVED_REASONS)
    for stop in boundary_stops:
        reason = str(stop.get("reason") or "")
        if reason not in boundary_stops_by_reason:
            boundary_stops_by_reason[reason] = 0
        boundary_stops_by_reason[reason] += int(stop.get("count", 1) or 1)
    payload = {
        "workflow_mode": workflow_mode,
        "visited_section_count": len(sections),
        "resolved_edge_count": len(resolved_edges),
        "resolved_edges_by_relation_type": resolved_edges_by_relation_type,
        "boundary_stop_count": len(boundary_stops),
        "boundary_stops_by_reason": _sorted_mapping(boundary_stops_by_reason),
        "truncation_count": truncation_count,
        "cycle_boundary_count": cycle_boundary_count,
        "skipped_path_count": skipped_path_count,
        "inactive_section_count": sum(1 for item in sections if item.get("unit_status") == "inactive"),
        "provenance_completeness": _workflow_provenance_completeness(
            sections=sections,
            resolved_edges=resolved_edges,
            boundary_stops=boundary_stops,
        ),
        "missing_target_inventory_status": missing_target_inventory_status,
    }
    return _sorted_mapping(payload)


def _workflow_provenance_completeness(
    *,
    sections: list[dict[str, Any]],
    resolved_edges: list[dict[str, Any]],
    boundary_stops: list[dict[str, Any]],
) -> dict[str, Any]:
    specs = {
        "section_required_identity": (
            sections,
            ("legal_section_id", "law_code", "section_reference", "unit_status", "depth", "role"),
        ),
        "section_optional_source_provenance": (
            sections,
            (
                "source_document_id",
                "source_fragment_id",
                "source_version_id",
                "source_revision_marker",
                "build_date",
                "content_checksum",
            ),
        ),
        "edge_required_identity": (
            resolved_edges,
            (
                "source_legal_section_id",
                "target_legal_section_id",
                "relation_type",
                "depth",
                "legal_reference_ids",
            ),
        ),
        "edge_optional_reference_provenance": (
            resolved_edges,
            (
                "source_fragment_ids",
                "target_law_code",
                "target_section_reference",
                "target_unit_status",
                "classifier_policy_version",
                "temporal_evidence_status",
            ),
        ),
        "boundary_required_identity": (
            boundary_stops,
            (
                "boundary_id",
                "source_legal_section_id",
                "source_fragment_id",
                "legal_reference_id",
                "raw_reference_text",
                "target_law_code",
                "target_section_reference",
                "reason",
                "count",
                "source_samples",
                "inventory_match",
            ),
        ),
        "boundary_optional_reference_provenance": (
            boundary_stops,
            ("normalized_reference_text",),
        ),
    }
    return _sorted_mapping({name: _provenance_bucket(items, fields) for name, (items, fields) in specs.items()})


def _provenance_bucket(items: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    missing_by_field = {field: 0 for field in fields}
    total_fields = len(items) * len(fields)
    present_fields = 0
    for item in items:
        for field in fields:
            if _has_provenance_value(item.get(field)):
                present_fields += 1
            else:
                missing_by_field[field] += 1
    return {
        "item_count": len(items),
        "field_count": total_fields,
        "present_count": present_fields,
        "missing_count": total_fields - present_fields,
        "missing_by_field": missing_by_field,
    }


def _has_provenance_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, list | tuple | dict | set):
        return bool(value)
    return True


def _normalize_inventory_reference(
    inventory_reference: dict[str, Any] | None,
    selected_scope: Mapping[str, Any],
) -> dict[str, Any]:
    raw = dict(inventory_reference or {})
    status = str(raw.get("status") or "not_provided")
    if status not in MISSING_TARGET_INVENTORY_STATUSES:
        status = "not_provided"
    selected_law_codes = _normalize_string_list(selected_scope.get("law_codes", []))
    inventory_law_codes = _normalize_string_list(raw.get("law_codes", selected_law_codes))
    if status == "available" and inventory_law_codes and selected_law_codes:
        if not set(selected_law_codes).issubset(set(inventory_law_codes)):
            status = "scope_mismatch"
    targets = _normalize_inventory_targets(raw)
    return _sorted_mapping(
        {
            "path": str(raw.get("path") or ""),
            "status": status,
            "generated_at": str(raw.get("generated_at") or ""),
            "law_codes": inventory_law_codes,
            "target_count": len(targets),
            "targets": targets,
        }
    )


def _normalize_inventory_targets(raw: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_targets = raw.get("targets")
    if raw_targets is None:
        raw_targets = raw.get("items")
    if raw_targets is None:
        raw_targets = raw.get("top_missing_targets")
    if raw_targets is None:
        raw_targets = raw.get("missing_targets")
    if not isinstance(raw_targets, list):
        raw_targets = []
    targets: list[dict[str, str]] = []
    for item in raw_targets:
        if not isinstance(item, Mapping):
            continue
        reason = str(item.get("reason") or item.get("unresolved_reason") or "missing_target_in_corpus")
        targets.append(
            {
                "reason": reason,
                "target_law_code": str(item.get("target_law_code") or ""),
                "target_section_reference": str(item.get("target_section_reference") or ""),
            }
        )
    return sorted({_stable_item(target): target for target in targets}.values(), key=_inventory_target_sort_key)


def _inventory_match_status(
    inventory_reference: Mapping[str, Any],
    *,
    reason: str,
    target_law_code: str,
    target_section_reference: str,
) -> str:
    status = str(inventory_reference.get("status") or "not_provided")
    if status == "stale":
        return "stale_inventory"
    if status != "available":
        return "not_checked"
    target = {
        "reason": reason,
        "target_law_code": target_law_code,
        "target_section_reference": target_section_reference,
    }
    targets = inventory_reference.get("targets", [])
    if not isinstance(targets, list):
        return "not_found"
    target_keys = {_stable_item(item) for item in targets if isinstance(item, Mapping)}
    match_status = "matched" if _stable_item(target) in target_keys else "not_found"
    if match_status not in INVENTORY_MATCH_STATUSES:
        return "not_found"
    return match_status


def _structural_workflow_ordering_policy() -> dict[str, str]:
    return {
        "sections": "depth, role, law_code, section_reference, legal_section_id",
        "resolved_edges": "depth, relation_type, source_legal_section_id, target_legal_section_id, first_legal_reference_id",
        "coverage_boundary_stops": "reason, target_law_code, target_section_reference, source_legal_section_id, legal_reference_id",
    }


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list | tuple | set):
        return []
    return sorted({str(item) for item in value if str(item)})


def _role_order(role: str) -> int:
    return STRUCTURAL_WORKFLOW_SECTION_ROLES.index(role) if role in STRUCTURAL_WORKFLOW_SECTION_ROLES else 99


def _section_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(item.get("depth", 0) or 0),
        _role_order(str(item.get("role") or "")),
        str(item.get("law_code") or ""),
        str(item.get("section_reference") or ""),
        str(item.get("legal_section_id") or ""),
    )


def _edge_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    refs = item.get("legal_reference_ids", [])
    first_ref = refs[0] if isinstance(refs, list) and refs else ""
    return (
        int(item.get("depth", 0) or 0),
        str(item.get("relation_type") or ""),
        str(item.get("source_legal_section_id") or ""),
        str(item.get("target_legal_section_id") or ""),
        str(first_ref),
    )


def _boundary_sample_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("source_legal_section_id") or ""),
        str(item.get("source_fragment_id") or ""),
        str(item.get("legal_reference_id") or ""),
    )


def _boundary_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(item.get("reason") or ""),
        str(item.get("target_law_code") or ""),
        str(item.get("target_section_reference") or ""),
        str(item.get("source_legal_section_id") or ""),
        str(item.get("legal_reference_id") or ""),
    )


def _inventory_target_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("reason") or ""),
        str(item.get("target_law_code") or ""),
        str(item.get("target_section_reference") or ""),
    )


def _sorted_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, Mapping):
            normalized[str(key)] = _sorted_mapping(item)
        elif isinstance(item, list):
            normalized[str(key)] = [
                _sorted_mapping(child) if isinstance(child, Mapping) else child for child in item
            ]
        else:
            normalized[str(key)] = item
    return normalized


def _normalize_temporal_completeness(
    payload: Mapping[str, Any],
    *,
    selected_scope: dict[str, Any],
) -> dict[str, Any]:
    counts_by_status = _complete_counts(
        payload.get("counts_by_temporal_evidence_status", {})
        if isinstance(payload.get("counts_by_temporal_evidence_status"), Mapping)
        else {},
        TEMPORAL_EVIDENCE_STATUSES,
    )
    raw_relation_counts = (
        payload.get("counts_by_relation_type")
        if isinstance(payload.get("counts_by_relation_type"), Mapping)
        else {}
    )
    relation_counts: dict[str, dict[str, int]] = {}
    for relation_type in RELATION_TYPES:
        raw = raw_relation_counts.get(relation_type, {}) if isinstance(raw_relation_counts, Mapping) else {}
        raw = raw if isinstance(raw, Mapping) else {}
        relation_counts[relation_type] = {
            "total": int(raw.get("total", 0) or 0),
            "with_any_temporal_metadata": int(raw.get("with_any_temporal_metadata", 0) or 0),
            "missing_required_temporal_fields": int(raw.get("missing_required_temporal_fields", 0) or 0),
        }
    missing_field_summary = payload.get("missing_field_summary", {})
    if not isinstance(missing_field_summary, Mapping):
        missing_field_summary = {}
    return {
        "selected_scope": _sorted_mapping(payload.get("selected_scope", selected_scope)),
        "counts_by_temporal_evidence_status": counts_by_status,
        "counts_by_relation_type": relation_counts,
        "missing_field_summary": {
            field: int(missing_field_summary.get(field, 0) or 0)
            for field in (
                "effective_from",
                "effective_until",
                "publication_date",
                "source_version_id",
                "source_revision_marker",
                "temporal_context_text",
                "temporal_context_checksum",
            )
        },
        "total_reference_evidence_count": int(payload.get("total_reference_evidence_count", 0) or 0),
    }


def _deferred_relation_strategy(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    strategy = {
        relation_type: raw.get(
            relation_type,
            {
                "strategy": "recognized_and_counted_when_observed",
                "trusted_edge_support": "deferred_until_source_strategy_is_sufficient",
            },
        )
        for relation_type in DEFERRED_RELATION_TYPES
    }
    return _sorted_mapping(strategy)


def _stable_digest(payload: Mapping[str, Any], *, prefix: str) -> str:
    normalized = json.dumps(to_artifact_dict(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{prefix}:{sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def _diff_value(new_value: Any, baseline_value: Any) -> tuple[Any, Any, Any]:
    if isinstance(new_value, dict) and isinstance(baseline_value, dict):
        matching: dict[str, Any] = {}
        missing: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        for key in sorted(set(new_value) | set(baseline_value)):
            if key not in new_value:
                missing[key] = baseline_value[key]
                continue
            if key not in baseline_value:
                extra[key] = new_value[key]
                continue
            child_matching, child_missing, child_extra = _diff_value(new_value[key], baseline_value[key])
            if child_matching not in ({}, [], None):
                matching[key] = child_matching
            if child_missing not in ({}, [], None):
                missing[key] = child_missing
            if child_extra not in ({}, [], None):
                extra[key] = child_extra
        return matching, missing, extra
    if isinstance(new_value, list) and isinstance(baseline_value, list):
        new_index = {_stable_item(item): item for item in new_value}
        baseline_index = {_stable_item(item): item for item in baseline_value}
        shared_keys = sorted(new_index.keys() & baseline_index.keys())
        matching = [baseline_index[key] for key in shared_keys]
        missing = [baseline_index[key] for key in sorted(baseline_index.keys() - new_index.keys())]
        extra = [new_index[key] for key in sorted(new_index.keys() - baseline_index.keys())]
        return matching, missing, extra
    if new_value == baseline_value:
        return new_value, {}, {}
    return {}, baseline_value, new_value


def _stable_item(item: Any) -> str:
    return json.dumps(to_plain_dict(item), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _count_value(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_count_value(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_value(item) for item in value)
    if value in ({}, [], None):
        return 0
    return 1
