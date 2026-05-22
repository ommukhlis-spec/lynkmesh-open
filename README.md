# LynkMesh

> Local-first semantic code intelligence infrastructure for AI agents.

LynkMesh is an experimental open-core project for building deterministic code understanding layers on top of real-world software systems.

Modern AI can read source code, but it still struggles to understand software systems as connected, evolving architectures. LynkMesh explores a graph-first approach: instead of treating a repository as isolated files, chunks, or embeddings, it models codebases as semantic graphs with explicit relationships, traversal boundaries, confidence signals, and architecture-aware retrieval.

The long-term goal is to provide a reliable semantic substrate for AI-native software engineering systems.

---

## Why LynkMesh Exists

Most AI coding tools rely heavily on:

- large context windows
- file chunking
- vector search
- heuristic retrieval
- repeated repository scanning

These approaches are useful, but they often fail when a system requires:

- deterministic dependency awareness
- architecture-level reasoning
- impact analysis
- request-flow understanding
- large-codebase navigation
- persistent project memory
- safe context selection for AI agents

LynkMesh exists to explore a missing infrastructure layer between raw source code and AI reasoning.

```text
Codebase
   ↓
Ingestion
   ↓
Intermediate Representation (IR)
   ↓
Semantic Graph
   ↓
Query / Reasoning Layer
   ↓
Context Compilation
   ↓
AI Agents
```

---

## What LynkMesh Is

LynkMesh is:

- a semantic graph engine for codebases
- a deterministic code reasoning foundation
- a local-first context layer for AI agents
- an experimental MCP-ready infrastructure layer
- a foundation for architecture-aware retrieval

LynkMesh is not:

- a chatbot wrapper
- a vector database
- a generic code summarizer
- a hosted SaaS dashboard
- a production-ready autonomous coding agent

---

## Open-Core Model

LynkMesh is being developed as an open-core project.

### Community Edition

The public repository focuses on the local-first core:

- deterministic graph identity
- graph serialization foundations
- ingestion pipeline
- parser orchestration
- IR normalization
- graph construction
- semantic contracts
- symbol/type registry foundations
- basic analysis and reasoning layers
- local MCP integration foundation
- experimental PHP-oriented static analysis

The Community Edition is intended to help developers and AI agents inspect, reason about, and retrieve structured context from codebases locally.

### Pro / Private Runtime

Advanced runtime capabilities may be developed separately as private or commercial layers, including:

- incremental diff runtime
- persistent graph cache runtime
- large-repository optimization
- advanced semantic cache
- team/workspace graph memory
- hosted MCP server
- cloud repository connectors
- multi-project indexing
- advanced framework-aware analysis
- enterprise audit/security controls

This boundary keeps the public core useful while preserving room for sustainable commercial development.

---

## Current Status

LynkMesh is currently in early alpha.

The project is usable for research, experimentation, and internal development, but public APIs are still evolving.

Current focus:

- deterministic graph foundations
- graph versioning and serialization
- semantic contracts
- query-layer stabilization
- local MCP exposure
- AI-oriented context retrieval
- PHP-first static analysis exploration

Expect breaking changes.

---

## Documentation

LynkMesh is currently an early validation / research preview of a deterministic context protocol for AI-assisted code understanding. It is not production-ready.

- [The LynkMesh Protocol](docs/lynkmesh_protocol.md) — the problem, the deterministic pipeline, and the privacy model.
- [Quickstart](docs/quickstart.md) — prerequisites, validation/smoke workflow, and high-level MCP usage.
- [Case study template](docs/case_study_template.md) — a reusable, sanitized format for analysis examples.
- [MeshContext MCP release notes (v4.4.1)](docs/mcp_mesh_context_release_notes_v4.4.1.md) — current MCP capability metadata and guarantees.

### Release status

LynkMesh is at an early validation / research-preview stage and is not production-ready.

- [Public release notes (v0.1)](docs/public_release_notes_v0.1.md) — release status, what's included, and limitations.
- [GitHub public profile draft](docs/github_public_profile.md) — suggested public-facing descriptions and release copy.

---

## Current Language Support

LynkMesh should be treated as language-layered:

```text
Core graph engine       = language-agnostic
Ingestion / parser      = language-specific
Framework understanding = framework-specific
```

Current practical support:

| Language | Status | Notes |
|---|---|---|
| PHP | Partial / early alpha | File scanning, namespace/class-oriented parsing, dependency graph foundations |
| Laravel-style PHP | Experimental | Some architectural patterns are being explored, but framework magic is not fully modeled |
| Other languages | Not officially supported | Basic file inventory may be possible later, but semantic graph accuracy is not guaranteed |

