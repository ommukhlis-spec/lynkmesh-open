# Comparison Summary — mini_auth_shop_php_001

> **Evidence run, not public benchmark proof.** The deterministic LynkMesh
> artifacts and a qualitative Claude before/after capture have now been
> generated and committed. The quantitative side-by-side metrics below
> (timing, tokens supplied, claim counts, correctness scoring) remain
> `pending_manual_capture` and must not be estimated. No values are fabricated.

## Identity

- **Scenario ID:** `architecture_impact_baseline`
- **Run ID (shared):** `mini_auth_shop_php_001`
- **Target (sanitized):** Synthetic PHP MVC auth+shop fixture
- **AI model / version (same in both arms):** `pending_manual_capture`
- **LynkMesh version (after arm):** `pending_manual_capture`

## Status of inputs

| Input | Status |
| --- | --- |
| MeshContext Report artifact | captured (`artifacts/report_output.json`) |
| AI Context Pack artifact | captured (`artifacts/pack_output.json`, `artifacts/pack_expanded_output.json`) |
| Token Benchmark artifact | captured (`artifacts/benchmark_output.json`, `artifacts/benchmark_all_profiles_output.json`) |
| BEFORE AI transcript | captured (`transcripts/before/`) |
| AFTER AI transcript | captured (`transcripts/after/`) |

## Side-by-side metrics (measured vs pending)

| Metric | Before (no LynkMesh) | After (with LynkMesh) |
| --- | --- | --- |
| Manual context-prep time (min) | pending_manual_capture | pending_manual_capture |
| Files opened manually | pending_manual_capture | pending_manual_capture |
| Context tokens supplied | pending_manual_capture | pending_manual_capture |
| Time to first useful answer (s) | pending_manual_capture | pending_manual_capture |
| Iterations to answer | pending_manual_capture | pending_manual_capture |
| Claims made | pending_manual_capture | pending_manual_capture |
| Claims supported by evidence | pending_manual_capture | pending_manual_capture |
| Unsupported claims | pending_manual_capture | pending_manual_capture |
| Architecture findings correct / total | pending_manual_capture | pending_manual_capture |

No measured values are available for these quantitative cells yet. Do not
populate this table with estimates. Deterministic artifact facts that *have*
been measured are reported in the dedicated sections below.

## Observations

- `pending_manual_capture` — fill only with observations of the actual run.

## Interpretation (conservative)

- This run is currently a **scaffold**. It establishes the target, the exact
  prompt, the manual-context plan, and where deterministic artifacts will be
  attached. It is not evidence of any outcome yet.
- When completed, permitted framing is limited to: in this single run, LynkMesh
  deterministic evidence *appeared to* reduce manual context preparation and/or
  improve grounding for the scenario tasks — subject to evaluation. No claim that
  the model became smarter; no benchmark proof; not production-ready.

## Threats to validity

- Single synthetic fixture, single model version, single reviewer — not
  generalizable.
- Static analysis can be incomplete (dynamic dispatch, framework magic, runtime
  behavior not fully modeled). Impact results are candidates, not validated
  blast radius.
- Token figures are deterministic heuristics, not tokenizer-exact counts.

## Disclaimers

- Evaluation baseline, not benchmark proof.
- `is_benchmark_proof: false` in the metric files.

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

Still pending manual capture:
- BEFORE AI transcript
- AFTER AI transcript
- screenshots
- human correctness scoring
- unsupported-assumption count from actual model answers

Conservative interpretation: this run now has deterministic LynkMesh evidence available for the AFTER arm, including PHP language metadata and entrypoint candidates. Model behavior and visual before/after evidence remain pending.
<!-- STAGE_4_7_0C_ARTIFACT_SUMMARY_END -->

<!-- STAGE_4_7_0D_MANUAL_CAPTURE_SUMMARY_START -->
## Stage 4.7.0D/E — Manual Claude before/after capture summary

This section summarizes the manual Claude Haiku 4.5 before/after capture. It is **not benchmark proof** and should not be presented as evidence that LynkMesh makes an AI inherently smarter.

