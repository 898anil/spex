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
    token_budget: int | None = None,
    pipeline_only: bool = False,
) -> None:
    from spex.config import load_config

    root = Path(".").resolve()
    config = load_config(root)
    graph = build_graph(root, config=config)
    bundle = context_bundle(
        graph, file_path, root, depth=depth,
        include_content=not no_content,
        token_budget=token_budget,
        pipeline_only=pipeline_only,
    )

    if tokens_only:
        click.echo(f"Estimated tokens: ~{bundle.estimated_tokens:,}")
        click.echo(f"Files: {bundle.file_count}")
        if bundle.truncated:
            click.echo(f"Budget: {bundle.token_budget:,} tokens (excluded {bundle.excluded_count} files)")
        return

    # Build markdown output
    lines = [f"# Context Bundle: {bundle.target}\n"]
    meta_parts = [
        f"Files: {bundle.file_count}",
        f"Estimated tokens: ~{bundle.estimated_tokens:,}",
    ]
    if bundle.token_budget:
        meta_parts.append(f"Budget: {bundle.token_budget:,}")
    if bundle.truncated:
        meta_parts.append(f"Excluded: {bundle.excluded_count} files (budget reached)")
    if pipeline_only:
        meta_parts.append("Mode: pipeline-only")
    lines.append(" | ".join(meta_parts) + "\n")
    lines.append("---\n")

    for f in bundle.files:
        role_label = f["role"].upper()
        rel_info = ""
        if f.get("relationship"):
            rel_info = f" ({f['relationship']})"
        depth_info = ""
        if f.get("depth"):
            depth_info = f" [depth {f['depth']}]"
        lines.append(f"## [{role_label}] {f['path']}{rel_info}{depth_info}\n")
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
        if bundle.truncated:
            click.echo(f"  Excluded {bundle.excluded_count} files (budget: {bundle.token_budget:,} tokens)")
    else:
        click.echo(content)
