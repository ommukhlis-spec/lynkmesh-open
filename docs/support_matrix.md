# LynkMesh Support Matrix

> **Status: early alpha / research preview.** This matrix is a snapshot of
> current capability levels as of the most recent public release. Expect
> changes.

This document describes what is currently supported, experimental, partial,
or unsupported in the LynkMesh public open-core release.

## Status definitions

| Status | Meaning |
|--------|---------|
| **Supported (alpha)** | Works in the public release with known scope and test coverage. APIs may still change. |
| **Experimental** | Functional but limited; output quality varies; may change significantly. |
| **Partial** | Basic support exists but many cases are not covered. Expect gaps. |
| **Planned** | On the roadmap but not yet implemented in the public release. |
| **Not currently supported** | Not available in the public release. May be explored in future work. |

---

## Core scanning

| Area | Status | Notes |
|------|--------|-------|
| File scanning | Supported (alpha) | Recursive file discovery with language-agnostic inventory. |
| File classification | Supported (alpha) | Extension-based classification; language-specific detection for PHP. |
| Directory structure analysis | Supported (alpha) | Directory-level architecture hints. |
| Incremental scanning | Planned | Incremental diff pipeline is in the roadmap (Stage 5). |

## PHP support

| Area | Status | Notes |
|------|--------|-------|
| PHP file parsing | Supported (alpha) | Uses nikic/PHP-Parser via internal bridge. |
| Namespace resolution | Supported (alpha) | PSR-4 and explicit namespace resolution. |
| Class/interface/trait detection | Supported (alpha) | Full class-like structure detection. |
| Method/function detection | Supported (alpha) | Method and function symbol extraction. |
| Use-statement resolution | Experimental | Most common patterns resolved; edge cases may be missed. |
| Property/constant detection | Partial | Basic detection; type inference is limited. |
| DocBlock parsing | Partial | Structural extraction; full semantic interpretation is not provided. |
| Anonymous classes | Partial | Detected but not deeply analyzed. |
| Closures / arrow functions | Partial | Detected; call graph edges may be incomplete. |
| Traits | Partial | Detected; trait composition edges are not fully modeled. |
| Enums (PHP 8.1+) | Experimental | Basic detection; enum-backed edges are limited. |
| Attributes (PHP 8.0+) | Experimental | Detected; not yet integrated into graph edges. |
| Match expressions | Not currently supported | PHP 8.0 match is not modeled in the dependency graph. |
| Generator-based control flow | Not currently supported | Yield-based control flow is not traced. |

## Composer / PSR-4

| Area | Status | Notes |
|------|--------|-------|
| `composer.json` parsing | Supported (alpha) | Autoload configuration is read. |
| PSR-4 namespace-to-path mapping | Supported (alpha) | Standard PSR-4 autoloading is resolved. |
| PSR-0 fallback | Not currently supported | PSR-0 autoloading is not resolved. |
| Classmap autoloading | Not currently supported | Classmap-based autoloading is not parsed. |
| Files autoloading | Not currently supported | `files` autoload entries are not traced. |
| Composer dependencies (vendor) | Experimental | Vendor packages detected but not deeply analyzed. |

## Dependency graph

| Area | Status | Notes |
|------|--------|-------|
| File-level dependencies | Supported (alpha) | `include`/`require` and use-statement edges. |
| Class-level dependencies | Supported (alpha) | Inheritance and interface implementation edges. |
| Method-level call edges | Partial | Direct method calls are resolved; indirect calls may be missed. |
| Static call resolution | Partial | `ClassName::method()` calls are partially resolved. |
| Dynamic call resolution | Not currently supported | `$obj->$method()` patterns are not resolved. |
| Dependency direction | Supported (alpha) | Edges carry direction metadata. |
| Circular dependency detection | Experimental | Basic cycle detection; may produce false positives. |

## Semantic graph

| Area | Status | Notes |
|------|--------|-------|
| Graph identity (deterministic) | Supported (alpha) | Graph hashing is deterministic with `PYTHONHASHSEED=0`. |
| Graph versioning | Supported (alpha) | Version metadata is attached to each graph snapshot. |
| Graph serialization | Supported (alpha) | Deterministic JSON serialization. |
| Symbol registry | Supported (alpha) | Symbols are registered with type and location metadata. |
| Type registry | Supported (alpha) | Types are registered with resolution status. |
| Confidence semantics | Supported (alpha) | Each edge/node carries a confidence level. |
| Provenance tracking | Supported (alpha) | Artifacts track their source build and scan metadata. |
| Telemetry contracts | Supported (alpha) | Internal telemetry structure defined; no external reporting. |
| Structural validation | Supported (alpha) | Cross-artifact consistency checks. |

## AI context pack

| Area | Status | Notes |
|------|--------|-------|
| Compact profile | Supported (alpha) | Minimal token footprint; deterministic output. |
| Balanced profile | Supported (alpha) | Moderate detail; deterministic output. |
| Expanded profile | Supported (alpha) | Full available context; deterministic output. |
| Privacy safety guardrails | Supported (alpha) | `privacy_safe` flag and safety scan before output. |
| `contains_llm_inference` guarantee | Supported (alpha) | Always `false` in generated artifacts. |

