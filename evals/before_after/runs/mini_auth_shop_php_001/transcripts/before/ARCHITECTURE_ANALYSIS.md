# Architecture Analysis: mini_auth_shop_php

## 1. High-Level Structure: Main Components & Layers

The project follows an **MVC architecture with service/repository layers**, split into **two independent subsystems**:

### Entry Points (Wiring & Routing)

| Component | Role | Evidence |
|-----------|------|----------|
| `public/index.php` | **Front controller**: Constructs the dependency graph by hand; loads route table | Lines 1-50: Explicit `new` instantiations of all services, repositories, controllers, middleware |
| `routes/web.php` | **Route table**: Maps HTTP paths to controller actions; marks protected routes with middleware | Lines 17-27: 4 route definitions with explicit controller/action/middleware references |

### Authentication Subsystem (main focus)

**HTTP Layer (Request Handlers)**
- `AuthController` (lines 1-37) — Handles `/login` and `/logout` endpoints
- `AccountController` (lines 1-33) — Handles protected `/account` dashboard
- `AuthMiddleware` (lines 1-26) — Guards protected routes via `AuthService`

**Service Layer (Business Logic)**
- `AuthService` (lines 1-69) — **Core**: Coordinates authentication logic; uses UserRepository, SessionService, AuditLogService
- `SessionService` (lines 1-32) — In-memory session state storage
- `AuditLogService` (lines 1-22) — Records auth events (login success/fail, logout)

**Data Layer (Persistence & Models)**
- `UserRepository` (lines 1-38) — Provides `findByEmail()` and `findById()`; instantiates User objects
- `User` (lines 1-23) — Plain record with id, email, displayName, passwordHash, active

**Configuration**
- `config/auth.php` (lines 1-10) — Session key, protected route prefixes, login route

### Product Subsystem (non-auth distractor)

**HTTP Layer**
- `ProductController` (lines 1-33) — Handles public `/products` endpoint

**Service Layer**
- `PricingService` (lines 1-31) — Computes product prices with markup

**Data Layer**
- `ProductRepository` (lines 1-32) — Provides `all()` and `findById()`; instantiates Product objects
- `Product` (lines 1-22) — Plain record with id, sku, name, basePriceCents

### Structural Relationship

```
Entry: public/index.php (wires all dependencies)
  ↓
routes/web.php (4 route definitions)
  ├─→ AuthController → AuthService ─┐
  ├─→ AccountController → AuthService │
  ├─→ AuthMiddleware → AuthService ─┤
  │                                  └→ UserRepository → User
  │                                  ├→ SessionService (internal state)
  │                                  └→ AuditLogService (internal state)
  │
  └─→ ProductController ─→ ProductRepository → Product
                       ├→ PricingService → ProductRepository
                       └→ ProductRepository (used twice)

config/auth.php (referenced at runtime but not compiled)
```

---

## 2. Dependency Analysis: High-Centrality Components

### Components with Most Dependents (Most Depended Upon)

#### **`AuthService` — Highest centrality**
**Direct dependents: 3 components**
- `AuthController::login()` calls `$this->auth->attempt($email, $password)` (AuthController.php:25)
- `AuthController::logout()` calls `$this->auth->logout()` (AuthController.php:34)
- `AccountController::dashboard()` calls `$this->auth->currentUser()` (AccountController.php:20)
- `AuthMiddleware::handle()` calls `$this->auth->check()` (AuthMiddleware.php:19)

**Reason**: AuthService is the facade/coordinator for all auth operations; all HTTP-layer auth concerns flow through it.

**Evidence**:
- `public/index.php:26` — `AuthService` instantiated once and injected into three controllers and one middleware
- Constructor signature (AuthService.php:18-23) shows no other class depends on it directly except HTTP layer

#### **`ProductRepository` — Secondary centrality**
**Direct dependents: 2 components**
- `PricingService::priceFor()` calls `$this->products->findById($productId)` (PricingService.php:19)
- `ProductController::index()` calls `$this->products->all()` (ProductController.php:23)

