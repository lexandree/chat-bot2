"""Bounded structural traversal for legal graph context."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


ALLOWED_DEPTH_TWO_RELATIONS = {"DEFINES", "APPLIES_IF", "REQUIRES"}
HIGH_PRIORITY_DIRECT_RELATIONS = {"EXCEPTION_TO", "EXCLUDES_IF"}
DEFAULT_RELATION_WHITELIST = {
    "CITES",
    "DEFINES",
    "EXCEPTION_TO",
    "AMENDS",
    "SUPERSEDED_BY",
    "APPLIES_IF",
    "REQUIRES",
}


@dataclass(slots=True)
class TraversalPolicy:
    default_depth: int = 1
    max_depth: int = 2
    max_fanout: int = 10
    max_nodes: int = 50
    relation_whitelist: frozenset[str] = frozenset(DEFAULT_RELATION_WHITELIST)


def traverse_structural_context(
    start_section_id: str,
    *,
    sections_by_id: dict[str, dict[str, object]],
    edges: list[dict[str, object]],
    policy: TraversalPolicy | None = None,
) -> list[dict[str, object]]:
    active_policy = policy or TraversalPolicy()
    outgoing: dict[str, list[dict[str, object]]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge["source_section_id"]), []).append(edge)

    visited = {start_section_id}
    queue = deque([(start_section_id, 0)])
    collected: list[dict[str, object]] = []

    while queue and len(collected) < active_policy.max_nodes:
        node_id, depth = queue.popleft()
        if depth >= active_policy.max_depth:
            continue
        next_edges = [
            edge
            for edge in outgoing.get(node_id, [])
            if str(edge.get("reference_type")) in active_policy.relation_whitelist
        ][: active_policy.max_fanout]
        for edge in next_edges:
            relation = str(edge["reference_type"])
            target_id = str(edge["target_section_id"])
            if target_id in visited or target_id not in sections_by_id:
                continue
            if depth + 1 > active_policy.default_depth and relation not in ALLOWED_DEPTH_TWO_RELATIONS:
                continue
            visited.add(target_id)
            target_node = dict(sections_by_id[target_id])
            target_node["traversal_relation"] = relation
            target_node["traversal_depth"] = depth + 1
            collected.append(target_node)
            if relation not in HIGH_PRIORITY_DIRECT_RELATIONS:
                queue.append((target_id, depth + 1))
    return collected
