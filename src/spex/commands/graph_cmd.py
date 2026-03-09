"""spex graph - explore the document graph."""

from __future__ import annotations

import json
from pathlib import Path

import click

from spex.graph.builder import build_graph


def run(
    file_path: str = "",
    file_type: str | None = None,
    stats: bool = False,
    depth: int = 1,
    as_json: bool = False,
) -> None:
    root = Path(".").resolve()
    graph = build_graph(root)

    if stats or (not file_path and not file_type):
        _show_stats(graph, as_json)
        return

    if file_type and not file_path:
        _show_type(graph, file_type, as_json)
        return

    if file_path:
        _show_node(graph, file_path, depth, as_json)
        return


def _show_stats(graph, as_json: bool) -> None:
    types = graph.all_types()
    edge_types: dict[str, int] = {}
    for edge in graph.edges:
        edge_types[edge.relationship] = edge_types.get(edge.relationship, 0) + 1

    data = {
        "files": len(graph),
        "edges": len(graph.edges),
        "document_types": types,
        "relationship_types": edge_types,
    }

    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    click.echo(f"Files: {len(graph)}")
    click.echo(f"Edges: {len(graph.edges)}")
    click.echo(f"\nDocument types:")
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        click.echo(f"  {t}: {count}")
    click.echo(f"\nRelationship types:")
    for r, count in sorted(edge_types.items(), key=lambda x: -x[1]):
        click.echo(f"  {r}: {count}")


def _show_type(graph, file_type: str, as_json: bool) -> None:
    nodes = graph.nodes_of_type(file_type)
    if not nodes:
        click.echo(f"No files of type '{file_type}'")
        return

    if as_json:
        click.echo(json.dumps({
            "type": file_type,
            "files": [{"path": n.path, "layer": n.layer} for n in nodes],
            "total": len(nodes),
        }, indent=2))
        return

    click.echo(f"Type: {file_type} ({len(nodes)} files)")
    for n in nodes:
        layer = f" [{n.layer}]" if n.layer else ""
        click.echo(f"  {n.path}{layer}")


def _show_node(graph, file_path: str, depth: int, as_json: bool) -> None:
    node = graph.get_node(file_path)
    if not node:
        click.echo(f"File not found in graph: {file_path}", err=True)
        return

    outgoing = graph.outgoing(file_path)
    incoming = graph.incoming(file_path)

    data = {
        "path": node.path,
        "type": node.doc_type,
        "layer": node.layer,
        "is_index": node.is_index,
        "outgoing": [
            {"target": e.target, "relationship": e.relationship, "origin": e.origin}
            for e in outgoing
        ],
        "incoming": [
            {"source": e.source, "relationship": e.relationship, "origin": e.origin}
            for e in incoming
        ],
    }

    if as_json:
        click.echo(json.dumps(data, indent=2))
        return

    click.echo(f"File: {node.path}")
    click.echo(f"Type: {node.doc_type}")
    if node.layer:
        click.echo(f"Layer: {node.layer}")

    if outgoing:
        click.echo(f"\nOutgoing ({len(outgoing)}):")
        for e in outgoing:
            click.echo(f"  -> {e.target} ({e.relationship})")

    if incoming:
        click.echo(f"\nIncoming ({len(incoming)}):")
        for e in incoming:
            click.echo(f"  <- {e.source} ({e.relationship})")

    if not outgoing and not incoming:
        click.echo("\n  (no relationships)")
