"""spex scan - build the graph and report summary statistics."""

from __future__ import annotations

import json
import time

import click

from spex.graph.builder import build_graph


def run(path: str, as_json: bool = False, verbose: bool = False) -> None:
    start = time.monotonic()
    graph = build_graph(path)
    elapsed = time.monotonic() - start

    types = graph.all_types()
    edge_origins = {}
    for edge in graph.edges:
        edge_origins[edge.origin] = edge_origins.get(edge.origin, 0) + 1

    # Count files with/without frontmatter
    with_fm = sum(1 for n in graph if n.frontmatter is not None)
    without_fm = len(graph) - with_fm

    if as_json:
        output = {
            "files": len(graph),
            "with_frontmatter": with_fm,
            "without_frontmatter": without_fm,
            "types": types,
            "edges": len(graph.edges),
            "edge_origins": edge_origins,
            "elapsed_seconds": round(elapsed, 2),
        }
        click.echo(json.dumps(output, indent=2))
        return

    click.echo(f"Scanning {path} ...\n")
    click.echo(f"Files: {len(graph)} markdown files found")
    click.echo(f"  {with_fm} with YAML frontmatter")
    click.echo(f"  {without_fm} without frontmatter\n")

    click.echo(f"Document Types ({len(types)} inferred):")
    for doc_type, count in sorted(types.items(), key=lambda x: -x[1]):
        click.echo(f"  {doc_type:<25} {count:>4} files")

    click.echo(f"\nRelationships: {len(graph.edges)}")
    for origin, count in sorted(edge_origins.items(), key=lambda x: -x[1]):
        click.echo(f"  {count:>6} from {origin}")

    if verbose:
        click.echo("\nAll nodes:")
        for node in sorted(graph, key=lambda n: n.path):
            fm_keys = list(node.frontmatter.keys) if node.frontmatter else []
            click.echo(f"  [{node.doc_type}] {node.path} ({node.line_count} lines)")
            if fm_keys:
                click.echo(f"    frontmatter: {', '.join(sorted(fm_keys))}")

    click.echo(f"\nGraph ready (built in {elapsed:.1f}s).")
