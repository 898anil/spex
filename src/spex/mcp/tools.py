"""MCP tool definitions and handlers."""

from __future__ import annotations

import json
from pathlib import Path

from spex.graph.model import Graph
from spex.graph.query import context_bundle, impact

TOOLS = [
    {
        "name": "get_change_impact",
        "description": (
            "Given a file path that was changed, returns all upstream and downstream "
            "files affected by the change with recursive depth traversal. Use this "
            "FIRST when any documentation file is modified to know exactly which "
            "other files need updating."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path to the changed file.",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to traverse (default 2, max 10).",
                    "default": 2,
                },
                "direction": {
                    "type": "string",
                    "enum": ["downstream", "upstream", "both"],
                    "description": "Which direction to traverse.",
                    "default": "both",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_context_bundle",
        "description": (
            "Returns file contents for a changed file and all affected files. "
            "Use AFTER get_change_impact to get the actual content you need to "
            "read and update."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path to the target file.",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to include (default 2).",
                    "default": 2,
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Whether to include file contents (default true).",
                    "default": True,
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_propagation_steps",
        "description": (
            "Returns human-readable step-by-step instructions for propagating "
            "a change through the dependency chain."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path to the changed file.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "query_graph",
        "description": (
            "Query the document graph. List document types, find files by type, "
            "search by frontmatter fields, or get repository statistics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["list_types", "list_files", "search", "stats"],
                    "description": "Type of query to run.",
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by document type (for list_files, search).",
                },
                "field": {
                    "type": "string",
                    "description": "Frontmatter field to filter on (for search).",
                },
                "value": {
                    "type": "string",
                    "description": "Value to match (for search).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50).",
                    "default": 50,
                },
            },
            "required": ["query_type"],
        },
    },
    {
        "name": "validate_file",
        "description": "Validate a single file's frontmatter, links, and relationships.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path to validate.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_stale_files",
        "description": (
            "Find files that may need updating based on timestamp analysis. "
            "A file is stale if its upstream dependencies were modified more recently."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_type": {
                    "type": "string",
                    "description": "Filter by document type (optional).",
                },
                "min_days": {
                    "type": "integer",
                    "description": "Minimum staleness in days (default 7).",
                    "default": 7,
                },
            },
        },
    },
    {
        "name": "get_document_type",
        "description": (
            "Get the inferred type information for a file, including required "
            "fields and expected relationships. Useful when creating new documents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Repo-relative path (existing or planned).",
                },
            },
            "required": ["file_path"],
        },
    },
]


