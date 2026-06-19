# Public Alpha Criteria

> **Current status: early alpha.** LynkMesh should remain described as
> "early alpha" until the criteria in this document are met.

## Purpose

This document defines the criteria required before LynkMesh graduates from
"early alpha" to "public alpha / developer preview."

These criteria are intentionally concrete and verifiable. They exist to
ensure that when LynkMesh is described as a public alpha, users and reviewers
can trust that the project meets a consistent baseline of quality, stability,
and documentation.

---

## Status

None of the criteria below are currently met. LynkMesh is **early alpha**.

The next milestone is:

> **Public Alpha / Developer Preview** — stable local-first AI context
> workflows, repeatable evidence artifacts, and clear integration paths for
> AI coding agents.

---

## Criteria

### 1. CLI stability

- [ ] All public CLI commands (`doctor`, `report`, `pack`, `benchmark`)
  have stable subcommand names, argument names, and flag contracts.
- [ ] Breaking changes to the CLI are announced in a changelog before
  release.
- [ ] CLI help text (`--help`) is complete for every public command.
- [ ] CLI exit codes are documented and stable (0 = success,
  non-zero = error).

### 2. JSON schema / output stability

- [ ] The JSON schema for `report`, `pack`, and `benchmark` outputs is
  versioned (e.g., `schema_version: "1.0.0"`).
- [ ] Schema changes between versions are documented with a migration
  guide or changelog.
- [ ] Breaking schema changes are version-gated and communicated in
  advance.
- [ ] All schema fields have documented meaning, type, and stability
  level.

### 3. Deterministic fixtures

- [ ] At least one public, committed fixture produces byte-identical
  output across platforms (Linux, macOS, Windows) when
  `PYTHONHASHSEED=0` is set.
- [ ] The fixture is small enough to run in under 30 seconds.
- [ ] The expected output for the fixture is checked into the repository
  as a golden file.
- [ ] CI validates that the fixture output matches the golden file.

### 4. Public tests

- [ ] All public unit tests pass on Linux, macOS, and Windows.
- [ ] All public semantic contract tests pass on all three platforms.
- [ ] Test results are documented in the repository (not just CI).
- [ ] At least one platform-specific CI run is publicly visible (e.g.,
  GitHub Actions).
- [ ] Test coverage for public modules is measured and reported.

### 5. Documentation completeness

- [ ] A public-facing README explains what LynkMesh is, what it does,
  and how to try it.
- [ ] A demo script (`docs/demo_script.md`) walks through a complete
  first experience.
- [ ] A support matrix (`docs/support_matrix.md`) honestly describes
  what is supported, experimental, and unsupported.
- [ ] A getting-started guide (`docs/try_in_5_minutes.md`) provides the
  shortest onboarding path.
- [ ] A public FAQ (`docs/public_faq.md`) answers common questions.
- [ ] Public release notes exist for the current version.
- [ ] Known limitations are documented and linked from the README.
- [ ] The open-core model is clearly explained.

### 6. Evidence pack expansion

- [ ] At least one public fixture-level before/after evaluation run is
  committed and documented.
- [ ] The evidence pack README explains how to reproduce the run.
- [ ] The evidence pack includes conservative comparison language (no
  overclaiming).
- [ ] At least one additional scenario is defined beyond the initial
  mini_auth_shop_php fixture.
- [ ] Screenshot capture guidelines are documented and followed for
  committed runs.

### 7. MCP demo repeatability

- [ ] A documented MCP workflow can be completed from scratch by a new
  user in under 15 minutes.
- [ ] All MCP tools return deterministic or documented-variable results.
- [ ] The MCP capability report matches the documented feature stage.
- [ ] MCP error handling is documented (what happens when a build fails,
  when a project path doesn't exist, etc.).

### 8. Release tag readiness

- [ ] The repository has at least one annotated git tag (e.g., `v0.2.0`)
  with release notes.
- [ ] The tag corresponds to a specific commit that has passed all
  public tests.
- [ ] The open-core export manifest (`open_core_manifest.yml`) is
  versioned and matches the tag.
- [ ] The open-core export process is documented so that any maintainer
  can produce a clean public release.

### 9. Changelog

- [ ] A `CHANGELOG.md` exists at the repository root.
- [ ] The changelog covers all releases from the first public alpha tag
  onward.
- [ ] Each changelog entry describes what changed, what broke (if
  anything), and what was added.
- [ ] The changelog distinguishes between public/community changes and
  internal/private changes.

### 10. Known limitations

- [ ] A `LIMITATIONS.md` or equivalent section in the README clearly
  lists what LynkMesh cannot do.
- [ ] The limitations include language coverage, framework coverage,
  repository size limits, and analysis scope.
- [ ] The limitations are dated so readers know when they were last
  reviewed.

---

## What "public alpha" means

When LynkMesh meets these criteria and is described as **public alpha /
developer preview**, it means:

- The project is stable enough for other developers to evaluate, integrate,
  and provide feedback on.
- The CLI contract, JSON output, and MCP behavior are versioned and changing
  at a documented pace.
- Known limitations are clearly stated so users can decide whether LynkMesh
  fits their use case.
- The project is NOT production-ready, NOT enterprise-ready, and NOT a
  finished product.
- Breaking changes may still occur, but they will be communicated through the
  changelog.

## What public alpha does NOT mean

Even after these criteria are met:

- LynkMesh is not production-ready.
- LynkMesh is not benchmark-proven.
- LynkMesh does not guarantee correct AI analysis.
- LynkMesh does not support all languages or frameworks.
- LynkMesh is not a replacement for human code review.

---

## Tracking

This document will be updated as criteria are met. Each checked item should
reference the commit, PR, or issue where it was satisfied.

Last reviewed: 2026-06-19 — no criteria met; early alpha.
