# LynkMesh Public FAQ

> **Status: early alpha / research preview.** Answers reflect the current
> state of the project and may evolve as LynkMesh matures.

---

## What is LynkMesh?

LynkMesh is a local-first semantic context layer for AI agents working on
software projects. It turns codebases into graph-backed, inspectable context
artifacts that AI coding agents can use as deterministic evidence before
modifying, reviewing, or explaining software changes.

Think of it as: a structured, auditable map of the codebase that an AI agent
can read before it starts reasoning, rather than relying on raw file searches
or guessing from partial context.

---

## Is LynkMesh like Sourcegraph?

No. Sourcegraph is primarily a code search and navigation platform. LynkMesh
is a deterministic context infrastructure layer designed for AI agent
consumption.

Key differences:

- LynkMesh builds a **semantic graph** with explicit relationships,
  confidence levels, and provenance — not just a searchable index.
- LynkMesh produces **AI-oriented context packs** designed for token-aware
  consumption by coding agents.
- LynkMesh is **local-first** by default; Sourcegraph is typically a hosted
  or self-hosted server.
- LynkMesh does not provide a code search UI or browser-based navigation.

LynkMesh and Sourcegraph could be complementary: LynkMesh could provide
graph-backed context while Sourcegraph provides interactive search.

---

## Is LynkMesh a vector database?

No. LynkMesh does not use vector embeddings for retrieval. It builds an
explicit, deterministic semantic graph from static analysis.

Vector databases are useful for semantic similarity search. LynkMesh is
designed for deterministic, auditable code structure analysis. The two
approaches can be complementary, but LynkMesh is not a replacement for or
competitor to vector databases.

---

## Does LynkMesh make AI smarter?

No. LynkMesh does not change the AI model, improve its reasoning, or increase
its capabilities. The AI model is the same with or without LynkMesh.

What LynkMesh does is provide **better evidence** for the model to reason
from. Instead of the model guessing about project structure from raw files,
it receives a structured, deterministic map. This may improve the quality of
the model's output in code understanding tasks, but the model itself is
unchanged.

We do not claim LynkMesh makes an AI model smarter, and we do not present
benchmark proof of AI improvement.

---

## Is LynkMesh production-ready?

No. LynkMesh is currently **early alpha**. It is suitable for research,
experimentation, and internal development. It is not suitable for production
CI enforcement, enterprise dependency governance, or any workflow where
incorrect output would have significant consequences.

See [public alpha criteria](public_alpha_criteria.md) for what needs to
happen before LynkMesh reaches public alpha / developer preview.

---

## What languages are supported?

PHP is the only language with partial semantic support in the current public
release. The PHP parser bridge provides namespace resolution, class/method
detection, use-statement resolution, and basic dependency graph construction.

Other languages fall back to structural-only results (file inventory) without
semantic analysis. See the [support matrix](support_matrix.md) for details.

Framework support (Laravel, Symfony, etc.) is experimental or not yet
supported.

---

## Why not just use a 1M token context window?

Large context windows are powerful, but they don't solve every problem:

- **Structure matters more than volume.** Dumping 500 files into a context
  window gives the model raw text, not structured relationships. The model
  still has to infer which files are related, which classes depend on each
  other, and what the architecture looks like.
- **Determinism and auditability.** A 1M token dump from raw files is
  different every time the file set changes. LynkMesh produces a
  deterministic, versioned artifact that can be compared, reviewed, and
  tested.
- **Token efficiency.** LynkMesh's compact profile provides structured
  context in far fewer tokens than raw file dumps, leaving more room for the
  actual task.
- **Privacy.** LynkMesh context packs are designed to expose structural
  metadata without including raw source code by default.

Large context windows and LynkMesh are complementary — LynkMesh provides the
structured map; the context window provides the space to use it.

---

## How does LynkMesh relate to Claude, Cursor, Copilot, and coding agents?

LynkMesh is not a competitor to these tools. It is a context infrastructure
layer that these tools or their users could potentially consume.

- **Claude, Copilot, Cursor** — AI coding assistants that generate, review,
  and explain code. LynkMesh could provide them with structured project
  context to improve their output.
- **MCP (Model Context Protocol)** — LynkMesh exposes its capabilities via
  MCP so that MCP-compatible AI clients can request context artifacts
  programmatically.

LynkMesh sits below the AI reasoning layer, providing evidence. AI agents sit
above it, consuming that evidence.

---

## What does "local-first" mean?

Local-first means:

- LynkMesh runs on your machine, not on a remote server.
- Your source code is not uploaded to any hosted service.
- The graph is built from your local filesystem.
- MCP communication happens over local stdio (standard input/output).
- No network access is required for core operations (`doctor`, `report`,
  `pack`, `benchmark`).

