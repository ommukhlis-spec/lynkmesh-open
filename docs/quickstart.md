# LynkMesh Quickstart

> Status: early validation / research preview. Expect breaking changes.
> This guide covers only workflows that exist in the repository today.

LynkMesh does not currently ship a task-oriented command-line interface. There
is no `lynkmesh init` or `lynkmesh scan` command. You interact with LynkMesh in
two ways: by running its test/validation suites, and by exposing it to an AI
client over MCP (Model Context Protocol). This guide walks through both.

> **Paths in this guide are placeholders.** Wherever you see
> `<PATH_TO_REPO>` or `<PATH_TO_PROJECT>`, substitute the actual location on
> your machine. Do not commit real local paths into documentation.

## Prerequisites

- Python 3.11+ available on your PATH.
- Git, to clone the repository.
- For PHP analysis: a working PHP toolchain is used by the internal parser
  bridge. PHP is the only language with partial semantic support today; other
  languages fall back to structural-only results.
- For MCP usage: the `mcp` Python package and an MCP-capable client (for example,
  a desktop AI client that supports MCP servers).

## Install from source

Packaging is still stabilizing, so run from a source checkout:

```bash
git clone https://github.com/ommukhlis-spec/lynkmesh.git
cd lynkmesh
python -m pip install -U pip
python -m pip install "mcp[cli]"
```

## Run the validation / smoke workflow

From the repository root, with deterministic hashing enabled:

```bash
# Linux / macOS
export PYTHONHASHSEED=0
python -m pytest test/semantic/contracts -q
```

```bat
REM Windows (cmd)
set PYTHONHASHSEED=0
python -m pytest test\semantic\contracts -q
```

The public, open-core-safe semantic contract tests live under
`test/semantic/contracts`. To run the full default suite:

```bash
python -m pytest
```

The semantic contract suite is the validation surface that ships with the
public core. Run it as your smoke check after any change.

## Use LynkMesh over MCP (high level)

LynkMesh is designed to be exposed to an AI agent through a local MCP server,
following the local-first model described in the project README. Register the
LynkMesh MCP server in your MCP-capable client's configuration so it runs
locally over stdio. The server is local-first: source code stays on your
machine and is not uploaded to a hosted service.

> **Host path note.** Some AI clients present a sandbox namespace, but the
> LynkMesh MCP server runs on your **local host**. When you call the build tool,
> pass the project path **exactly as it exists on the host** (substitute
> `<PATH_TO_PROJECT>`). A sandbox-namespaced path will target a location that does
> not exist on the host.

A typical MCP session uses these tools in order:

1. `get_capabilities` — confirm what is enabled.
2. `start_build` with `project_path = <PATH_TO_PROJECT>`, then `wait_for_build`
   until the build succeeds.
3. `get_mesh_context_report` — the deterministic report.
4. `get_mesh_context_ai_pack` with `profile = "compact"` (also `balanced`,
   `expanded`).
5. `get_mesh_context_token_benchmark` with
   `profiles = "compact,balanced,expanded"`.

## Verify a healthy run

After the build completes and you fetch the three artifacts, confirm:

- **Capabilities** report `feature_stage` 4.4.1 and the flags
  `mesh_context_report_enabled`, `mesh_context_ai_pack_enabled`,
  `mesh_context_token_benchmark_enabled`,
  `mesh_context_token_benchmark_calibrated`, `mesh_context_ai_pack_privacy_safe`,
  and `mesh_context_structural_validation_available` are all `true`.
- **MeshContext Report** returns `status: "ok"`.
- **AI Context Pack** (compact) returns `status: "ok"`.
- **Token Benchmark** returns `status: "ok"`.
- **`source_baselines`** in the token benchmark includes both
  `mesh_context_report` and `serialized_graph_payload`.
- **`contains_llm_inference`** is `false` in the report provenance, the AI pack
  guardrails, and the token benchmark guardrails.

If any of these differ, treat the run as not healthy and re-check the build
status before relying on the output.

## Related documentation

- [The LynkMesh Protocol](lynkmesh_protocol.md)
- [Case study template](case_study_template.md)
- [MeshContext MCP release notes (v4.4.1)](mcp_mesh_context_release_notes_v4.4.1.md)

<!-- LYNKMESH_PUBLIC_CLI_START -->
# LynkMesh public CLI quickstart

LynkMesh provides a local-first CLI for producing deterministic artifacts from a local project.

This is a research preview / early validation workflow. It is not production-ready, does not prove runtime behavior, and does not embed LLM inference in generated artifacts.

## 1. Check the environment

```bash
python -m lynkmesh doctor
```

## 2. Generate a MeshContext Report

```bash
python -m lynkmesh report /path/to/project --pretty > report.json
```

Windows:

```bat
python -m lynkmesh report "C:\path\to\project" --pretty > report.json
```

## 3. Generate an AI Context Pack

```bash
python -m lynkmesh pack /path/to/project --profile compact --pretty > ai-pack.json
```

Windows:

```bat
python -m lynkmesh pack "C:\path\to\project" --profile compact --pretty > ai-pack.json
```

Profiles:

- `compact`
- `balanced`
- `expanded`

Default profile: `compact`.

## 4. Generate a Token Benchmark

```bash
python -m lynkmesh benchmark /path/to/project --profile compact --pretty > benchmark.json
```

Windows:

```bat
python -m lynkmesh benchmark "C:\path\to\project" --profile compact --pretty > benchmark.json
```

Multi-profile benchmark:

```bash
python -m lynkmesh benchmark /path/to/project --profiles compact,balanced,expanded --pretty
```

## 5. Validate JSON output

For successful `report`, `pack`, and `benchmark` commands, stdout is valid JSON and stderr contains diagnostics.

```bash
python -m json.tool report.json > /dev/null
python -m json.tool ai-pack.json > /dev/null
python -m json.tool benchmark.json > /dev/null
```

Windows:

```bat
python -m json.tool report.json > nul
python -m json.tool ai-pack.json > nul
python -m json.tool benchmark.json > nul
```

## Notes

- The CLI is local-first and does not perform network access.
- `report`, `pack`, and `benchmark` do not write files unless stdout is redirected.
- Generated artifacts contain no embedded LLM inference.
- Generated payloads may contain project names, symbols, structural information, and code-derived metadata.
- Static analysis can be incomplete.
- Dynamic dispatch and runtime behavior may be incomplete.
- Deterministic candidates are not confirmed runtime truth.
<!-- LYNKMESH_PUBLIC_CLI_END -->
