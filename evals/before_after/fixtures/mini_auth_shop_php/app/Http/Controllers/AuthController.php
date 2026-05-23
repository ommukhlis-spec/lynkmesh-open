<?php

namespace App\Http\Controllers;

use App\Services\AuthService;

/**
 * Handles login/logout. Entry point into the auth subsystem.
 */
class AuthController
{
    public function __construct(
        private AuthService $auth
    ) {
    }

    /**
     * @param array{email?: string, password?: string} $input
     */
    public function login(array $input): array
    {
        $email = (string) ($input['email'] ?? '');
        $password = (string) ($input['password'] ?? '');

        if ($this->auth->attempt($email, $password)) {
            return ['status' => 'ok', 'redirect' => '/account'];
        }

        return ['status' => 'error', 'message' => 'invalid_credentials'];
    }

    public function logout(): array
    {
        $this->auth->logout();
        return ['status' => 'ok', 'redirect' => '/login'];
    }
}
