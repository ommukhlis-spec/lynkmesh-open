# Screenshot Capture Guidelines

> For before/after **evaluation** visuals only. Screenshots illustrate a recorded
> run; they are **not** benchmark proof and must not be presented as one.

## Principles

- A screenshot must correspond to a recorded run (a filled `runs/` file and its
  metrics JSON). Never publish a visual without the run behind it.
- Pair visuals: a `before_without_lynkmesh` shot and the matching
  `after_with_lynkmesh` shot, same model, task, and reviewer.
- Caption honestly: state that this is an evaluation baseline, single run, not
  generalizable, not benchmark proof.

## Public-safety checklist (before sharing any screenshot)

- [ ] No private absolute paths (e.g. user home directories). Crop or redact.
- [ ] No private project names. Use a sanitized category label.
- [ ] No secrets, tokens, credentials, `.env` contents, or customer data.
- [ ] No internal-only tool names or private infrastructure references.
- [ ] Generated JSON shown is from a public-safe project, or is redacted.
- [ ] The caption includes the conservative positioning wording.

## What to capture

1. **Setup / environment:** `python -m lynkmesh doctor` output (shows research
   preview + environment), with any private path cropped.
2. **Evidence generation (after arm):** the CLI commands producing `report.json`
   / `ai-pack.json` / `benchmark.json`, with `<PATH_TO_PROJECT>` redacted.
3. **Task answers:** the agent's answer in each arm for the same task, side by
   side where possible.
4. **Grounding:** where the `after` answer cites deterministic evidence vs. the
   `before` answer's manual context.

## Recommended caption template

> Evaluation baseline (single run): `architecture_impact_baseline`. Same model
> and task in both arms; the only intended difference is LynkMesh deterministic
> evidence in the "after" arm. Research preview / early validation — not
> production-ready, not benchmark proof. Results reflect one project, model
> version, and reviewer and do not generalize.

## Storage

- Do not commit screenshots derived from private projects.
- If committing public-safe visuals, keep filenames descriptive and tied to the
  Run ID, e.g. `2026-01-15-run-01_before_task1.png`.
