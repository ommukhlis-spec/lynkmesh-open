# LynkMesh Case Study Template

> A reusable, public-safe format for documenting analysis examples.
>
> **Rules for using this template:**
> - Never use real private project names. Sanitize to a category, e.g.
>   "Legacy PHP administrative system".
> - Never include raw or absolute local paths. Use placeholders like
>   `<PATH_TO_PROJECT>`.
> - Report deterministic facts only. Do not present LLM interpretation as a
>   LynkMesh output.
> - Label any concrete numbers as a sanitized example, not as a published
>   benchmark claim.

---

## 1. Project type

A short, sanitized description of the system category. Avoid the real name.

> _Example:_ Legacy PHP administrative system (single-module slice).

## 2. Language / ecosystem

Primary language and any relevant framework context, with honest coverage notes.

> _Example:_ PHP (partial / early-alpha semantic support). Framework magic and
> runtime behavior are not fully modeled.

## 3. Graph facts

Deterministic counts and breakdowns taken directly from the MeshContext Report
(`graph_facts`). These are facts, not conclusions.

> _Sanitized example values (illustrative only — not a benchmark claim):_
>
> - node_count: 26
> - edge_count: 53
> - node_type_breakdown: file 1, class 1, method 11, function 0, external 13
> - edge_type_breakdown: calls_confirmed 11, calls_external 19, contains 11,
>   defined_in 12

## 4. Architectural signals

Deterministic candidates surfaced by the report and AI pack — entrypoint
candidates, dominant component types, dependency/layer candidates, cycles
detected. Note that these are candidates, not validated conclusions, and that an
empty set is a valid, honest result for a small slice.

> _Sanitized example:_ dominant components by count — external (13), method (11),
> class (1), file (1); entrypoint/hotspot/risk candidates: none surfaced for this
> slice; cycles detected: 0.

## 5. MeshContext summary

The report's status and provenance highlights.

> _Sanitized example:_ report status `ok`; schema `0.1.0`;
> `is_deterministic: true`; `contains_llm_inference: false`.

## 6. AI Context Pack summary

The pack profile used, its status, and guardrails.

> _Sanitized example:_ profile `compact`; AI pack status `ok`; schema
> `mesh_context_ai_pack.v0.1`; guardrails `contains_llm_inference: false`,
> `deterministic_facts_only: true`, `must_cite_evidence_ids: true`.

## 7. Token benchmark summary

The benchmark status, source kind, baselines, and reduction figures — always
with both baselines so the comparison stays honest.

> _Sanitized example (illustrative, deterministic-heuristic, not tokenizer-exact):_
>
> - token benchmark status: ok
> - benchmark_source_kind: mesh_context_report
> - source_baselines: mesh_context_report, serialized_graph_payload
> - reduction vs `mesh_context_report` baseline: small / slightly negative
>   (expected — the report is already a minimal projection)
> - reduction vs `serialized_graph_payload` baseline: large (the fair raw graph
>   compression comparison)
> - hotspot / risk retention: 100%

## 8. Limitations

State what this example does and does not demonstrate.

> _Example:_ early validation only; not a performance benchmark; no aggregate
> `risk_score`; PHP partial support; token estimates are deterministic heuristics,
> not tokenizer-exact counts; call-graph resolution is heuristic for dynamic
> dispatch.

## 9. Privacy notes

Confirm the privacy guarantees held for this example.

> _Example:_ no `mesh_context_report.json` written by default; no private
> absolute paths or private project names exposed; `contains_llm_inference: false`
> across report, AI pack, and token benchmark; benchmark embeds derived metrics
> only, not raw payloads.

---

> The example values above are a single sanitized illustration of the output
> shape. They are not a public benchmark, a performance guarantee, or a claim of
> production readiness.

## Related documentation

- [The LynkMesh Protocol](lynkmesh_protocol.md)
- [Quickstart](quickstart.md)
- [MeshContext MCP release notes (v4.4.1)](mcp_mesh_context_release_notes_v4.4.1.md)
