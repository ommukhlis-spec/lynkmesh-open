# The LynkMesh Protocol

> A deterministic context protocol for AI-assisted code understanding.
> Status: early validation / research preview. Not production-ready.

## The problem: the semantic gap

AI coding agents can read source code, but they struggle to understand a
codebase as a connected, evolving system. The common approaches — large context
windows, file chunking, vector search, repeated repository scanning — recover
fragments of a codebase, but they do not give an agent a stable, structured,
trustworthy picture of how the system fits together.

There is a gap between a *raw code graph* (precise but large, noisy, and not
shaped for consumption) and the *context an AI agent actually needs* (compact,
scoped, evidence-linked, and explicit about confidence). LynkMesh exists to
close that gap with a deterministic protocol rather than another layer of
probabilistic retrieval.

## The protocol pipeline

LynkMesh transforms a codebase into AI-ready context through an ordered,
deterministic pipeline. Each stage is a well-defined projection of the previous
one, and no stage performs LLM inference.

```text
serialized graph payload
        ↓
MeshContext Report
        ↓
MeshContext AI Context Pack
        ↓
Token Benchmark
        ↓
Structural Validation
```

**Serialized graph payload.** The full, serialized snapshot of the semantic
graph produced by a build: nodes (files, classes, methods, external symbols),
edges (contains, defined_in, calls_confirmed, calls_external), and breakdowns.
This is the precise but verbose source of truth.

**MeshContext Report.** A deterministic, machine-readable projection of the
latest successful build (schema `0.1.0`). It carries graph facts (node/edge
counts and type breakdowns), deterministic candidates (entrypoints, hotspots,
risk candidates), declared limitations, and provenance. The report is already a
compact distillation of the graph — it contains facts and candidates only, never
inference.

**MeshContext AI Context Pack.** A compact, token-conscious, evidence-linked
projection of the report (schema `mesh_context_ai_pack.v0.1`), available in
`compact`, `balanced`, and `expanded` profiles. It adds an AI task guide,
architecture context, an evidence index, and explicit guardrails so an agent
knows what it may and may not infer.

**Token Benchmark.** A deterministic measurement of the relative size of each AI
pack profile (schema `mesh_context_token_benchmark.v0.1`). It estimates source
tokens, AI pack tokens, reduction percentages, and hotspot/risk retention. It
calibrates against more than one baseline (see below) so reduction is never read
from a single source alone.

**Structural Validation.** A semantic contract that checks consistency across
the whole chain — node/edge counts, node/edge type breakdowns, and the token
benchmark calibration fields — and asserts the privacy and determinism
guarantees. Structural validation exists as a completed semantic contract; it is
not exposed as a separate MCP tool.

## Why deterministic context matters

AI systems can hallucinate. Infrastructure should not. If the layer that feeds
an agent its understanding of a codebase is itself probabilistic, errors compound
silently. A deterministic protocol means:

- the same build of the same code produces the same context, every time;
- every fact an agent receives is traceable to a graph relationship, not to a
  guess;
- confidence is explicit, so heuristic and propagated facts can be down-weighted
  rather than treated as ground truth;
- the context can be validated, benchmarked, and reproduced independently of any
  model.

This is what lets an agent reason *over* the context safely rather than
re-deriving it unreliably on every request.

## Why LynkMesh avoids LLM inference in its semantic contracts

The semantic contracts (Report, AI Pack, Token Benchmark, Structural Validation)
are deliberately free of LLM inference. Every contract carries
`contains_llm_inference = false`. Interpretation — architecture narrative, domain
naming, recommendations, risk communication — is left to the consuming agent,
which is told explicitly what is allowed and what is forbidden (for example, it
must not invent edges, must not treat candidates as confirmed defects, and must
not claim runtime behavior from static facts).

Keeping inference out of the contracts means the substrate stays verifiable: a
contract is a fact projection that can be checked, not an opinion that must be
trusted.

## Privacy model

- **No default file writing.** Retrieving a MeshContext Report, AI Context Pack,
  or Token Benchmark does not write `mesh_context_report.json` or any artifact to
  disk. Output is returned in-process only.
- **No private path leakage.** The contracts expose derived facts, counts,
  breakdowns, and evidence references — not private absolute paths or private
  project names.
- **No LLM interpretation inside contracts.** The deterministic layer never
  embeds model output; `contains_llm_inference = false` everywhere.
- **No raw payload embedding in benchmarks.** The Token Benchmark reports derived
  metrics only; it does not embed raw reports, raw graph payloads, or full AI
  Context Packs.

## Source baselines and honest token claims

Token reduction is only meaningful relative to a chosen baseline, so the Token
Benchmark calibrates against two:

- **`mesh_context_report`** — the MeshContext Report itself. Because the report
  is already a minimal projection, the AI pack can be similar in size or slightly
  larger; a small or negative reduction against this baseline is expected and is
  not a regression.
- **`serialized_graph_payload`** — the serialized graph snapshot. This is the
  fair comparison for raw graph compression, against which the AI pack is
  substantially smaller.

Reporting both baselines keeps the protocol honest: it does not advertise
compression against a target that was already compact.

## Current limitations

LynkMesh is an early-validation research preview, not a finished or
production-ready system.

- **Early validation, not benchmark proof.** Results to date demonstrate that the
  protocol runs end-to-end deterministically; they are not a published
  performance benchmark.
- **No aggregate risk score yet.** The protocol surfaces deterministic risk
  *candidates*; it does not compute a single aggregate `risk_score`.
- **Language and runtime coverage is still evolving.** PHP is partial / early
  alpha; framework magic and runtime behavior are not fully modeled; other
  languages fall back to structural-only results.
- **Token estimates are deterministic heuristics.** They use a stable character
  heuristic for relative comparison; they are not tokenizer-exact counts and are
  not model-specific billing figures.
- **Call-graph resolution is heuristic** for dynamic dispatch and may include
  propagated edges with lower confidence.

## Related documentation

- [Quickstart](quickstart.md)
- [Case study template](case_study_template.md)
- [MeshContext MCP release notes (v4.4.1)](mcp_mesh_context_release_notes_v4.4.1.md)
