# Try LynkMesh in 5 Minutes

This guide shows the shortest public-safe path to try LynkMesh on the included synthetic fixture.

LynkMesh is a deterministic MeshContext evidence protocol for AI coding agents. It turns codebases into graph-backed, inspectable context artifacts that can support AI-assisted code understanding workflows.

This is an early validation workflow, not benchmark proof.

## Prerequisites

- Python 3.11+
- Git

## Step 1 — Clone and set up

```bash
git clone https://github.com/ommukhlis-spec/lynkmesh.git
cd lynkmesh
```

Set the deterministic hash seed (required by the pipeline):

**Linux / macOS:**
```bash
export PYTHONHASHSEED=0
```

**Windows (Command Prompt):**
```bat
set PYTHONHASHSEED=0
```

**Windows (PowerShell):**
```powershell
$env:PYTHONHASHSEED = "0"
```

## Step 2 — Verify the environment

```bash
python -m lynkmesh doctor
```

Expected: `Result: ready`.

## Step 3 — Run the tests

```bash
python -m pytest test/semantic/contracts test/unit/cli -q
```

Expected: 139+ passed.

## Step 4 — Build a MeshContext AI Context Pack

The included synthetic fixture is `evals/before_after/fixtures/mini_auth_shop_php` — a minimal PHP project with auth, products, routing, and middleware.

**Compact profile (default):**
```bash
python -m lynkmesh pack evals/before_after/fixtures/mini_auth_shop_php --pretty
```

**Expanded profile:**
```bash
python -m lynkmesh pack evals/before_after/fixtures/mini_auth_shop_php --profile expanded --pretty
```

Supported profiles: `compact`, `balanced`, `expanded`.

## Step 5 — Run a token benchmark across all profiles

```bash
python -m lynkmesh benchmark evals/before_after/fixtures/mini_auth_shop_php --profiles compact,balanced,expanded --pretty
```

Note: the `benchmark` command uses `--profiles` (plural, comma-separated), not `--profile`.

## What you just ran

| Step | Command | What it does |
|------|---------|--------------|
| 2 | `doctor` | Reports local environment diagnostics (no graph build, no file writes, no network). |
| 3 | `pytest` | Runs public contract and CLI unit tests. |
| 4 | `pack` | Builds a deterministic AI Context Pack from the synthetic fixture. |
| 5 | `benchmark` | Builds a deterministic token estimate across all three profiles. |

All commands are local-first: no network access, no LLM inference, no files written.

## Troubleshooting

**`PYTHONHASHSEED must be '0'` error:**
The pipeline requires `PYTHONHASHSEED=0` for deterministic output. Set it as shown in Step 1.

**`error: path does not exist`:**
Ensure you are running commands from the repository root (the directory containing `__main__.py`).

**`No module named lynkmesh`:**
If you installed from source, add the parent directory to `PYTHONPATH`:
```bash
export PYTHONPATH="$(pwd)/..:$PYTHONPATH"    # Linux / macOS
```
```bat
set PYTHONPATH=%cd%\..;%PYTHONPATH%           # Windows
```

## Next steps

- Read the [positioning note](positioning.md) to understand what LynkMesh is and isn't.
- Read the [quickstart](quickstart.md) for a deeper workflow.
- Explore the [evidence pack](../evals/before_after/) to review deterministic graph artifacts.
