"""CLI entry point for spex.

All commands are registered here. Each command delegates to its module
in spex.commands.
"""

from __future__ import annotations

import click

from spex import __version__


@click.group()
@click.version_option(version=__version__, prog_name="spex")
def main() -> None:
    """spex - The graph layer for large markdown repos."""


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--verbose", is_flag=True, help="Show per-file details.")
def scan(path: str, as_json: bool, verbose: bool) -> None:
    """Scan a markdown repo and build the document graph."""
    from spex.commands.scan import run

    run(path, as_json=as_json, verbose=verbose)


@main.command()
@click.argument("file_path", type=click.Path())
@click.option("--downstream", is_flag=True, help="Only show downstream impact.")
@click.option("--upstream", is_flag=True, help="Only show upstream impact.")
@click.option("--depth", default=2, help="Traversal depth (default: 2).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def impact(
    file_path: str, downstream: bool, upstream: bool, depth: int, as_json: bool
) -> None:
    """Show what files are affected by changing a file."""
    from spex.commands.impact import run

    direction = "downstream" if downstream else ("upstream" if upstream else "both")
    run(file_path, depth=depth, direction=direction, as_json=as_json)


@main.command()
@click.argument("file_path", type=click.Path())
@click.option("--depth", default=2, help="Context depth (default: 2).")
@click.option("--output", "-o", type=click.Path(), help="Write to file.")
@click.option("--tokens", is_flag=True, help="Show token estimate only.")
@click.option("--no-content", is_flag=True, help="Metadata only.")
def context(
    file_path: str, depth: int, output: str | None, tokens: bool, no_content: bool
) -> None:
    """Assemble a context bundle for AI consumption."""
    from spex.commands.context import run

    run(file_path, depth=depth, output=output, tokens_only=tokens, no_content=no_content)


@main.command()
@click.option("--links", is_flag=True, help="Only check links.")
@click.option("--schema", is_flag=True, help="Only check frontmatter schema.")
@click.option("--stale", is_flag=True, help="Only check staleness.")
@click.option("--orphans", is_flag=True, help="Only check orphaned files.")
@click.option("--indexes", is_flag=True, help="Only check INDEX.md consistency.")
@click.option("--circular", is_flag=True, help="Only check circular dependencies.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def validate(
    links: bool,
    schema: bool,
    stale: bool,
    orphans: bool,
    indexes: bool,
    circular: bool,
    as_json: bool,
) -> None:
    """Run validation checks on the documentation repo."""
    from spex.commands.validate import run

    checks = []
    if links:
        checks.append("links")
    if schema:
        checks.append("schema")
    if stale:
        checks.append("stale")
    if orphans:
        checks.append("orphans")
    if indexes:
        checks.append("indexes")
    if circular:
        checks.append("circular")
    run(checks=checks or None, as_json=as_json)


@main.command()
@click.argument("file_path", default="", type=click.Path())
@click.option("--type", "file_type", help="Filter by document type.")
@click.option("--stats", is_flag=True, help="Show repository statistics.")
@click.option("--depth", default=1, help="Neighborhood depth (default: 1).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def graph(file_path: str, file_type: str | None, stats: bool, depth: int, as_json: bool) -> None:
    """Explore the document graph."""
    from spex.commands.graph_cmd import run

    run(file_path=file_path, file_type=file_type, stats=stats, depth=depth, as_json=as_json)


@main.command()
@click.option("--days", default=14, help="Minimum staleness in days.")
@click.option("--type", "file_type", help="Filter by document type.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def stale(days: int, file_type: str | None, as_json: bool) -> None:
    """Find files that may need updating based on timestamps."""
    from spex.commands.stale import run

    run(days=days, file_type=file_type, as_json=as_json)


@main.command()
@click.option("--indexes", is_flag=True, help="Only regenerate INDEX files.")
@click.option("--dashboard", is_flag=True, help="Only regenerate dashboard.")
@click.option("--dry-run", is_flag=True, help="Show what would be generated.")
def compile(indexes: bool, dashboard: bool, dry_run: bool) -> None:
    """Auto-generate files from the graph."""
    from spex.commands.compile import run

    run(indexes=indexes, dashboard=dashboard, dry_run=dry_run)


@main.command()
@click.option("--stdout", is_flag=True, help="Print to stdout instead of writing file.")
def init(stdout: bool) -> None:
    """Generate spex.yaml from inferred state."""
    from spex.commands.init import run

    run(stdout=stdout)


@main.command()
@click.option("--watch", is_flag=True, help="Rebuild graph on file changes.")
def serve(watch: bool) -> None:
    """Start the MCP server."""
    from spex.commands.serve import run

    run(watch=watch)
