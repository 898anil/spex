# MCP Server Reference

mdpp exposes a Model Context Protocol (MCP) server that allows AI agents to query the documentation graph in real time. This is the primary interface for AI-assisted documentation workflows.

## Starting the Server

```bash
# stdio mode (for Claude Code, Cursor, etc.)
mdpp serve

# With file watching (rebuilds graph on changes)
mdpp serve --watch
```

### Claude Code Integration

Add to `.mcp.json` in your repo root:

```json
{
  "mcpServers": {
    "mdpp": {
      "command": "mdpp",
      "args": ["serve"],
      "description": "Documentation graph - impact analysis, context assembly, validation"
    }
  }
}
```

Claude Code will auto-discover the server and make its tools available.

## Tools

### `get_change_impact`

Given a file that was changed (or is about to be changed), returns all upstream and downstream files affected by the change.

**When to use:** FIRST, before modifying any documentation file. Tells the AI agent the blast radius so it can plan updates.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | yes | - | Repo-relative path to the changed file |
| `depth` | integer | no | 2 | How many hops to traverse (1-10) |
| `direction` | string | no | "both" | `"downstream"`, `"upstream"`, or `"both"` |

**Output:**

```json
{
  "changed_file": "docs/03-product/features/01-meeting-capture/overview.md",
  "type": "feature-overview",
  "cascade": [
    {
      "path": "docs/03-product/features/01-meeting-capture/requirements.md",
      "type": "requirements",
      "relationship": "defines",
      "direction": "downstream",
      "depth": 1
    },
    {
      "path": "docs/06-tech/requirements/01-meeting-capture.md",
      "type": "tech-requirements",
      "relationship": "derives_to",
      "direction": "downstream",
      "depth": 2
    }
  ],
  "total_affected": 10,
  "downstream_count": 8,
  "upstream_count": 2
}
```

**Example AI agent usage:**

```
User: "Add offline support to the meeting capture feature"

Agent thinking:
  1. Call get_change_impact("docs/03-product/features/01-meeting-capture/overview.md")
  2. See that 10 files are affected
  3. Plan: update overview first, then propagate to requirements, tech spec, etc.
```

---

### `get_context_bundle`

Returns file contents for the changed file and all its affected downstream files. Assembles the minimal set of documents an AI agent needs to make a coherent change.

**When to use:** AFTER `get_change_impact`, to load the actual content without reading each file individually.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | yes | - | Repo-relative path to the target file |
| `depth` | integer | no | 2 | How many downstream hops to include |
| `include_content` | boolean | no | true | Whether to include file contents |
| `include_upstream` | boolean | no | true | Whether to include upstream context |

**Output:**

```json
{
  "changed_file": "docs/03-product/features/01-meeting-capture/overview.md",
  "files": [
    {
      "path": "docs/00-vision-and-strategy/business-goals.md",
      "role": "upstream",
      "type": "strategy",
      "relationship": "informs",
      "content": "# Business Goals\n...",
      "content_length": 2340
    },
    {
      "path": "docs/03-product/features/01-meeting-capture/overview.md",
      "role": "target",
      "type": "feature-overview",
      "content": "---\nid: 01\nname: Meeting Capture\n...",
      "content_length": 4120
    },
    {
      "path": "docs/06-tech/specs/01-meeting-capture.md",
      "role": "downstream",
      "type": "tech-spec",
      "relationship": "satisfied_by",
      "content": "# Meeting Capture Tech Spec\n...",
      "content_length": 8900
    }
  ],
  "file_count": 14,
  "estimated_tokens": 18400
}
```

**Token savings:** A typical context bundle is 80-96% smaller than loading the full repo, while containing everything needed for the task.

---

### `get_propagation_steps`

Returns human-readable, step-by-step instructions for propagating a change through the dependency chain. Tells the AI agent exactly what to do for each affected file.

**When to use:** After understanding the impact, to get actionable instructions for each affected file.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | yes | - | Repo-relative path to the changed file |

**Output:**

```json
{
  "changed_file": "docs/03-product/features/01-meeting-capture/overview.md",
  "type": "feature-overview",
  "steps": [
    "1. You changed: feature overview (docs/03-product/features/01-meeting-capture/overview.md)",
    "2. [REQUIREMENTS] docs/03-product/features/01-meeting-capture/requirements.md\n   Action: update PRQs to match new capability",
    "3. [TECH-REQUIREMENTS] docs/06-tech/requirements/01-meeting-capture.md\n   Action: derive new TRQs from updated PRQs",
    "4. [TECH-SPEC] docs/06-tech/specs/01-meeting-capture.md\n   Action: verify spec still satisfies updated requirements",
    "5. [JOURNEY] docs/04-ux/journeys/02-in-meeting-journey.md\n   Action: review journey for consistency with feature changes",
    "6. Update 'Last Updated' date in all modified files"
  ],
  "affected_file_count": 10
}
```