| Dimension | BEFORE: raw files only | AFTER: LynkMesh artifacts only |
|---|---|---|
| Model setup | Claude Haiku 4.5, fresh chat | Claude Haiku 4.5, fresh chat |
| Input material | Uploaded raw fixture zip | `report_output.json`, `pack_expanded_output.json`, `benchmark_all_profiles_output.json` |
| Raw source availability | Yes | No |
| LynkMesh artifact availability | No | Yes |
| Evidence mode | Manual source inspection and line-level citations | Deterministic graph artifacts and evidence IDs |
| Observed output | Detailed semantic analysis with named components such as AuthService/AuthController/ProductRepository | Graph-level reasoning using entrypoints, node/edge evidence, centrality, and uncertainty boundaries |
| Artifact facts available | Not applicable | 61 evidence nodes, 99 evidence edges, 2 entrypoint candidates, no LLM inference |
| Strength | High semantic readability because raw source was provided | No raw source required; deterministic evidence and guardrails available |
| Limitation | Requires uploading or exposing raw source files to the model | Node/edge labels are still UUID-heavy/unknown, so semantic component names are not safely recoverable from artifacts alone yet |
| Safe interpretation | Baseline manual analysis from raw code | Grounded graph reasoning from sanitized LynkMesh evidence |
| Unsafe interpretation to avoid | N/A | Do not claim runtime truth, complete impact analysis, or that LynkMesh makes the model smarter |

### Conservative conclusion

The current evidence supports a narrow claim: **LynkMesh can provide deterministic, sanitized graph artifacts that let an AI reason about project structure without raw source files, while keeping uncertainty visible.**

It does **not** prove benchmark superiority, production readiness, full semantic understanding, or complete impact analysis. The next evidence-improving step is **Stage 4.7.0F — Human-readable node/edge labels for the evidence index**, so artifact-only analysis can safely refer to semantic component names rather than UUID-heavy graph records.

> **Historical note.** The "UUID-heavy / unknown labels" limitation recorded in
> this Stage 4.7.0D/E capture was a point-in-time observation. It was
> superseded by the Stage 4.7.0F update (see the section below), which exposes
> deterministic, sanitized, human-readable node/edge labels. This section is
> retained unchanged as a record of the original capture.
<!-- STAGE_4_7_0D_MANUAL_CAPTURE_SUMMARY_END -->

## Stage 4.7.0F Update — Readable Expanded Evidence Index

After the initial manual before/after capture, the expanded AI Context Pack evidence index was improved to expose deterministic, human-readable graph metadata while preserving the original safety constraints.

This update does not change the evaluation framing:

- It does not introduce LLM inference.
- It does not expose raw source code.
- It does not expose private absolute paths.
- It does not claim runtime truth.
- It does not convert this fixture-level comparison into benchmark proof.

What changed:

- Expanded evidence nodes now expose readable deterministic labels where graph metadata is available.
- File evidence now uses safe relative paths such as `app/Services/AuthService.php`.
- Class and method evidence now exposes labels such as `App\\Services\\AuthService` and `App\\Services\\AuthService::attempt`.
- Edge evidence can include readable `source_label` and `target_label` values derived from node evidence, not guessed.
- `defined_in` edge targets now point to stable file evidence IDs such as `node:file:app/Http/Controllers/AuthController.php`.

Validated artifact facts after regeneration:

- `pack_expanded_output.json` remains valid JSON.
- `evidence_index.nodes`: 61
- `evidence_index.edges`: 99
- `guardrails.contains_llm_inference`: false
- Important component labels are present, including:
  - `AuthService`
  - `AuthController`
  - `AccountController`
  - `AuthMiddleware`
  - `UserRepository`
  - `SessionService`
  - `AuditLogService`
  - `ProductController`
  - `ProductRepository`
  - `PricingService`
- Safe relative paths are present, including:
  - `app/Services/AuthService.php`
  - `app/Http/Controllers/AuthController.php`
- Privacy scan terms returned no hits for private machine paths or internal-only project terms.

Interpretation:

The original AFTER capture showed that Claude could reason from deterministic graph evidence without raw source files, but semantic interpretation was limited by UUID-heavy node and edge labels.

Stage 4.7.0F improves that evidence readability. A future AFTER evaluator should be able to ground more of its reasoning in deterministic component names and relative file paths, while still operating without raw source files.

This remains conservative fixture-level evidence. It should be described as improved deterministic artifact readability, not as proof that LynkMesh makes an AI smarter or as production-grade benchmark evidence.
