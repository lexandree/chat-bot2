from __future__ import annotations

import pytest

from graph.types import RELATION_TYPES
from retrieval.legal_traversal import (
    TraversalEdge,
    bounded_structural_traversal,
    bounded_traversal_from_edges,
    normalize_allowed_relation_types,
)


def test_bounded_traversal_respects_relation_depth_fanout_and_node_limits() -> None:
    result = bounded_traversal_from_edges(
        start_section_id="s1",
        edges=[
            TraversalEdge("s1", "s2", "CITES", ["r1"]),
            TraversalEdge("s1", "s3", "CITES", ["r2"]),
            TraversalEdge("s2", "s4", "CITES", ["r3"]),
            TraversalEdge("s1", "x", "IGNORED", ["rx"]),
        ],
        allowed_relation_types={"CITES"},
        depth_limit=1,
        fanout_limit=1,
        node_limit=10,
    )

    assert result.visited_count == 2
    assert result.relation_types == ["CITES"]
    assert result.source_references == ["r1"]
    assert result.depth_limit == 1
    assert result.fanout_limit == 1
    assert result.node_limit == 10


def test_bounded_traversal_prevents_cycles_and_node_limit_overflow() -> None:
    result = bounded_traversal_from_edges(
        start_section_id="s1",
        edges=[
            TraversalEdge("s1", "s2", "CITES", []),
            TraversalEdge("s2", "s1", "CITES", []),
            TraversalEdge("s2", "s3", "CITES", []),
        ],
        allowed_relation_types={"CITES"},
        depth_limit=3,
        fanout_limit=10,
        node_limit=2,
    )

    assert result.visited_count == 2
    assert "answer" not in result.as_dict()


def test_traversal_policy_accepts_full_relationship_taxonomy_without_related() -> None:
    assert normalize_allowed_relation_types(RELATION_TYPES) == set(RELATION_TYPES)
    with pytest.raises(ValueError):
        normalize_allowed_relation_types({"RELATED"})


def test_structural_traversal_uses_resolved_edges_only_and_direction() -> None:
    result = bounded_structural_traversal(
        seed_section_ids=["s2"],
        edges=[
            TraversalEdge("s1", "s2", "CITES", ["r1"]),
            TraversalEdge("s2", "s3", "DEFINES", ["r2"]),
            TraversalEdge("s4", "s2", "IGNORED", ["rx"]),
        ],
        allowed_relation_types={"CITES"},
        direction="incoming",
        depth_limit=1,
        fanout_limit=10,
        node_limit=10,
        edge_limit=10,
    )

    assert result.visited_section_ids == ["s2", "s1"]
    assert result.relation_types == ["CITES"]
    assert result.source_references == ["r1"]
    assert len(result.traversed_edges) == 1
    assert result.traversed_edges[0].source_id == "s1"
    assert result.traversed_edges[0].target_id == "s2"


def test_structural_traversal_reports_fanout_edge_limit_and_cycles_deterministically() -> None:
    result = bounded_structural_traversal(
        seed_section_ids=["s1"],
        edges=[
            TraversalEdge("s1", "s2", "CITES", ["r2"]),
            TraversalEdge("s1", "s3", "CITES", ["r3"]),
            TraversalEdge("s2", "s1", "CITES", ["r-cycle"]),
        ],
        allowed_relation_types={"CITES"},
        direction="outgoing",
        depth_limit=2,
        fanout_limit=1,
        node_limit=10,
        edge_limit=10,
    )

    assert result.visited_section_ids == ["s1", "s2"]
    assert [edge.source_references for edge in result.traversed_edges] == [["r2"], ["r-cycle"]]
    assert result.truncation_count == 1
    assert result.skipped_path_count == 1
    assert result.cycle_boundary_count == 1
    assert result.traversed_edges[1].cycle_boundary is True


def test_structural_traversal_reports_edge_and_node_limit_truncation() -> None:
    edge_limited = bounded_structural_traversal(
        seed_section_ids=["s1"],
        edges=[
            TraversalEdge("s1", "s2", "CITES", ["r2"]),
            TraversalEdge("s1", "s3", "CITES", ["r3"]),
        ],
        allowed_relation_types={"CITES"},
        direction="outgoing",
        depth_limit=1,
        fanout_limit=10,
        node_limit=10,
        edge_limit=1,
    )
    node_limited = bounded_structural_traversal(
        seed_section_ids=["s1"],
        edges=[TraversalEdge("s1", "s2", "CITES", ["r2"])],
        allowed_relation_types={"CITES"},
        direction="outgoing",
        depth_limit=1,
        fanout_limit=10,
        node_limit=1,
        edge_limit=10,
    )

    assert [edge.source_references for edge in edge_limited.traversed_edges] == [["r2"]]
    assert edge_limited.truncation_count == 1
    assert node_limited.visited_section_ids == ["s1"]
    assert node_limited.traversed_edges[0].truncated is True
    assert node_limited.truncation_count == 1


def test_structural_traversal_validates_005_bounds_and_relation_types() -> None:
    with pytest.raises(ValueError):
        bounded_structural_traversal(
            seed_section_ids=["s1"],
            edges=[],
            allowed_relation_types={"CITES"},
            direction="outgoing",
            depth_limit=3,
            fanout_limit=25,
            node_limit=100,
            edge_limit=500,
        )
    with pytest.raises(ValueError):
        bounded_structural_traversal(
            seed_section_ids=["s1"],
            edges=[],
            allowed_relation_types={"RELATED"},
            direction="outgoing",
            depth_limit=1,
            fanout_limit=25,
            node_limit=100,
            edge_limit=500,
        )
