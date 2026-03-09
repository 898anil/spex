"""spex stale - find files that may need updating based on timestamps."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from spex.graph.builder import build_graph


def run(days: int = 14, file_type: str | None = None, as_json: bool = False) -> None:
    root = Path(".").resolve()
    graph = build_graph(root)
    now = time.time()
    threshold_seconds = days * 86400

    stale_files: list[dict] = []

    for node in graph:
        if file_type and node.doc_type != file_type:
            continue

        # A file is stale if any of its upstream (incoming) dependencies
        # were modified more recently than it was
        incoming = graph.incoming(node.path)
        if not incoming:
            continue

        newer_deps = []
        seen_deps: set[str] = set()
        for edge in incoming:
            dep_node = graph.get_node(edge.source)
            if not dep_node or dep_node.path in seen_deps:
                continue
            seen_deps.add(dep_node.path)
            if dep_node.modified_time > node.modified_time:
                age_days = (dep_node.modified_time - node.modified_time) / 86400
                if age_days * 86400 >= threshold_seconds or threshold_seconds == 0:
                    newer_deps.append({
                        "path": dep_node.path,
                        "relationship": edge.relationship,
                        "days_newer": round(age_days, 1),
                    })

        if newer_deps:
            file_age_days = (now - node.modified_time) / 86400
            stale_files.append({
                "path": node.path,
                "type": node.doc_type,
                "last_modified_days_ago": round(file_age_days, 1),
                "newer_dependencies": newer_deps,
            })

    stale_files.sort(key=lambda x: -len(x["newer_dependencies"]))

    if as_json:
        click.echo(json.dumps({
            "stale_files": stale_files,
            "total_stale": len(stale_files),
        }, indent=2))
        return

    if not stale_files:
        click.echo(f"No stale files found (threshold: {days} days, {len(graph)} files scanned)")
        return

    click.echo(f"Found {len(stale_files)} potentially stale files:\n")
    for item in stale_files:
        click.echo(f"  {item['path']} ({item['type']})")
        click.echo(f"    Last modified: {item['last_modified_days_ago']} days ago")
        for dep in item["newer_dependencies"]:
            click.echo(
                f"    <- {dep['path']} ({dep['relationship']}) "
                f"is {dep['days_newer']} days newer"
            )
        click.echo()
