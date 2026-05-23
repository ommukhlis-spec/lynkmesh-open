<?php

namespace App\Services;

/**
 * Minimal session abstraction used by the auth subsystem.
 */
class SessionService
{
    /** @var array<string, mixed> */
    private array $store = [];

    public function put(string $key, mixed $value): void
    {
        $this->store[$key] = $value;
    }

    public function get(string $key): mixed
    {
        return $this->store[$key] ?? null;
    }

    public function forget(string $key): void
    {
        unset($this->store[$key]);
    }

    public function has(string $key): bool
    {
        return isset($this->store[$key]);
    }
}
