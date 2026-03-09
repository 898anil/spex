# Vision & Design Principles

## Why mdpp Exists

Every software team writes documentation in markdown. It's simple, universal, and every tool supports it. But markdown was designed for single documents, not interconnected knowledge bases.

When your docs grow past ~50 files, you hit a wall:

- **No relationships.** Markdown has links, but links are untyped. There's no difference between "this spec derives from that requirement" and "here's a see-also link." Tooling can't reason about the structure.

- **No validation.** Nothing checks that your frontmatter is consistent, your links aren't broken, or your index files match what's on disk. Documentation rots silently.

- **No change propagation.** When a product requirement changes, there's no way to know which tech specs, user journeys, and implementation docs are now stale. You'd need a human who holds the entire repo in their head.

- **No AI integration.** LLMs are increasingly writing and maintaining docs, but they can't fit 200 files in context. They need a machine-readable way to ask "what's relevant to this task?" and get back the minimal set of files, in the right order.

These aren't hypothetical problems. We hit every one of them managing a 695-file product documentation repo. We built custom scripts to solve each one. mdpp is those solutions, generalized.

## What mdpp Is (And Isn't)

**mdpp IS:**
- A CLI tool and MCP server for managing large markdown repos
- A graph engine that infers relationships from your existing files
- A validator, impact analyzer, and context assembler
- Zero-config by default, configurable when needed
- A tool that works WITH markdown, not instead of it

**mdpp IS NOT:**
- A new markup language (your files stay as standard .md)
- A static site generator (use Docusaurus, MkDocs, etc. for that)
- A note-taking app (use Obsidian, Notion, etc. for that)
- A wiki (no web UI, no real-time collaboration)
- A replacement for git (it reads your repo, doesn't manage versions)

## Design Principles

### 1. Zero Config, Then Progressive Disclosure

The tool must work the first time you run it, on any markdown repo, with no setup. Inference handles the common case. Config files are generated (not required) for customization. Advanced features (auto-generation templates, custom relationship types) are opt-in.

**Litmus test:** If a user has to create a file before getting value, we've failed.

### 2. Markdown In, Markdown Out

mdpp never requires you to write non-standard syntax. Your files are valid markdown before and after. If mdpp generates files (like INDEX.md), the output is standard markdown that GitHub, VS Code, and every other tool renders correctly.

The only place non-standard syntax appears is in optional compile directives (like `<!-- mdpp:query ... -->`) that degrade gracefully to HTML comments in any standard renderer.

### 3. The Graph Is Inferred, Not Declared

Users shouldn't have to manually maintain a dependency graph. mdpp builds the graph from what's already in the files:

- Frontmatter fields that reference other documents
- Inline markdown links between files
- ID patterns that appear across files (e.g., PRQ-01-003 in a TRQ doc)
- Directory structure and naming conventions

If the inferred graph is wrong, users can override it with frontmatter - but the default should be right 90% of the time.

### 4. AI-First, Human-Friendly

The MCP server is a first-class interface, not an afterthought. The primary consumer of impact analysis and context bundles is an AI agent. But every output is also human-readable: CLI output uses clear text, context bundles are valid markdown, and dashboards are browsable HTML.

### 5. Fast Enough to Be Interactive

Graph building must complete in under 3 seconds for repos up to 1,000 files. Impact analysis and context assembly must complete in under 500ms. The MCP server must respond in under 200ms. If the tool is too slow to use interactively, people won't use it.

### 6. Correct by Construction

When mdpp auto-generates an INDEX file, it's guaranteed to be consistent with the files on disk. When it reports a broken link, the link is actually broken. When it says a file is stale, the timestamp math is correct. No false positives, no hallucinated relationships. Deterministic, pure parsing - no LLM calls in the core pipeline.

### 7. Batteries Included, Opinions Removable

mdpp ships with sensible defaults for document type detection, relationship inference, and validation rules. These work for most repos out of the box. But every default can be overridden or disabled via config. The tool is opinionated about what it checks by default, but never locks you into those opinions.

## The Inference Engine

The core of mdpp is the inference engine that turns a bag of markdown files into a typed, connected graph. Here's how it works:

### Step 1: Parse

Every `.md` file is parsed to extract:
- **Frontmatter** (YAML between `---` delimiters)
- **Headings** (structure and nesting)
- **Inline links** (markdown `[text](path)` links)
- **ID references** (patterns like `PRQ-01-003`, `F-07`, `MS-12` detected by regex)
- **Metadata** (file path, modification time, size)

### Step 2: Cluster into Types

Files are grouped by frontmatter shape. Two files belong to the same type if they share a similar set of frontmatter keys. The clustering algorithm:

1. Extract the set of frontmatter keys from each file
2. Compute Jaccard similarity between key sets
3. Group files with similarity > 0.6 into the same type
4. Name each type from its directory path pattern

Files without frontmatter are typed by directory path pattern alone (e.g., all files in `decisions/` are type `decision`).

### Step 3: Build Edges

Relationships are created from three sources:

1. **Frontmatter references:** Fields like `depends_on`, `used_by`, `features`, `primary_persona`, `journey` are parsed as references to other nodes. The field name becomes the relationship type.

2. **Inline links:** Markdown links between files become `links_to` edges. If the link text contains semantic hints (e.g., "[Tech Spec](...)"), the relationship type is upgraded.

3. **ID cross-references:** When a known ID pattern (e.g., `PRQ-01-003`) appears in a different file, a `references` edge is created.

### Step 4: Enrich

After the raw graph is built, mdpp enriches it:

- **Infer directionality:** If type A always links to type B but not vice versa, the relationship is directional (A -> B). This powers impact analysis.
- **Detect layers:** Numbered directory prefixes (00-, 01-, ..., 07-) suggest a layered architecture. mdpp infers the flow direction between layers.
- **Identify hubs:** INDEX files, traceability matrices, and similar aggregation documents are tagged as hubs.
- **Flag anomalies:** Orphaned files (no connections), circular dependencies, and broken links.

## Success Criteria

mdpp succeeds if:

1. A user can run `mdpp scan .` on any markdown repo with 50+ files and get a useful graph in under 5 seconds.
2. An AI agent using the MCP server can determine the blast radius of any change in under 200ms.
3. Running `mdpp validate` catches real documentation issues (broken links, missing fields, stale files) with zero false positives.
4. `mdpp context` reduces the token count needed for an AI task by 80%+ compared to loading the full repo.
5. The tool requires zero configuration for the common case.
