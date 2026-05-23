# Dependency Graph: mini_auth_shop_php

## Full Dependency Structure (with evidence locations)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ENTRY POINT LAYER                                   │
└─────────────────────────────────────────────────────────────────────────────┘

  public/index.php (lines 11-50)
  ├── uses statements (lines 11-20)
  └── wiring code (lines 23-35)
       │
       ├─→ INSTANTIATES & INJECTS:
       │
       ├─ Auth Subsystem (lines 23-30)
       │  ├── UserRepository (line 23) → instantiated, passed to AuthService
       │  ├── SessionService (line 24) → instantiated, passed to AuthService
       │  ├── AuditLogService (line 25) → instantiated, passed to AuthService
       │  ├── AuthService (line 26) ← receives 3 collaborators
       │  ├── AuthController (line 28) ← receives AuthService
       │  ├── AccountController (line 29) ← receives AuthService
       │  └── AuthMiddleware (line 30) ← receives AuthService
       │
       └─ Product Subsystem (lines 33-35)
          ├── ProductRepository (line 33) → instantiated
          ├── PricingService (line 34) ← receives ProductRepository
          └── ProductController (line 35) ← receives ProductRepository + PricingService

┌─────────────────────────────────────────────────────────────────────────────┐
│                       ROUTING LAYER                                          │
└─────────────────────────────────────────────────────────────────────────────┘

  routes/web.php (lines 17-27)
  │
  ├── Route: POST /login (line 19)
  │   └──→ AuthController::login (uses AuthService.attempt())
  │
  ├── Route: POST /logout (line 20)
  │   ├──→ AuthController::logout (uses AuthService.logout())
  │   └──→ AuthMiddleware (guards route; uses AuthService.check())
  │
  ├── Route: GET /account (line 23)
  │   ├──→ AccountController::dashboard (uses AuthService.currentUser())
  │   └──→ AuthMiddleware (guards route; uses AuthService.check())
  │
  └── Route: GET /products (line 26)
      └──→ ProductController::index (uses ProductRepository.all(), PricingService.priceFor())

┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTH SUBSYSTEM (Main Focus)                              │
└─────────────────────────────────────────────────────────────────────────────┘

HTTP LAYER
──────────
AuthController (lines 1-37)
  ├── depends on: AuthService
  └── methods:
      ├── login() → calls authService.attempt() [line 25]
      └── logout() → calls authService.logout() [line 34]

AccountController (lines 1-33)
  ├── depends on: AuthService
  └── methods:
      └── dashboard() → calls authService.currentUser() [line 20]

AuthMiddleware (lines 1-26)
  ├── depends on: AuthService
  └── methods:
      └── handle() → calls authService.check() [line 19]


CORE SERVICE LAYER
──────────────────
AuthService (lines 1-69) [THE CORE]
  │
  ├── depends on: UserRepository, SessionService, AuditLogService
  │
  ├── constructor (lines 18-23):
  │   ├── private UserRepository $users
  │   ├── private SessionService $session
  │   └── private AuditLogService $audit
  │
  ├── public methods (lines 25-62):
  │   ├── attempt(email, password): bool
  │   │   ├── calls $users.findByEmail() [line 27]
  │   │   ├── calls $audit.record('login_failed', ...) [line 29]
  │   │   ├── calls verifyPassword() [line 33]
  │   │   ├── calls $session.put() [line 38]
  │   │   └── calls $audit.record('login_succeeded', ...) [line 39]
  │   │
  │   ├── check(): bool
  │   │   └── calls $session.has() [line 45]
  │   │
  │   ├── currentUser(): ?User
  │   │   ├── calls $session.get() [line 50]
  │   │   └── calls $users.findById() [line 55]
  │   │
  │   └── logout(): void
  │       ├── calls $session.forget() [line 60]
  │       └── calls $audit.record('logout', ...) [line 61]
  │
  └── private methods (lines 64-68):
      └── verifyPassword() [placeholder]


COLLABORATING SERVICES
──────────────────────
SessionService (lines 1-32)
  ├── CALLED BY: AuthService [lines 24, 38, 45, 50, 60]
  ├── no dependencies
  └── methods:
      ├── put(key, value): void
      ├── get(key): mixed
      ├── forget(key): void
      └── has(key): bool

AuditLogService (lines 1-22)
  ├── CALLED BY: AuthService [lines 25, 29, 34, 39, 61]
  ├── no dependencies
  └── methods:
      ├── record(event, subject): void
      └── entries(): array


DATA ACCESS LAYER
─────────────────
UserRepository (lines 1-38)
  │
  ├── CALLED BY: AuthService [lines 27, 55]
  ├── depends on: User model
  │
  └── methods:
      ├── findByEmail(email): ?User [line 23]
      │   └── iterates $users array, instantiates User
      │
      └── findById(id): ?User [line 34]
          └── returns $users[$id] or User instance


USER MODEL
──────────
User (lines 1-23) [Plain Record]
  │
  ├── INSTANTIATED BY: UserRepository [line 18]
  ├── no dependencies
  │
  ├── constructor:
  │   ├── id: int
  │   ├── email: string
  │   ├── displayName: string
  │   ├── passwordHash: string
  │   └── active: bool = true
  │
  └── methods:
      └── isActive(): bool


