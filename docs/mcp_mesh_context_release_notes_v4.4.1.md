# MeshContext MCP Release Notes — Stage 4.4.1

**Stage:** 4.4.1 — MCP/Docs Release Polish
**Type:** Release polish checkpoint (no new core behavior, no new MCP tool)
**Feature stage reported by MCP:** `4.4.1`

This document summarizes the MeshContext MCP surface as of Stage 4.4.1. Stage
4.4.1 does not change runtime graph behavior, parser behavior, report
generation semantics, AI pack schema semantics, token benchmark calculations,
or open-core safety rules. It synchronizes capability metadata and consolidates
documentation for the MeshContext milestone sequence (Stages 4.3.2 → 4.4.0).

## What changed in 4.4.1

- `get_capabilities` and `get_runtime_diagnostics` now report
  `feature_stage = 4.4.1`. The reported stage is sourced from a single
  `FEATURE_STAGE` constant, so capability metadata and runtime diagnostics no
  longer drift apart.
- `get_capabilities` now exposes three additional, descriptive capability
  flags:
  - `mesh_context_token_benchmark_calibrated: true`
  - `mesh_context_ai_pack_privacy_safe: true`
  - `mesh_context_structural_validation_available: true`

No MCP tool was added, removed, or renamed.

## MeshContext Report

The MeshContext Report is a deterministic, privacy-safe projection of the latest
successful graph snapshot. It contains facts and candidates only — node/edge
counts, type breakdowns, language mix, hotspots, and risk candidates derived
directly from the graph. It contains no LLM inference and is not written to disk
by default (no `mesh_context_report.json` is created unless explicitly
requested). It is retrieved via the `get_mesh_context_report` MCP tool.

## MeshContext AI Context Pack

The AI Context Pack is a compact, evidence-linked, AI-ready JSON projection
built from the MeshContext Report. It is intended as a grounding layer for
reasoning interfaces, not as a replacement for the graph. It is available in
three profiles — `compact`, `balanced`, and `expanded` — and carries the
guardrail `guardrails.contains_llm_inference = false`. It is retrieved via the
`get_mesh_context_ai_pack` MCP tool. The pack is privacy-safe: it embeds derived
evidence references, not private paths or raw source.

## Token Benchmark

The Token Benchmark deterministically estimates token sizes and reduction across
the `compact`, `balanced`, and `expanded` AI pack profiles. It estimates source
tokens, AI pack tokens, the token reduction percentage, and the hotspot/risk
retention percentage. Token estimates use a deterministic heuristic for stable
relative comparison — they are not model-specific billing figures. The benchmark
payload contains derived metrics only; it does not embed raw reports, raw graph
payloads, or full AI Context Packs. It is retrieved via the
`get_mesh_context_token_benchmark` MCP tool.

### What `source_baselines` means

Token reduction is only meaningful relative to a chosen baseline. The benchmark
calibrates against more than one source baseline so reduction is never
interpreted from a single minimal source alone:

- **`mesh_context_report`** — the MeshContext Report itself. This is the default
  `benchmark_source_kind`.
- **`serialized_graph_payload`** — the full serialized graph payload.

For each baseline the benchmark reports `baseline_token_reduction_percent` and
`baseline_token_ratio_to_source`, with `calibration_notes` explaining the
interpretation.

#### Why the `mesh_context_report` baseline may show small or negative reduction

The MeshContext Report is already a compact, distilled projection of the graph.
When the AI Context Pack is compared against it, the AI Pack can be similar in
size or even slightly larger — because both are already compact, and the AI Pack
adds evidence links and profile structure. A small or negative reduction against
this baseline is expected and is **not** a regression; it reflects that the
report is already minimal.

#### Why `serialized_graph_payload` is the right raw-compression comparison

The fair comparison for "how much smaller is the AI Pack than the raw graph" is
the serialized graph payload, which represents the unreduced graph. Against this
baseline the AI Pack is substantially smaller, which is the meaningful raw graph
compression figure.

## Structural Validation

Stage 4.4.0 added deterministic structural validation across the chain:

```
serialized graph payload → MeshContext Report → AI Context Pack → Token Benchmark
```

The validator checks consistency of `node_count`, `edge_count`,
`node_type_breakdown`, and `edge_type_breakdown` across the chain, verifies the
token benchmark calibration fields, and asserts the privacy and determinism
guarantees: `guardrails.contains_llm_inference = false`, no private path leakage,
deterministic output, no filesystem I/O, and no runtime graph extraction
performed by the validator itself.

## Privacy guarantees

- **No LLM inference.** Every MeshContext surface carries
  `guardrails.contains_llm_inference = false`. All output is deterministic.
- **No default file writing.** No `mesh_context_report.json` (or any artifact)
  is written to disk unless a write is explicitly requested.
- **No private path leakage.** Output contains derived facts and evidence
  references only — no private absolute paths and no private project names.

## MCP smoke-test flow

1. **Check capabilities** — call `get_capabilities` and confirm
   `feature_stage = 4.4.1`, `mesh_context_report_enabled`,
   `mesh_context_ai_pack_enabled`, `mesh_context_token_benchmark_enabled`,
   `mesh_context_token_benchmark_calibrated`, `mesh_context_ai_pack_privacy_safe`,
   and `mesh_context_structural_validation_available`.
2. **Build graph** — build from the project path (see host path note below).
3. **Get MeshContext Report** — call `get_mesh_context_report`.
4. **Get AI Context Pack** — call `get_mesh_context_ai_pack` (try `compact`,
   `balanced`, `expanded`).
5. **Get Token Benchmark** — call `get_mesh_context_token_benchmark` and review
   `source_baselines` / calibration fields.
6. **Verify privacy** — confirm `guardrails.contains_llm_inference = false` and
   that no private paths appear in any payload.

### Host path note

An MCP client may present a sandbox namespace, but the LynkMesh MCP server runs
on the **local host**. When calling the build tool, pass the **host project path
exactly** as it exists on the machine (e.g. `<PATH_TO_PROJECT>`) — do not pass a
sandbox-namespaced path. Using a sandbox path will cause the build to target a
path that does not exist on the host.
