# AI-Assisted Code Review with Graph-Backed Context

> **Status: target use case description.** This document describes the
> intended use case for LynkMesh in AI-assisted code review workflows. The
> underlying capabilities are early alpha. This workflow is a design target,
> not a claim of current completeness.

## Purpose

This document explains how LynkMesh is designed to support AI-assisted code
review by providing graph-backed, deterministic context evidence. It covers
the rationale, a target workflow, a reviewer checklist, and guidance on safe
MR/PR comment structure.

LynkMesh does not replace human review. It helps AI and human reviewers
ground their analysis in deterministic project context.

---

## Why AI code review needs project context

AI coding agents can review code changes, but they face the same challenge
human reviewers do: understanding the impact of a change requires knowing how
the changed code fits into the larger system.

Without structured project context, an AI reviewer:

- Sees only the diff — not the dependencies, callers, or architectural role
  of the changed code.
- May miss side effects because it cannot see what depends on the changed
  function.
- May hallucinate relationships that don't exist in the actual codebase.
- Spends tokens reasoning from raw file contents rather than from structured
  facts.

With LynkMesh, an AI reviewer receives:

- A **deterministic map of the project** (nodes, edges, architecture profile)
  before reviewing the diff.
- **Impact evidence** — which symbols, files, or architectural boundaries
  are affected by a change.
- **Confidence metadata** — so the reviewer can distinguish high-confidence
  structural facts from lower-confidence inferences.
- **Token-efficient context** — compact, structured evidence instead of raw
  file dumps.

---

## Target AI reviewer workflow

The following workflow is the design target for LynkMesh-assisted AI code
review. Steps marked with `(*)` depend on capabilities still under
development.

### Phase 1 — Understand the project (once per project)

1. **Generate a MeshContext Report** for the target project.
2. **Generate an AI Context Pack** (compact profile) for quick reference.
3. The AI agent reads the report to understand:
   - Project structure (entrypoints, layers, namespaces)
   - Architecture profile (patterns, boundaries, risks)
   - Dependency graph shape
   - Known limitations and confidence levels

### Phase 2 — Review a change (per MR/PR)

1. **Receive the diff** — the set of changed files and lines.
2. **Query impact** (*) — determine what depends on the changed symbols.
3. **Expand context** (*) — retrieve the semantic neighborhood of the change
   (callers, callees, implementations, interfaces).
4. **Review with evidence** — the AI agent produces a review that:
   - References specific graph facts from LynkMesh
   - Distinguishes deterministic evidence from AI inference
   - Flags risks based on impact analysis, not speculation
   - Suggests specific tests or manual checks where confidence is low

### Phase 3 — Document findings

1. The AI agent writes review comments using the safe comment structure
   below.
2. Each comment cites its evidence source (e.g., "per LynkMesh dependency
   graph, this method is called by 3 controllers").
3. Human reviewer validates or overrides.

---

## Example AI reviewer checklist

When using LynkMesh context to review a code change, the AI agent should
check:

- [ ] **What changed?** — File, class, method, or function modified.
- [ ] **What depends on it?** — Callers, subclasses, interface implementors.
- [ ] **What does it depend on?** — New or changed dependencies introduced by
  the change.
- [ ] **Architectural role** — Is this an entrypoint, a domain service, a
  utility, infrastructure, or middleware?
- [ ] **Architectural boundary crossing** — Does the change cross layers
  (e.g., controller directly calling a repository it shouldn't)?
- [ ] **Risk candidates** — Does the change touch a known hotspot, complex
  method, or frequently-modified file?
- [ ] **Confidence** — What is the confidence level of each finding? Flag
  low-confidence findings for human review.
- [ ] **Missing context** — Are there relationships LynkMesh could not
  resolve? Flag these as review gaps.

---

## Example safe MR/PR comment structure

When posting review comments, use a structure that separates evidence from
interpretation. This helps the human reviewer understand what is fact and
what is the AI's judgment.

### Template

```markdown
**Finding:** [One-sentence summary of the issue or observation]

**Evidence (LynkMesh):**
- [Graph fact, e.g., "This method is called by UserController::login()
  and AdminController::createUser()"]
- [Architecture context, e.g., "This class sits in the Auth domain
  boundary"]
- [Confidence: high / medium / low]

**AI assessment:**
- [The AI's interpretation of the evidence]
- [Suggested action or question for the human reviewer]

**Recommendation:**
- [Specific, actionable step]
- [If confidence is low: "This finding should be validated by a human
  reviewer before acting on it."]
```

### Example

```markdown
**Finding:** `AuthService::validateToken()` now depends on a new
`CacheInterface` implementation, but the existing callers do not inject a
cache dependency.

**Evidence (LynkMesh):**
- `AuthService::validateToken()` is called by `UserController::login()`,
  `AdminController::createUser()`, and `Api\AuthController::refresh()`.
- The new `CacheInterface` typehint was added in this diff; no caller was
  updated to pass a cache instance.
- Architecture confidence: high (all three callers are statically
  resolvable).

**AI assessment:**
- This change introduces a required dependency that existing callers may
  not satisfy. If the service container resolves it automatically (e.g.,
  Laravel auto-injection), this may be fine. If callers manually
  instantiate `AuthService`, this will break at runtime.

**Recommendation:**
- Verify how `AuthService` is instantiated in each caller.
- If manual instantiation: update callers or make the dependency optional.
- Consider adding a test that exercises the token validation path with the
  new cache dependency.
```

---

## What NOT to claim in AI review comments

When writing AI-assisted review comments, do not:

- Claim certainty about runtime behavior based on static analysis alone.
- Present AI interpretation as if it were a LynkMesh graph fact.
- Suggest changes without citing the evidence that supports them.
- Claim that a finding is "proven" or "guaranteed."
- Imply that the AI reviewer replaces human judgment.

Always distinguish:

| This is a LynkMesh fact | This is AI interpretation |
|--------------------------|---------------------------|
| "This method is called by X, Y, Z" | "This change may break X, Y, Z" |
| "This class crosses architectural boundary B" | "This boundary crossing should be reviewed" |
| "Confidence: high (static resolution)" | "I recommend adding a test for this path" |

---

## Current limitations (early alpha)

As of the current release, the following capabilities in this workflow are
limited or not yet available:

- **Impact querying** — impact analysis is available through MCP but has
  limited scope and confidence.
- **Semantic neighborhood expansion** — callers/callees are partially
  resolved; indirect and dynamic calls are not traced.
- **Framework-aware analysis** — automatic dependency injection, service
  containers, and framework magic are not fully modeled.
- **Multi-language review** — only PHP projects receive semantic analysis.
- **Incremental review** — the current workflow requires a full build for
  each review session; incremental diff analysis is planned.

These limitations will be addressed as LynkMesh progresses toward public
alpha.

---

## Related documentation

- [Demo script](demo_script.md) — walk through the basic LynkMesh workflow.
- [Support matrix](support_matrix.md) — current capability levels.
- [Public FAQ](public_faq.md) — common questions about LynkMesh.
- [Positioning note](positioning.md) — what LynkMesh is and is not.
- [Public alpha criteria](public_alpha_criteria.md) — criteria for
  graduation from early alpha.