Unsupported languages should not be treated as fully analyzable. LynkMesh should report unsupported or fallback behavior instead of pretending to understand code it cannot reliably parse.

---

## MCP Integration

LynkMesh is designed to be exposed to AI agents through the Model Context Protocol (MCP).

The intended MCP model is local-first:

```text
MCP Client / AI Client
        ↓
Local MCP Server
        ↓
LynkMesh Core
        ↓
Local Codebase
```

This allows AI agents to use LynkMesh without uploading source code to a hosted service.

Early MCP tools may include:

- `ping`
- `get_status`
- `get_capabilities`
- `scan_project`
- `get_project_summary`
- `build_graph`
- `get_graph_summary`
- `analyze_impact`
- `trace_dependencies`

MCP support is experimental and will evolve as the public interface stabilizes.

---

## Architecture Overview

```text
lynkmesh/
├── ingestion/
│   ├── file scanning
│   ├── language loading
│   ├── parser orchestration
│   └── IR normalization
│
├── graph/
│   ├── graph building
│   ├── call resolution
│   ├── graph enrichment
│   ├── graph mapping
│   └── validation
│
├── core/
│   ├── graph core
│   ├── graph versioning
│   ├── graph serialization
│   ├── IR models
│   ├── symbol registry
│   └── type registry
│
├── semantic/contracts/
│   ├── confidence semantics
│   ├── resolution contracts
│   ├── edge semantics
│   ├── provenance
│   └── telemetry
│
├── analysis/
│   ├── architecture analysis
│   ├── flow analysis
│   ├── impact analysis
│   └── semantic reasoning
│
├── query/
│   ├── query planning
│   ├── query execution
│   └── unified query abstraction
│
├── reasoning/
│   ├── graph reasoning
│   └── chain execution
│
├── pipeline/
│   └── orchestration layer
│
├── exporters/
│   └── experimental export interfaces
│
└── test/
    ├── unit tests
    ├── integration tests
    └── semantic contract tests
```

---

## Core Principles

### Determinism

LynkMesh prioritizes deterministic graph identity, stable serialization, and reproducible reasoning boundaries.

AI systems can hallucinate. Infrastructure should not.

### Semantic Graphs Over Raw Files

The goal is not only to retrieve files, but to understand relationships between entities:

- files
- symbols
- classes
- methods
- dependencies
- calls
- semantic edges
- architectural boundaries

### Local-First by Default

The Community Edition is designed to run locally. Source code should remain on the developer machine unless the user explicitly chooses a hosted workflow.

### AI-Oriented Context

LynkMesh is designed for AI consumption. Outputs should be structured, scoped, and explicit enough for agents to reason over safely.

### Honest Capability Reporting

If a language, framework, or runtime behavior is not supported, LynkMesh should say so clearly.

---

## Current Public Capabilities

The public core currently focuses on:

- file scanning foundations
- parser orchestration
- IR normalization
- graph construction
- graph version identity
- deterministic serialization foundations
- symbol registry
- type registry
- semantic contracts
- confidence semantics
- provenance tracking
- telemetry contracts
- basic architecture and reasoning layers
- experimental query abstractions

Advanced incremental runtime and persistent cache internals are intentionally not part of the public Community Edition at this stage.

---

## Limitations

LynkMesh is not production-ready yet.

Known limitations:

- public APIs are not stable
- MCP interface is still evolving
- PHP support is partial
- non-PHP languages are not officially supported
- framework magic is not fully modeled
- runtime behavior is not fully inferred
- exporters are still incomplete
- query APIs are still experimental
- large repository optimization is not yet public

Use LynkMesh as research infrastructure and early alpha tooling.

---

## Installation

Packaging is still being stabilized.

For now, use the repository from source:

```bash
git clone https://github.com/ommukhlis-spec/lynkmesh.git
cd lynkmesh
python -m pip install -U pip
python -m pip install "mcp[cli]"
```

Additional dependency and packaging instructions will be added as the public CLI and MCP entrypoints stabilize.

---

## Development

Run tests from the repository root:

```bash
python -m pytest
```

Run a specific test module:

```bash
python -m pytest test/unit/core/test_graph_version.py -v
```

Some modules are experimental and may change rapidly.

---

## Suggested Use Cases

LynkMesh Community Edition is currently best suited for:

- AI-assisted codebase exploration
- semantic graph experiments
- local MCP tooling experiments
- deterministic graph identity research
- architecture-aware retrieval prototypes
- PHP-oriented static analysis exploration
- building foundations for AI code intelligence systems

It is not yet intended for:

- production CI enforcement
- enterprise dependency governance
- complete runtime tracing
- universal multi-language analysis
- fully automated refactoring workflows