## Benchmark / evidence artifacts

| Area | Status | Notes |
|------|--------|-------|
| Token estimation | Supported (alpha) | Deterministic heuristic; not tokenizer-exact. |
| Dual-baseline calibration | Supported (alpha) | Benchmarks against `mesh_context_report` and `serialized_graph_payload`. |
| Multi-profile benchmarking | Supported (alpha) | `--profiles compact,balanced,expanded` |
| Before/after evaluation baseline | Supported (alpha) | Scenarios, templates, metrics schema, and one committed fixture run. |
| Published benchmark results | Not currently supported | The evidence pack is an evaluation baseline, not published benchmark proof. |

## MCP integration

| Area | Status | Notes |
|------|--------|-------|
| Local MCP server | Experimental | Runs locally over stdio; API is evolving. |
| `get_capabilities` | Experimental | Reports enabled features and stage. |
| `start_build` / `wait_for_build` | Experimental | Triggers graph build on the local project. |
| `get_mesh_context_report` | Experimental | Returns the deterministic report via MCP. |
| `get_mesh_context_ai_pack` | Experimental | Returns AI context packs via MCP. |
| `get_mesh_context_token_benchmark` | Experimental | Returns token benchmarks via MCP. |
| Hosted MCP server | Not currently supported | Local-first only; hosted MCP is a future consideration. |

## Non-PHP languages

| Area | Status | Notes |
|------|--------|-------|
| Python | Not currently supported | Basic file inventory may be possible; no semantic analysis. |
| JavaScript / TypeScript | Not currently supported | No parser integration. |
| Java / Kotlin | Not currently supported | No parser integration. |
| C# / .NET | Not currently supported | No parser integration. |
| Go | Not currently supported | No parser integration. |
| Rust | Not currently supported | No parser integration. |
| Ruby | Not currently supported | No parser integration. |
| C / C++ | Not currently supported | No parser integration. |
| Multi-language projects | Not currently supported | Only PHP files receive semantic analysis; other files are inventoried only. |

## Framework magic / runtime behavior

| Area | Status | Notes |
|------|--------|-------|
| Laravel service container | Experimental | Basic detection; automatic dependency injection is not fully modeled. |
| Laravel facades | Not currently supported | Facade resolution is not traced. |
| Laravel Eloquent ORM | Not currently supported | Dynamic query scopes and relationships are not modeled. |
| Symfony DI | Not currently supported | No Symfony-specific DI analysis. |
| WordPress hooks / actions | Not currently supported | No WordPress-specific analysis. |
| Dynamic dispatch (`__call`, `__get`) | Not currently supported | PHP magic methods are not resolved. |
| Reflection-based invocation | Not currently supported | Runtime reflection patterns are not analyzed. |
| `call_user_func` / `call_user_func_array` | Not currently supported | Dynamic callbacks are not traced. |
| Routing files (web.php, api.php) | Partial | Basic file inventory; route-to-handler edges are experimental. |
| Middleware chains | Experimental | Basic middleware detection; full chain resolution is limited. |

## Large repository behavior

| Area | Status | Notes |
|------|--------|-------|
| Projects under 1,000 files | Supported (alpha) | Expected to complete without issues. |
| Projects 1,000–10,000 files | Experimental | May complete; performance and memory usage not yet profiled publicly. |
| Projects over 10,000 files | Not currently supported | Not tested; may exceed practical limits. |
| Incremental updates | Planned | Incremental pipeline is in the roadmap. |
| Persistent graph cache | Planned | Cache layer is in the roadmap (Stage 5). |

## CLI stability

| Area | Status | Notes |
|------|--------|-------|
| `lynkmesh doctor` | Supported (alpha) | Stable command; output format may evolve. |
| `lynkmesh report` | Supported (alpha) | Stable command; JSON schema may evolve. |
| `lynkmesh pack` | Supported (alpha) | Stable command; profile definitions may evolve. |
| `lynkmesh benchmark` | Supported (alpha) | Stable command; metric structure may evolve. |
| stdout JSON contract | Supported (alpha) | Valid JSON on success; diagnostics on stderr. |
| Exit codes | Supported (alpha) | 0 on success; non-zero on error. |

---

## Summary

The LynkMesh public open-core release is most reliable for:

- **PHP projects** with standard PSR-4 autoloading
- **Small to medium repositories** (under 1,000 files)
- **Local-first deterministic analysis** of code structure, dependencies, and
  architecture
- **AI context pack generation** for use with AI coding agents

It is **not yet suitable** for:

- Non-PHP languages (no semantic analysis)
- Large repositories (untested)
- Runtime behavior analysis (static analysis only)
- Framework-heavy projects with significant magic/dynamic behavior
- Production enforcement or governance workflows

Treat capability claims conservatively. If you encounter an area where
LynkMesh's behavior does not match this matrix, please open an issue.
