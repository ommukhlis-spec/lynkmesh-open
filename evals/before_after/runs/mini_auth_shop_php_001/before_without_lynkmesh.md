# Run — BEFORE (without LynkMesh) — mini_auth_shop_php_001

> Evaluation baseline, **not** benchmark proof. The AI transcript for this arm
> has been captured and committed under `transcripts/before/`. Human correctness
> scoring remains `pending_manual_capture`. No answers are fabricated.

## Run identity

- **Evaluation mode:** `before_without_lynkmesh`
- **Scenario ID:** `architecture_impact_baseline`
- **Run ID:** `mini_auth_shop_php_001`
- **Target (sanitized):** synthetic PHP MVC auth+shop fixture
- **LynkMesh used:** no

## Environment

- All fields `pending_manual_capture` (record OS, Python version, AI model, AI
  client at capture time; must match the AFTER arm).

## Exact evaluation prompt (asked identically in both arms)

> You are analyzing an unfamiliar local PHP project. Using only what you gather
> yourself, answer:
> 1. Describe the high-level structure: the main components/layers and how they
>    relate.
> 2. Which components depend on the most others, and which are most depended
>    upon?
> 3. If we change the authentication logic, which other components are
>    candidates for review?
> 4. Where is your answer uncertain or unsupported by available evidence?
> Cite the evidence you relied on for each answer.

## Manual context selection plan (no LynkMesh)

In this arm the agent has only raw repository access and must gather context
manually. The likely manual exploration path for the auth question, derived from
the fixture layout, is:

1. Entry points first: `public/index.php`, then `routes/web.php`.
2. Follow auth wiring: `app/Http/Controllers/AuthController.php` →
   `app/Services/AuthService.php`.
3. `AuthService` collaborators: `app/Repositories/UserRepository.php`,
   `app/Services/SessionService.php`, `app/Services/AuditLogService.php`.
4. Route guard + protected area: `app/Http/Middleware/AuthMiddleware.php`,
   `app/Http/Controllers/AccountController.php`.
5. Supporting: `app/Models/User.php`, `config/auth.php`.
6. Distractor noise the agent may also open before realizing it is unrelated:
   `ProductController.php`, `PricingService.php`, `ProductRepository.php`,
   `Product.php`.

This plan documents the manual effort the BEFORE arm represents. The actual
files the agent opens and the order are recorded at capture time.

## AI transcript

Captured and committed under `transcripts/before/`:
`ARCHITECTURE_ANALYSIS.md`, `CODE_EVIDENCE.md`, `DEPENDENCY_GRAPH.md`,
`SUMMARY.md`. These record the model working from the raw fixture only (no
LynkMesh artifacts). Not fabricated; not benchmark proof.

## Reviewer assessment (vs. fixture ground truth)

- Task 1 (architecture): `pending_manual_capture`
- Task 2 (dependencies): `pending_manual_capture`
- Task 3 (impact candidates): `pending_manual_capture`
- Task 4 (uncertainty): `pending_manual_capture`

Ground-truth reference for scoring: `../../fixtures/mini_auth_shop_php/README.md`.

## Disclaimers

- Single run; not generalizable. Evaluation baseline, not benchmark proof.
