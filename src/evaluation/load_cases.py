"""Report serialization and snapshot-comparison helpers."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from graph.types import (
    GraphSnapshotArtifact,
    LegacyAufenthGBaselineGraphSnapshotArtifact,
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
    present = FORBIDDEN_ANSWER_FIELDS.intersection(payload)
    if present:
        raise ValueError(f"structural retrieval artifact contains forbidden answer fields: {sorted(present)}")


def structural_retrieval_artifact(record: Any) -> dict[str, Any]:
    payload = to_artifact_dict(record)
    ensure_no_answer_fields(payload)
    return payload


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
