<?php

/**
 * Front controller (entry point) for the fixture.
 *
 * Wires the dependency graph by hand so the structure is easy to trace
 * statically, then loads the route table. There is no full HTTP runtime here;
 * this fixture exists for before/after evaluation, not for serving traffic.
 */

use App\Http\Controllers\AccountController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\ProductController;
use App\Http\Middleware\AuthMiddleware;
use App\Repositories\ProductRepository;
use App\Repositories\UserRepository;
use App\Services\AuditLogService;
use App\Services\AuthService;
use App\Services\PricingService;
use App\Services\SessionService;

// --- Auth subsystem wiring -------------------------------------------------
$userRepository = new UserRepository();
$sessionService = new SessionService();
$auditLogService = new AuditLogService();
$authService = new AuthService($userRepository, $sessionService, $auditLogService);

$authController = new AuthController($authService);
$accountController = new AccountController($authService);
$authMiddleware = new AuthMiddleware($authService);

// --- Product (non-auth distractor) subsystem wiring ------------------------
$productRepository = new ProductRepository();
$pricingService = new PricingService($productRepository);
$productController = new ProductController($productRepository, $pricingService);

// Route table (controllers/middleware referenced here).
$routes = require __DIR__ . '/../routes/web.php';

return [
    'routes' => $routes,
    'controllers' => [
        'auth' => $authController,
        'account' => $accountController,
        'product' => $productController,
    ],
    'middleware' => [
        'auth' => $authMiddleware,
    ],
];
