"""Tests for the markdown parser."""

from pathlib import Path

from spex.scanner.parser import (
    parse_file,
    parse_frontmatter,
    parse_headings,
    parse_links,
)


def test_parse_frontmatter_basic():
    content = "---\nid: F-01\nname: Test\n---\n\n# Hello\n"
    fm = parse_frontmatter(content)
    assert fm is not None
    assert fm.get("id") == "F-01"
    assert fm.get("name") == "Test"
    assert "id" in fm.keys
    assert "name" in fm.keys


def test_parse_frontmatter_none():
    assert parse_frontmatter("# Just a heading\n") is None


def test_parse_headings():
    content = "# Title\n\nSome text\n\n## Section\n\n### Sub\n"
    headings = parse_headings(content)
    assert len(headings) == 3
    assert headings[0].level == 1
    assert headings[0].text == "Title"
    assert headings[1].level == 2
    assert headings[2].level == 3


def test_parse_links():
    content = "See [Feature A](../features/overview.md) and [external](https://example.com).\n"
    links = parse_links(content)
    assert len(links) == 2
    assert links[0].target == "../features/overview.md"
    assert links[0].text == "Feature A"
    assert not links[0].is_image


def test_parse_links_image():
    content = "![alt](image.png)\n"
    links = parse_links(content)
    assert len(links) == 1
    assert links[0].is_image


def test_parse_file(minimal_root):
    path = minimal_root / "features" / "overview.md"
    parsed = parse_file(path, minimal_root)
    assert parsed.rel_path == "features/overview.md"
    assert parsed.frontmatter is not None
    assert parsed.frontmatter.get("id") == "F-01"
    assert len(parsed.links) >= 2
    assert parsed.line_count > 0
