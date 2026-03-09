"""Directory walker with .gitignore support.

Walks a directory tree and yields paths to markdown files,
respecting .gitignore rules and default exclusions.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
    ".eggs",
}


def _load_gitignore(root: Path) -> list[str]:
    """Load .gitignore patterns from the root directory."""
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return []
    patterns = []
    for line in gitignore.read_text(errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _is_excluded(path: Path, root: Path, gitignore_patterns: list[str]) -> bool:
    """Check if a path should be excluded."""
    rel = str(path.relative_to(root))
    for pattern in gitignore_patterns:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
            return True
    return False


def walk_markdown_files(
    root: Path,
    extra_excludes: list[str] | None = None,
) -> list[Path]:
    """Walk directory tree and return all markdown file paths.

    Respects .gitignore and default exclusions.
    """
    root = root.resolve()
    gitignore_patterns = _load_gitignore(root)
    excludes = DEFAULT_EXCLUDES | set(extra_excludes or [])

    files: list[Path] = []

    for item in sorted(root.rglob("*.md")):
        # Skip files in excluded directories
        skip = False
        for part in item.relative_to(root).parts[:-1]:
            if part in excludes or part.startswith("."):
                skip = True
                break
        if skip:
            continue

        # Check gitignore patterns
        if _is_excluded(item, root, gitignore_patterns):
            continue

        files.append(item)

    return files
