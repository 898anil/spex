"""Graph builder - orchestrates scanning and inference to produce a Graph.

Inference is generic by default but can be guided by a spex.yaml config
that provides type overrides (pattern-based), semantic relationship names,
and custom ID patterns for cross-reference detection.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from spex.config import SpexConfig
from spex.graph.model import Edge, Graph, Node
from spex.scanner.parser import parse_file
from spex.scanner.types import ParsedFile
from spex.scanner.walker import walk_markdown_files


# ---------------------------------------------------------------------------
# Type inference (generic)
# ---------------------------------------------------------------------------

def _infer_layer(rel_path: str) -> str | None:
    """Infer the documentation layer from the file path.

    Detects numbered directory prefixes like 01-intro, 03-product, etc.
    This is a common documentation convention, not repo-specific.
    """
    for part in rel_path.split("/"):
        if len(part) >= 2 and part[:2].isdigit() and part[2:3] == "-":
            return part
    return None


def _singularize(word: str) -> str:
    """Naive English singularization for directory names."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"  # stories -> story, journeys handled below
    if word.endswith("ses") and len(word) > 4:
        return word[:-2]  # analyses -> analyse (close enough)
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _infer_doc_type(parsed: ParsedFile) -> str:
    """Infer document type using only generic signals.

    Priority:
    1. Well-known index filenames (INDEX.md, README.md)
    2. Explicit frontmatter 'type' field
    3. Parent directory name as type (the most common convention)
    """
    name = Path(parsed.rel_path).name.lower()

    # 1. Index files
    if name in ("index.md", "readme.md"):
        return "index"

    # 2. Explicit frontmatter type
    if parsed.frontmatter:
        fm_type = parsed.frontmatter.get("type")
        if isinstance(fm_type, str) and fm_type.strip():
            return fm_type.strip().lower().replace(" ", "-")

    # 3. Parent directory name as type (singularized)
    parent = Path(parsed.rel_path).parent.name
    if parent and parent != ".":
        # Strip leading number prefix (e.g., "03-product" -> "product")
        clean = re.sub(r"^\d+-", "", parent)
        if clean:
            clean = _singularize(clean)
            return clean.lower().replace(" ", "-")

    return "document"


def _cluster_types_by_frontmatter(parsed_files: list[ParsedFile]) -> dict[str, str]:
    """Refine type assignments using frontmatter key clustering.

    Only creates sub-types when a directory has a large number of files
    with clearly distinct frontmatter schemas (indicating genuinely
    different document types co-located in the same directory).
    """
    # Group files by (parent_dir, frozenset of frontmatter keys)
    dir_key_groups: dict[tuple[str, frozenset[str]], list[str]] = {}
    for parsed in parsed_files:
        if not parsed.frontmatter or not parsed.frontmatter.keys:
            continue
        parent = str(Path(parsed.rel_path).parent)
        group_key = (parent, parsed.frontmatter.keys)
        dir_key_groups.setdefault(group_key, []).append(parsed.rel_path)

    overrides: dict[str, str] = {}
    dir_schemas: dict[str, list[tuple[frozenset[str], list[str]]]] = {}
    for (parent, keys), paths in dir_key_groups.items():
        dir_schemas.setdefault(parent, []).append((keys, paths))

    for parent, schema_groups in dir_schemas.items():
        # Only differentiate if there are multiple schemas AND enough files
        # to be meaningful (at least 5 files per group)
        if len(schema_groups) <= 1:
            continue

        total_files = sum(len(paths) for _, paths in schema_groups)
        if total_files < 10:
            continue

        # Only split if schemas are really different (Jaccard < 0.5)
        all_keys = [keys for keys, _ in schema_groups]
        for i, (keys_a, paths_a) in enumerate(schema_groups):
            for keys_b, _ in schema_groups[i + 1:]:
                intersection = len(keys_a & keys_b)
                union = len(keys_a | keys_b)
                if union > 0 and intersection / union < 0.5 and len(paths_a) >= 3:
                    unique = keys_a - keys_b
                    if unique:
                        qualifier = sorted(unique)[0]
                        base_type = re.sub(r"^\d+-", "", parent.split("/")[-1]) if parent != "." else "document"
                        for p in paths_a:
                            overrides[p] = f"{base_type}-{qualifier}"

    return overrides


# ---------------------------------------------------------------------------
# Relationship inference (generic)
# ---------------------------------------------------------------------------

