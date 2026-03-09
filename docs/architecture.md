# Architecture

## System Overview

```
                          User's Markdown Repo
                                  |
                                  v
                    +--------------------------+
                    |        Scanner           |
                    |  Parse .md files         |
                    |  Extract frontmatter     |
                    |  Extract links & IDs     |
                    +--------------------------+
                                  |
                                  v
                    +--------------------------+
                    |     Inference Engine      |
                    |  Cluster document types   |
                    |  Detect relationships     |
                    |  Infer directionality     |
                    +--------------------------+
                                  |
                                  v
                    +--------------------------+
                    |         Graph            |
                    |  Nodes (files + metadata)|
                    |  Edges (typed relations) |
                    |  In-memory, queryable    |
                    +--------------------------+
                          |       |       |
                    +-----+   +---+---+   +------+
                    |         |       |          |
                    v         v       v          v
                +------+ +-------+ +------+ +--------+
                | CLI  | | MCP   | | Valid| | Compile|
                |impact| |Server | |ation | |  Gen   |
                |context| |      | |      | |        |
                |graph | |      | |      | |        |
                +------+ +-------+ +------+ +--------+
```

## Project Structure

```
markdownpp/
├── README.md
├── pyproject.toml              # Package definition, dependencies, entry points
├── LICENSE
│
├── docs/                       # Project documentation
│   ├── vision.md
│   ├── architecture.md         # (this file)
│   ├── user-guide.md
│   ├── mcp-reference.md
│   └── configuration.md
│
├── src/
│   └── mdpp/
│       ├── __init__.py         # Version, public API
│       ├── cli.py              # Click-based CLI entry point
│       │
│       ├── scanner/
│       │   ├── __init__.py
│       │   ├── parser.py       # Markdown file parser (frontmatter, links, IDs)
│       │   ├── walker.py       # Directory walker with .gitignore support
│       │   └── types.py        # ParsedFile, Frontmatter, Link data classes
│       │
│       ├── inference/
│       │   ├── __init__.py
│       │   ├── type_detector.py    # Document type clustering
│       │   ├── relationship.py     # Relationship inference from links/frontmatter/IDs
│       │   ├── convention.py       # Naming convention detection
│       │   └── enrichment.py       # Directionality, layers, hubs, anomalies
│       │
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── model.py        # Node, Edge, Graph data structures
│       │   ├── builder.py      # Orchestrates scanner + inference -> Graph
│       │   ├── query.py        # Graph query API (impact, context, traversal)
│       │   └── cache.py        # Optional disk cache for large repos
│       │
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── scan.py         # mdpp scan
│       │   ├── impact.py       # mdpp impact
│       │   ├── context.py      # mdpp context
│       │   ├── validate.py     # mdpp validate
│       │   ├── graph_cmd.py    # mdpp graph
│       │   ├── stats.py        # mdpp stats
│       │   ├── stale.py        # mdpp stale
│       │   ├── compile.py      # mdpp compile
│       │   ├── init.py         # mdpp init
│       │   └── serve.py        # mdpp serve
│       │
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── schema.py       # Frontmatter schema validation
│       │   ├── links.py        # Broken link detection
│       │   ├── orphans.py      # Orphaned file detection
│       │   ├── staleness.py    # Timestamp-based staleness detection
│       │   ├── indexes.py      # INDEX.md consistency checking
│       │   └── circular.py     # Circular dependency detection
│       │
│       ├── compiler/
│       │   ├── __init__.py
│       │   ├── index_gen.py    # Auto-generate INDEX.md files
│       │   ├── dashboard.py    # Generate HTML dashboards
│       │   └── templates/      # Jinja2 templates for generated files
│       │       ├── index.md.j2
│       │       ├── coverage.md.j2
│       │       └── dashboard.html.j2
│       │
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── server.py       # MCP stdio server
│       │   └── tools.py        # Tool definitions and handlers
│       │
│       └── config/
│           ├── __init__.py
│           ├── loader.py       # Load mdpp.yaml (if present)
│           ├── generator.py    # Generate mdpp.yaml from inferred state
│           └── schema.py       # Config file schema
│
└── tests/
    ├── conftest.py             # Shared fixtures (sample repos)
    ├── fixtures/               # Sample markdown repos for testing
    │   ├── minimal/            # 5-file repo
    │   ├── medium/             # 50-file repo
    │   └── large/              # 200-file repo (generated)
    │
    ├── test_scanner/
    │   ├── test_parser.py
    │   └── test_walker.py
    ├── test_inference/
    │   ├── test_type_detector.py
    │   └── test_relationship.py
    ├── test_graph/
    │   ├── test_builder.py
    │   └── test_query.py
    ├── test_validation/
    │   ├── test_schema.py
    │   ├── test_links.py
    │   ├── test_staleness.py
    │   └── test_orphans.py
    ├── test_mcp/
    │   └── test_server.py
    └── test_cli/
        └── test_commands.py
```

## Module Responsibilities

### Scanner (`scanner/`)

Reads raw files from disk. No inference, no interpretation. Pure parsing.

- `walker.py` - Walks the directory tree, respects `.gitignore`, skips binary files. Returns a list of file paths.
- `parser.py` - Parses a single `.md` file. Extracts YAML frontmatter, heading structure, inline links (with line numbers), and ID references (regex-based pattern detection). Returns a `ParsedFile` object.
- `types.py` - Data classes: `ParsedFile`, `Frontmatter`, `Link`, `Heading`, `IdReference`.

**Key design decision:** The parser does NOT resolve links or validate anything. It just extracts raw data. Resolution and validation happen later.

### Inference (`inference/`)

Takes raw parsed files and infers structure.

