# Run — AFTER (with LynkMesh) — mini_auth_shop_php_001

> Evaluation baseline, **not** benchmark proof. The AI transcript for this arm
> has been captured and committed under `transcripts/after/`. Human correctness
> scoring remains `pending_manual_capture`. LynkMesh provides deterministic
> evidence; the AI reasons above that evidence layer.

## Run identity

- **Evaluation mode:** `after_with_lynkmesh`
- **Scenario ID:** `architecture_impact_baseline`
- **Run ID:** `mini_auth_shop_php_001`
- **Target (sanitized):** synthetic PHP MVC auth+shop fixture
- **LynkMesh used:** yes

## Environment

- All fields `pending_manual_capture` (must match the BEFORE arm; also record the
  LynkMesh version from `python -m lynkmesh doctor`).

## Exact evaluation prompt (identical to the BEFORE arm)

> You are analyzing an unfamiliar local PHP project. Using the provided LynkMesh
> deterministic artifacts as grounding evidence, answer:
> 1. Describe the high-level structure: the main components/layers and how they
>    relate.
> 2. Which components depend on the most others, and which are most depended
>    upon?
> 3. If we change the authentication logic, which other components are
>    candidates for review?
> 4. Where is your answer uncertain or unsupported by available evidence?
> Cite the evidence IDs / artifact sections you relied on for each answer.

(The task wording is held constant across arms; only the available evidence
differs.)

## Evidence provided (deterministic LynkMesh artifacts)

Generated from the fixture via the public CLI (see `artifacts/README.md`) and
committed to `artifacts/`:

- `artifacts/report_output.json` — MeshContext Report
- `artifacts/pack_output.json` — AI Context Pack (compact)
- `artifacts/pack_expanded_output.json` — AI Context Pack (expanded; readable
  deterministic evidence index)
- `artifacts/benchmark_output.json` — Token Benchmark (compact)
- `artifacts/benchmark_all_profiles_output.json` — Token Benchmark across the
  compact, balanced, and expanded profiles

These artifacts contain deterministic facts and **candidates** (not validated
runtime truth) and declare `contains_llm_inference: false`.

## AI transcript

Captured and committed under `transcripts/after/`:
`CLAUDE_AFTER_EXPANDED_ARTIFACT_ANALYSIS.md`. It records the model reasoning from
the LynkMesh artifacts only (no raw source files). Not fabricated; not benchmark
proof.

## Reviewer assessment (vs. fixture ground truth)

- Task 1 (architecture): `pending_manual_capture`
- Task 2 (dependencies): `pending_manual_capture`
- Task 3 (impact candidates): `pending_manual_capture`
- Task 4 (uncertainty): `pending_manual_capture`

Ground-truth reference for scoring: `../../fixtures/mini_auth_shop_php/README.md`.

## Honest interpretation

- A favorable AFTER result supports only the narrow, conditional claim that
  LynkMesh **may** reduce manual context preparation and improve grounding **in
  selected workflows, subject to evaluation**. It does not show the model became
  smarter.

## Disclaimers

- Single run; not generalizable. Evaluation baseline, not benchmark proof.

<!-- STAGE_4_7_0C_ARTIFACT_SUMMARY_START -->
## Stage 4.7.0C — Deterministic artifact measurements

These values are derived from committed LynkMesh CLI artifacts only. They are not AI transcript results and are not benchmark proof.

| Measurement | Value |
|---|---|
| Report schema | 0.1.0 |
| Report type | mesh_context_report |
| Project | {"display_name": "mini_auth_shop_php", "languages": {"php": 15}, "primary_language": "php"} |
| Languages | {"mix": {"php": 15}, "primary": "php", "supported": ["php"]} |
| Entrypoints count | 2 |
| Entrypoints | [{"confidence": "HEURISTIC", "evidence": "deterministic_path_candidate", "kind": "php_front_controller", "path": "public/index.php", "reason": "Conventional PHP front controller."}, {"confidence": "HEURISTIC", "evidence": "deterministic_path_candidate", "kind": "php_routes_file", "path": "routes/web.php", "reason": "Conventional PHP web routes file."}] |
| Graph facts | {"confidence_distribution": {"EXACT": 0, "EXTERNAL": 0, "FRAMEWORK": 0, "HEURISTIC": 0, "PROPAGATED": 0, "UNKNOWN": 0}, "edge_count": 99, "edge_type_breakdown": {}, "node_count": 61, "node_type_breakdown": {"class": 12, "external": 0, "file": 15, "function": 0, "method": 34}} |
| Pack profile | compact |
| Pack context budget | {"estimated_input_tokens": 691, "estimated_output_tokens": 0, "estimated_source_report_tokens": 722, "estimated_token_reduction_percent": 4.29, "estimator": "deterministic_char_heuristic_v0.1", "profile": "compact"} |
| Source report chars | 2885 |
| Source report tokens | 722 |
| Best profile by tokens | compact |
| Max token reduction percent | 4.29 |
| contains_llm_inference all false | True |

Captured since this section was first written: the BEFORE and AFTER AI
transcripts and the before/after screenshots are now committed (see
`transcripts/` and `screenshots/`).

Still pending manual capture:
- human correctness scoring
- unsupported-assumption count from actual model answers

Conservative interpretation: this run now has deterministic LynkMesh evidence available for the AFTER arm, including PHP language metadata and entrypoint candidates, plus committed before/after transcripts and screenshots. Quantitative correctness scoring of the model answers remains pending.
<!-- STAGE_4_7_0C_ARTIFACT_SUMMARY_END -->
