"""MCP stdio server implementing the Model Context Protocol.

Builds the document graph on startup and exposes tools for
impact analysis, context assembly, and graph queries.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from spex.graph.builder import build_graph
from spex.graph.model import Graph
from spex.mcp.tools import TOOLS, handle_tool_call

SERVER_INFO = {
    "name": "spex",
    "version": "0.1.0",
}

_graph: Graph | None = None
_root: Path | None = None


def _ensure_graph() -> tuple[Graph, Path]:
    global _graph, _root
    if _graph is None:
        from spex.config import load_config

        _root = Path(".").resolve()
        config = load_config(_root)
        _graph = build_graph(_root, config=config)
        print(
            f"spex: graph built ({len(_graph)} nodes, {len(_graph.edges)} edges)",
            file=sys.stderr,
        )
    return _graph, _root


def handle_message(msg: dict) -> dict | None:
    """Handle an incoming JSON-RPC message."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        graph, root = _ensure_graph()
        try:
            result_text = handle_tool_call(tool_name, arguments, graph, root)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": False,
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                    "isError": True,
                },
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return None


def start_server(watch: bool = False) -> None:
    """Run the MCP server over stdio."""
    # Pre-build graph
    _ensure_graph()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
