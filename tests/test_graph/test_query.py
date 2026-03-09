"""Tests for graph query API."""

from pathlib import Path

from spex.graph.model import Graph
from spex.graph.query import context_bundle, impact


def test_impact_downstream(minimal_graph: Graph):
    result = impact(minimal_graph, "features/overview.md", depth=2, direction="downstream")
    assert result.target == "features/overview.md"
    assert result.target_type != "unknown"
    downstream_paths = {c["path"] for c in result.cascade}
    assert len(downstream_paths) > 0


def test_impact_upstream(minimal_graph: Graph):
    result = impact(minimal_graph, "features/requirements.md", depth=2, direction="upstream")
    upstream_paths = {c["path"] for c in result.cascade if c["direction"] == "upstream"}
    assert len(upstream_paths) >= 0


def test_impact_nonexistent_file(minimal_graph: Graph):
    result = impact(minimal_graph, "nonexistent.md")
    assert result.target_type == "unknown"
    assert result.total_affected == 0


def test_context_bundle_includes_target(minimal_graph: Graph, minimal_root: Path):
    bundle = context_bundle(minimal_graph, "features/overview.md", minimal_root, depth=1)
    paths = [f["path"] for f in bundle.files]
    assert "features/overview.md" in paths
    target_entry = next(f for f in bundle.files if f["path"] == "features/overview.md")
    assert target_entry["role"] == "target"


def test_context_bundle_has_content(minimal_graph: Graph, minimal_root: Path):
    bundle = context_bundle(minimal_graph, "features/overview.md", minimal_root, depth=1)
    target = next(f for f in bundle.files if f["role"] == "target")
    assert "content" in target
    assert "Feature A" in target["content"]


def test_context_bundle_no_content(minimal_graph: Graph, minimal_root: Path):
    bundle = context_bundle(
        minimal_graph, "features/overview.md", minimal_root,
        depth=1, include_content=False,
    )
    for f in bundle.files:
        assert "content" not in f
