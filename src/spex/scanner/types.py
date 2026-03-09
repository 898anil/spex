"""Data classes for parsed file content."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Heading:
    """A markdown heading."""

    level: int  # 1-6
    text: str
    line: int


@dataclass(frozen=True)
class Link:
    """A markdown link [text](target)."""

    text: str
    target: str  # raw target as written
    line: int
    is_image: bool = False


@dataclass
class Frontmatter:
    """Parsed YAML frontmatter."""

    raw: dict  # the full parsed YAML dict
    keys: frozenset[str] = field(default_factory=frozenset)

    def get(self, key: str, default: object = None) -> object:
        return self.raw.get(key, default)

    def __post_init__(self) -> None:
        if not self.keys:
            self.keys = frozenset(self.raw.keys())


@dataclass
class ParsedFile:
    """A fully parsed markdown file."""

    path: Path  # absolute path
    rel_path: str  # relative to scan root
    frontmatter: Frontmatter | None
    headings: list[Heading]
    links: list[Link]
    line_count: int
    modified_time: float  # os.path.getmtime
    size_bytes: int
