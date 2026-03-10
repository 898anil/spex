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
    pipeline_only: bool = False,
) -> None:
    from pathlib import Path

    from spex.config import load_config

    root = Path(".").resolve()
    config = load_config(root)
    graph = build_graph(root, config=config)
    result = impact(
        graph, file_path, depth=depth, direction=direction,
        pipeline_only=pipeline_only,
    )

    if not result.cascade and result.target_type == "unknown":
        click.echo(f"File not found in graph: {file_path}", err=True)
        click.echo("Run 'spex scan' to see all tracked files.", err=True)
        raise SystemExit(1)

    if as_json:
        output = {
            "target": result.target,
            "type": result.target_type,
            "pipeline_only": pipeline_only,
            "cascade": result.cascade,
            "total_affected": result.total_affected,
            "downstream_count": result.downstream_count,
            "upstream_count": result.upstream_count,
        }
        click.echo(json.dumps(output, indent=2))
        return

    mode_label = " (pipeline only)" if pipeline_only else ""
    click.echo(f"Impact analysis for: {result.target}{mode_label}")
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
