"""spex init - generate spex.yaml from inferred state."""

from __future__ import annotations

from pathlib import Path

import click
import yaml

from spex.graph.builder import build_graph


def run(stdout: bool = False) -> None:
    root = Path(".").resolve()
    graph = build_graph(root)

    # Collect inferred types and their field patterns
    type_info: dict[str, dict] = {}
    for node in graph:
        if node.doc_type == "document":
            continue
        entry = type_info.setdefault(node.doc_type, {
            "count": 0,
            "fields": {},
            "paths": [],
        })
        entry["count"] += 1
        if len(entry["paths"]) < 3:
            entry["paths"].append(node.path)
        if node.frontmatter:
            for key in node.frontmatter.keys:
                entry["fields"][key] = entry["fields"].get(key, 0) + 1

    # Build types section
    types_config = {}
    for doc_type, info in sorted(type_info.items()):
        # Only include fields present in >50% of files of this type
        threshold = info["count"] * 0.5
        required = sorted(k for k, v in info["fields"].items() if v >= threshold)
        optional = sorted(k for k, v in info["fields"].items() if v < threshold and v > 1)

        type_entry = {"count": info["count"]}
        if required:
            type_entry["required_fields"] = required
        if optional:
            type_entry["optional_fields"] = optional
        type_entry["examples"] = info["paths"][:3]
        types_config[doc_type] = type_entry

    # Collect relationship types
    rel_counts: dict[str, int] = {}
    for edge in graph.edges:
        rel_counts[edge.relationship] = rel_counts.get(edge.relationship, 0) + 1

    # Detect ID patterns in use
    id_patterns = set()
    for node in graph:
        if node.frontmatter:
            file_id = node.frontmatter.get("id")
            if isinstance(file_id, str):
                # Detect the pattern
                import re
                if re.match(r"^[A-Z]{2,4}-\d", file_id):
                    prefix = re.match(r"^([A-Z]{2,4})-", file_id).group(1)
                    id_patterns.add(prefix)

    config = {
        "version": "1",
        "scan": {
            "root": ".",
            "exclude": [".git", "node_modules", "__pycache__", ".venv"],
        },
        "types": types_config,
        "relationships": {
            rel: count for rel, count in sorted(rel_counts.items(), key=lambda x: -x[1])
        },
    }

    if id_patterns:
        config["id_patterns"] = sorted(id_patterns)

    config["stats"] = {
        "total_files": len(graph),
        "total_edges": len(graph.edges),
        "types_detected": len(types_config),
    }

    output = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if stdout:
        click.echo(output)
    else:
        out_path = root / "spex.yaml"
        out_path.write_text(output)
        click.echo(f"Generated {out_path} ({len(graph)} files, {len(types_config)} types detected)")
