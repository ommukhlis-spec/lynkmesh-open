<?php

namespace App\Http\Controllers;

use App\Services\AuthService;

/**
 * Protected account/dashboard area. Requires authentication via AuthMiddleware
 * (see routes/web.php). Reads the current user through AuthService.
 */
class AccountController
{
    public function __construct(
        private AuthService $auth
    ) {
    }

    public function dashboard(): array
    {
        $user = $this->auth->currentUser();
        if ($user === null) {
            return ['status' => 'error', 'message' => 'not_authenticated'];
        }

        return [
            'status' => 'ok',
            'user' => [
                'id' => $user->id,
                'displayName' => $user->displayName,
            ],
        ];
    }
}