- `type_detector.py` - Clusters files into document types based on frontmatter key similarity. Files with the same set of keys (within a Jaccard threshold) are grouped. Types are named from directory patterns.
- `relationship.py` - Creates edges from: (a) frontmatter references, (b) resolved inline links, (c) ID cross-references. Each edge has a source, target, and type.
- `convention.py` - Detects naming conventions (numbered prefixes, slugs, INDEX patterns). Used for validation rules.
- `enrichment.py` - Post-processing: infer edge directionality, detect layers from directory numbering, tag hub nodes (INDEX files), flag anomalies.

### Graph (`graph/`)

The in-memory graph that everything else queries.

- `model.py` - `Node` (file path, type, frontmatter, metadata), `Edge` (source, target, type, metadata), `Graph` (nodes dict, edges list, indexes).
- `builder.py` - Orchestrator. Calls scanner to parse files, calls inference to build types and edges, returns a `Graph` object. This is the main entry point for building the graph.
- `query.py` - Query API on the graph:
  - `impact(node, depth, direction)` - BFS/DFS traversal for impact analysis
  - `context(node, depth)` - Assemble context bundle (upstream + target + downstream, ordered)
  - `neighbors(node, direction, edge_type)` - Direct neighbors
  - `path(from, to)` - Shortest path between two nodes
  - `subgraph(nodes)` - Extract a subgraph
  - `filter(type, field, value)` - Query nodes by type and field values
- `cache.py` - Optional JSON cache of the graph (for repos where scanning takes > 3s). Invalidated by file modification times.

### Commands (`commands/`)

CLI command implementations. Each module is a thin wrapper that builds the graph, calls the appropriate query/validation, and formats output.

### Validation (`validation/`)

All validation checks. Each module is independent and returns a list of `Issue` objects.

- `schema.py` - Validates frontmatter against inferred or configured schemas.
- `links.py` - Resolves all inline links and frontmatter references. Reports broken ones.
- `orphans.py` - Finds files with no incoming or outgoing edges.
- `staleness.py` - Compares modification timestamps along dependency edges. If a downstream file is older than its upstream dependency, it may be stale.
- `indexes.py` - Compares INDEX.md entries against files on disk. Reports invisible files and stale entries.
- `circular.py` - Detects circular dependencies using DFS cycle detection.

### Compiler (`compiler/`)

Generates files from the graph.

- `index_gen.py` - Auto-generates INDEX.md files from the graph. Uses Jinja2 templates.
- `dashboard.py` - Generates self-contained HTML dashboards (coverage matrix, graph explorer).

### MCP (`mcp/`)

MCP server for AI agent integration.

- `server.py` - stdio JSON-RPC server implementing MCP protocol. Builds the graph on startup, handles tool calls.
- `tools.py` - Tool definitions and implementations:
  - `get_change_impact` - Impact analysis
  - `get_context_bundle` - Context assembly with file contents
  - `get_propagation_steps` - Human-readable change propagation guide
  - `query_graph` - Flexible graph queries (filter by type, list files, etc.)
  - `validate_file` - Validate a single file
  - `get_stale_files` - Files that may need updating
  - `get_document_type` - Inferred type info for a file

### Config (`config/`)

Configuration handling.

- `loader.py` - Loads `mdpp.yaml` from the repo root (if present). Merges with defaults.
- `generator.py` - Generates `mdpp.yaml` from the inferred graph state.
- `schema.py` - Pydantic schema for the config file.

## Data Flow

### Building the Graph

```
1. walker.py -> list of .md file paths
2. parser.py -> ParsedFile for each path (parallel, using multiprocessing)
3. type_detector.py -> document types (clustered from frontmatter shapes)
4. relationship.py -> edges (from links, frontmatter refs, ID cross-refs)
5. enrichment.py -> directionality, layers, hubs, anomalies
6. Graph object (in-memory, queryable)
```

### Serving via MCP

```
1. Graph built on startup (or loaded from cache)
2. AI agent sends tool call via stdio JSON-RPC
3. server.py dispatches to tools.py
4. tools.py calls graph.query methods
5. Result serialized as JSON, sent back via stdio
```

## Dependencies

Minimal dependency footprint:

- **Python 3.11+** (for modern typing, tomllib)
- **click** - CLI framework
- **pyyaml** - YAML frontmatter parsing
- **jinja2** - Template rendering for compile
- **pydantic** - Config schema validation (optional, for mdpp.yaml)

No heavy dependencies. No LLM libraries. No web frameworks. The core (scanner + inference + graph) has only pyyaml as a dependency.

## Performance Targets

| Operation | Target | Approach |
|-----------|--------|----------|
| Scan 1,000 files | < 3s | Parallel parsing with multiprocessing |
| Impact analysis | < 500ms | Pre-built graph, BFS traversal |
| Context assembly | < 500ms | Pre-built graph + file reads |
| MCP tool response | < 200ms | Graph in memory, no disk I/O for queries |
| Validation (full) | < 5s | Parallel checks, short-circuit on first error per file |

## Extensibility

### Custom Relationship Types

Users can define custom relationship types in `mdpp.yaml`:

```yaml
relationships:
  - field: implements
    type: implements
    direction: downstream
```

### Custom Validators

Users can add custom validation rules:

```yaml
validation:
  custom:
    - type: feature-overview
      rule: "frontmatter.stage != 'Core' or frontmatter.platforms is not None"
      message: "Core features must specify platforms"
```

### Custom Templates

Users can provide Jinja2 templates for auto-generated files:

```yaml
compile:
  indexes:
    - output: "features/INDEX.md"
      source_type: feature-overview
      template: ".mdpp/templates/feature-index.md.j2"
```