---

## Roadmap

### Stage 1 — Semantic Foundation

- ingestion pipeline
- parser orchestration
- IR normalization
- graph construction
- symbol/type registries

### Stage 2 — Deterministic Graph Core

- graph identity
- graph versioning
- semantic contracts
- confidence/provenance/telemetry
- deterministic serialization

### Stage 3 — MCP + Query Layer

- local MCP server
- capability reporting
- graph summary tools
- project scanning tools
- scoped query APIs
- AI-oriented context retrieval

### Stage 4 — Context Compiler

- context ranking
- semantic neighborhood retrieval
- impact-aware expansion
- token-aware context selection
- AI-ready explanation payloads

### Stage 5 — Advanced Runtime

Advanced runtime capabilities may be developed in private or commercial layers:

- incremental diff engine
- persistent graph cache
- large-repo graph optimization
- hosted MCP
- team graph memory
- cloud repository integrations

---

## Repository Hygiene

The public repository intentionally excludes:

- local AI client settings
- private diagnostics
- local benchmark project paths
- debug artifacts
- generated graph caches
- experimental private runtime modules

If you find sensitive or machine-local artifacts in the public repository, please open an issue.

---

## Contributing

LynkMesh is still early. Contributions are welcome, but the architecture is moving quickly.

Good contribution areas:

- documentation
- tests
- parser fixtures
- small bug fixes
- semantic contract improvements
- MCP tool interface feedback
- supported-language capability reporting

Before larger architectural changes, please open an issue or discussion first.

---

## Security and Privacy

LynkMesh Community Edition is designed to run locally.

The project should not upload source code by default. Any future hosted or remote workflow should be explicit, permissioned, and documented separately.

Do not commit:

- `.env`
- local Claude settings
- private project paths
- generated graph dumps
- debug traces
- API keys
- local cache databases

---

## License

LynkMesh Community Edition is intended to be released under the Apache License 2.0.

Commercial, hosted, or Pro runtime components may be distributed separately under different terms.

Before using LynkMesh in production, confirm the current license file in this repository.

---

## Author

Built as an independent semantic infrastructure research project for deterministic AI-oriented code intelligence.

---

## Project Philosophy

AI agents need more than larger context windows.

They need stable semantic infrastructure.

LynkMesh is an attempt to build that layer.

<!-- LYNKMESH_PUBLIC_CLI_START -->
## Public CLI quickstart

LynkMesh provides a local-first public CLI for producing deterministic, static-analysis-derived artifacts from a local project.

This workflow is a research preview / early validation. It is not production-ready, does not prove runtime behavior, and does not embed LLM inference in generated artifacts.

### Commands

```bash
python -m lynkmesh doctor
python -m lynkmesh report /path/to/project --pretty > report.json
python -m lynkmesh pack /path/to/project --profile compact --pretty > ai-pack.json
python -m lynkmesh benchmark /path/to/project --profile compact --pretty > benchmark.json
```

Windows:

```bat
python -m lynkmesh doctor
python -m lynkmesh report "C:\path\to\project" --pretty > report.json
python -m lynkmesh pack "C:\path\to\project" --profile compact --pretty > ai-pack.json
python -m lynkmesh benchmark "C:\path\to\project" --profile compact --pretty > benchmark.json
```

### Artifact types

- **MeshContext Report**: deterministic project graph facts and conservative architecture context.
- **AI Context Pack**: compact, balanced, or expanded context package intended for AI assistants.
- **Token Benchmark**: deterministic token estimate / calibration for report and pack profiles.

Available profiles:

- `compact`
- `balanced`
- `expanded`

Default profile: `compact`.

For benchmark multi-profile output, use:

```bash
python -m lynkmesh benchmark /path/to/project --profiles compact,balanced,expanded --pretty
```

### stdout and stderr

For successful `report`, `pack`, and `benchmark` commands:

- stdout is valid JSON.
- stderr contains progress, warnings, and diagnostics.
- redirect stdout with `>` to save artifacts.

Validate JSON:

```bash
python -m json.tool report.json > /dev/null
```

Windows:

```bat
python -m json.tool report.json > nul
```

### Privacy and limitations

The public CLI is local-first and does not perform network access. Generated payloads pass safety checks before printing, but they may still contain project names, symbols, structural information, and code-derived metadata. Avoid sharing generated JSON publicly if the source project is private.

Static analysis can be incomplete. Dynamic dispatch and runtime behavior may be incomplete. Entrypoints, hotspots, and risk candidates are deterministic candidates, not confirmed defects.
<!-- LYNKMESH_PUBLIC_CLI_END -->

