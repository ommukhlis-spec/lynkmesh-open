# LynkMesh Demo Script

> **Status: early alpha / research preview.** This demo script describes a
> workflow that works today on the included synthetic fixture. It does not
> claim production readiness, benchmark proof, or universal applicability.

## Purpose

This document explains the basic LynkMesh demo story for a new user, reviewer,
or AI-agent developer. It covers what problem LynkMesh solves, what it
produces, and how to walk through a complete first experience.

After reading this, you should be able to:

- Explain what LynkMesh does and why it exists
- Run the core LynkMesh commands on the included fixture
- Inspect the outputs and understand what each artifact contains
- Understand which claims are supported and which are not

---

## The problem LynkMesh addresses

AI coding agents are powerful, but they often reason from incomplete or noisy
context:

- They see isolated files without understanding how they connect.
- They repeat expensive repository scans for every task.
- They lack deterministic awareness of dependencies, architecture, and impact
  boundaries.
- They cannot easily distinguish structural facts from their own inferences.

LynkMesh provides a graph-backed, deterministic evidence layer so that AI
agents can ground their reasoning in structured project context before
modifying, reviewing, or explaining software changes.

---

## What LynkMesh produces

LynkMesh turns a codebase into three types of deterministic, inspectable
artifacts:

| Artifact | Command | Description |
|----------|---------|-------------|
| **MeshContext Report** | `report` | Deterministic project graph facts and conservative architecture context. |
| **AI Context Pack** | `pack` | Compact, balanced, or expanded context package designed for AI consumption. |
| **Token Benchmark** | `benchmark` | Deterministic token estimate / calibration across profiles. |

All artifacts are:

- **Local-first** — no network access, no source code uploaded.
- **Deterministic** — same inputs produce same outputs (`PYTHONHASHSEED=0`).
- **Inference-free** — `contains_llm_inference` is always `false`.
- **Valid JSON** — stdout is machine-readable; stderr carries diagnostics.

---

## Example demo workflow

### Prerequisites

- Python 3.11+
- Git
- `PYTHONHASHSEED=0` set in your environment

### Step 1 — Set up

```bash
git clone https://github.com/ommukhlis-spec/lynkmesh-open.git
cd lynkmesh-open
```

Set the deterministic hash seed:

**Linux / macOS:**
```bash
export PYTHONHASHSEED=0
```

**Windows (PowerShell):**
```powershell
$env:PYTHONHASHSEED = "0"
```

### Step 2 — Verify the environment

```bash
python -m lynkmesh doctor
```

Expected: `Result: ready`.

This command checks your local environment without building a graph or writing
any files.

### Step 3 — Run the tests (optional but recommended)

```bash
python -m pytest test/semantic/contracts test/unit/cli -q
```

Expected: 139+ passed.

This confirms that the semantic contract tests and CLI unit tests pass in your
environment.

### Step 4 — Generate a MeshContext Report

The included synthetic fixture is `evals/before_after/fixtures/mini_auth_shop_php` —
a minimal PHP project with auth, products, routing, and middleware.

```bash
python -m lynkmesh report evals/before_after/fixtures/mini_auth_shop_php --pretty > report.json
```

Inspect the report:

```bash
python -m json.tool report.json | head -80
```

Key fields to look for:
- `status`: should be `"ok"`
- `node_count` and `edge_count`: graph structure summary
- `provenance.contains_llm_inference`: must be `false`
- `architecture_profile`: summary of architectural findings

### Step 5 — Generate an AI Context Pack

```bash
python -m lynkmesh pack evals/before_after/fixtures/mini_auth_shop_php --profile compact --pretty > ai-pack.json
```

Try other profiles:

```bash
python -m lynkmesh pack evals/before_after/fixtures/mini_auth_shop_php --profile balanced --pretty > ai-pack-balanced.json
python -m lynkmesh pack evals/before_after/fixtures/mini_auth_shop_php --profile expanded --pretty > ai-pack-expanded.json
```

