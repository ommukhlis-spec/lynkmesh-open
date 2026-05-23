# Run Template — BEFORE (without LynkMesh)

> Copy this file for a single evaluation run. Fill in every field honestly.
> This is one arm of an evaluation baseline, **not** benchmark proof.
> Keep all content public-safe: no private absolute paths, no private project
> names, no secrets. Use placeholders such as `<PATH_TO_PROJECT>`.

## Run identity

- **Evaluation mode:** `before_without_lynkmesh`
- **Scenario ID:** `architecture_impact_baseline`
- **Run ID:** `<fill-in, e.g. 2026-01-15-run-01>`
- **Date (ISO 8601):** `<fill-in>`
- **Reviewer:** `<initials or role, not personal data>`

## Environment (disclose fully)

- **OS:** `<e.g. Windows 11>`
- **Python version:** `<e.g. 3.11.x>`
- **AI model / version:** `<e.g. model-name vX>`
- **AI client:** `<e.g. a desktop AI client>`
- **LynkMesh used:** `no` (this is the BEFORE arm)
- **Target project (sanitized category):** `<e.g. Legacy PHP administrative system>`

## Method

The AI agent has access to the raw repository only. It gathers context manually
(opening files, searching) with no LynkMesh artifacts. Ask the scenario tasks
exactly as written, in order. Do not coach beyond the scenario prompts.

## Tasks and answers

For each task, record the agent's answer, the evidence it actually used, and the
reviewer's assessment.

### Task 1 — Architecture overview
- Answer summary: `<fill-in>`
- Evidence the agent used: `<files opened / searches run>`
- Reviewer assessment (correct / partial / incorrect): `<fill-in>`

### Task 2 — Dependency / relationship reading
- Answer summary: `<fill-in>`
- Evidence the agent used: `<fill-in>`
- Reviewer assessment: `<fill-in>`

### Task 3 — Impact analysis (candidate-level)
- Answer summary: `<fill-in>`
- Evidence the agent used: `<fill-in>`
- Reviewer assessment: `<fill-in>`

### Task 4 — Confidence & gaps
- Answer summary: `<fill-in>`
- Reviewer assessment: `<fill-in>`

## Metrics

Fill in `metrics/sample_before_metrics.json` (copy it; do not overwrite the
sample) following `metrics/before_after_metrics.schema.json`. Summary of the key
numbers for quick reference:

- Manual context-prep time (minutes): `<fill-in>`
- Files opened manually: `<fill-in>`
- Claims made / supported by evidence / unsupported: `<fill-in>`
- Architecture findings correct / total: `<fill-in>`
- Time to first useful answer (seconds): `<fill-in>`
- Iterations to answer: `<fill-in>`

## Notes & deviations

- `<record anything that differed from the standard method>`

## Disclaimers

- Single run; not generalizable.
- Reflects this project, model version, and reviewer only.
- Evaluation baseline, not benchmark proof.
