# Before/After Evaluation Baseline

> **Status: evaluation baseline, not benchmark proof.**
> This directory defines a *repeatable method* for comparing AI coding workflows
> **without** LynkMesh vs **with** LynkMesh. It does not contain proven results,
> and nothing here should be cited as a benchmark or performance guarantee.

## Purpose

Before publishing any before/after screenshots or comparison claims, we need a
trustworthy, repeatable way to gather evidence. This baseline provides the
scenario definitions, metric schema, run templates, and capture guidelines so
that any evaluation can be reproduced and reviewed by a human.

The intent is honest measurement, not marketing. Filled-in runs are only as
credible as the human who recorded them, the scenario used, and the disclosure
of the environment.

## What LynkMesh is (and is not) in this evaluation

- LynkMesh provides **deterministic, static-analysis-derived project evidence**
  (graph facts, conservative architecture context, AI Context Packs, token
  benchmarks) for an AI agent to consume.
- The **AI reasoning happens above the evidence layer.** LynkMesh does not
  reason, and it does not embed LLM inference into its artifacts.
- **We do not claim LynkMesh makes an AI model smarter.** The model is the same
  in both arms of the evaluation.
- The claim under evaluation is narrow and conditional:
  > LynkMesh **may** reduce manual context preparation and improve grounding in
  > selected workflows, **subject to evaluation**.
  Any published claim must be backed by recorded runs using this baseline and
  must state its scope and limitations.

## Evaluation modes

Each scenario is run in two modes, holding the model, task, and reviewer
constant:

1. **`before_without_lynkmesh`** — the AI agent works from the raw repository
   only (manual file opening, ad-hoc context gathering, no LynkMesh artifacts).
2. **`after_with_lynkmesh`** — the AI agent is additionally given LynkMesh
   deterministic artifacts (MeshContext Report / AI Context Pack / Token
   Benchmark) as grounding evidence.

The only intended difference between the two arms is the presence of the
deterministic evidence layer. Document any other differences explicitly.

## How to run an evaluation (high level)

1. Pick a scenario from `scenarios/`.
2. Choose a **public-safe** target project (see public-safety rules below).
3. Run the `before` arm using `runs/before_without_lynkmesh.template.md`.
4. Run the `after` arm using `runs/after_with_lynkmesh.template.md`. Generate the
   LynkMesh artifacts with the public CLI, e.g.:
   ```bash
   python -m lynkmesh report <PATH_TO_PROJECT> --pretty > report.json
   python -m lynkmesh pack <PATH_TO_PROJECT> --profile compact --pretty > ai-pack.json
   python -m lynkmesh benchmark <PATH_TO_PROJECT> --profile compact --pretty > benchmark.json
   ```
5. Record metrics for each arm against `metrics/before_after_metrics.schema.json`.
6. Summarize with `summaries/comparison_summary.template.md`.
7. Capture screenshots per `screenshots/README.md`.

## Public-safety rules

- **No private absolute paths.** Use placeholders such as `<PATH_TO_PROJECT>`.
- **No private project names.** Sanitize to a category, e.g.
  "Legacy PHP administrative system".
- **No secrets, credentials, tokens, or customer data** in any committed file.
- **Do not commit generated artifacts** (`report.json`, `ai-pack.json`,
  `benchmark.json`) that were produced from a private project. Treat them like
  source-derived data.
- Generated LynkMesh payloads pass an internal privacy safety scan before they
  are printed, but they **may still contain project names, symbols, and
  structural metadata** derived from the analyzed code. Review before sharing.
- Keep all wording conservative and evidence-first (see below).

## Wording rules (avoid overclaiming)

Use: "research preview", "early validation", "evaluation baseline",
"deterministic artifacts", "static-analysis-derived", "may reduce", "in selected
workflows", "subject to evaluation".

Avoid: "production-ready", "guaranteed", "proves", "benchmark proof", "makes the
AI smarter", "fully understands runtime behavior".

## Contents

- `scenarios/` — task definitions to evaluate.
- `runs/` — per-arm run templates (`before` / `after`).
- `metrics/` — JSON Schema for run metrics plus illustrative sample files.
- `summaries/` — comparison summary template.
- `screenshots/` — capture guidelines for before/after visuals.

## Disclaimers

- This baseline produces *evidence to be reviewed by a human*, not automated
  proof.
- Sample metric files in `metrics/` contain **illustrative placeholder values
  only** and are explicitly **not** measured results.
- Results from any single project, model version, or reviewer do not generalize.
  State scope and limitations alongside any published comparison.
