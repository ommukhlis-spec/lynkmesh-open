# Screenshots — mini_auth_shop_php_001

> Capture guidance for this specific run. Follow the shared rules in
> `../../../screenshots/README.md`. Evaluation baseline only, **not** benchmark
> proof. Status: captured — the reviewed before/after screenshots
> (`01_before_raw_files_uploaded.png` … `05_after_uncertainty_guardrails.png`)
> are committed in this directory. The guidance below documents how they were
> captured and the public-safety checks applied before committing.

## What was captured (and how to reproduce)

1. `python -m lynkmesh doctor` output (research-preview banner; crop any path).
2. The artifact-generation commands producing `report_output.json` /
   `pack_output.json` / `benchmark_output.json` for the fixture.
3. The BEFORE answer and the AFTER answer for the same task, side by side.
4. Where the AFTER answer cites deterministic evidence vs. the BEFORE answer's
   manual context.

## Public-safety checklist (applied before committing)

- [x] No private absolute paths (the fixture path is shown as a relative repo
      path; any user home directory is cropped).
- [x] No private project names (the target is a synthetic fixture — named as
      "synthetic PHP MVC auth+shop fixture").
- [x] No secrets/credentials.
- [x] Captions use the conservative wording (research preview, single run, not
      benchmark proof, not production-ready).

## Storage

- Saved with the Run ID prefix, e.g. `01_before_raw_files_uploaded.png`.
- The screenshots for this run were committed only after the run was executed
  and the public-safety checklist above was reviewed.
