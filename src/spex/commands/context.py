"""spex context - assemble a context bundle for AI consumption."""

from __future__ import annotations

from pathlib import Path

import click

from spex.graph.builder import build_graph
from spex.graph.query import context_bundle


def run(
    file_path: str,
    depth: int = 2,
    output: str | None = None,
    tokens_only: bool = False,
    no_content: bool = False,
) -> None:
    root = Path(".").resolve()
    graph = build_graph(root)
    bundle = context_bundle(
        graph, file_path, root, depth=depth, include_content=not no_content
    )

    if tokens_only:
        click.echo(f"Estimated tokens: ~{bundle.estimated_tokens:,}")
        click.echo(f"Files: {bundle.file_count}")
        return

    # Build markdown output
    lines = [f"# Context Bundle: {bundle.target}\n"]
    lines.append(f"Files: {bundle.file_count} | Estimated tokens: ~{bundle.estimated_tokens:,}\n")
    lines.append("---\n")

    for f in bundle.files:
        role_label = f["role"].upper()
        rel_info = f""
        if f.get("relationship"):
            rel_info = f" ({f['relationship']})"
        lines.append(f"## [{role_label}] {f['path']}{rel_info}\n")
        lines.append(f"Type: {f['type']}\n")
        if f.get("content"):
            lines.append(f["content"])
            lines.append("\n")
        lines.append("---\n")

    content = "\n".join(lines)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Context bundle written to: {output}")
        click.echo(f"  {bundle.file_count} files, ~{bundle.estimated_tokens:,} tokens")
    else:
        click.echo(content)
