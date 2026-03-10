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
    """Detect circular dependency chains.

    Only follows pipeline edges (semantic relationships like derives_to,
    satisfied_by, implemented_by). Skips structural/navigational edges
    (links_to, related_to, indexed_by) which create noise from bidirectional
    links and INDEX cross-references that are normal in documentation repos.
    """
    from spex.config import STRUCTURAL_RELATIONSHIPS

    issues = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    # Build filtered adjacency: only pipeline edges
    pipeline_outgoing: dict[str, list[tuple[str, str]]] = {}
    for edge in graph.edges:
        if edge.relationship not in STRUCTURAL_RELATIONSHIPS:
            pipeline_outgoing.setdefault(edge.source, []).append(
                (edge.target, edge.relationship)
            )

    def _dfs(path: str, chain: list[str]) -> None:
        visited.add(path)
        rec_stack.add(path)
        chain.append(path)
        for target, _rel in pipeline_outgoing.get(path, []):
            if target in rec_stack:
                cycle_start = chain.index(target)
                cycle = chain[cycle_start:] + [target]
                cycles.append(cycle)
            elif target not in visited:
                _dfs(target, chain)
        chain.pop()
        rec_stack.discard(path)

    for node in graph:
        if node.path not in visited:
            _dfs(node.path, [])

    seen_cycles: set[tuple[str, ...]] = set()
    for cycle in cycles:
        # Skip 2-node cycles (bidirectional relationships, not real circular deps)
        # e.g., domain-spec → tech-spec and tech-spec → domain-spec
        unique_nodes = set(cycle[:-1])
        if len(unique_nodes) <= 2:
            continue

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


def _check_required_sections(graph: Graph, root: Path) -> list[dict]:
    """Check that documents have required sections (from config type_rules or doc_specs)."""
    from spex.config import load_config

    config = load_config(root)
    issues = []

    # Build section requirements from type_rules and doc_specs
    section_reqs: dict[str, list[str]] = {}
    for rule in config.type_rules:
        if rule.required_sections:
            section_reqs[rule.type] = rule.required_sections
    for spec in config.doc_specs:
        if spec.required_sections:
            section_reqs[spec.type] = spec.required_sections

    if not section_reqs:
        return issues

    for node in graph:
        required = section_reqs.get(node.doc_type)
        if not required:
            continue

        file_path = root / node.path
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8", errors="replace")
        for section in required:
            # Check for the heading text (allowing for trailing content)
            if section not in content:
                issues.append({
                    "check": "sections",
                    "severity": "warning",
                    "file": node.path,
                    "message": f"Missing required section '{section}' for type '{node.doc_type}'",
                })

    return issues


def _check_chains(graph: Graph) -> list[dict]:
    """Check requirement chain completeness (from config chain rules)."""
    from spex.config import load_config

    config = load_config(Path(".").resolve())
    issues = []

    for chain in config.chains:
        anchor_nodes = graph.nodes_of_type(chain.anchor_type)
        if not anchor_nodes:
            continue

        for anchor in anchor_nodes:
            if chain.match_by == "directory":
                anchor_dir = str(Path(anchor.path).parent)
                for required_type in chain.required_chain:
                    found = any(
                        n.doc_type == required_type
                        and str(Path(n.path).parent) == anchor_dir
                        for n in graph
                    )
                    if not found:
                        issues.append({
                            "check": "chains",
                            "severity": chain.severity,
                            "file": anchor.path,
                            "message": (
                                f"Chain '{chain.name}': missing '{required_type}' "
                                f"co-located with '{anchor.doc_type}'"
                            ),
                        })
            elif chain.match_by == "feature_id":
                # Match by feature number extracted from path
                import re

                m = re.search(r"/(\d{2})-", anchor.path)
                if not m:
                    continue
                feature_num = m.group(1)
                for required_type in chain.required_chain:
                    found = any(
                        n.doc_type == required_type and f"/{feature_num}-" in n.path
                        for n in graph
                    )
                    if not found:
                        issues.append({
                            "check": "chains",
                            "severity": chain.severity,
                            "file": anchor.path,
                            "message": (
                                f"Chain '{chain.name}': no '{required_type}' found "
                                f"for feature {feature_num}"
                            ),
                        })

    return issues


def _check_must_reference(graph: Graph) -> list[dict]:
    """Check that documents reference required types (from config doc_specs.must_reference)."""
    from spex.config import load_config

    config = load_config(Path(".").resolve())
    issues = []

    for spec in config.doc_specs:
        if not spec.must_reference:
            continue

        nodes = graph.nodes_of_type(spec.type)
        for node in nodes:
            outgoing = graph.outgoing(node.path)
            referenced_types = set()
            for edge in outgoing:
                target_node = graph.get_node(edge.target)
                if target_node:
                    referenced_types.add(target_node.doc_type)

            for req_type in spec.must_reference:
                if req_type not in referenced_types:
                    issues.append({
                        "check": "must_reference",
                        "severity": "warning",
                        "file": node.path,
                        "message": (
                            f"Type '{spec.type}' should reference '{req_type}' "
                            f"but no outgoing link found"
                        ),
                    })

    return issues


ALL_CHECKS = {
    "links": _check_broken_links,
    "orphans": _check_orphans,
    "circular": _check_circular,
    "indexes": _check_indexes,
    "schema": _check_frontmatter,
    "sections": _check_required_sections,
    "chains": _check_chains,
    "must_reference": _check_must_reference,
}

# Checks that need root path vs graph-only
_NEEDS_ROOT = {"links", "indexes", "sections"}


def run(checks: list[str] | None = None, as_json: bool = False) -> None:
    from spex.config import load_config

    root = Path(".").resolve()
    config = load_config(root)
    graph = build_graph(root, config=config)

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
