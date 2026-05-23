<?php

namespace App\Services;

use App\Models\User;
use App\Repositories\UserRepository;

/**
 * Core authentication logic.
 *
 * This is the center of the auth subsystem: it coordinates the user store,
 * the session, and the audit log.
 */
class AuthService
{
    private const SESSION_KEY = 'auth_user_id';

    public function __construct(
        private UserRepository $users,
        private SessionService $session,
        private AuditLogService $audit
    ) {
    }

    public function attempt(string $email, string $password): bool
    {
        $user = $this->users->findByEmail($email);
        if ($user === null || !$user->isActive()) {
            $this->audit->record('login_failed', $email);
            return false;
        }

        if (!$this->verifyPassword($user, $password)) {
            $this->audit->record('login_failed', $email);
            return false;
        }

        $this->session->put(self::SESSION_KEY, $user->id);
        $this->audit->record('login_succeeded', $email);
        return true;
    }

    public function check(): bool
    {
        return $this->session->has(self::SESSION_KEY);
    }

    public function currentUser(): ?User
    {
        $id = $this->session->get(self::SESSION_KEY);
        if ($id === null) {
            return null;
        }

        return $this->users->findById((int) $id);
    }

    public function logout(): void
    {
        $this->session->forget(self::SESSION_KEY);
        $this->audit->record('logout', 'session');
    }

    private function verifyPassword(User $user, string $password): bool
    {
        // Structural placeholder only; not a real credential check.
        return $user->passwordHash !== '' && $password !== '';
    }
}
