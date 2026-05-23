<?php

use App\Http\Controllers\AccountController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\ProductController;
use App\Http\Middleware\AuthMiddleware;

/**
 * Route table for the fixture.
 *
 * Returns a list of route definitions. Routes under the protected prefix are
 * marked with the auth middleware. This is a static definition intended to be
 * easy to trace; there is no live router runtime here.
 *
 * @return array<int, array{method: string, path: string, controller: string, action: string, middleware: ?string}>
 */
return [
    // Auth routes (entry into the auth subsystem).
    ['method' => 'POST', 'path' => '/login',  'controller' => AuthController::class,    'action' => 'login',     'middleware' => null],
    ['method' => 'POST', 'path' => '/logout', 'controller' => AuthController::class,    'action' => 'logout',    'middleware' => AuthMiddleware::class],

    // Protected account area.
    ['method' => 'GET',  'path' => '/account', 'controller' => AccountController::class, 'action' => 'dashboard', 'middleware' => AuthMiddleware::class],

    // Public product area (non-auth distractor subsystem).
    ['method' => 'GET',  'path' => '/products', 'controller' => ProductController::class, 'action' => 'index',    'middleware' => null],
];
