<?php

namespace App\Http\Middleware;

use App\Services\AuthService;

/**
 * Guards protected routes by delegating to AuthService.
 */
class AuthMiddleware
{
    public function __construct(
        private AuthService $auth
    ) {
    }

    public function handle(string $path): bool
    {
        if ($this->auth->check()) {
            return true;
        }

        // Not authenticated: caller should redirect to the login route.
        return false;
    }
}
