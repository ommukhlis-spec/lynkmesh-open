# Scenario: Architecture + Impact Analysis Baseline

- **Scenario ID:** `architecture_impact_baseline`
- **Status:** evaluation baseline (not benchmark proof)
- **Applies to:** a single public-safe code project (PHP has partial support
  today; other languages fall back to structural-only results)

## Goal

Evaluate how well an AI agent can answer architecture-understanding and
change-impact questions about an unfamiliar local project, comparing the
`before_without_lynkmesh` arm against the `after_with_lynkmesh` arm with the
model, task, and reviewer held constant.

This scenario targets the workflow LynkMesh is meant to support: giving an AI
agent deterministic, static-analysis-derived project evidence so it spends less
effort on manual context preparation and grounds its answers in that evidence.
It does **not** test runtime behavior, and it does **not** prove the AI is
"smarter" — only whether the deterministic evidence layer changes the workflow
and grounding for these specific questions.

## Target project selection

- Use a **public-safe** project. Sanitize its name to a category (e.g.
  "Legacy PHP administrative system") in anything published.
- Record only structural facts needed for the evaluation; do not paste private
  source into committed files.
- Substitute `<PATH_TO_PROJECT>` for the real local path everywhere.

## Tasks (asked identically in both arms)

1. **Architecture overview.** "Describe the high-level structure of this
   project: the main components/layers and how they relate."
2. **Dependency / relationship reading.** "Which components depend on the most
   others, and which are most depended upon?"
3. **Impact analysis (candidate-level).** "If we change component X, which other
   components are candidates for review?" (Choose an X that exists in the graph
   facts.)
4. **Confidence & gaps.** "Where is your answer uncertain or unsupported by
   available evidence?"

Each answer should cite the evidence it relied on. In the `after` arm, that
evidence includes the LynkMesh artifacts; in the `before` arm, it is whatever
the agent gathered manually.

## Evidence provided per arm

- **`before_without_lynkmesh`:** raw repository access only. The agent opens
  files and gathers context manually. No LynkMesh artifacts.
- **`after_with_lynkmesh`:** raw repository access **plus** deterministic
  LynkMesh artifacts generated with the public CLI:
  ```bash
  python -m lynkmesh report <PATH_TO_PROJECT> --pretty > report.json
  python -m lynkmesh pack <PATH_TO_PROJECT> --profile compact --pretty > ai-pack.json
  python -m lynkmesh benchmark <PATH_TO_PROJECT> --profile compact --pretty > benchmark.json
  ```

## What to measure

Record the fields defined in `../metrics/before_after_metrics.schema.json`,
including manual context-prep effort, grounding (claims vs. evidence-supported
claims), correctness of architecture findings against a human-reviewed answer
key, and time/iterations to a useful answer.

## Honest interpretation rules

- LynkMesh artifacts are **deterministic candidates and facts**, not validated
  runtime truth. "Impact" results are *candidates for review*, not guaranteed
  blast radius.
- Differences between arms reflect this scenario, this project, this model
  version, and this reviewer. Do not generalize.
- A favorable `after` result supports only the narrow, conditional claim that
  LynkMesh **may** reduce manual context preparation and improve grounding **in
  selected workflows, subject to evaluation**.

## Answer key

Maintain a separate, human-reviewed answer key for the correctness metrics. Keep
it public-safe (sanitized) if committed; otherwise keep it local and uncommitted.