def _infer_relationship(source_path: str, target_path: str) -> str:
    """Infer relationship type from structural patterns only.

    No hardcoded domain types. Uses:
    - Index file patterns
    - Directory parent/child relationships
    - Sibling (same directory) relationships
    - Different top-level directory = cross-reference
    """
    src_name = Path(source_path).name.lower()
    tgt_name = Path(target_path).name.lower()
    src_parent = str(Path(source_path).parent)
    tgt_parent = str(Path(target_path).parent)

    # Index -> children
    if src_name in ("index.md", "readme.md"):
        return "indexes"
    if tgt_name in ("index.md", "readme.md"):
        return "indexed_by"

    # Parent directory contains child directory
    if tgt_parent.startswith(src_parent + "/"):
        return "contains"
    if src_parent.startswith(tgt_parent + "/"):
        return "contained_by"

    # Same directory = siblings
    if src_parent == tgt_parent:
        return "related_to"

    # Different top-level directories
    src_top = source_path.split("/")[0] if "/" in source_path else ""
    tgt_top = target_path.split("/")[0] if "/" in target_path else ""
    if src_top and tgt_top and src_top != tgt_top:
        return "cross_references"

    return "links_to"


# ---------------------------------------------------------------------------
# Frontmatter reference detection (generic)
# ---------------------------------------------------------------------------

def _looks_like_path(value: str) -> bool:
    """Check if a string looks like a file path reference."""
    if not isinstance(value, str):
        return False
    # Contains path separator or ends with .md
    if "/" in value or value.endswith(".md"):
        return True
    return False


def _looks_like_id(value: str) -> bool:
    """Check if a string looks like a document ID."""
    if not isinstance(value, str) or len(value) > 50:
        return False
    # Common ID patterns: UPPER-digits, kebab-case IDs, etc.
    return bool(re.match(r"^[A-Za-z][\w-]*$", value))


def _extract_frontmatter_edges(parsed: ParsedFile) -> list[tuple[str, str]]:
    """Extract relationship edges from frontmatter by detecting path/ID-like values.

    Instead of checking a hardcoded list of field names, we scan ALL
    frontmatter fields and detect values that look like references
    (paths or IDs).
    """
    if not parsed.frontmatter:
        return []

    edges: list[tuple[str, str]] = []

    # Skip these common non-reference fields
    skip_fields = {
        "title", "name", "description", "summary", "date", "created",
        "updated", "author", "status", "version", "tags", "draft",
        "weight", "order", "slug", "layout", "template", "lang",
        "locale", "published", "modified", "excerpt",
    }

    for key in parsed.frontmatter.keys:
        if key.lower() in skip_fields:
            continue

        value = parsed.frontmatter.get(key)
        if value is None:
            continue

        # Normalize to list
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = [str(v) for v in value if isinstance(v, (str, int, float))]
        else:
            continue

        for v in values:
            v = str(v).strip()
            if _looks_like_path(v) or (
                _looks_like_id(v) and len(v) > 2
            ):
                edges.append((key, v))

    return edges


# ---------------------------------------------------------------------------
# ID pattern auto-detection (generic)
# ---------------------------------------------------------------------------

def _detect_id_patterns(parsed_files: list[ParsedFile]) -> list[re.Pattern]:
    """Auto-detect ID patterns from frontmatter 'id' fields.

    Instead of hardcoded regexes, we look at what IDs actually exist
    in the repo and derive patterns from them.
    """
    id_examples: list[str] = []
    for parsed in parsed_files:
        if parsed.frontmatter:
            file_id = parsed.frontmatter.get("id")
            if isinstance(file_id, str):
                id_examples.append(file_id)

    if not id_examples:
        return []

    # Discover prefix patterns: group by the alphabetic prefix
    prefix_counts: Counter[str] = Counter()
    for eid in id_examples:
        m = re.match(r"^([A-Za-z][\w]*?)[-_]", eid)
        if m:
            prefix_counts[m.group(1)] += 1

    patterns: list[re.Pattern] = []
    for prefix, count in prefix_counts.items():
        if count >= 2:  # Need at least 2 examples to consider it a pattern
            # Build a pattern that matches this prefix followed by separators and digits
            pat = rf"\b{re.escape(prefix)}[-_][\w-]+\b"
            patterns.append(re.compile(pat))

    return patterns


# ---------------------------------------------------------------------------
# Main graph builder
# ---------------------------------------------------------------------------

def _resolve_link(source_path: str, target: str, root: Path) -> str | None:
    """Resolve a relative markdown link to a repo-relative path."""
    if target.startswith(("http://", "https://", "mailto:", "#", "javascript:")):
        return None

    target_path = target.split("#")[0]
    if not target_path:
        return None

    source_dir = (root / source_path).parent
    resolved = (source_dir / target_path).resolve()

    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return None


