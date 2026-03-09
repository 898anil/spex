"""spex impact - show what files are affected by changing a file."""

from __future__ import annotations

import json

import click

from spex.graph.builder import build_graph
from spex.graph.query import impact


def run(
    file_path: str,
    depth: int = 2,
    direction: str = "both",
    as_json: bool = False,
) -> None:
    graph = build_graph(".")
    result = impact(graph, file_path, depth=depth, direction=direction)

    if not result.cascade and result.target_type == "unknown":
        click.echo(f"File not found in graph: {file_path}", err=True)
        click.echo("Run 'spex scan' to see all tracked files.", err=True)
        raise SystemExit(1)

    if as_json:
        output = {
            "target": result.target,
            "type": result.target_type,
            "cascade": result.cascade,
            "total_affected": result.total_affected,
            "downstream_count": result.downstream_count,
            "upstream_count": result.upstream_count,
        }
        click.echo(json.dumps(output, indent=2))
        return

    click.echo(f"Impact analysis for: {result.target}")
    click.echo(f"Type: {result.target_type}\n")

    downstream = [c for c in result.cascade if c["direction"] == "downstream"]
    upstream = [c for c in result.cascade if c["direction"] == "upstream"]

    if upstream:
        click.echo(f"Upstream ({len(upstream)} files):")
        for item in upstream:
            indent = "  " * item["depth"]
            click.echo(f"  {indent}{item['path']}  [{item['relationship']}]")

    if downstream:
        click.echo(f"\nDownstream ({len(downstream)} files):")
        for item in downstream:
            indent = "  " * item["depth"]
            click.echo(f"  {indent}{item['path']}  [{item['relationship']}]")

    if not upstream and not downstream:
        click.echo("No connections found for this file.")
    else:
        click.echo(f"\nTotal blast radius: {result.total_affected} files.")
