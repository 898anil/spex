"""Core graph data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from spex.scanner.types import Frontmatter


@dataclass
class Node:
    """A document node in the graph."""

    path: str  # repo-relative path
    doc_type: str  # inferred or configured document type
    frontmatter: Frontmatter | None
    line_count: int
    modified_time: float
    size_bytes: int
    layer: str | None = None  # inferred layer (e.g., "03-product")
    is_index: bool = False  # whether this is an INDEX.md file


@dataclass(frozen=True)
class Edge:
    """A typed, directed relationship between two documents."""

    source: str  # source node path
    target: str  # target node path
    relationship: str  # e.g., "links_to", "indexes", "references", "related_to"
    origin: str  # how this edge was detected: "frontmatter", "link", "id_reference"
    line: int | None = None  # line number in source file where the reference occurs


@dataclass
class Graph:
    """The document graph. Nodes are files, edges are relationships."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    # Indexes built after graph construction
    _outgoing: dict[str, list[Edge]] = field(default_factory=dict)
    _incoming: dict[str, list[Edge]] = field(default_factory=dict)
    _types: dict[str, list[str]] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        self.nodes[node.path] = node
        self._types.setdefault(node.doc_type, []).append(node.path)

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)
        self._outgoing.setdefault(edge.source, []).append(edge)
        self._incoming.setdefault(edge.target, []).append(edge)

    def get_node(self, path: str) -> Node | None:
        return self.nodes.get(path)

    def outgoing(self, path: str) -> list[Edge]:
        return self._outgoing.get(path, [])

    def incoming(self, path: str) -> list[Edge]:
        return self._incoming.get(path, [])

    def nodes_of_type(self, doc_type: str) -> list[Node]:
        paths = self._types.get(doc_type, [])
        return [self.nodes[p] for p in paths if p in self.nodes]

    def all_types(self) -> dict[str, int]:
        return {t: len(paths) for t, paths in self._types.items()}

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, path: str) -> bool:
        return path in self.nodes

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())
