"""Tests for graph builder."""

from spex.graph.model import Graph


def test_build_graph_node_count(minimal_graph: Graph):
    assert len(minimal_graph) == 6


def test_build_graph_has_edges(minimal_graph: Graph):
    assert len(minimal_graph.edges) > 0


def test_node_types_inferred(minimal_graph: Graph):
    types = minimal_graph.all_types()
    assert "index" in types


def test_index_detected(minimal_graph: Graph):
    node = minimal_graph.get_node("INDEX.md")
    assert node is not None
    assert node.doc_type == "index"
    assert node.is_index


def test_feature_dir_type(minimal_graph: Graph):
    """Files in 'features/' should get type from directory name."""
    node = minimal_graph.get_node("features/overview.md")
    assert node is not None
    # Generic inference: parent dir "features" -> singularized "feature"
    assert node.doc_type == "feature"


def test_journey_from_frontmatter_type(minimal_graph: Graph):
    """Files with explicit frontmatter type should use it."""
    node = minimal_graph.get_node("journeys/onboarding.md")
    assert node is not None
    assert node.doc_type == "journey"


def test_tech_spec_from_dir(minimal_graph: Graph):
    node = minimal_graph.get_node("features/tech-spec.md")
    assert node is not None
    # Should get type from parent dir
    assert node.doc_type == "feature"


def test_index_has_outgoing(minimal_graph: Graph):
    outgoing = minimal_graph.outgoing("INDEX.md")
    targets = {e.target for e in outgoing}
    assert "features/overview.md" in targets
    assert "features/requirements.md" in targets


def test_relationship_types_are_structural(minimal_graph: Graph):
    """Relationship types should be structural, not domain-specific."""
    rel_types = {e.relationship for e in minimal_graph.edges}
    # Should have generic types like indexes, related_to, links_to
    assert rel_types & {"indexes", "related_to", "links_to", "cross_references", "contains"}


def test_orphan_has_no_edges(minimal_graph: Graph):
    node = minimal_graph.get_node("orphan.md")
    assert node is not None
    assert len(minimal_graph.outgoing("orphan.md")) == 0
    assert len(minimal_graph.incoming("orphan.md")) == 0
