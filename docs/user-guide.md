# User Guide

## Installation

### Via pip (recommended)

```bash
pip install mdpp
```

### Via Homebrew

```bash
brew tap anyteamai/mdpp
brew install mdpp
```

### Via pipx (isolated environment)

```bash
pipx install mdpp
```

### From source

```bash
git clone https://github.com/AnyTeamAI/markdownpp.git
cd markdownpp
pip install -e .
```

## Getting Started

### Your First Scan

Navigate to any directory containing markdown files and run:

```bash
mdpp scan .
```

That's it. mdpp walks the directory, parses every `.md` file, infers document types and relationships, and reports what it found. No config file needed.

### Understanding the Output

```
$ mdpp scan .
Scanning docs/ ...

Files: 695 markdown files found
  623 with YAML frontmatter
  72 without frontmatter (typed by path only)

Document Types (12 inferred):
  feature-overview     22 files   docs/03-product/features/*/overview.md
  tech-spec            21 files   docs/06-tech/specs/*.md
  user-story           51 files   docs/03-product/user-stories/*.md
  persona              13 files   docs/02-discovery/personas/*.md
  journey              18 files   docs/04-ux/journeys/*.md
  flow                 43 files   docs/04-ux/flows/*.md
  requirements         22 files   docs/03-product/features/*/requirements.md
  tech-requirements    16 files   docs/06-tech/requirements/*.md
  decision-record       9 files   docs/*/decisions/*.md
  directive            12 files   docs/*/directives/dir-*.md
  index                62 files   */INDEX.md
  untyped             406 files   (no frontmatter pattern match)

Relationships: 2,847
  1,203 inline links
    847 frontmatter references
    797 ID cross-references

Issues: 91
  47 broken links
  23 schema issues
  12 orphaned files
   8 stale files
   1 circular dependency

Graph ready (built in 1.8s).
```

## CLI Commands

### `mdpp scan`

Build the graph and report summary statistics.

```bash
mdpp scan [PATH]           # Scan a directory (default: current)
mdpp scan . --json         # Output as JSON
mdpp scan . --verbose      # Show per-file details
```

### `mdpp validate`

Run all validation checks.

```bash
mdpp validate              # All checks
mdpp validate --links      # Only broken links
mdpp validate --schema     # Only frontmatter schema
mdpp validate --stale      # Only staleness detection
mdpp validate --orphans    # Only orphaned files
mdpp validate --indexes    # Only INDEX.md consistency
mdpp validate --circular   # Only circular dependencies
mdpp validate --json       # Output as JSON (for CI integration)
mdpp validate --fix        # Auto-fix what's possible (broken relative links)
```

**Exit codes:** 0 if no issues, 1 if issues found. Use in CI:

```yaml
# GitHub Actions
- run: mdpp validate --json > mdpp-report.json
```

### `mdpp impact`

Show what's affected by changing a file.

```bash
mdpp impact <file>                  # Show upstream and downstream
mdpp impact <file> --downstream     # Only downstream (what needs updating)
mdpp impact <file> --upstream       # Only upstream (what informs this file)
mdpp impact <file> --depth 3        # Traverse 3 hops (default: 2)
mdpp impact <file> --json           # Output as JSON
```

### `mdpp context`

Assemble a context bundle for AI consumption.

```bash
mdpp context <file>                 # Assemble context for this file
mdpp context <file> --depth 2       # Include 2 hops of context (default)
mdpp context <file> --output /tmp/ctx.md   # Write to file
mdpp context <file> --tokens        # Show token estimate only
mdpp context <file> --no-content    # Metadata only (no file contents)
```

The output is a single markdown file with all relevant documents assembled in dependency order, annotated with their role (upstream/target/downstream) and relationship type.

### `mdpp graph`

Explore the graph structure.

```bash
mdpp graph <file>                   # Show connections for a file
mdpp graph <file> --depth 2         # Show 2-hop neighborhood
mdpp graph --type feature-overview  # List all files of a type
mdpp graph --stats                  # Repository-wide statistics
mdpp graph --dot > graph.dot        # Export as Graphviz DOT
mdpp graph --json                   # Full graph as JSON
```

### `mdpp stale`

Find files that may need updating based on timestamps.

```bash
mdpp stale                          # All stale files
mdpp stale --days 14                # Only files stale by 14+ days
mdpp stale --type tech-spec         # Only stale tech specs
```

### `mdpp compile`

Auto-generate files from the graph.

```bash
mdpp compile                        # Generate all configured outputs
mdpp compile --indexes              # Only regenerate INDEX files
mdpp compile --dashboard            # Only regenerate HTML dashboard
mdpp compile --dry-run              # Show what would be generated
```

### `mdpp init`

Generate a config file from the inferred state.

```bash
mdpp init                           # Write mdpp.yaml
mdpp init --stdout                  # Print to stdout instead
```

### `mdpp serve`

Start the MCP server.

```bash
mdpp serve                          # stdio MCP server (for Claude Code, etc.)
mdpp serve --watch                  # Rebuild graph on file changes
mdpp serve --port 3100              # HTTP mode (for non-MCP clients)
```

## Workflows

### Workflow 1: Pre-Commit Validation

Add to your pre-commit hooks or CI:

```bash
mdpp validate --links --schema
```

This catches broken links and invalid frontmatter before they're merged.

### Workflow 2: Change Impact Review

Before making a significant documentation change:

```bash
# See what you're about to affect
mdpp impact docs/features/auth/overview.md

# Make your change
vim docs/features/auth/overview.md

# Validate everything is still consistent
mdpp validate --stale
```

### Workflow 3: AI-Assisted Documentation Updates

Using Claude Code with the mdpp MCP server:

```bash
# In one terminal, start the MCP server
mdpp serve

# In another, use Claude Code (it discovers mdpp via .mcp.json)
claude
> "Update the auth feature to include SSO support.
>  Use mdpp to check what else needs updating."
```

Claude will:
1. Call `get_change_impact` to see affected files
2. Call `get_context_bundle` to read the relevant content
3. Make the changes
4. Call `get_propagation_steps` to know what else to update

### Workflow 4: Onboarding to a New Docs Repo

When you're new to a documentation repo:

```bash
# Understand the structure
mdpp scan . --verbose

# See the big picture
mdpp graph --stats

# Explore a specific area
mdpp graph docs/features/ --depth 1

# Generate a visual overview
mdpp compile --dashboard
open docs/_meta/dashboard.html
```

### Workflow 5: Automated INDEX Generation

Stop manually maintaining INDEX files:

```bash
# See what indexes would be generated
mdpp compile --indexes --dry-run

# Generate them
mdpp compile --indexes

# Verify
git diff
```

## Configuration Reference

See [configuration.md](configuration.md) for the full `mdpp.yaml` reference.

## Integrating with Claude Code

Add to your repo's `.mcp.json`:

```json
{
  "mcpServers": {
    "mdpp": {
      "command": "mdpp",
      "args": ["serve"],
      "description": "Documentation graph for impact analysis and context assembly"
    }
  }
}
```

Now any AI agent using MCP can query your documentation graph.
