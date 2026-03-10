"""Graph query API - impact analysis, context assembly, traversal."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from spex.config import STRUCTURAL_RELATIONSHIPS
from spex.graph.model import Edge, Graph, Node


# ---------------------------------------------------------------------------
# Edge filters
# ---------------------------------------------------------------------------

def _is_pipeline_edge(edge: Edge) -> bool:
    """True if the edge represents a real pipeline dependency.

    Pipeline edges have semantic relationship names assigned by config
    (derives_to, satisfied_by, implemented_by, etc.). Structural edges
    (links_to, related_to, indexed_by) are navigational noise.
    """
    return edge.relationship not in STRUCTURAL_RELATIONSHIPS


def _is_any_edge(edge: Edge) -> bool:
    """Accept all edges (original behavior)."""
    return True


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ImpactResult:
    """Result of an impact analysis."""

    target: str
    target_type: str
    cascade: list[dict]
    total_affected: int
    downstream_count: int
    upstream_count: int


@dataclass
class ContextBundle:
    """An assembled context bundle for AI consumption."""

    target: str
    files: list[dict]
    file_count: int
    estimated_tokens: int
    token_budget: int | None = None
    truncated: bool = False
    excluded_count: int = 0


# ---------------------------------------------------------------------------
# Impact analysis
# ---------------------------------------------------------------------------

def impact(
    graph: Graph,
    target: str,
    depth: int = 2,
    direction: str = "both",
    pipeline_only: bool = False,
) -> ImpactResult:
    """Compute the cascade of files affected by changing target.

    Args:
        graph: The document graph
        target: Repo-relative path to the changed file
        depth: Maximum traversal depth (1-10)
        direction: "downstream", "upstream", or "both"
        pipeline_only: If True, only follow pipeline edges (semantic
            relationships like derives_to, satisfied_by). Skips generic
            links_to, related_to, indexed_by edges. This dramatically
            reduces noise and gives focused results for AI agents.
    """
    depth = max(1, min(depth, 10))
    edge_filter = _is_pipeline_edge if pipeline_only else _is_any_edge

    node = graph.get_node(target)
    if not node:
        return ImpactResult(
            target=target, target_type="unknown", cascade=[],
            total_affected=0, downstream_count=0, upstream_count=0,
        )

    visited: set[str] = {target}
    cascade: list[dict] = []

    # Queue entries: (path, depth, direction_label, relationship_that_led_here)
    queue: deque[tuple[str, int, str, str]] = deque()

    if direction in ("downstream", "both"):
        for edge in graph.outgoing(target):
            if edge.target not in visited and edge_filter(edge):
                queue.append((edge.target, 1, "downstream", edge.relationship))

    if direction in ("upstream", "both"):
        for edge in graph.incoming(target):
            if edge.source not in visited and edge_filter(edge):
                queue.append((edge.source, 1, "upstream", edge.relationship))

    while queue:
        path, current_depth, dir_label, rel = queue.popleft()
        if current_depth > depth or path in visited:
            continue
        visited.add(path)

        n = graph.get_node(path)
        if not n:
            continue

        cascade.append({
            "path": path,
            "type": n.doc_type,
            "relationship": rel,
            "direction": dir_label,
            "depth": current_depth,
        })

        if current_depth < depth:
            if dir_label == "downstream":
                for edge in graph.outgoing(path):
                    if edge.target not in visited and edge_filter(edge):
                        queue.append((edge.target, current_depth + 1, "downstream", edge.relationship))
            else:
                for edge in graph.incoming(path):
                    if edge.source not in visited and edge_filter(edge):
                        queue.append((edge.source, current_depth + 1, "upstream", edge.relationship))

    cascade.sort(key=lambda x: (0 if x["direction"] == "downstream" else 1, x["depth"]))

    return ImpactResult(
        target=target,
        target_type=node.doc_type,
        cascade=cascade,
        total_affected=len(cascade),
        downstream_count=sum(1 for c in cascade if c["direction"] == "downstream"),
        upstream_count=sum(1 for c in cascade if c["direction"] == "upstream"),
    )


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def context_bundle(
    graph: Graph,
    target: str,
    root: Path,
    depth: int = 2,
    include_content: bool = True,
    token_budget: int | None = None,
    pipeline_only: bool = False,
) -> ContextBundle:
    """Assemble a context bundle for AI consumption.

    Returns upstream context, the target file, and downstream files
    in dependency order. When pipeline_only=True, only includes files
    connected via semantic pipeline edges (not generic links).

    Args:
        token_budget: Max tokens to include. Files are added in priority
            order (target first, then depth-1 pipeline, then depth-2, etc.)
            and stops when budget would be exceeded. None = unlimited.
        pipeline_only: Only follow pipeline edges for focused context.
    """
    impact_result = impact(
        graph, target, depth=depth, direction="both",
        pipeline_only=pipeline_only,
    )

    # Prioritize files: target, then by depth (shallow first), then upstream before downstream
    upstream = [c for c in impact_result.cascade if c["direction"] == "upstream"]
    downstream = [c for c in impact_result.cascade if c["direction"] == "downstream"]

    # Sort each group by depth (nearest first)
    upstream.sort(key=lambda x: x["depth"])
    downstream.sort(key=lambda x: x["depth"])

    files: list[dict] = []
    tokens_used = 0
    excluded = 0

    def _add_file(entry: dict, content: str | None) -> bool:
        """Add a file to the bundle, respecting token budget. Returns False if budget exceeded."""
        nonlocal tokens_used, excluded
        if content is not None:
            entry["content"] = content
            entry["content_length"] = len(content)
            file_tokens = len(content) // 4
        else:
            file_tokens = 0

        if token_budget is not None and tokens_used + file_tokens > token_budget and files:
            # Budget exceeded, skip this file (but always include first file)
            excluded += 1
            return False

        tokens_used += file_tokens
        files.append(entry)
        return True

    def _read_file(path: str) -> str | None:
        if not include_content:
            return None
        file_path = root / path
        if file_path.exists():
            return file_path.read_text(encoding="utf-8", errors="replace")
        return None

    # 1. Target file (always included)
    target_entry: dict = {
        "path": target,
        "role": "target",
        "type": impact_result.target_type,
    }
    _add_file(target_entry, _read_file(target))

    # 2. Upstream files (context the target depends on)
    for item in upstream:
        entry: dict = {
            "path": item["path"],
            "role": "upstream",
            "type": item["type"],
            "relationship": item["relationship"],
            "depth": item["depth"],
        }
        if not _add_file(entry, _read_file(item["path"])):
            break  # budget exceeded, stop adding

    # 3. Downstream files (files that need updating)
    for item in downstream:
        entry = {
            "path": item["path"],
            "role": "downstream",
            "type": item["type"],
            "relationship": item["relationship"],
            "depth": item["depth"],
        }
        if not _add_file(entry, _read_file(item["path"])):
            break  # budget exceeded

    return ContextBundle(
        target=target,
        files=files,
        file_count=len(files),
        estimated_tokens=tokens_used,
        token_budget=token_budget,
        truncated=excluded > 0,
        excluded_count=excluded,
    )