---

### `query_graph`

Flexible graph queries. Filter files by type, search by field values, list relationships.

**When to use:** When the AI agent needs to discover documents (e.g., "find all features in Core stage") or understand the graph structure.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query_type` | string | yes | - | One of: `"list_types"`, `"list_files"`, `"search"`, `"stats"` |
| `file_type` | string | no | - | Filter by document type |
| `field` | string | no | - | Frontmatter field to filter on |
| `value` | string | no | - | Value to match |
| `limit` | integer | no | 50 | Max results |

**Examples:**

```json
// List all document types
{"query_type": "list_types"}

// List all feature overviews
{"query_type": "list_files", "file_type": "feature-overview"}

// Find features in Core stage
{"query_type": "search", "file_type": "feature-overview", "field": "stage", "value": "Core"}

// Repository stats
{"query_type": "stats"}
```

---

### `validate_file`

Validate a single file's frontmatter, links, and relationships.

**When to use:** After modifying a file, to ensure it's still valid before moving on.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | yes | - | Repo-relative path to validate |

**Output:**

```json
{
  "file_path": "docs/03-product/features/01-meeting-capture/overview.md",
  "type": "feature-overview",
  "valid": false,
  "issues": [
    {
      "severity": "error",
      "category": "schema",
      "message": "Missing required field: platforms"
    },
    {
      "severity": "warning",
      "category": "link",
      "message": "Link target does not exist: ../../../06-tech/architecture/native-capture.md",
      "line": 34
    }
  ]
}
```

---

### `get_stale_files`

Find files that may need updating based on timestamp analysis.

**When to use:** Periodically, to identify documentation that has drifted from its sources.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_type` | string | no | - | Filter by document type |
| `min_days` | integer | no | 7 | Minimum staleness in days |

**Output:**

```json
{
  "stale_files": [
    {
      "path": "docs/06-tech/specs/01-meeting-capture.md",
      "type": "tech-spec",
      "last_modified": "2026-02-03",
      "stale_because": [
        {
          "upstream_path": "docs/03-product/features/01-meeting-capture/overview.md",
          "upstream_modified": "2026-02-15",
          "relationship": "satisfied_by",
          "days_behind": 12
        }
      ]
    }
  ],
  "total_stale": 8
}
```

---

### `get_document_type`

Get the inferred type information for a file, including required fields and relationships.

**When to use:** When creating a new document and needing to know what frontmatter fields to include.

**Input:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | string | yes | - | Repo-relative path (existing or planned) |

**Output:**

```json
{
  "file_path": "docs/03-product/features/23-new-feature/overview.md",
  "inferred_type": "feature-overview",
  "required_fields": ["id", "name", "slug", "stage", "platforms"],
  "enum_fields": {
    "stage": ["Core", "Enhanced", "Advanced", "Communication", "Proactive", "Enterprise"],
    "spec": ["not-started", "partial", "complete"]
  },
  "expected_relationships": [
    {"field": "primary_persona", "target_type": "persona"},
    {"field": "primary_journey", "target_type": "journey"}
  ],
  "sibling_files": [
    "docs/03-product/features/22-action-studio/overview.md",
    "docs/03-product/features/21-notion-integration/overview.md"
  ]
}
```

## Typical AI Agent Workflow

Here's how an AI agent should use these tools together:

```
1. User asks: "Add SSO support to the settings feature"

2. Agent calls: get_change_impact("docs/03-product/features/15-settings/overview.md")
   Result: 8 files affected (requirements, tech spec, journey, flows, etc.)

3. Agent calls: get_context_bundle("docs/03-product/features/15-settings/overview.md")
   Result: 14 files assembled (upstream context + target + downstream), ~12K tokens

4. Agent reads the context bundle, understands the current state

5. Agent modifies: docs/03-product/features/15-settings/overview.md
   (adds SSO capability)

6. Agent calls: get_propagation_steps("docs/03-product/features/15-settings/overview.md")
   Result: Step-by-step instructions for updating each affected file

7. Agent follows the steps, updating each downstream file

8. Agent calls: validate_file for each modified file
   Result: All valid, no broken links or missing fields

9. Agent reports: "Updated 8 files. SSO support added to settings feature,
   requirements updated, tech spec updated, journey updated."
```

## Error Handling

All tools return structured errors:

```json
{
  "error": "File not found in graph: docs/nonexistent.md",
  "suggestion": "Run 'mdpp scan' to rebuild the graph, or check the file path."
}
```

Common errors:
- `"File not found in graph"` - The file doesn't exist or wasn't included in the scan.
- `"Graph not built"` - The server started but scanning failed. Check stderr.
- `"Depth out of range"` - depth must be 1-10.
