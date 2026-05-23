# Evidence Run: mini_auth_shop_php_001

> **Fixture-level evidence run — not public benchmark proof.**
> First before/after evaluation run targeting the committed public-safe fixture.
> The deterministic CLI artifacts, the before/after AI transcripts, and the
> screenshots have been generated and committed to this run directory. Human
> correctness scoring and the quantitative grounding metrics remain
> `pending_manual_capture`. No AI answers or benchmark numbers are fabricated here.

- **Scenario:** `architecture_impact_baseline` (see `../../scenarios/`)
- **Target fixture:** `evals/before_after/fixtures/mini_auth_shop_php`
- **Run ID:** `mini_auth_shop_php_001`
- **Status:** deterministic artifacts, AI transcripts, and screenshots captured
  and committed; human correctness scoring `pending_manual_capture`.

## How the deterministic artifacts were produced

The fixture is a PHP project. The LynkMesh public CLI (`report` / `pack` /
`benchmark`) builds a real graph via the PHP parser bridge, which requires a
`php` executable. The committed artifacts in `artifacts/` were generated on a
host with PHP available; the exact commands to reproduce them are documented in
`artifacts/README.md`.

## Layout

```
mini_auth_shop_php_001/
  README.md                     this file
  artifacts/README.md           how the deterministic CLI artifacts were generated
  artifacts/*.json              committed deterministic CLI artifacts
  before_without_lynkmesh.md    BEFORE arm: prompt + manual context plan
  after_with_lynkmesh.md        AFTER arm: prompt + artifact references
  transcripts/before/           committed BEFORE AI transcripts
  transcripts/after/            committed AFTER AI transcript
  metrics/before_metrics.json   BEFORE metrics (quantitative cells still pending)
  metrics/after_metrics.json    AFTER metrics (quantitative cells still pending)
  comparison_summary.md         conservative summary (measured vs pending separated)
  screenshots/                  committed before/after screenshots + capture guidance
```

## How this run was completed (reproduction)

1. Generated artifacts per `artifacts/README.md` (needs PHP).
2. Ran the BEFORE arm (no LynkMesh) and the AFTER arm (with the artifacts) using
   the same model and prompt; the transcripts are committed under
   `transcripts/before/` and `transcripts/after/`.
3. `metrics/*.json` capture what has been recorded so far; quantitative cells and
   human correctness scoring remain `pending_manual_capture`. `is_benchmark_proof`
   stays `false`.
4. `comparison_summary.md` separates measured deterministic facts from pending
   cells; screenshots are committed under `screenshots/`.

## Disclaimers

- Evaluation baseline, not benchmark proof.
- LynkMesh provides deterministic evidence; AI reasoning happens above the
  evidence layer. No claim that LynkMesh makes the model smarter.

<!-- STAGE_4_7_0C_ARTIFACT_SUMMARY_START -->
## Stage 4.7.0C status

Deterministic CLI artifacts have been generated and parsed. `metrics/after_artifact_measurements.json` contains artifact-derived measurements. The before/after AI transcripts and screenshots have since been captured and committed; human correctness scoring remains `pending_manual_capture`.

<!-- STAGE_4_7_0C_ARTIFACT_SUMMARY_END -->
