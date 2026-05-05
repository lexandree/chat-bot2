"""Bounded typed traversal policy for structural retrieval."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from graph.types import (
    RELATION_TYPES,
    STRUCTURAL_WORKFLOW_DIRECTIONS,
    STRUCTURAL_WORKFLOW_MAX_BOUNDS,
    StructuralRetrievalResult,
)


DEFAULT_ALLOWED_RELATION_TYPES = tuple(RELATION_TYPES)
FORBIDDEN_STRUCTURAL_RELATION_TYPES = {"RELATED", "SEMANTICALLY_RELATED"}


@dataclass(frozen=True, slots=True)
class TraversalEdge:
    source_id: str
    target_id: str
    relation_type: str
    source_references: list[str]


@dataclass(frozen=True, slots=True)
class TraversedPathEdge:
    source_id: str
    target_id: str
    relation_type: str
    source_references: list[str]
    depth: int
    traversal_from_id: str
    traversal_to_id: str
    cycle_boundary: bool = False
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class BoundedTraversalResult:
    seed_section_ids: list[str]
    visited_section_ids: list[str]
    section_depths: dict[str, int]
    traversed_edges: list[TraversedPathEdge] = field(default_factory=list)
    relation_types: list[str] = field(default_factory=list)
    source_references: list[str] = field(default_factory=list)
    direction: str = "outgoing"
    depth_limit: int = 1
    fanout_limit: int = 25
    node_limit: int = 100
    edge_limit: int = 500
    truncation_count: int = 0
    cycle_boundary_count: int = 0
    skipped_path_count: int = 0


def bounded_traversal_from_edges(
    *,
    start_section_id: str,
    edges: Iterable[TraversalEdge],
    allowed_relation_types: set[str],
    depth_limit: int,
    fanout_limit: int,
    node_limit: int,
) -> StructuralRetrievalResult:
    traversal = bounded_structural_traversal(
        seed_section_ids=[start_section_id],
        edges=edges,
        allowed_relation_types=allowed_relation_types,
        direction="outgoing",
        depth_limit=depth_limit,
        fanout_limit=fanout_limit,
        node_limit=node_limit,
        edge_limit=STRUCTURAL_WORKFLOW_MAX_BOUNDS["edge_limit"],
        enforce_max_bounds=False,
    )
    return StructuralRetrievalResult(
        query_reference={"legal_section_id": start_section_id},
        matched_legal_section_id=start_section_id,
        source_references=traversal.source_references,
        relation_types=traversal.relation_types,
        depth_limit=depth_limit,
        fanout_limit=fanout_limit,
        node_limit=node_limit,
        visited_count=len(traversal.visited_section_ids),
    )


def bounded_structural_traversal(
    *,
    seed_section_ids: Iterable[str],
    edges: Iterable[TraversalEdge],
    allowed_relation_types: Iterable[str] | None,
    direction: str,
    depth_limit: int,
    fanout_limit: int,
    node_limit: int,
    edge_limit: int,
    enforce_max_bounds: bool = True,
) -> BoundedTraversalResult:
    seed_ids = [str(item) for item in seed_section_ids if str(item)]
    if not seed_ids:
        raise ValueError("at least one seed section id is required")
    _validate_traversal_bounds(
        direction=direction,
        depth_limit=depth_limit,
        fanout_limit=fanout_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
        enforce_max_bounds=enforce_max_bounds,
    )
    allowed = normalize_allowed_relation_types(allowed_relation_types)
    adjacency: dict[str, list[tuple[TraversalEdge, str]]] = {}
    for edge in edges:
        if edge.relation_type not in allowed:
            continue
        if direction in {"outgoing", "both"}:
            adjacency.setdefault(edge.source_id, []).append((edge, edge.target_id))
        if direction in {"incoming", "both"}:
            adjacency.setdefault(edge.target_id, []).append((edge, edge.source_id))
    for node_id in adjacency:
        adjacency[node_id].sort(key=_adjacency_sort_key)
    visited: set[str] = set(seed_ids[:node_limit])
    visited_order: list[str] = list(seed_ids[:node_limit])
    section_depths: dict[str, int] = {section_id: 0 for section_id in visited_order}
    traversed_edges: list[TraversedPathEdge] = []
    truncation_count = max(0, len(seed_ids) - node_limit)
    skipped_path_count = truncation_count
    cycle_boundary_count = 0
    queue = deque((section_id, 0) for section_id in visited_order)
    edge_limit_reached = False
    while queue and not edge_limit_reached:
        node_id, depth = queue.popleft()
        if depth >= depth_limit:
            continue
        candidates = adjacency.get(node_id, [])
        if len(candidates) > fanout_limit:
            truncation_count += len(candidates) - fanout_limit
            skipped_path_count += len(candidates) - fanout_limit
        for edge, neighbor_id in candidates[:fanout_limit]:
            if len(traversed_edges) >= edge_limit:
                truncation_count += 1
                skipped_path_count += 1
                edge_limit_reached = True
                break
            edge_depth = depth + 1
            cycle_boundary = neighbor_id in visited
            if cycle_boundary:
                cycle_boundary_count += 1
            elif len(visited_order) >= node_limit:
                truncation_count += 1
                skipped_path_count += 1
                traversed_edges.append(
                    TraversedPathEdge(
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        relation_type=edge.relation_type,
                        source_references=sorted(set(edge.source_references)),
                        depth=edge_depth,
                        traversal_from_id=node_id,
                        traversal_to_id=neighbor_id,
                        truncated=True,
                    )
                )
                continue
            else:
                visited.add(neighbor_id)
                visited_order.append(neighbor_id)
                section_depths[neighbor_id] = edge_depth
                queue.append((neighbor_id, edge_depth))
            traversed_edges.append(
                TraversedPathEdge(
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    relation_type=edge.relation_type,
                    source_references=sorted(set(edge.source_references)),
                    depth=edge_depth,
                    traversal_from_id=node_id,
                    traversal_to_id=neighbor_id,
                    cycle_boundary=cycle_boundary,
                )
            )
    relation_types = sorted({edge.relation_type for edge in traversed_edges})
    source_references = sorted(
        {reference for edge in traversed_edges for reference in edge.source_references if reference}
    )
    return BoundedTraversalResult(
        seed_section_ids=seed_ids,
        visited_section_ids=visited_order,
        section_depths=section_depths,
        traversed_edges=traversed_edges,
        relation_types=relation_types,
        source_references=source_references,
        direction=direction,
        depth_limit=depth_limit,
        fanout_limit=fanout_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
        truncation_count=truncation_count,
        cycle_boundary_count=cycle_boundary_count,
        skipped_path_count=skipped_path_count,
    )


def normalize_allowed_relation_types(relation_types: Iterable[str] | None) -> set[str]:
    requested = set(relation_types or DEFAULT_ALLOWED_RELATION_TYPES)
    forbidden = requested.intersection(FORBIDDEN_STRUCTURAL_RELATION_TYPES)
    if forbidden:
        raise ValueError(f"unsupported structural relation type: {sorted(forbidden)}")
    unsupported = requested.difference(RELATION_TYPES)
    if unsupported:
        raise ValueError(f"unsupported structural relation type: {sorted(unsupported)}")
    return requested


def _validate_traversal_bounds(
    *,
    direction: str,
    depth_limit: int,
    fanout_limit: int,
    node_limit: int,
    edge_limit: int,
    enforce_max_bounds: bool,
) -> None:
    if direction not in STRUCTURAL_WORKFLOW_DIRECTIONS:
        raise ValueError(f"unsupported structural traversal direction: {direction}")
    if depth_limit < 0:
        raise ValueError("depth_limit must be non-negative")
    if fanout_limit < 0:
        raise ValueError("fanout_limit must be non-negative")
    if node_limit <= 0:
        raise ValueError("node_limit must be positive")
    if edge_limit <= 0:
        raise ValueError("edge_limit must be positive")
    if not enforce_max_bounds:
        return
    maximums = STRUCTURAL_WORKFLOW_MAX_BOUNDS
    if depth_limit > maximums["max_depth"]:
        raise ValueError(f"depth_limit exceeds maximum {maximums['max_depth']}")
    if fanout_limit > maximums["fanout_limit"]:
        raise ValueError(f"fanout_limit exceeds maximum {maximums['fanout_limit']}")
    if node_limit > maximums["node_limit"]:
        raise ValueError(f"node_limit exceeds maximum {maximums['node_limit']}")
    if edge_limit > maximums["edge_limit"]:
        raise ValueError(f"edge_limit exceeds maximum {maximums['edge_limit']}")


def _adjacency_sort_key(item: tuple[TraversalEdge, str]) -> tuple[str, str, str, str, str]:
    edge, neighbor_id = item
    first_ref = sorted(edge.source_references)[0] if edge.source_references else ""
    return (edge.relation_type, edge.source_id, edge.target_id, neighbor_id, first_ref)
