# mdpp - Markdown++

**The graph layer for large markdown repos.**

mdpp treats your markdown files as a connected knowledge graph, not isolated documents. It infers document types, tracks relationships, detects staleness, validates integrity, and serves everything to AI agents via MCP - all without you writing a single line of config.

```bash
# Point it at any markdown repo. Zero config.
mdpp scan .

# What breaks if I change this file?
mdpp impact docs/features/auth/overview.md

# Assemble context for an AI agent working on auth
mdpp context docs/features/auth/overview.md

# Validate the whole repo
mdpp validate

# Serve the graph to AI agents via MCP
mdpp serve
```

---

## The Problem

Markdown won. Every team writes docs in markdown. But when your documentation grows past ~50 files, three things break:

**1. You lose the map.** You have 200 files across nested folders. You can't answer basic questions: "What documents exist about feature X?" "Which files reference this persona?" "Is anything orphaned?" You resort to grep and hope.

**2. Changes don't propagate.** You update a product requirements doc. Somewhere, a tech spec derives from those requirements. Somewhere else, a user journey references that feature. You don't know what else needs updating, so you don't update it. Docs drift. Trust erodes.

**3. AI agents drown.** You point an LLM at your repo and say "implement this feature." It can't fit 200 files in context. It doesn't know which 8 files are relevant. It reads INDEX files, follows links, makes mistakes. There's no machine-readable way to say "give me everything related to feature X, in dependency order."

These aren't problems with markdown's syntax. The content is fine. What's broken is that markdown has no concept of **typed relationships between documents**. No way to say "this spec derives from that requirement" or "this journey covers these features" in a way that tooling can reason about.

**mdpp fixes this.** It reads your existing markdown files, infers the document graph from frontmatter and inline links, and gives you tools to query, validate, and serve that graph - to humans and AI agents alike.

---

## How It Works

### Zero-Config Inference

mdpp doesn't require you to define schemas, write config files, or change how you write markdown. It observes your repo and figures things out:

```bash
$ mdpp scan .
Scanning 695 files...

Inferred 12 document types:
  feature-overview  (22 files)  fields: id, name, slug, stage, platforms
  tech-spec         (21 files)  fields: feature_id, feature_name, status
  user-story        (51 files)  fields: id, title, persona, trigger
  persona           (13 files)  fields: id, name, role, company_type
  journey           (18 files)  fields: id, name, primary_persona
  flow              (43 files)  fields: id, name
  ...

Detected 2,847 relationships:
  1,203 from inline markdown links
  847 from frontmatter references (depends_on, used_by, features, ...)
  797 from ID-based cross-references (PRQ-01-003 -> TRQ-01-001)

Found 47 broken links, 12 orphaned files, 3 circular dependencies.

Graph ready. Run 'mdpp serve' to start MCP server.
```

**How inference works:**

- **Document types** are clustered by frontmatter shape. Files with `{id, name, slug, stage}` in frontmatter form a different type than files with `{id, title, persona, trigger}`. mdpp names types from their directory path (e.g., files under `features/*/overview.md` become `feature-overview`).

- **Relationships** come from three sources:
  1. Inline markdown links: `[Auth Feature](../features/06-auth/overview.md)` creates an edge.
  2. Frontmatter references: `depends_on: [02-discovery/personas/01-priya]` creates typed edges.
  3. ID cross-references: Text like `PRQ-01-003` appearing in a TRQ file creates a `references` edge.

- **Naming conventions** are detected from filename patterns. If files follow `NNN-slug.md` or `dir-prefix-NNN-title.md`, mdpp learns this and uses it for validation.

### Optional Config (Generated, Not Required)

After scanning, mdpp can generate a config file that captures what it inferred:

```bash
$ mdpp init .
Wrote mdpp.yaml (695 files, 12 types, 2847 relationships)
Review and adjust as needed. The tool works without this file.
```

The config is for customization, not bootstrapping. You'd edit it to:
- Mark certain frontmatter fields as required
- Define enum constraints (`stage` must be one of `[Core, Enhanced, Advanced]`)
- Override inferred document types
- Configure auto-generated index files

**If you never touch mdpp.yaml, everything still works.**

---

## Core Capabilities

### 1. Impact Analysis

"I'm about to change this file. What else is affected?"

```bash
$ mdpp impact docs/03-product/features/01-meeting-capture/overview.md

Direct dependents (6 files):
  docs/03-product/features/01-meeting-capture/requirements.md  [defines]
  docs/04-ux/journeys/02-in-meeting-journey.md                 [experienced_in]
  docs/04-ux/flows/15-in-meeting.md                            [detailed_by]
  docs/06-tech/requirements/01-meeting-capture.md              [derives_to]
  docs/06-tech/specs/01-meeting-capture.md                     [satisfied_by]
  docs/03-product/user-stories/005-ae-lost-track.md            [informs]

Transitive (depth 2, 4 more files):
  docs/06-tech/traceability/requirements-traceability.md       [aggregates]
  docs/07-implementation/modules/meeting-intelligence/README.md [implements]
  ...

Total blast radius: 10 files across 5 layers.
```

### 2. Context Assembly

"Give me everything an AI agent needs to work on this feature."

