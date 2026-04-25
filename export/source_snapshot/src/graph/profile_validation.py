"""Validation helpers for profile-consistent graph writes and reindex status."""

from __future__ import annotations


def summarize_profile_consistency(
    items: list[dict[str, object]],
    *,
    target_profile_id: str,
    expected_dim: int,
) -> dict[str, int]:
    summary = {"current": 0, "outdated": 0, "missing": 0, "invalid": 0}
    for item in items:
        vector = item.get("embedding_v1") or []
        if not vector:
            summary["missing"] += 1
        elif len(vector) != expected_dim:
            summary["invalid"] += 1
        elif item.get("embedding_profile_id") == target_profile_id:
            summary["current"] += 1
        else:
            summary["outdated"] += 1
    return summary


def is_scope_fully_current(
    items: list[dict[str, object]],
    *,
    target_profile_id: str,
    expected_dim: int,
) -> bool:
    summary = summarize_profile_consistency(
        items,
        target_profile_id=target_profile_id,
        expected_dim=expected_dim,
    )
    return summary["outdated"] == 0 and summary["missing"] == 0 and summary["invalid"] == 0