**Evidence**:
- `public/index.php:33-35` — ProductRepository instantiated once and injected into both PricingService and ProductController

### Components with Most Dependencies (Most Complex)

#### **`public/index.php` — Highest dependency count**
**Direct dependencies: 10 classes**
1. `UserRepository` (line 23)
2. `SessionService` (line 24)
3. `AuditLogService` (line 25)
4. `AuthService` (line 26)
5. `AuthController` (line 28)
6. `AccountController` (line 29)
7. `AuthMiddleware` (line 30)
8. `ProductRepository` (line 33)
9. `PricingService` (line 34)
10. `ProductController` (line 35)

**Reason**: As the front controller, it must construct and wire the entire dependency graph.

**Evidence**:
- Lines 11-20 (use statements) declare all 10 dependencies
- Lines 23-35 (instantiation code) construct and wire them manually
- Lines 40-50 (return array) expose them to the route table

#### **`AuthService` — Second-highest dependency count**
**Direct dependencies: 3 services**
- `UserRepository $users` (AuthService.php:19)
- `SessionService $session` (AuthService.php:20)
- `AuditLogService $audit` (AuthService.php:21)

**Used in methods**:
- `attempt()`: calls `$this->users->findByEmail()`, `$this->session->put()`, `$this->audit->record()` (lines 27-40)
- `check()`: calls `$this->session->has()` (line 45)
- `currentUser()`: calls `$this->session->get()`, `$this->users->findById()` (lines 50-56)
- `logout()`: calls `$this->session->forget()`, `$this->audit->record()` (lines 60-61)

**Evidence**:
- Constructor (AuthService.php:18-23) defines three injected dependencies
- All public methods use all three collaborators

#### **`PricingService` — Single dependency**
**Direct dependencies: 1 repository**
- `ProductRepository $products` (PricingService.php:13)

**Used in methods**:
- `priceFor()`: calls `$this->products->findById()` (line 19)

---

## 3. Auth Change Impact Candidates

If authentication logic in `AuthService` changes (method signature, behavior, or contract), these components are candidates for review:

### Tier 1: Direct Dependents (Highest Risk)
**Must review these**:
- **`AuthController`** (AuthController.php:12-36)
  - Uses: `$this->auth->attempt()` (login), `$this->auth->logout()`
  - Risk: Change to `attempt()` signature or return type impacts login handling

- **`AccountController`** (AccountController.php:12-32)
  - Uses: `$this->auth->currentUser()`
  - Risk: Change to return type (User | null behavior) impacts dashboard view logic

- **`AuthMiddleware`** (AuthMiddleware.php:11-25)
  - Uses: `$this->auth->check()`
  - Risk: Change to return type (bool) or behavior impacts route guard logic

### Tier 2: Collaborating Services (Medium Risk)
**Should review these**:
- **`UserRepository`** (UserRepository.php:1-38)
  - Reason: AuthService calls `findByEmail()` and `findById()`; changes to method signatures or return types impact auth flow
  - Risk: Adding filters, caching, or persistence changes could break auth lookups

- **`SessionService`** (SessionService.php:1-32)
  - Reason: AuthService relies on `put()`, `get()`, `forget()`, `has()` for auth state
  - Risk: Changes to session storage, lifetime, or key-value contract impact all auth operations

- **`AuditLogService`** (AuditLogService.php:1-22)
  - Reason: AuthService calls `record()` after auth attempts
  - Risk: Changes to event format or storage could break audit trails (lower risk for correctness, higher for compliance)

### Tier 3: Route & Config (Low-Medium Risk)
**May require review**:
- **`routes/web.php`** (web.php:1-27)
  - Reason: Routes define which paths are guarded by `AuthMiddleware`
  - Risk: Changing middleware assignment (e.g., removing from `/logout`) impacts security
  - Evidence: Lines 20 (logout guarded), 23 (account guarded), vs 19 (login unguarded) are explicit

