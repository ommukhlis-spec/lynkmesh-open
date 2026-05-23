# Code Evidence Cross-Reference: mini_auth_shop_php

This document maps each analytical claim to specific file:line citations for verification.

---

## Q1: High-Level Structure

### Claim: Project has two independent subsystems (Auth + Product)

**Evidence that subsystems are independent:**
- No imports from `App\Services\Auth*` in ProductController.php → lines 1-33 (only imports: ProductRepository, PricingService)
- No imports from `App\Services\Auth*` in PricingService.php → lines 1-31 (only imports: ProductRepository)
- No imports from `App\Services\Auth*` in ProductRepository.php → lines 1-32 (only imports: Product)
- No imports from `App\Services\Auth*` in Product.php → lines 1-22 (zero imports)
- No imports from `App\Http\Controllers\Product*` in any Auth file

**Evidence of Auth subsystem definition:**
- README.md:56-67 — Explicit list of auth-related files
- public/index.php:22 — Comment: "--- Auth subsystem wiring ---"
- public/index.php:32 — Comment: "--- Product (non-auth distractor) subsystem wiring ---"
- routes/web.php:18 — Comment: "// Auth routes (entry into the auth subsystem)."
- routes/web.php:25 — Comment: "// Public product area (non-auth distractor subsystem)."

### Claim: Three-layer architecture (HTTP → Services → Data)

**Auth Subsystem Layers:**
- **HTTP Layer**: AuthController.php:1, AccountController.php:1, AuthMiddleware.php:1
- **Service Layer**: AuthService.php:1, SessionService.php:1, AuditLogService.php:1
- **Data Layer**: UserRepository.php:1, User.php:1

**Product Subsystem Layers:**
- **HTTP Layer**: ProductController.php:1
- **Service Layer**: PricingService.php:1
- **Data Layer**: ProductRepository.php:1, Product.php:1

### Claim: Entry points are public/index.php and routes/web.php

**Evidence:**
- README.md:50-55 — Describes "Main entry points"
- public/index.php:4-8 — Comment: "Front controller (entry point) for the fixture. Wires the dependency graph..."
- public/index.php:38 — `$routes = require __DIR__ . '/../routes/web.php';`
- public/index.php:40-50 — Returns routes and wired controllers/middleware
- routes/web.php:9-15 — Comment describing route table as static definition

---

## Q2: Dependency Analysis - Most Depended Upon

### Claim: AuthService is highest-centrality component (depended on by 3 entities)

**AuthService depended on by AuthController:**
- AuthController.php:5 — `use App\Services\AuthService;`
- AuthController.php:13-15 — Constructor: `public function __construct(private AuthService $auth)`
- AuthController.php:25 — Usage: `if ($this->auth->attempt($email, $password))`
- AuthController.php:34 — Usage: `$this->auth->logout();`
- public/index.php:28 — Injection: `new AuthController($authService)`

**AuthService depended on by AccountController:**
- AccountController.php:5 — `use App\Services\AuthService;`
- AccountController.php:14-16 — Constructor: `public function __construct(private AuthService $auth)`
- AccountController.php:20 — Usage: `$user = $this->auth->currentUser();`
- public/index.php:29 — Injection: `new AccountController($authService)`

**AuthService depended on by AuthMiddleware:**
- AuthMiddleware.php:5 — `use App\Services\AuthService;`
- AuthMiddleware.php:12-15 — Constructor: `public function __construct(private AuthService $auth)`
- AuthMiddleware.php:19 — Usage: `if ($this->auth->check())`
- public/index.php:30 — Injection: `new AuthMiddleware($authService)`

**Centrality proof:**
- public/index.php:26 — `$authService = new AuthService(...);` (created once)
- public/index.php:28-30 — Same instance injected into three different classes
- README.md:79 — Explicit dependency chain lists AuthService as hub

### Claim: ProductRepository is second-highest centrality (depended on by 2 entities)

**ProductRepository depended on by PricingService:**
- PricingService.php:5 — `use App\Repositories\ProductRepository;`
- PricingService.php:13-15 — Constructor: `public function __construct(private ProductRepository $products)`
- PricingService.php:19 — Usage: `$product = $this->products->findById($productId);`
- public/index.php:34 — Injection: `new PricingService($productRepository)`

**ProductRepository depended on by ProductController:**
- ProductController.php:5 — `use App\Repositories\ProductRepository;`
- ProductController.php:15-17 — Constructor: `public function __construct(private ProductRepository $products, ...)`
- ProductController.php:23 — Usage: `foreach ($this->products->all() as $product)`
- public/index.php:35 — Injection: `new ProductController($productRepository, $pricingService)`

---

