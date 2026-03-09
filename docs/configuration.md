# Configuration Reference

mdpp works with zero configuration. This file documents the optional `mdpp.yaml` for users who want to customize behavior.

## Generating Config

```bash
# Generate from inferred state (recommended starting point)
mdpp init

# Preview without writing
mdpp init --stdout
```

This writes `mdpp.yaml` to the repo root, pre-populated with everything mdpp inferred from your files. Edit as needed.

## Config File Location

mdpp looks for config in this order:

1. `mdpp.yaml` in the scanned directory
2. `mdpp.yml` in the scanned directory
3. `.mdpp/config.yaml` in the scanned directory
4. No config (pure inference mode)

## Full Schema

```yaml
# mdpp.yaml

# Root directory containing markdown files (relative to this config file)
root: docs/

# Directories and patterns to exclude from scanning
exclude:
  - "node_modules/"
  - ".git/"
  - "**/archive/"
  - "**/_templates/"

# Document type definitions
# These override or extend the auto-inferred types.
# You don't need to define types that mdpp infers correctly.
types:
  feature-overview:
    # Glob pattern(s) matching files of this type
    pattern: "03-product/features/*/overview.md"
    # or multiple patterns:
    # patterns:
    #   - "03-product/features/*/overview.md"
    #   - "03-product/features/*/summary.md"

    # Required frontmatter fields
    required_fields:
      - id
      - name
      - slug
      - stage

    # Enum constraints for frontmatter fields
    enums:
      stage: [Core, Enhanced, Advanced, Communication, Proactive, Enterprise]
      spec: [not-started, partial, complete]

    # Fields that reference other documents
    reference_fields:
      - field: primary_persona
        target_type: persona
      - field: primary_journey
        target_type: journey
      - field: depends_on
        target_type: "*"  # any type

  tech-spec:
    pattern: "06-tech/specs/*.md"
    required_fields: [feature_id, feature_name, status]
    enums:
      status: [Not Started, In Progress, Complete]

  # ... other types

# Relationship definitions
# These supplement the auto-inferred relationships.
relationships:
  # Explicit relationship types from specific frontmatter fields
  - from_type: feature-overview
    to_type: tech-spec
    via_field: feature_id      # field in tech-spec that references feature
    relationship: satisfied_by
    direction: downstream       # feature -> tech-spec

  - from_type: requirements
    to_type: tech-requirements
    via_field: derives_from
    relationship: derives_to
    direction: downstream

# ID patterns to detect as cross-references
# mdpp auto-detects common patterns (PRQ-NN-NNN, TRQ-NN-NNN, etc.)
# Add custom patterns here:
id_patterns:
  - pattern: "F-(\\d{2})"
    name: feature-id
  - pattern: "MS-(\\d{2})"
    name: module-id
  - pattern: "PRQ-(\\d{2})-(\\d{3}[a-z]?)"
    name: product-requirement
  - pattern: "TRQ-(\\d{2})-(\\d{3}[a-z]?)"
    name: tech-requirement

# Validation configuration
validation:
  # Enable/disable specific checks
  checks:
    broken_links: true
    schema: true
    orphans: true
    staleness: true
    indexes: true
    circular: true

  # Staleness threshold (days)
  stale_days: 14

  # Files to exclude from orphan detection
  orphan_exceptions:
    - "docs/articles/*"
    - "scraps/*"

  # Custom validation rules
  custom:
    - type: feature-overview
      rule: "stage == 'Core' implies platforms is not None"
      message: "Core features must specify platforms"
      severity: warning

# Compile (auto-generation) configuration
compile:
  # INDEX files to auto-generate
  indexes:
    - output: "03-product/features/INDEX.md"
      source_type: feature-overview
      template: default        # Use built-in template
      sort_by: id

    - output: "04-ux/flows/INDEX.md"
      source_type: flow
      template: default
      sort_by: id

  # HTML dashboards to generate
  dashboards:
    - output: "_meta/dashboard.html"
      template: default

# MCP server configuration
mcp:
  # Whether to watch for file changes and rebuild graph
  watch: false

  # Maximum depth for impact traversal
  max_depth: 10

  # Whether to include file contents in context bundles
  include_content: true

  # Maximum total tokens for a context bundle
  max_bundle_tokens: 50000
```

## Minimal Config Examples

### Just add a required field

```yaml
types:
  feature-overview:
    pattern: "features/*/overview.md"
    required_fields: [id, name, status]
```

### Just exclude a directory

```yaml
exclude:
  - "archive/"
  - "drafts/"
```

### Just configure staleness threshold

```yaml
validation:
  stale_days: 30
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MDPP_CONFIG` | `mdpp.yaml` | Path to config file |
| `MDPP_CACHE_DIR` | `.mdpp/cache/` | Directory for graph cache |
| `MDPP_LOG_LEVEL` | `warning` | Logging level (debug, info, warning, error) |
| `MDPP_NO_COLOR` | - | Disable colored output |
