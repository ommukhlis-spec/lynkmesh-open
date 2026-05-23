# LynkMesh Public Release Notes — v0.1

> **Release status: early validation / research preview.** LynkMesh is not
> production-ready. Expect breaking changes.

## What LynkMesh is

LynkMesh is a deterministic context protocol for AI-assisted code understanding.
Instead of feeding an AI agent raw files or relying on probabilistic retrieval,
LynkMesh turns a codebase into a structured, evidence-linked, reproducible
context layer that an agent can reason over safely. The semantic contracts that
make up the protocol perform no LLM inference — interpretation is left to the
consuming agent, under explicit guardrails.

## What is included in this release

- **Graph serialization / graph payload foundation** — a deterministic
  serialized snapshot of the semantic code graph.
- **MeshContext Report** — a deterministic, machine-readable projection of the
  latest successful build (facts and candidates only; no inference).
- **MeshContext AI Context Pack** — a compact, token-conscious, evidence-linked
  projection of the report, in `compact`, `balanced`, and `expanded` profiles.
- **Token Benchmark with `source_baselines`** — deterministic token measurement
  calibrated against two baselines (`mesh_context_report` and
  `serialized_graph_payload`) so reduction is never read from a single source.
- **Structural Validation** — a semantic contract that checks consistency across
  the payload → report → AI pack → benchmark chain and asserts the privacy and
  determinism guarantees.
- **Open-core safety export pipeline** — a curated, allow-listed export with an
  automated privacy/safety scan over the generated public output.

## What is not included / current limitations

- **Not production-ready.** This is an early-validation research preview.
- **Not benchmark proof yet.** A passing run demonstrates the protocol works
  end-to-end deterministically; it is not a published performance benchmark.
- **No aggregate `risk_score` yet.** Risk is surfaced only as deterministic
  candidates.
- **No LLM inference inside the semantic contracts.** Every contract carries
  `contains_llm_inference = false`.
- **Token estimates are deterministic heuristics**, not tokenizer-exact counts
  and not model-specific billing figures.
- **Language/runtime coverage is still evolving.** PHP is partial / early alpha;
  framework magic and runtime behavior are not fully modeled; other languages
  fall back to structural-only results.

## Validation snapshot

The most recent recorded validation for this release candidate:

- Semantic contract tests: pass.
- MCP / internal validation suite: pass.
- Open-core dry-run safety scan: clean (warnings expected at the documented
  baseline; safety errors: 0).
- Open-core release-candidate smoke: passed.

## Dogfooding note

LynkMesh uses its own deterministic context outputs as evidence for release
documentation, with human review. The figures below come from running LynkMesh
on its own repository through the validated MCP capabilities; they are
deterministic facts, not LLM interpretation, and not a performance claim.

Sanitized self-analysis snapshot (illustrative, single run):

- capabilities: `feature_stage` 4.4.1; MeshContext Report, AI Context Pack, and
  Token Benchmark all enabled; token benchmark calibrated; AI pack privacy-safe;
  structural validation available.
- MeshContext Report status: ok; `node_count` 26; `edge_count` 53.
- AI Context Pack (compact) status: ok.
- Token Benchmark status: ok; `benchmark_source_kind`: `mesh_context_report`;
  `source_baselines`: `mesh_context_report`, `serialized_graph_payload`;
  calibration notes: 4.
- `guardrails.contains_llm_inference`: false across report, AI pack, and token
  benchmark.

These values describe the output shape on one small run; they are not a public
benchmark or a guarantee.

## Privacy guarantees

- No `mesh_context_report.json` is written by default.
- No private absolute paths or private project names are exposed in the
  protocol outputs.
- `contains_llm_inference = false` across all semantic contracts.
- The token benchmark embeds derived metrics only, never raw payloads.

## Related documentation

- [The LynkMesh Protocol](lynkmesh_protocol.md)
- [Quickstart](quickstart.md)
- [Case study template](case_study_template.md)
- [MeshContext MCP release notes (v4.4.1)](mcp_mesh_context_release_notes_v4.4.1.md)
- [GitHub public profile draft](github_public_profile.md)
