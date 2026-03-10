"""Config loading for spex.

Loads spex.yaml from the project root and provides typed access to all
configuration: type overrides, relationship semantics, ID patterns,
validation rules, and SDD (spec-driven design) conventions.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class TypeRule(BaseModel):
    """A pattern-based type assignment rule."""

    pattern: str  # glob pattern like "docs/03-product/features/*/overview.md"
    type: str  # semantic type like "feature-overview"
    required_fields: list[str] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)


class RelationshipRule(BaseModel):
    """A semantic relationship definition."""

    from_type: str
    to_type: str
    relationship: str  # semantic name like "derives_to"
    via: str = ""  # how the link is created: "link", "frontmatter_field", "co-location"


class IDPattern(BaseModel):
    """A custom ID pattern for cross-reference detection."""

    prefix: str  # e.g., "PRQ"
    pattern: str  # regex like "PRQ-\\d{2}-\\d{3}[a-z]?"
    name: str = ""  # human name like "product-requirement"


class ChainRule(BaseModel):
    """A requirement chain completeness rule."""

    name: str  # e.g., "feature-completeness"
    anchor_type: str  # the type that starts the chain, e.g., "feature-overview"
    required_chain: list[str]  # e.g., ["prq", "trq", "tech-spec"]
    match_by: str = "directory"  # how to match: "directory" or "feature_id"
    severity: str = "warning"


class DocTypeSpec(BaseModel):
    """Document type specification for SDD validation."""

    type: str
    description: str = ""
    required_sections: list[str] = Field(default_factory=list)
    required_frontmatter: list[str] = Field(default_factory=list)
    must_reference: list[str] = Field(default_factory=list)  # must link to these types
    co_located_with: list[str] = Field(default_factory=list)  # expected sibling files


class SpexConfig(BaseModel):
    """Complete spex configuration."""

    version: str = "1"
    scan_root: str = "."
    scan_excludes: list[str] = Field(default_factory=lambda: [".git", "node_modules", "__pycache__", ".venv"])
    type_rules: list[TypeRule] = Field(default_factory=list)
    relationships: list[RelationshipRule] = Field(default_factory=list)
    id_patterns: list[IDPattern] = Field(default_factory=list)
    chains: list[ChainRule] = Field(default_factory=list)
    doc_specs: list[DocTypeSpec] = Field(default_factory=list)

    def resolve_type(self, rel_path: str) -> str | None:
        """Match a file path against type rules, return first match or None.

        Handles patterns that include a directory prefix (like "docs/...")
        by also trying to match the rel_path with the prefix prepended.
        """
        for rule in self.type_rules:
            if fnmatch.fnmatch(rel_path, rule.pattern):
                return rule.type
        # Try matching with common prefixes stripped from pattern
        for rule in self.type_rules:
            parts = rule.pattern.split("/", 1)
            if len(parts) == 2:
                prefix, rest = parts
                if fnmatch.fnmatch(rel_path, rest):
                    return rule.type
        return None

    def get_type_rule(self, doc_type: str) -> TypeRule | None:
        """Get the first rule that assigns a given type."""
        for rule in self.type_rules:
            if rule.type == doc_type:
                return rule
        return None

    def get_doc_spec(self, doc_type: str) -> DocTypeSpec | None:
        """Get the doc type specification for validation."""
        for spec in self.doc_specs:
            if spec.type == doc_type:
                return spec
        return None

    def get_id_regex_patterns(self) -> list[re.Pattern]:
        """Compile all configured ID patterns into regex objects."""
        patterns = []
        for idp in self.id_patterns:
            try:
                patterns.append(re.compile(idp.pattern))
            except re.error:
                continue
        return patterns

    def get_relationship_name(self, source_type: str, target_type: str) -> str | None:
        """Look up semantic relationship name for a source→target type pair."""
        for rule in self.relationships:
            if rule.from_type == source_type and rule.to_type == target_type:
                return rule.relationship
        return None

    def get_pipeline_relationships(self) -> set[str]:
        """Return all semantic relationship names defined in config.

        These are "pipeline" edges — real dependency relationships like
        derives_to, satisfied_by, implemented_by. Everything else (links_to,
        related_to, indexed_by) is structural/navigational.
        """
        return {rule.relationship for rule in self.relationships}


# Relationships that are structural/navigational, not pipeline dependencies.
# Pipeline edges are the semantic relationships defined in spex.yaml
# (derives_to, satisfied_by, implemented_by, etc.) — real dependency chains.
# Everything below is informational/navigational noise for impact analysis.
STRUCTURAL_RELATIONSHIPS = frozenset({
    "links_to",           # generic markdown link
    "related_to",         # same-directory sibling
    "indexed_by",         # INDEX.md cross-reference
    "indexes",            # INDEX.md listing
    "contains",           # directory hierarchy
    "contained_by",       # directory hierarchy
    "cross_references",   # cross-layer generic link
    "references",         # ID pattern mention (contextual, not dependency)
})


def load_config(root: Path) -> SpexConfig:
    """Load spex.yaml from root or any ancestor. Returns defaults if not found."""
    search_dir = root.resolve()
    # Search upward from root to find spex.yaml
    for _ in range(10):  # max 10 levels up
        candidates = [
            search_dir / "spex.yaml",
            search_dir / "spex.yml",
            search_dir / ".spex" / "config.yaml",
        ]
        for path in candidates:
            if path.exists():
                return _parse_config(path)
        parent = search_dir.parent
        if parent == search_dir:
            break
        search_dir = parent

    return SpexConfig()


def _parse_config(path: Path) -> SpexConfig:
    """Parse a spex.yaml file into a SpexConfig."""
    raw = yaml.safe_load(path.read_text()) or {}

    config = SpexConfig(
        version=raw.get("version", "1"),
        scan_root=raw.get("scan", {}).get("root", "."),
        scan_excludes=raw.get("scan", {}).get("exclude", [".git", "node_modules"]),
    )

    # Parse type rules
    for rule_data in raw.get("type_rules", []):
        config.type_rules.append(TypeRule(**rule_data))

    # Parse relationship definitions
    for rel_data in raw.get("relationships", []):
        if isinstance(rel_data, dict) and "from_type" in rel_data:
            config.relationships.append(RelationshipRule(**rel_data))

    # Parse ID patterns
    for idp_data in raw.get("id_patterns", []):
        config.id_patterns.append(IDPattern(**idp_data))

    # Parse chain rules
    for chain_data in raw.get("chains", []):
        config.chains.append(ChainRule(**chain_data))

    # Parse doc type specs
    for spec_data in raw.get("doc_specs", []):
        config.doc_specs.append(DocTypeSpec(**spec_data))

    return config