CONFIG
──────
config/auth.php (lines 1-10)
  ├── STATUS: Defined but NOT IMPORTED by any PHP file
  ├── NOTES: AuthService.php hardcodes SESSION_KEY = 'auth_user_id' [line 16]
  │          instead of reading from config
  │
  └── values:
      ├── guard: 'web'
      ├── session_key: 'auth_user_id' (matches AuthService hardcoded value)
      ├── login_route: '/login'
      ├── protected_prefixes: ['/account']
      └── middleware: 'auth'


┌─────────────────────────────────────────────────────────────────────────────┐
│              PRODUCT SUBSYSTEM (Non-Auth Distractor)                        │
└─────────────────────────────────────────────────────────────────────────────┘

HTTP LAYER
──────────
ProductController (lines 1-33) [NO AUTH DEPENDENCY]
  │
  ├── depends on: ProductRepository, PricingService
  ├── NO imports from Auth* namespace
  │
  └── methods:
      └── index(): array
          ├── calls $products.all() [line 23]
          └── calls $pricing.priceFor() [line 27]


SERVICE LAYER
─────────────
PricingService (lines 1-31) [NO AUTH DEPENDENCY]
  │
  ├── depends on: ProductRepository
  ├── NO imports from Auth* namespace
  │
  └── methods:
      ├── priceFor(productId): ?int
      │   ├── calls $products.findById() [line 19]
      │   └── calls applyMarkup() [line 24]
      │
      └── applyMarkup(baseCents): int [private]


DATA ACCESS LAYER
─────────────────
ProductRepository (lines 1-32) [NO AUTH DEPENDENCY]
  │
  ├── depends on: Product model
  ├── NO imports from Auth* namespace
  │
  └── methods:
      ├── all(): array [line 23]
      │   └── returns all Product instances
      │
      └── findById(id): ?Product [line 28]
          └── returns $products[$id] or Product instance


PRODUCT MODEL
─────────────
Product (lines 1-22) [Plain Record, NO AUTH DEPENDENCY]
  │
  ├── INSTANTIATED BY: ProductRepository [line 18]
  ├── no dependencies
  │
  ├── constructor:
  │   ├── id: int
  │   ├── sku: string
  │   ├── name: string
  │   └── basePriceCents: int
  │
  └── methods:
      └── basePrice(): int


┌─────────────────────────────────────────────────────────────────────────────┐
│                  DEPENDENCY SUMMARY TABLE                                    │
└─────────────────────────────────────────────────────────────────────────────┘

Component              │ Depends On                        │ Depended On By        │ Centrality
─────────────────────────────────────────────────────────────────────────────────
public/index.php       │ All 10 others                     │ None (entry point)    │ Ultra-high
AuthService            │ UserRepository                    │ AuthController        │ HIGHEST
                       │ SessionService                    │ AccountController     │
                       │ AuditLogService                   │ AuthMiddleware        │
─────────────────────────────────────────────────────────────────────────────────
ProductRepository      │ Product                           │ PricingService        │ High
                       │                                   │ ProductController     │
─────────────────────────────────────────────────────────────────────────────────
AuthController         │ AuthService                       │ routes/web.php        │ Medium
AccountController      │ AuthService                       │ routes/web.php        │ Medium
AuthMiddleware         │ AuthService                       │ routes/web.php        │ Medium
─────────────────────────────────────────────────────────────────────────────────
PricingService         │ ProductRepository                 │ ProductController     │ Medium
─────────────────────────────────────────────────────────────────────────────────
UserRepository         │ User                              │ AuthService           │ Medium
─────────────────────────────────────────────────────────────────────────────────
ProductController      │ ProductRepository                 │ routes/web.php        │ Low
                       │ PricingService                    │                       │
─────────────────────────────────────────────────────────────────────────────────
SessionService         │ None                              │ AuthService           │ Low
AuditLogService        │ None                              │ AuthService           │ Low
User                   │ None                              │ UserRepository        │ Low
Product                │ None                              │ ProductRepository     │ Low


┌─────────────────────────────────────────────────────────────────────────────┐
│                  IF AUTHSERVICE CHANGES: IMPACT SCOPE                        │
└─────────────────────────────────────────────────────────────────────────────┘

TIER 1: DIRECT DEPENDENTS (MUST REVIEW)
────────────────────────────────────────
  AuthController
  AccountController
  AuthMiddleware

  IF CHANGE: AuthService method signature or behavior
  IMPACT: Login/logout flows break; protected routes can't verify auth

TIER 2: COLLABORATORS (SHOULD REVIEW)
──────────────────────────────────────
  UserRepository (used by AuthService for lookups)
  SessionService (used by AuthService for state)
  AuditLogService (used by AuthService for logging)

  IF CHANGE: AuthService calls to these shift
  IMPACT: Auth logic may depend on their contract; changes propagate

TIER 3: CONFIG & ROUTING (MAY REVIEW)
──────────────────────────────────────
  routes/web.php (defines which routes are guarded)
  config/auth.php (session key, protected prefixes) [NOT CURRENTLY IMPORTED]

  IF CHANGE: Guarded routes or session key behavior changes
  IMPACT: Routing may not work; session state may be lost

TIER 4: NOT AFFECTED
─────────────────────
  ProductController ✓ (zero auth dependency)
  PricingService ✓ (zero auth dependency)
  ProductRepository ✓ (zero auth dependency)
  Product ✓ (zero auth dependency)

  REASON: No imports, no calls, no shared types