## Q2: Dependency Analysis - Most Dependencies

### Claim: public/index.php has most dependencies (10 classes)

**Imported classes (lines 11-20):**
1. AuthController (line 11)
2. AuthService (line 18)
3. ProductController (line 13)
4. AuthMiddleware (line 14)
5. ProductRepository (line 15)
6. UserRepository (line 16)
7. AuditLogService (line 17)
8. PricingService (line 19)
9. SessionService (line 20)
10. AccountController (line 12)

**Instantiated (lines 23-35):**
- Line 23: `$userRepository = new UserRepository();`
- Line 24: `$sessionService = new SessionService();`
- Line 25: `$auditLogService = new AuditLogService();`
- Line 26: `$authService = new AuthService($userRepository, $sessionService, $auditLogService);`
- Line 28: `$authController = new AuthController($authService);`
- Line 29: `$accountController = new AccountController($authService);`
- Line 30: `$authMiddleware = new AuthMiddleware($authService);`
- Line 33: `$productRepository = new ProductRepository();`
- Line 34: `$pricingService = new PricingService($productRepository);`
- Line 35: `$productController = new ProductController($productRepository, $pricingService);`

### Claim: AuthService has second-highest dependencies (3 collaborators)

**AuthService dependencies:**
- AuthService.php:18-23 — Constructor declares three parameters:
  - Line 19: `private UserRepository $users`
  - Line 20: `private SessionService $session`
  - Line 21: `private AuditLogService $audit`

**AuthService usage of dependencies:**
- Lines 27-40 (attempt method):
  - Line 27: `$user = $this->users->findByEmail($email);`
  - Line 29: `$this->audit->record('login_failed', $email);`
  - Line 38: `$this->session->put(self::SESSION_KEY, $user->id);`
  - Line 39: `$this->audit->record('login_succeeded', $email);`

- Lines 43-46 (check method):
  - Line 45: `return $this->session->has(self::SESSION_KEY);`

- Lines 48-56 (currentUser method):
  - Line 50: `$id = $this->session->get(self::SESSION_KEY);`
  - Line 55: `return $this->users->findById((int) $id);`

- Lines 58-62 (logout method):
  - Line 60: `$this->session->forget(self::SESSION_KEY);`
  - Line 61: `$this->audit->record('logout', 'session');`

---

## Q3: Auth Change Impact Candidates

### Tier 1: Direct Dependents (MUST REVIEW)

**AuthController:**
- File: AuthController.php:1-37
- Methods that call AuthService:
  - Line 25: `if ($this->auth->attempt($email, $password))`
  - Line 34: `$this->auth->logout();`
- Routes that use it: routes/web.php:19-20
- Risk: Change to attempt() signature or logout() behavior directly impacts login/logout functionality

**AccountController:**
- File: AccountController.php:1-33
- Methods that call AuthService:
  - Line 20: `$user = $this->auth->currentUser();`
- Routes that use it: routes/web.php:23
- Risk: Change to currentUser() return type (User | null) impacts dashboard view logic

**AuthMiddleware:**
- File: AuthMiddleware.php:1-26
- Methods that call AuthService:
  - Line 19: `if ($this->auth->check())`
- Routes that use it: routes/web.php:20, 23
- Risk: Change to check() signature or behavior impacts protected route guarding

### Tier 2: Collaborators (SHOULD REVIEW)

**UserRepository:**
- Called by AuthService at:
  - AuthService.php:27 — `$user = $this->users->findByEmail($email);`
  - AuthService.php:55 — `return $this->users->findById((int) $id);`
- Risk: Changes to findByEmail() or findById() contract break auth lookups

**SessionService:**
- Called by AuthService at:
  - AuthService.php:38 — `$this->session->put(self::SESSION_KEY, $user->id);`
  - AuthService.php:45 — `return $this->session->has(self::SESSION_KEY);`
  - AuthService.php:50 — `$id = $this->session->get(self::SESSION_KEY);`
  - AuthService.php:60 — `$this->session->forget(self::SESSION_KEY);`
- Risk: Changes to put(), get(), forget(), has() contract break all auth state operations

**AuditLogService:**
- Called by AuthService at:
  - AuthService.php:29 — `$this->audit->record('login_failed', $email);`
  - AuthService.php:34 — `$this->audit->record('login_failed', $email);`
  - AuthService.php:39 — `$this->audit->record('login_succeeded', $email);`
  - AuthService.php:61 — `$this->audit->record('logout', 'session');`
- Risk: Changes to record() signature impact audit trail functionality

### Tier 3: Config & Routing (MAY REVIEW)

**routes/web.php:**
- AuthMiddleware assigned to:
  - Line 20: POST /logout (should require auth before logout)
  - Line 23: GET /account (protected dashboard)
