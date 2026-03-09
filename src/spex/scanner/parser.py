"""Markdown file parser.

Extracts frontmatter, headings, and links from a single markdown file.
No interpretation or inference - just extraction.

ID pattern detection is handled by the graph builder, which auto-detects
patterns from frontmatter 'id' fields across the repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from spex.scanner.types import Frontmatter, Heading, Link, ParsedFile

# Patterns
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")


def parse_frontmatter(content: str) -> Frontmatter | None:
    """Extract and parse YAML frontmatter from markdown content."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return Frontmatter(raw=data)


def parse_headings(content: str) -> list[Heading]:
    """Extract all headings with their line numbers."""
    headings = []
    for i, line in enumerate(content.split("\n"), 1):
        m = HEADING_RE.match(line)
        if m:
            headings.append(Heading(level=len(m.group(1)), text=m.group(2).strip(), line=i))
    return headings


def parse_links(content: str) -> list[Link]:
    """Extract all markdown links with line numbers."""
    links = []
    for i, line in enumerate(content.split("\n"), 1):
        for m in LINK_RE.finditer(line):
            links.append(
                Link(
                    text=m.group(2),
                    target=m.group(3),
                    line=i,
                    is_image=m.group(1) == "!",
                )
            )
    return links


def parse_file(path: Path, root: Path) -> ParsedFile:
    """Parse a single markdown file into a ParsedFile object."""
    content = path.read_text(encoding="utf-8", errors="replace")
    stat = path.stat()
    return ParsedFile(
        path=path,
        rel_path=str(path.relative_to(root)),
        frontmatter=parse_frontmatter(content),
        headings=parse_headings(content),
        links=[link for link in parse_links(content) if not link.is_image],
        line_count=content.count("\n") + 1,
        modified_time=stat.st_mtime,
        size_bytes=stat.st_size,
    )
