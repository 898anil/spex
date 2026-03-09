"""Tests for validation checks."""

from pathlib import Path

from spex.commands.validate import (
    _check_circular,
    _check_indexes,
    _check_orphans,
)
from spex.graph.model import Graph


def test_orphan_detection(minimal_graph: Graph):
    issues = _check_orphans(minimal_graph)
    orphan_paths = {i["file"] for i in issues}
    assert "orphan.md" in orphan_paths


def test_no_false_positive_orphans(minimal_graph: Graph):
    issues = _check_orphans(minimal_graph)
    orphan_paths = {i["file"] for i in issues}
    assert "features/overview.md" not in orphan_paths
    assert "INDEX.md" not in orphan_paths


def test_circular_detection():
    """Test with a manually constructed circular graph."""
    from spex.graph.model import Edge, Node
    graph = Graph()
    graph.add_node(Node(path="a.md", doc_type="doc", frontmatter=None,
                        line_count=10, modified_time=0, size_bytes=100))
    graph.add_node(Node(path="b.md", doc_type="doc", frontmatter=None,
                        line_count=10, modified_time=0, size_bytes=100))
    graph.add_node(Node(path="c.md", doc_type="doc", frontmatter=None,
                        line_count=10, modified_time=0, size_bytes=100))
    graph.add_edge(Edge(source="a.md", target="b.md", relationship="links_to", origin="link"))
    graph.add_edge(Edge(source="b.md", target="c.md", relationship="links_to", origin="link"))
    graph.add_edge(Edge(source="c.md", target="a.md", relationship="links_to", origin="link"))

    issues = _check_circular(graph)
    assert len(issues) >= 1
    assert "Circular dependency" in issues[0]["message"]