- **`config/auth.php`** (auth.php:1-10)
  - Reason: Defines `session_key` constant used in AuthService (AuthService.php:16)
  - Risk: If session key changes, AuthService must be updated to match
  - Evidence: AuthService hardcodes `SESSION_KEY = 'auth_user_id'` (line 16), matching config (line 6)

### NOT Candidates (No Auth Dependency)

These components have **zero dependency** on `AuthService` or auth subsystem:
- **`ProductController`** — Only depends on `ProductRepository` and `PricingService` (ProductController.php:15-16)
- **`PricingService`** — Only depends on `ProductRepository` (PricingService.php:13)
- **`ProductRepository`** — Only depends on `Product` model (ProductRepository.php:5)
- **`Product`** — No dependencies (Product.php:1-22)

**Evidence**: Zero imports or references to Auth* classes in any product subsystem file.

---

## 4. Uncertainties and Limitations

### What is Well-Supported by Evidence

✅ **Clear dependencies**: All dependency relationships are explicit in constructor injection and `use` statements.
✅ **Entry point clarity**: Front controller wiring in `public/index.php` is explicit and static.
✅ **Auth subsystem isolation**: No cross-subsystem dependencies between auth and product code.
✅ **Impact scope**: Direct dependents and collaborators are unambiguous.

### Where Analysis is Uncertain

⚠️ **Runtime behavior not visible**:
- No reflection, dynamic dispatch, or interface implementations in the code.
- No indication of how the fixture integrates with an HTTP framework or routing engine (structure is simplified for analysis).
- `routes/web.php` defines routes as static array; actual request dispatch mechanism is not shown.

⚠️ **Implicit dependencies not captured**:
- No evidence of external vendor dependencies (only PHP >=8.1 required in composer.json:11).
- No database or ORM integration; data is in-memory.
- The `config/auth.php` is loaded but never used directly in the code; it's described as "structural" but no runtime code references it.
  - **Uncertainty**: Is config/auth.php actually read at runtime, or is it documentation? No require/import found in any file.
  - **Evidence**: config/auth.php exists but is NOT imported in any PHP file; AuthService hardcodes `SESSION_KEY` instead of reading from config.

⚠️ **Distractor subsystem not fully exercised**:
- ProductController → PricingService → ProductRepository dependency chain is clear, but no evidence that changes to Product model would require changes to PricingService (only uses `basePrice()` method).
- If Product.basePrice() contract changes, would PricingService break? **Not directly evident** from the code alone.

⚠️ **Session state mutations not analyzed**:
- SessionService is a simple key-value store; no indication of persistence, expiry, or concurrency.
- If SessionService were replaced with Redis or database-backed session, would AuthService break? **Likely yes**, but depends on interface contract remaining the same.

### What Cannot Be Determined Without Additional Context

❓ **Framework integration**: The fixture structure suggests a Laravel-like MVC, but no framework is imported. How does routing, middleware execution, and dependency injection actually happen at runtime?

❓ **Testing scope**: No test files present. Which components have high test coverage? Which are risky to change?

❓ **Performance implications**: AuthService calls multiple methods on UserRepository and SessionService. Are there N+1 query risks or caching opportunities?

❓ **Security contract**: AuthService::verifyPassword() is a placeholder (lines 64-68). In production, password verification logic would be more complex. Changing this affects all login attempts.

---

## Summary of Evidence Locations

| Finding | Evidence |
|---------|----------|
| Entry point wiring | `public/index.php:11-50` |
| Route definitions | `routes/web.php:17-27` |
| AuthService centrality | `AuthController.php:25,34`, `AccountController.php:20`, `AuthMiddleware.php:19` |
| AuthService dependencies | `AuthService.php:18-23` (constructor) |
| Auth subsystem boundaries | `public/index.php:22-30` (comment marks auth section), `routes/web.php:18` (comment) |
| Product distractor | `public/index.php:32-35`, `ProductController.php:15-16` (no auth imports) |
| Session key contract mismatch | `AuthService.php:16` hardcodes value; `config/auth.php:6` has matching value but is never imported |
