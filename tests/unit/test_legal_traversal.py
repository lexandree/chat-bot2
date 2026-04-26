from __future__ import annotations

from retrieval.legal_traversal import TraversalEdge, bounded_traversal_from_edges


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