This is a deliberate design choice for privacy, determinism, and
independence. Future hosted options (if any) will be opt-in and separately
documented.

---

## What is the open-core model here?

LynkMesh is developed as an **open-core** project:

- The **Community Edition** (this repository) is open-source under Apache
  2.0. It includes the core graph engine, ingestion pipeline, parser
  orchestration, semantic contracts, and the public CLI and MCP foundations.
- **Pro / private runtime** capabilities (incremental diff engine,
  persistent graph cache, large-repo optimization, hosted MCP, team graph
  memory, etc.) may be developed separately and distributed under different
  terms.

The goal is to keep the public core useful for individual developers and AI
agent experimentation while preserving room for sustainable commercial
development.

See the [README](../README.md#open-core-model) for more detail.

---

## What is the current maturity level?

LynkMesh is **early alpha**. This means:

- Public APIs are evolving and may break without notice.
- The CLI and MCP interfaces are functional but not stable.
- Language support is limited to PHP (partial).
- The evidence pack is an evaluation baseline, not benchmark proof.
- The project is suitable for research, experimentation, and feedback.

The next milestone is **public alpha / developer preview**. See
[public alpha criteria](public_alpha_criteria.md) for the specific criteria
required.

---

## Does LynkMesh replace human code review?

No. LynkMesh provides evidence that can help both AI and human reviewers, but
it does not replace human judgment, domain knowledge, or responsibility for
code quality.

The intended use is: LynkMesh gives the reviewer (human or AI) a structured
map of the codebase. The reviewer uses that map to ground their analysis. The
final decision always rests with a human.

---

## Can LynkMesh analyze my private codebase?

Yes — that's the point. LynkMesh is designed to run locally on your machine.
Your source code never leaves your machine unless you choose to share the
generated artifacts.

Be aware that generated artifacts (`report`, `pack`, `benchmark`) may
contain project names, symbol names, and structural metadata derived from
your code. Review them before sharing publicly.

---

## Does LynkMesh run in CI/CD?

Not yet. LynkMesh is designed for local interactive use in its current form.
CI/CD integration would require stabilized CLI contracts, deterministic
golden-file testing, and platform-independent verification — all of which are
on the roadmap but not yet available.

---

## How can I contribute?

LynkMesh is early, and contributions are welcome. Good areas:

- **Documentation** — improving or adding docs, fixing errors, improving
  clarity.
- **Tests** — adding tests for public modules, improving coverage.
- **Parser fixtures** — providing example PHP projects for testing.
- **Feedback** — reporting bugs, suggesting improvements, sharing your
  experience.

Before making larger architectural changes, please open an issue or
discussion first. The architecture is still evolving.

---

## Where can I report issues or ask questions?

Open an issue on the GitHub repository:
[https://github.com/ommukhlis-spec/lynkmesh/issues](https://github.com/ommukhlis-spec/lynkmesh/issues)

---

## Is there a roadmap?

Yes. The [README](../README.md#roadmap) describes five stages:

1. Semantic Foundation
2. Deterministic Graph Core
3. MCP + Query Layer
4. Context Compiler
5. Advanced Runtime (private/commercial)

The public release is currently focused on Stages 1–3.

---

## Can I use LynkMesh commercially?

The Community Edition is intended to be released under the Apache License
2.0, which permits commercial use. However, the project is early alpha and
not production-ready. Confirm the current license file in the repository
before using LynkMesh in any commercial context.

---

## How is LynkMesh different from static analysis tools (Psalm, PHPStan)?

Static analysis tools like Psalm and PHPStan focus on finding bugs, type
errors, and code quality issues in PHP code. They are developer-facing tools
for improving code correctness.

LynkMesh is different:

- It builds a **semantic graph** of the codebase rather than reporting
  individual issues.
- Its output is designed for **AI agent consumption**, not developer
  notification.
- It includes **confidence semantics**, **provenance tracking**, and
  **privacy-aware output packaging**.
- It is **language-layered** — the graph engine is language-agnostic; the
  PHP parser is one language-specific ingestion layer.

LynkMesh could potentially consume output from tools like Psalm or PHPStan
as additional evidence sources in the future.

---

## How can I verify LynkMesh's claims?

Run the deterministic workflow yourself:

1. Clone the repository.
2. Set `PYTHONHASHSEED=0`.
3. Run `python -m lynkmesh doctor`.
4. Run the included tests.
5. Generate artifacts from the included synthetic fixture.
6. Inspect the outputs.

Everything LynkMesh produces is deterministic and inspectable. You don't
have to trust us — you can verify the outputs directly.

See [Try in 5 Minutes](try_in_5_minutes.md) for the quickest path.
