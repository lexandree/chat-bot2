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
    LegacyAufenthGBaselineGraphSnapshotArtifact,
    RELATION_TYPES,
    RESOLUTION_STATUSES,
    RelationshipQualityArtifact,
    STRUCTURE_CLASSES,
    STRUCTURE_CLASS_RULES_VERSION,
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
