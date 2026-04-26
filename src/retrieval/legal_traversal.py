"""Bounded typed traversal policy for structural retrieval."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from graph.types import StructuralRetrievalResult


@dataclass(frozen=True, slots=True)
class TraversalEdge:
    source_id: str
    target_id: str
    relation_type: str
    source_references: list[str]


def bounded_traversal_from_edges(
    *,
    start_section_id: str,
    edges: Iterable[TraversalEdge],
    allowed_relation_types: set[str],
    depth_limit: int,
    fanout_limit: int,
    node_limit: int,
) -> StructuralRetrievalResult:
    if depth_limit < 0 or fanout_limit < 0 or node_limit <= 0:
        raise ValueError("depth_limit and fanout_limit must be non-negative; node_limit must be positive")
    adjacency: dict[str, list[TraversalEdge]] = {}
    for edge in edges:
        if edge.relation_type in allowed_relation_types:
            adjacency.setdefault(edge.source_id, []).append(edge)
    visited = {start_section_id}
    relation_types: list[str] = []
    source_references: list[str] = []
    queue = deque([(start_section_id, 0)])
    while queue and len(visited) < node_limit:
        node_id, depth = queue.popleft()
        if depth >= depth_limit:
            continue
        for edge in adjacency.get(node_id, [])[:fanout_limit]:
            relation_types.append(edge.relation_type)
            source_references.extend(edge.source_references)
            if edge.target_id not in visited and len(visited) < node_limit:
                visited.add(edge.target_id)
                queue.append((edge.target_id, depth + 1))
    return StructuralRetrievalResult(
        query_reference={"legal_section_id": start_section_id},
        matched_legal_section_id=start_section_id,
        source_references=sorted(set(source_references)),
        relation_types=sorted(set(relation_types)),
        depth_limit=depth_limit,
        fanout_limit=fanout_limit,
        node_limit=node_limit,
        visited_count=len(visited),
    )
