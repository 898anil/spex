"""spex serve - start the MCP server."""

from __future__ import annotations

import click


def run(watch: bool = False) -> None:
    from spex.mcp.server import start_server

    start_server(watch=watch)
