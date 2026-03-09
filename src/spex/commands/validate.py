"""spex validate - run validation checks on the documentation repo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from spex.graph.builder import build_graph
from spex.graph.model import Graph


def _check_broken_links(graph: Graph, root: Path) -> list[dict]:
    """Find edges whose targets don't resolve to actual files."""
    issues = []
    for edge in graph.edges:
        if edge.origin == "link":
            target_path = root / edge.target
            if not target_path.exists():
                issues.append({
                    "check": "links",
                    "severity": "error",
                    "file": edge.source,
                    "line": edge.line,
                    "message": f"Broken link to {edge.target}",
                })
    return issues


def _check_orphans(graph: Graph) -> list[dict]:
    """Find files with no incoming or outgoing edges (completely disconnected)."""
    issues = []
    for node in graph:
        if node.is_index:
            continue
        incoming = graph.incoming(node.path)
        outgoing = graph.outgoing(node.path)
        if not incoming and not outgoing:
            issues.append({
                "check": "orphans",
                "severity": "warning",
                "file": node.path,
                "message": "Orphaned file: no incoming or outgoing relationships",
            })
    return issues


def _check_circular(graph: Graph) -> list[dict]:
    """Detect circular dependency chains."""
    issues = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def _dfs(path: str, chain: list[str]) -> None:
        visited.add(path)
        rec_stack.add(path)
        chain.append(path)
        for edge in graph.outgoing(path):
            if edge.target in rec_stack:
                cycle_start = chain.index(edge.target)
                cycle = chain[cycle_start:] + [edge.target]
                cycles.append(cycle)
            elif edge.target not in visited:
                _dfs(edge.target, chain)
        chain.pop()
        rec_stack.discard(path)

    for node in graph:
        if node.path not in visited:
            _dfs(node.path, [])

    seen_cycles: set[tuple[str, ...]] = set()
    for cycle in cycles:
        normalized = tuple(sorted(cycle[:-1]))
        if normalized not in seen_cycles:
            seen_cycles.add(normalized)
            issues.append({
                "check": "circular",
                "severity": "warning",
                "file": cycle[0],
                "message": f"Circular dependency: {' -> '.join(cycle)}",
            })

    return issues


def _check_indexes(graph: Graph, root: Path) -> list[dict]:
    """Check that directories with markdown files have an INDEX.md."""
    issues = []
    dirs_with_files: set[str] = set()
    dirs_with_index: set[str] = set()

    for node in graph:
        parent = str(Path(node.path).parent)
        dirs_with_files.add(parent)
        if node.is_index:
            dirs_with_index.add(parent)

    for d in sorted(dirs_with_files):
        files_in_dir = [
            n for n in graph if str(Path(n.path).parent) == d and not n.is_index
        ]
        if len(files_in_dir) >= 2 and d not in dirs_with_index:
            issues.append({
                "check": "indexes",
                "severity": "info",
                "file": d,
                "message": f"Directory has {len(files_in_dir)} files but no INDEX.md",
            })

    return issues


def _check_frontmatter(graph: Graph) -> list[dict]:
    """Check that frontmatter has expected fields based on document type."""
    issues = []
    type_fields: dict[str, set[str]] = {}
    for node in graph:
        if node.frontmatter:
            type_fields.setdefault(node.doc_type, set()).update(node.frontmatter.keys)

    for node in graph:
        if node.doc_type == "document" or node.doc_type == "index":
            continue
        expected = type_fields.get(node.doc_type, set())
        if expected and node.frontmatter:
            missing = expected - node.frontmatter.keys
            common_missing = {k for k in missing if sum(
                1 for n2 in graph.nodes_of_type(node.doc_type)
                if n2.frontmatter and k in n2.frontmatter.keys
            ) > len(graph.nodes_of_type(node.doc_type)) * 0.7}
            for key in sorted(common_missing):
                issues.append({
                    "check": "schema",
                    "severity": "info",
                    "file": node.path,
                    "message": f"Missing common field '{key}' for type '{node.doc_type}'",
                })
        elif not node.frontmatter and expected:
            issues.append({
                "check": "schema",
                "severity": "info",
                "file": node.path,
                "message": f"No frontmatter; type '{node.doc_type}' peers usually have one",
            })

    return issues


ALL_CHECKS = {
    "links": _check_broken_links,
    "orphans": _check_orphans,
    "circular": _check_circular,
    "indexes": _check_indexes,
    "schema": _check_frontmatter,
}

# Checks that need root path vs graph-only
_NEEDS_ROOT = {"links", "indexes"}


def run(checks: list[str] | None = None, as_json: bool = False) -> None:
    root = Path(".").resolve()
    graph = build_graph(root)

    selected = checks or list(ALL_CHECKS.keys())
    all_issues: list[dict] = []

    for check_name in selected:
        fn = ALL_CHECKS.get(check_name)
        if not fn:
            click.echo(f"Unknown check: {check_name}", err=True)
            continue

        if check_name in _NEEDS_ROOT:
            issues = fn(graph, root)
        else:
            issues = fn(graph)
        all_issues.extend(issues)

    if as_json:
        click.echo(json.dumps({"issues": all_issues, "total": len(all_issues)}, indent=2))
        return

    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]
    infos = [i for i in all_issues if i["severity"] == "info"]

    if not all_issues:
        click.echo(f"All checks passed ({len(graph)} files scanned)")
        return

    for issue in sorted(all_issues, key=lambda x: (x["severity"], x["file"])):
        sev = issue["severity"].upper()
        loc = issue["file"]
        if issue.get("line"):
            loc += f":{issue['line']}"
        click.echo(f"  [{sev}] {loc}: {issue['message']}")

    click.echo(
        f"\n{len(errors)} errors, {len(warnings)} warnings, {len(infos)} info "
        f"({len(graph)} files scanned)"
    )

    if errors:
        sys.exit(1)
