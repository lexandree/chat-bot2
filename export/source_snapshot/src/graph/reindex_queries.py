"""Helpers for classifying nodes during reindex planning."""

from __future__ import annotations


def classify_reindex_item(
    item: dict[str, object],
    *,
    target_profile_id: str,
    expected_dim: int,
) -> str:
    vector = item.get("embedding_v1") or []
    profile_id = item.get("embedding_profile_id")
    if not vector:
        return "missing"
    if len(vector) != expected_dim:
        return "invalid"
    if profile_id == target_profile_id:
        return "current"
    return "outdated"


def select_reindex_items(
    items: list[dict[str, object]],
    *,
    target_profile_id: str,
    expected_dim: int,
    force_rewrite: bool = False,
) -> list[dict[str, object]]:
    selected = []
    for item in items:
        status = classify_reindex_item(
            item,
            target_profile_id=target_profile_id,
            expected_dim=expected_dim,
        )
        enriched = dict(item)
        enriched["reindex_status"] = status
        if force_rewrite or status in {"missing", "invalid", "outdated"}:
            selected.append(enriched)
    return selected
