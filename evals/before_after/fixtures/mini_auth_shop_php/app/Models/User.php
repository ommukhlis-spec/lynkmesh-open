<?php

namespace App\Models;

/**
 * Plain user record used by the auth subsystem.
 */
class User
{
    public function __construct(
        public int $id,
        public string $email,
        public string $displayName,
        public string $passwordHash,
        public bool $active = true
    ) {
    }

    public function isActive(): bool
    {
        return $this->active;
    }
}
