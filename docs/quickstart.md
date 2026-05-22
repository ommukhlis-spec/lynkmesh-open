# LynkMesh Quickstart

> Status: early validation / research preview. Expect breaking changes.
>
> This guide covers workflows that exist in the public source checkout today. LynkMesh now includes a local CLI for generating deterministic artifacts. It does not include a `lynkmesh init` or `lynkmesh scan` workflow yet.

LynkMesh is local-first. The public CLI reads a local project path and writes JSON only when you redirect stdout.

> **Path placeholders.** Wherever you see `/path/to/project` or `C:\path\to\project`, substitute a real path on your machine. Do not commit real local paths into documentation, issues, examples, or generated public artifacts.

---

## Prerequisites

- Python 3.11+ available on your PATH.
- Git, to clone the repository.
- For PHP analysis: a working PHP toolchain may be used by parser bridge workflows.
- PHP is the only language with partial semantic support today; other languages should be treated as unsupported or structural-only unless explicitly documented.

---

## Install from source

Packaging is still stabilizing, so use the public source checkout:

```bash
git clone https://github.com/ommukhlis-spec/lynkmesh-open.git
cd lynkmesh-open
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

For source-checkout usage, prefer:

```bash
python -m lynkmesh --help
```

After editable installation, the console entrypoint should also be available:

```bash
lynkmesh --help
```

Do not treat this as a production-ready package or a PyPI availability claim.

---

## 1. Check the environment

Run:

```bash
python -m lynkmesh doctor
```

`doctor` performs local readiness checks and prints human-readable diagnostics. It does not build a graph, write files, call hosted services, or run LLM inference.

---

## 2. Generate a MeshContext Report

Linux / macOS:

```bash
python -m lynkmesh report /path/to/project --pretty > report.json
```

Windows:

```bat
python -m lynkmesh report "C:\path\to\project" --pretty > report.json
```

The report is a deterministic, machine-readable projection of code-derived facts and candidates. It should not be interpreted as proof of runtime behavior.

---

## 3. Generate an AI Context Pack

Linux / macOS:

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

The AI Context Pack is token-conscious and evidence-linked, but it does not contain embedded LLM inference.

---

## 4. Generate a Token Benchmark

Single profile:

```bash
python -m lynkmesh benchmark /path/to/project --profile compact --pretty > benchmark.json
```

Windows:

```bat
python -m lynkmesh benchmark "C:\path\to\project" --profile compact --pretty > benchmark.json
```

Multiple profiles:

```bash
python -m lynkmesh benchmark /path/to/project --profiles compact,balanced,expanded --pretty > benchmark.json
```

Token benchmark figures are deterministic heuristics for relative comparison. They are not tokenizer-exact counts, model-specific billing numbers, or published benchmark proof.

---

## 5. Validate JSON output

For successful `report`, `pack`, and `benchmark` commands:

- stdout is valid JSON
- stderr contains diagnostics/progress messages
- no output file is written unless stdout is redirected

Validate output files:

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

---

## 6. Run the validation / smoke workflow

From the repository root, with deterministic hashing enabled:

Linux / macOS:

```bash
export PYTHONHASHSEED=0
python -m pytest test/semantic/contracts -q
python -m pytest test/unit/cli
```

Windows cmd:

```bat
set PYTHONHASHSEED=0
python -m pytest test\semantic\contracts -q
python -m pytest test\unit\cli
```

To run the full default suite:

```bash
python -m pytest
```

The semantic contract suite is the validation surface that ships with the public core. Run it as your smoke check after any change.

---

## Optional: high-level MCP usage

LynkMesh is designed to be exposed to AI agents through a local MCP server, following the local-first model described in the project README.

The server model is local-first: source code stays on your machine and should not be uploaded to a hosted service by default.

MCP support is experimental and capability-dependent. Prefer the CLI quickstart above when validating the current public source checkout.

---

## Notes and limitations

- The CLI is local-first and does not perform network access.
- `report`, `pack`, and `benchmark` do not write files unless stdout is redirected.
- Generated artifacts contain no embedded LLM inference.
- Generated payloads may contain project names, symbols, structural information, and code-derived metadata.
- Static analysis can be incomplete.
- Dynamic dispatch and runtime behavior may be incomplete.
- Deterministic candidates are not confirmed runtime truth.
- LynkMesh is not production-ready.

---

## Related documentation

- [The LynkMesh Protocol](lynkmesh_protocol.md)
- [Case study template](case_study_template.md)
- [MeshContext MCP release notes (v4.4.1)](mcp_mesh_context_release_notes_v4.4.1.md)
- [Public release notes (v0.1)](public_release_notes_v0.1.md)
- [GitHub public profile draft](github_public_profile.md)
