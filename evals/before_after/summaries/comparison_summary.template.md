# Comparison Summary — Before vs After (Template)

> Copy this file per comparison. It summarizes one matched pair of runs
> (`before_without_lynkmesh` + `after_with_lynkmesh`). **Evaluation baseline, not
> benchmark proof.** Keep public-safe: no private paths, no private project names.

## Identity

- **Scenario ID:** `architecture_impact_baseline`
- **Run ID (shared):** `<fill-in>`
- **Date (ISO 8601):** `<fill-in>`
- **Reviewer:** `<initials/role>`
- **AI model / version (same in both arms):** `<fill-in>`
- **Target project (sanitized category):** `<fill-in>`
- **LynkMesh version (after arm):** `<fill-in>`

## Method note

Same model, same tasks, same reviewer. The only intended difference is the
presence of LynkMesh deterministic evidence in the "after" arm. Any other
difference is recorded under Deviations.

## Side-by-side metrics

| Metric | Before (no LynkMesh) | After (with LynkMesh) |
| --- | --- | --- |
| Manual context-prep time (min) | `<fill>` | `<fill>` |
| Files opened manually | `<fill>` | `<fill>` |
| Context tokens supplied | `<fill>` | `<fill>` |
| Time to first useful answer (s) | `<fill>` | `<fill>` |
| Iterations to answer | `<fill>` | `<fill>` |
| Claims made | `<fill>` | `<fill>` |
| Claims supported by evidence | `<fill>` | `<fill>` |
| Unsupported claims | `<fill>` | `<fill>` |
| Architecture findings correct / total | `<fill>` | `<fill>` |

## Observations (factual, no overclaiming)

- `<what changed between arms, stated as observations of this run only>`

## Interpretation (conservative)

- State only what this single run supports. Permitted framing:
  > In this run, LynkMesh deterministic evidence appeared to reduce manual
  > context preparation and/or improve grounding for the scenario tasks.
- Do **not** write that LynkMesh made the model smarter, proved anything, or is
  production-ready.
- Remember impact results are deterministic **candidates**, not validated
  runtime truth.

## Threats to validity

- Single project, single model version, single reviewer — not generalizable.
- Possible reviewer bias; correctness depends on the answer key quality.
- Static analysis can be incomplete (dynamic dispatch, framework magic, runtime
  behavior not fully modeled).
- Token figures are deterministic heuristics, not tokenizer-exact counts.

## Disclaimers

- Evaluation baseline, not benchmark proof.
- The claim under evaluation is narrow and conditional: LynkMesh **may** reduce
  manual context preparation and improve grounding **in selected workflows,
  subject to evaluation**.
- Publish scope and limitations alongside any shared result.