```bash
$ mdpp context docs/03-product/features/01-meeting-capture/overview.md --depth 2

Assembled 14 files in dependency order:
  1. docs/00-vision-and-strategy/business-goals.md          (upstream: why this matters)
  2. docs/02-discovery/personas/01-priya-menon.md            (upstream: who it's for)
  3. docs/03-product/features/01-meeting-capture/overview.md (target)
  4. docs/03-product/features/01-meeting-capture/requirements.md
  5. docs/04-ux/journeys/02-in-meeting-journey.md
  6. docs/04-ux/flows/14-meeting-detection.md
  7. docs/04-ux/flows/15-in-meeting.md
  8. docs/04-ux/flows/16-missed-meeting.md
  9. docs/06-tech/requirements/01-meeting-capture.md
  10. docs/06-tech/specs/01-meeting-capture.md
  ...

Total: ~18,400 tokens (vs ~490,000 for full repo - 96% reduction)

Output written to: /tmp/mdpp-context-meeting-capture.md
```

The assembled context file is ordered by the dependency graph - upstream docs first, target in the middle, downstream docs after. An AI agent reading top-to-bottom gets the full picture in the right order.

### 3. Validation

"Is my documentation repo healthy?"

```bash
$ mdpp validate

Schema violations (23):
  docs/03-product/features/05-calendar/overview.md
    Missing required field: platforms
  docs/04-ux/flows/27-proactive-alerts.md
    Invalid enum value for priority: 'critical' (expected: P0, P1, P2)
  ...

Broken links (47):
  docs/06-tech/specs/01-meeting-capture.md:34
    Link target does not exist: ../architecture/native-capture.md
  ...

Orphaned files (12):
  docs/01-research/sketches/early-dashboard-v1.md
    Not referenced by any other file or INDEX.
  ...

Stale files (8):
  docs/06-tech/specs/01-meeting-capture.md
    Last modified: Feb 3. Parent overview modified: Feb 15. Possibly stale.
  ...

Circular dependencies (1):
  docs/03-product/features/09-account-intelligence/overview.md
    -> docs/03-product/features/07-deal-intelligence/overview.md
    -> docs/03-product/features/09-account-intelligence/overview.md
  ...

Summary: 91 issues (23 schema, 47 links, 12 orphans, 8 stale, 1 circular)
```

### 4. Graph Exploration

"Show me the structure of my documentation."

```bash
# Tree view of a specific node
$ mdpp graph docs/03-product/features/01-meeting-capture/overview.md
feature-overview: Meeting Capture
  upstream:
    persona/01-priya-menon (referenced by primary_persona)
    business-goals (referenced in content)
  downstream:
    requirements/01-meeting-capture (defines)
    journey/02-in-meeting (experienced_in)
    flow/14-meeting-detection (detailed_by)
    flow/15-in-meeting (detailed_by)
    flow/16-missed-meeting (detailed_by)
    tech-spec/01-meeting-capture (satisfied_by)
    user-story/005-ae-lost-track (informs)
    user-story/011-ae-first-meeting (informs)

# Stats for the whole repo
$ mdpp stats
Files: 695 (623 with frontmatter, 72 without)
Document types: 12
Relationships: 2,847
Avg connections per file: 4.1
Most connected: features/INDEX.md (89 connections)
Least connected: research/sketches/* (0-1 connections)
Orphaned: 12 files
Layers: 8 (00-vision through 07-implementation)
```

### 5. Auto-Generation (Compile)

"Generate INDEX files and dashboards from the graph."

```bash
$ mdpp compile

Generated:
  docs/03-product/features/INDEX.md        (from 22 feature-overview files)
  docs/04-ux/flows/INDEX.md                (from 43 flow files)
  docs/04-ux/journeys/INDEX.md             (from 18 journey files)
  docs/_meta/coverage-matrix.md            (from graph traversal)
  docs/_meta/review-dashboard.html         (interactive HTML)

Skipped (no template defined):
  docs/02-discovery/personas/INDEX.md      (run 'mdpp init' to generate template)
```

### 6. MCP Server

"Let AI agents query the graph in real time."

```bash
$ mdpp serve
mdpp MCP server running on stdio
4 tools available: get_change_impact, get_context_bundle, get_propagation_steps, query_graph
Graph: 695 nodes, 2847 edges (built in 1.2s)
```

See [MCP Reference](docs/mcp-reference.md) for the full tool specification.

---

## Installation

```bash
# Via pip (Python 3.11+)
pip install mdpp

# Via Homebrew
brew install mdpp

# Via npx (no install needed)
npx mdpp scan .
```

---

## Quick Start

```bash
# 1. Scan your repo (zero config)
cd your-docs-repo
mdpp scan .

# 2. See what's broken
mdpp validate

# 3. Check impact before making a change
mdpp impact path/to/file-you-want-to-change.md

# 4. Start MCP server for AI agents
mdpp serve
```

---

## Documentation

- [Vision & Design Principles](docs/vision.md) - Why this exists and the principles behind it.
- [Architecture](docs/architecture.md) - How mdpp is built internally.
- [User Guide](docs/user-guide.md) - Complete CLI reference and workflows.
- [MCP Reference](docs/mcp-reference.md) - MCP server tools for AI agents.
- [Configuration](docs/configuration.md) - Optional mdpp.yaml reference.
- [Contributing](docs/contributing.md) - How to contribute to mdpp.

---

## Origin Story

mdpp was born from managing a 695-file, 195K-line product documentation repo ([AnyTeam](https://anyteam.ai)). We built 7 Python scripts to validate links, track requirements traceability, compute change impact, and serve the graph to Claude Code via MCP. It worked. Then we realized every team with a large docs repo has the same problems and no tooling.

mdpp is those scripts, generalized into a zero-config tool that works on any markdown repo.

---

## License

MIT