def handle_tool_call(
    name: str, arguments: dict, graph: Graph, root: Path
) -> str:
    """Dispatch a tool call and return JSON result."""

    if name == "get_change_impact":
        result = impact(
            graph,
            arguments["file_path"],
            depth=arguments.get("depth", 2),
            direction=arguments.get("direction", "both"),
        )
        return json.dumps({
            "target": result.target,
            "type": result.target_type,
            "cascade": result.cascade,
            "total_affected": result.total_affected,
            "downstream_count": result.downstream_count,
            "upstream_count": result.upstream_count,
        }, indent=2)

    if name == "get_context_bundle":
        bundle = context_bundle(
            graph,
            arguments["file_path"],
            root,
            depth=arguments.get("depth", 2),
            include_content=arguments.get("include_content", True),
        )
        return json.dumps({
            "target": bundle.target,
            "files": bundle.files,
            "file_count": bundle.file_count,
            "estimated_tokens": bundle.estimated_tokens,
        }, indent=2)

    if name == "get_propagation_steps":
        result = impact(graph, arguments["file_path"], depth=3, direction="downstream")
        steps = [f"1. You changed: {result.target} ({result.target_type})"]
        n = 2
        for item in result.cascade:
            if item["direction"] == "downstream":
                steps.append(
                    f"{n}. [{item['type'].upper()}] {item['path']}\n"
                    f"   Action: review for consistency ({item['relationship']})"
                )
                n += 1
        steps.append(f"{n}. Update 'Last Updated' date in all modified files")
        return json.dumps({
            "changed_file": result.target,
            "type": result.target_type,
            "steps": steps,
            "affected_file_count": result.total_affected,
        }, indent=2)

    if name == "query_graph":
        query_type = arguments.get("query_type", "stats")

        if query_type == "list_types":
            return json.dumps({"types": graph.all_types()}, indent=2)

        if query_type == "list_files":
            file_type = arguments.get("file_type")
            limit = arguments.get("limit", 50)
            if file_type:
                nodes = graph.nodes_of_type(file_type)[:limit]
            else:
                nodes = list(graph)[:limit]
            return json.dumps({
                "files": [
                    {"path": n.path, "type": n.doc_type, "layer": n.layer}
                    for n in nodes
                ],
                "total": len(nodes),
            }, indent=2)

        if query_type == "search":
            file_type = arguments.get("file_type")
            field = arguments.get("field")
            value = arguments.get("value")
            limit = arguments.get("limit", 50)
            results = []
            candidates = graph.nodes_of_type(file_type) if file_type else list(graph)
            for node in candidates:
                if field and value and node.frontmatter:
                    fv = node.frontmatter.get(field)
                    if str(fv) == value:
                        results.append({"path": node.path, "type": node.doc_type})
                elif not field:
                    results.append({"path": node.path, "type": node.doc_type})
                if len(results) >= limit:
                    break
            return json.dumps({"results": results, "total": len(results)}, indent=2)

        # stats
        return json.dumps({
            "files": len(graph),
            "types": graph.all_types(),
            "edges": len(graph.edges),
        }, indent=2)

    if name == "validate_file":
        file_path = arguments["file_path"]
        node = graph.get_node(file_path)
        if not node:
            return json.dumps({"file_path": file_path, "error": "File not found in graph"})
        issues = []
        # Check broken outgoing links
        for edge in graph.outgoing(file_path):
            if edge.origin == "link":
                target_path = root / edge.target
                if not target_path.exists():
                    issues.append({
                        "severity": "error",
                        "message": f"Broken link to {edge.target}",
                        "line": edge.line,
                    })
        # Check if orphaned
        if not graph.incoming(file_path) and not graph.outgoing(file_path) and not node.is_index:
            issues.append({"severity": "warning", "message": "File is orphaned (no relationships)"})
        return json.dumps({
            "file_path": file_path,
            "valid": len([i for i in issues if i["severity"] == "error"]) == 0,
            "issues": issues,
        }, indent=2)

    if name == "get_stale_files":
        import time
        file_type = arguments.get("file_type")
        min_days = arguments.get("min_days", 7)
        threshold = min_days * 86400
        stale = []
        for node in graph:
            if file_type and node.doc_type != file_type:
                continue
            incoming = graph.incoming(node.path)
            for edge in incoming:
                dep = graph.get_node(edge.source)
                if dep and dep.modified_time > node.modified_time:
                    delta = dep.modified_time - node.modified_time
                    if delta >= threshold:
                        stale.append({
                            "path": node.path,
                            "type": node.doc_type,
                            "newer_dependency": dep.path,
                            "days_behind": round(delta / 86400, 1),
                        })
                        break
        return json.dumps({"stale_files": stale, "total_stale": len(stale)}, indent=2)

    if name == "get_document_type":
        node = graph.get_node(arguments["file_path"])
        if node:
            return json.dumps({
                "file_path": node.path,
                "inferred_type": node.doc_type,
                "frontmatter_keys": sorted(node.frontmatter.keys) if node.frontmatter else [],
            }, indent=2)
        return json.dumps({
            "file_path": arguments["file_path"],
            "error": "File not found in graph",
        })

    return json.dumps({"error": f"Unknown tool: {name}"})
