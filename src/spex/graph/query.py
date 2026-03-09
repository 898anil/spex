"""Graph query API - impact analysis, context assembly, traversal."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from spex.graph.model import Edge, Graph, Node


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


def impact(
    graph: Graph,
    target: str,
    depth: int = 2,
    direction: str = "both",
) -> ImpactResult:
    """Compute the cascade of files affected by changing target.

    Args:
        graph: The document graph
        target: Repo-relative path to the changed file
        depth: Maximum traversal depth (1-10)
        direction: "downstream", "upstream", or "both"
    """
    depth = max(1, min(depth, 10))
    node = graph.get_node(target)
    if not node:
        return ImpactResult(
            target=target, target_type="unknown", cascade=[],
            total_affected=0, downstream_count=0, upstream_count=0,
        )

    visited: set[str] = {target}
    cascade: list[dict] = []

    queue: deque[tuple[str, int, str]] = deque()

    if direction in ("downstream", "both"):
        for edge in graph.outgoing(target):
            if edge.target not in visited:
                queue.append((edge.target, 1, "downstream"))

    if direction in ("upstream", "both"):
        for edge in graph.incoming(target):
            if edge.source not in visited:
                queue.append((edge.source, 1, "upstream"))

    while queue:
        path, current_depth, dir_label = queue.popleft()
        if current_depth > depth or path in visited:
            continue
        visited.add(path)

        n = graph.get_node(path)
        if not n:
            continue

        # Find the edge that brought us here
        relationship = "links_to"
        if dir_label == "downstream":
            for e in graph.outgoing(target if current_depth == 1 else path):
                if e.target == path:
                    relationship = e.relationship
                    break
        else:
            for e in graph.incoming(target if current_depth == 1 else path):
                if e.source == path:
                    relationship = e.relationship
                    break

        cascade.append({
            "path": path,
            "type": n.doc_type,
            "relationship": relationship,
            "direction": dir_label,
            "depth": current_depth,
        })

        if current_depth < depth:
            if dir_label == "downstream":
                for edge in graph.outgoing(path):
                    if edge.target not in visited:
                        queue.append((edge.target, current_depth + 1, "downstream"))
            else:
                for edge in graph.incoming(path):
                    if edge.source not in visited:
                        queue.append((edge.source, current_depth + 1, "upstream"))

    cascade.sort(key=lambda x: (0 if x["direction"] == "downstream" else 1, x["depth"]))

    return ImpactResult(
        target=target,
        target_type=node.doc_type,
        cascade=cascade,
        total_affected=len(cascade),
        downstream_count=sum(1 for c in cascade if c["direction"] == "downstream"),
        upstream_count=sum(1 for c in cascade if c["direction"] == "upstream"),
    )


def context_bundle(
    graph: Graph,
    target: str,
    root: Path,
    depth: int = 2,
    include_content: bool = True,
) -> ContextBundle:
    """Assemble a context bundle for AI consumption.

    Returns upstream context, the target file, and downstream files
    in dependency order.
    """
    # Get upstream and downstream
    impact_result = impact(graph, target, depth=depth, direction="both")

    files: list[dict] = []

    # Upstream files first (context)
    upstream = [c for c in impact_result.cascade if c["direction"] == "upstream"]
    for item in upstream:
        entry: dict = {
            "path": item["path"],
            "role": "upstream",
            "type": item["type"],
            "relationship": item["relationship"],
        }
        if include_content:
            file_path = root / item["path"]
            if file_path.exists():
                entry["content"] = file_path.read_text(encoding="utf-8", errors="replace")
                entry["content_length"] = len(entry["content"])
        files.append(entry)

    # Target file
    target_entry: dict = {
        "path": target,
        "role": "target",
        "type": impact_result.target_type,
    }
    if include_content:
        target_path = root / target
        if target_path.exists():
            target_entry["content"] = target_path.read_text(encoding="utf-8", errors="replace")
            target_entry["content_length"] = len(target_entry["content"])
    files.append(target_entry)

    # Downstream files
    downstream = [c for c in impact_result.cascade if c["direction"] == "downstream"]
    for item in downstream:
        entry = {
            "path": item["path"],
            "role": "downstream",
            "type": item["type"],
            "relationship": item["relationship"],
        }
        if include_content:
            file_path = root / item["path"]
            if file_path.exists():
                entry["content"] = file_path.read_text(encoding="utf-8", errors="replace")
                entry["content_length"] = len(entry["content"])
        files.append(entry)

    total_chars = sum(f.get("content_length", 0) for f in files)

    return ContextBundle(
        target=target,
        files=files,
        file_count=len(files),
        estimated_tokens=total_chars // 4,
    )