Profiles:
- `compact` — minimal token footprint (default)
- `balanced` — moderate detail
- `expanded` — full available context

Key fields to inspect:
- `status`
- `guardrails.contains_llm_inference`: must be `false`
- `guardrails.privacy_safe`: should be `true`
- `context_sections`: the structured sections provided to an AI agent

### Step 6 — Run a token benchmark

```bash
python -m lynkmesh benchmark evals/before_after/fixtures/mini_auth_shop_php --profiles compact,balanced,expanded --pretty > benchmark.json
```

Note: `benchmark` uses `--profiles` (plural, comma-separated).

Key fields to inspect:
- `status`
- `source_baselines`: should include both `mesh_context_report` and
  `serialized_graph_payload`
- `guardrails.contains_llm_inference`: must be `false`
- Per-profile token estimates

### Step 7 — Explore the evidence pack (optional)

The public evidence pack at `evals/before_after/` provides:

- Scenario definitions for reproducible evaluations
- Before/after run templates
- Metric schemas
- The first committed fixture-level run (`mini_auth_shop_php_001`)
- Screenshots and comparison summaries

Read `evals/before_after/README.md` for details on how to run your own
evaluation.

---

## How a human reviewer or AI agent should consume LynkMesh artifacts

### For human reviewers

1. Read the **MeshContext Report** for a deterministic summary of the project
   structure, architecture profile, and known limitations.
2. Use the **AI Context Pack** as a structured reference when reviewing AI
   agent outputs or code changes — it provides the same context the agent
   received.
3. Check the **Token Benchmark** to understand the size and scope of context
   being provided.

### For AI agents

1. Request the **MeshContext Report** to understand the project's structure
   before reasoning.
2. Use the **AI Context Pack** as grounding evidence for analysis tasks.
3. Reference specific graph facts (nodes, edges, architecture findings) in
   your explanations instead of making unsupported claims.
4. Always distinguish between deterministic facts from LynkMesh and your own
   inferences.

---

## What claims are supported

The following claims are consistent with the current evidence and
documentation:

- LynkMesh provides **deterministic, static-analysis-derived project
  evidence** for AI-assisted code understanding workflows.
- LynkMesh artifacts are **inspectable, reproducible, and free of embedded
  LLM inference**.
- LynkMesh **may reduce manual context preparation** in selected workflows.
- LynkMesh operates **local-first** — no source code is uploaded.
- LynkMesh is at an **early alpha / research preview** stage.

---

## What claims are NOT supported

Do not claim or imply:

- LynkMesh makes an AI model smarter.
- LynkMesh provides benchmark proof of AI improvement.
- LynkMesh is production-ready.
- LynkMesh fully understands all languages, frameworks, or runtime behavior.
- LynkMesh replaces Sourcegraph, vector databases, IDEs, or coding agents.
- LynkMesh guarantees correct AI analysis.
- LynkMesh is enterprise-ready.
- Results from the included fixture generalize to all projects.

---

## After the demo

Suggested next steps for the audience:

1. **Read the positioning note** — `docs/positioning.md`
2. **Review the support matrix** — `docs/support_matrix.md`
3. **Explore the agent review workflow** — `docs/agent_review_workflow.md`
4. **Read the public FAQ** — `docs/public_faq.md`
5. **Check the public alpha criteria** — `docs/public_alpha_criteria.md`
6. **Run your own evaluation** using the evidence pack templates

---

## Demo checklist (for presenters)

- [ ] `python -m lynkmesh doctor` returns `ready`
- [ ] Tests pass: `python -m pytest test/semantic/contracts test/unit/cli -q`
- [ ] `report` produces valid JSON with `status: "ok"`
- [ ] `pack` produces valid JSON with `status: "ok"` for each profile
- [ ] `benchmark` produces valid JSON with `status: "ok"` and dual baselines
- [ ] All artifacts have `contains_llm_inference: false`
- [ ] Presenter states: "This is an early alpha research preview"
- [ ] Presenter does not overclaim
- [ ] Presenter can point to the evidence pack for further exploration