- NOT assigned to:
  - Line 19: POST /login (public)
  - Line 26: GET /products (public)
- Risk: Removing or changing middleware assignments alters auth behavior

**config/auth.php:**
- Defines:
  - Line 6: `'session_key' => 'auth_user_id'`
  - Line 8: `'protected_prefixes' => ['/account']`
- AuthService.php:16 hardcodes: `private const SESSION_KEY = 'auth_user_id';`
- Risk: Mismatch between config and code; changes to config are ignored

### NOT Candidates (Zero Auth Dependency)

**ProductController - Evidence of zero auth imports:**
- ProductController.php:1-33 imports only:
  - Line 5: `use App\Repositories\ProductRepository;`
  - Line 6: `use App\Services\PricingService;`
- No import of AuthService, AuthMiddleware, or any Auth* class
- Methods (lines 20-31) only call: `$this->products.all()` and `$this->pricing.priceFor()`

**PricingService - Evidence of zero auth imports:**
- PricingService.php:1-31 imports only:
  - Line 5: `use App\Repositories\ProductRepository;`
- No import of AuthService or any Auth* class
- Methods (lines 17-30) only call: `$this->products.findById()` and `$this->applyMarkup()`

**ProductRepository - Evidence of zero auth imports:**
- ProductRepository.php:1-32 imports only:
  - Line 5: `use App\Models\Product;`
- No import of AuthService or any Auth* class
- Methods (lines 23-36) only manipulate: `$this->products` array and Product instances

**Product - Evidence of zero auth imports:**
- Product.php:1-22 has zero imports
- Methods (lines 18-22) only return: `$this->active` and `$this->basePriceCents`

---

## Q4: Uncertainties & Evidence Gaps

### Uncertainty: config/auth.php is never imported

**Evidence that config exists:**
- File: config/auth.php:1-10
- Contains: guard, session_key, login_route, protected_prefixes, middleware

**Evidence that config is NOT imported:**
- public/index.php — No `require`, `include`, or import of config/auth.php
- AuthService.php — No reference to config; hardcodes `SESSION_KEY = 'auth_user_id'` (line 16)
- AuthMiddleware.php — No reference to config
- routes/web.php — No reference to config

**Evidence of hardcoding instead of config:**
- AuthService.php:16 — `private const SESSION_KEY = 'auth_user_id';`
- config/auth.php:6 — `'session_key' => 'auth_user_id'` (matches hardcoded value)
- BUT: No code path imports config, so values are effectively ignored

**Impact:** If someone changed config/auth.php session_key to 'different_key', AuthService would still use 'auth_user_id', breaking sessions.

### Uncertainty: Framework integration not visible

**Evidence that fixture is standalone:**
- README.md:7-8 — "It is not a real application... not wired into open-core export..."
- public/index.php:4-8 — "There is no full HTTP runtime here; this fixture exists for before/after evaluation..."
- No Laravel, Symfony, Slim, or other framework imports in composer.json:1-13
- Only requires: PHP >=8.1 (no vendor dependencies)

**Missing pieces:**
- No HTTP kernel or application bootstrap
- No container/DI framework
- No actual request/response handling
- No real database or ORM

### Uncertainty: Session persistence is in-memory only

**Evidence:**
- SessionService.php:8-31 uses `private array $store = [];`
- No database, Redis, or file-based persistence
- Data is lost when SessionService instance is destroyed

**Impact:** Real production auth would need persistent session store; changes to SessionService interface might be needed.

### Uncertainty: Password verification is obviously placeholder

**Evidence:**
- AuthService.php:64-68 — `return $user->passwordHash !== '' && $password !== '';`
- README.md:107 — "All passwords/hashes are obvious placeholders (e.g. hash-placeholder-1)"
- User.php:18-19 — Users created with `'hash-placeholder-1'` and `'hash-placeholder-2'`

**Impact:** Real password verification (bcrypt, Argon2) would be much more complex and could introduce new dependencies.

---

## Summary of Evidence Density

| Section | Total Claims | Citations | Avg Citations/Claim |
|---------|--------------|-----------|---------------------|
| Q1: Structure | 3 major claims | 20+ line refs | 6.7 |
| Q2: Centrality | 4 major claims | 35+ line refs | 8.75 |
| Q3: Impact | 7 tier groups | 40+ line refs | 5.7 |
| Q4: Uncertainties | 4 major uncertainties | 15+ line refs | 3.75 |
| **TOTAL** | **18 major claims** | **110+ line references** | **6.1** |

**Conclusion:** Every major analytical claim is supported by direct code evidence (file:line citations). Uncertainties are identified and their evidence gaps clearly marked.
