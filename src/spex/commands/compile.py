"""spex compile - auto-generate files from the graph."""

from __future__ import annotations

from pathlib import Path

import click

from spex.graph.builder import build_graph
from spex.graph.model import Graph


def _generate_index(graph: Graph, root: Path, directory: str, dry_run: bool) -> str | None:
    """Generate an INDEX.md for a directory from the graph."""
    nodes_in_dir = [
        n for n in graph
        if str(Path(n.path).parent) == directory and not n.is_index
    ]
    if not nodes_in_dir:
        return None

    nodes_in_dir.sort(key=lambda n: n.path)

    # Determine the directory title from path
    dir_name = Path(directory).name
    title = dir_name.replace("-", " ").replace("_", " ").title()

    lines = [f"# {title}", ""]

    # Group by type if there are multiple types
    types_present = {}
    for n in nodes_in_dir:
        types_present.setdefault(n.doc_type, []).append(n)

    if len(types_present) == 1:
        lines.append(f"| File | Type | Description |")
        lines.append(f"|------|------|-------------|")
        for n in nodes_in_dir:
            name = Path(n.path).stem
            desc = ""
            if n.frontmatter:
                desc = str(n.frontmatter.get("name", "") or n.frontmatter.get("title", "") or "")
            rel_link = Path(n.path).name
            lines.append(f"| [{name}]({rel_link}) | {n.doc_type} | {desc} |")
    else:
        for doc_type, type_nodes in sorted(types_present.items()):
            type_title = doc_type.replace("-", " ").replace("_", " ").title()
            lines.append(f"## {type_title}")
            lines.append("")
            for n in type_nodes:
                name = Path(n.path).stem
                desc = ""
                if n.frontmatter:
                    desc = str(
                        n.frontmatter.get("name", "") or n.frontmatter.get("title", "") or ""
                    )
                rel_link = Path(n.path).name
                suffix = f" - {desc}" if desc else ""
                lines.append(f"- [{name}]({rel_link}){suffix}")
            lines.append("")

    lines.append("")
    content = "\n".join(lines)

    index_path = root / directory / "INDEX.md"
    if dry_run:
        return str(index_path)

    index_path.write_text(content)
    return str(index_path)


def run(indexes: bool = False, dashboard: bool = False, dry_run: bool = False) -> None:
    from spex.config import load_config

    root = Path(".").resolve()
    config = load_config(root)
    graph = build_graph(root, config=config)

    if dashboard and not indexes:
        click.echo("Dashboard generation not yet implemented")
        return

    # Default to indexes if nothing specified
    if not indexes and not dashboard:
        indexes = True

    if indexes:
        # Find directories that have 2+ files but no INDEX.md
        dirs_with_files: dict[str, int] = {}
        dirs_with_index: set[str] = set()

        for node in graph:
            parent = str(Path(node.path).parent)
            dirs_with_files[parent] = dirs_with_files.get(parent, 0) + 1
            if node.is_index:
                dirs_with_index.add(parent)

        generated = []
        for directory, count in sorted(dirs_with_files.items()):
            if directory in dirs_with_index:
                continue
            if count < 2:
                continue
            result = _generate_index(graph, root, directory, dry_run)
            if result:
                generated.append(result)

        if dry_run:
            if generated:
                click.echo(f"Would generate {len(generated)} INDEX files:")
                for path in generated:
                    click.echo(f"  {path}")
            else:
                click.echo("No INDEX files to generate")
        else:
            if generated:
                click.echo(f"Generated {len(generated)} INDEX files:")
                for path in generated:
                    click.echo(f"  {path}")
            else:
                click.echo("No INDEX files to generate (all directories already have one)")