def build_graph(
    root: str | Path,
    extra_excludes: list[str] | None = None,
    config: SpexConfig | None = None,
) -> Graph:
    """Build the complete document graph from a directory.

    If config is provided, uses pattern-based type overrides, semantic
    relationship names, and custom ID patterns from spex.yaml.
    Otherwise falls back to generic inference.
    """
    root = Path(root).resolve()
    graph = Graph()

    # Step 1: Scan all files
    excludes = extra_excludes or []
    if config:
        excludes = list(set(excludes + config.scan_excludes))
    paths = walk_markdown_files(root, excludes or None)
    parsed_files: list[ParsedFile] = []
    for path in paths:
        try:
            parsed = parse_file(path, root)
            parsed_files.append(parsed)
        except Exception:
            continue

    # Step 2: Infer types and create nodes
    # Config type rules take priority, then frontmatter clustering, then generic inference
    cluster_overrides = _cluster_types_by_frontmatter(parsed_files)

    for parsed in parsed_files:
        # Priority: config pattern > frontmatter cluster > generic inference
        doc_type = None
        if config:
            doc_type = config.resolve_type(parsed.rel_path)
        if not doc_type:
            doc_type = cluster_overrides.get(parsed.rel_path) or _infer_doc_type(parsed)

        node = Node(
            path=parsed.rel_path,
            doc_type=doc_type,
            frontmatter=parsed.frontmatter,
            line_count=parsed.line_count,
            modified_time=parsed.modified_time,
            size_bytes=parsed.size_bytes,
            layer=_infer_layer(parsed.rel_path),
            is_index=Path(parsed.rel_path).name.lower() in ("index.md", "readme.md"),
        )
        graph.add_node(node)

    # Step 3: Build edges from inline links
    for parsed in parsed_files:
        src_node = graph.get_node(parsed.rel_path)
        for link in parsed.links:
            resolved = _resolve_link(parsed.rel_path, link.target, root)
            if resolved and resolved in graph:
                tgt_node = graph.get_node(resolved)
                # Try semantic relationship from config first
                relationship = None
                if config and src_node and tgt_node:
                    relationship = config.get_relationship_name(
                        src_node.doc_type, tgt_node.doc_type
                    )
                if not relationship:
                    relationship = _infer_relationship(parsed.rel_path, resolved)
                graph.add_edge(
                    Edge(
                        source=parsed.rel_path,
                        target=resolved,
                        relationship=relationship,
                        origin="link",
                        line=link.line,
                    )
                )

    # Step 4: Build edges from frontmatter references
    for parsed in parsed_files:
        fm_refs = _extract_frontmatter_edges(parsed)
        for field_name, ref in fm_refs:
            candidates = [ref, ref + ".md", ref + "/INDEX.md", ref + "/README.md"]
            for prefix in _guess_doc_roots(parsed_files):
                if not ref.startswith(prefix):
                    candidates.extend([
                        prefix + "/" + ref,
                        prefix + "/" + ref + ".md",
                    ])

            for candidate in candidates:
                if candidate in graph:
                    graph.add_edge(
                        Edge(
                            source=parsed.rel_path,
                            target=candidate,
                            relationship=field_name,
                            origin="frontmatter",
                        )
                    )
                    break

    # Step 5: Build edges from ID cross-references
    id_to_file: dict[str, str] = {}
    for parsed in parsed_files:
        if parsed.frontmatter:
            file_id = parsed.frontmatter.get("id")
            if isinstance(file_id, str):
                id_to_file[file_id] = parsed.rel_path

    # Use config ID patterns if available, otherwise auto-detect
    id_patterns = []
    if config and config.id_patterns:
        id_patterns = config.get_id_regex_patterns()
    if not id_patterns:
        id_patterns = _detect_id_patterns(parsed_files)

    if id_patterns:
        for parsed in parsed_files:
            content = (root / parsed.rel_path).read_text(
                encoding="utf-8", errors="replace"
            ) if (root / parsed.rel_path).exists() else ""
            for pattern in id_patterns:
                for match in pattern.finditer(content):
                    ref_id = match.group(0)
                    owner = id_to_file.get(ref_id)
                    if owner and owner != parsed.rel_path:
                        graph.add_edge(
                            Edge(
                                source=parsed.rel_path,
                                target=owner,
                                relationship="references",
                                origin="id_reference",
                                line=_line_of_match(content, match.start()),
                            )
                        )

    return graph


def _line_of_match(content: str, pos: int) -> int:
    """Get the 1-based line number for a character position."""
    return content[:pos].count("\n") + 1


def _guess_doc_roots(parsed_files: list[ParsedFile]) -> list[str]:
    """Guess common documentation root directories from file paths."""
    top_dirs: Counter[str] = Counter()
    for parsed in parsed_files:
        parts = parsed.rel_path.split("/")
        if len(parts) > 1:
            top_dirs[parts[0]] += 1

    # Return directories that contain a significant portion of files
    threshold = len(parsed_files) * 0.1
    return [d for d, count in top_dirs.items() if count >= threshold]
