# Fixture: mini_auth_shop_php

> **Synthetic, public-safe evaluation fixture.** A small PHP MVC-style project
> built only for the before/after evaluation baseline. It is **not** a real
> application, contains no secrets or real credentials, and is **not** wired into
> open-core export, release, tags, or publishing.

## Purpose

Provide a deterministic, easy-to-trace target for the
`architecture_impact_baseline` scenario. The structure is designed so that an
architecture/impact question about the **authentication** flow has a clear,
reviewable ground truth, while a separate **product** subsystem acts as a
distractor that should *not* appear in auth-change impact answers.

All passwords/hashes are obvious placeholders (e.g. `hash-placeholder-1`), and
emails use the reserved `example.test` domain. There are no real credentials.

## Layout

```
mini_auth_shop_php/
  README.md
  public/index.php              front controller (entry point; wires the graph)
  routes/web.php                route table (entry point; maps paths to controllers)
  config/auth.php               structural auth config (no secrets)
  app/
    Http/
      Controllers/
        AuthController.php       login/logout  -> AuthService
        AccountController.php    protected dashboard -> AuthService
        ProductController.php    public products (distractor)
      Middleware/
        AuthMiddleware.php       route guard -> AuthService
    Services/
      AuthService.php            core auth -> UserRepository, SessionService, AuditLogService
      SessionService.php         session storage (auth)
      AuditLogService.php        auth event log (auth)
      PricingService.php         pricing (distractor) -> ProductRepository
    Repositories/
      UserRepository.php         user store (auth)
      ProductRepository.php      product store (distractor)
    Models/
      User.php                   user record (auth)
      Product.php                product record (distractor)
```

## Expected ground truth

### Main entry points

- `public/index.php` — front controller; constructs the dependency graph and
  loads the route table.
- `routes/web.php` — route table mapping paths to controllers/actions, marking
  protected routes with `AuthMiddleware`.

### Auth-related files (the auth subsystem)

- `app/Http/Controllers/AuthController.php` — login/logout entry point.
- `app/Http/Controllers/AccountController.php` — protected account dashboard.
- `app/Http/Middleware/AuthMiddleware.php` — guards protected routes.
- `app/Services/AuthService.php` — **core** of the subsystem.
- `app/Services/SessionService.php` — session state.
- `app/Services/AuditLogService.php` — auth event logging.
- `app/Repositories/UserRepository.php` — user lookups.
- `app/Models/User.php` — user record.
- `config/auth.php` — auth configuration.

### Auth dependency chain (what makes it traceable)

```
AuthController        -> AuthService
AccountController     -> AuthService
AuthMiddleware        -> AuthService
AuthService           -> UserRepository, SessionService, AuditLogService
UserRepository        -> User
routes/web.php        -> AuthController, AccountController, AuthMiddleware (+ ProductController)
public/index.php      -> all controllers, middleware, services, repositories
```

### Likely impact candidates if authentication logic changes

If `AuthService` (or its contract/behavior) changes, the candidates for review
are its direct dependents and collaborators:

- `AuthController` (login/logout)
- `AccountController` (reads current user)
- `AuthMiddleware` (auth check on protected routes)
- `SessionService`, `AuditLogService`, `UserRepository` (collaborators)
- `routes/web.php` (which routes are guarded) and `config/auth.php`
  (session key, protected prefixes)

These are **candidates for review**, not a guaranteed blast radius. Static
analysis cannot prove runtime behavior.

### Non-auth distractor files (should NOT appear in auth-change impact)

- `app/Http/Controllers/ProductController.php`
- `app/Services/PricingService.php`
- `app/Repositories/ProductRepository.php`
- `app/Models/Product.php`

The product subsystem depends only on `ProductRepository` / `Product` /
`PricingService` and has no dependency on the auth services. A correct
auth-change impact answer should exclude these files.

## Safety notes

- No secrets, real credentials, private absolute paths, internal repo names, or
  private project references are present.
- Evaluation fixture only. Do not add it to `open_core_manifest.yml`, and do not
  publish, tag, or release it as part of the product.
