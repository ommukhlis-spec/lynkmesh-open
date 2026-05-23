# Run Template — AFTER (with LynkMesh)

> Copy this file for a single evaluation run. Fill in every field honestly.
> This is one arm of an evaluation baseline, **not** benchmark proof.
> Keep all content public-safe: no private absolute paths, no private project
> names, no secrets. Use placeholders such as `<PATH_TO_PROJECT>`.

## Run identity

- **Evaluation mode:** `after_with_lynkmesh`
- **Scenario ID:** `architecture_impact_baseline`
- **Run ID:** `<fill-in, pair with the matching BEFORE run>`
- **Date (ISO 8601):** `<fill-in>`
- **Reviewer:** `<initials or role, not personal data>`

## Environment (disclose fully)

- **OS:** `<e.g. Windows 11>`
- **Python version:** `<e.g. 3.11.x>`
- **AI model / version:** `<must match the BEFORE arm>`
- **AI client:** `<must match the BEFORE arm>`
- **LynkMesh used:** `yes`
- **LynkMesh version:** `<output of: python -m lynkmesh doctor>`
- **Target project (sanitized category):** `<must match the BEFORE arm>`

## Evidence preparation

Generate the deterministic LynkMesh artifacts with the public CLI (no files are
written by default; redirect explicitly):

```bash
python -m lynkmesh doctor
python -m lynkmesh report <PATH_TO_PROJECT> --pretty > report.json
python -m lynkmesh pack <PATH_TO_PROJECT> --profile compact --pretty > ai-pack.json
python -m lynkmesh benchmark <PATH_TO_PROJECT> --profile compact --pretty > benchmark.json
```

The AI agent is given the raw repository **plus** these artifacts as grounding
evidence. The only intended difference from the BEFORE arm is the presence of
this deterministic evidence layer.

> Do not commit generated artifacts derived from a private project.

## Tasks and answers

Ask the same scenario tasks, in the same order, with the same model. Record the
agent's answer, the evidence it cited (LynkMesh artifact sections and/or files),
and the reviewer's assessment.

### Task 1 — Architecture overview
- Answer summary: `<fill-in>`
- Evidence cited (artifact sections / files): `<fill-in>`
- Reviewer assessment (correct / partial / incorrect): `<fill-in>`

### Task 2 — Dependency / relationship reading
- Answer summary: `<fill-in>`
- Evidence cited: `<fill-in>`
- Reviewer assessment: `<fill-in>`

### Task 3 — Impact analysis (candidate-level)
- Answer summary: `<fill-in>`
- Evidence cited: `<fill-in>`
- Reviewer assessment: `<fill-in>`

### Task 4 — Confidence & gaps
- Answer summary: `<fill-in>`
- Reviewer assessment: `<fill-in>`

## Metrics

Fill in `metrics/sample_after_metrics.json` (copy it; do not overwrite the
sample) following `metrics/before_after_metrics.schema.json`. Quick reference:

- Manual context-prep time (minutes): `<fill-in>`
- Files opened manually: `<fill-in>`
- Claims made / supported by evidence / unsupported: `<fill-in>`
- Architecture findings correct / total: `<fill-in>`
- Time to first useful answer (seconds): `<fill-in>`
- Iterations to answer: `<fill-in>`
- Used deterministic evidence: `yes`

## Honest interpretation

- LynkMesh artifacts are deterministic **candidates and facts**, not validated
  runtime truth. Impact results are *candidates for review*.
- A favorable result supports only the narrow claim that LynkMesh **may** reduce
  manual context preparation and improve grounding **in selected workflows,
  subject to evaluation**. It does not show the model became smarter.

## Notes & deviations

- `<record anything that differed from the standard method>`

## Disclaimers

- Single run; not generalizable.
- Reflects this project, model version, and reviewer only.
- Evaluation baseline, not benchmark proof.
