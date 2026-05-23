<?php

namespace App\Repositories;

use App\Models\User;

/**
 * In-memory user store. Part of the auth subsystem.
 */
class UserRepository
{
    /** @var array<int, User> */
    private array $users;

    public function __construct()
    {
        $this->users = [
            1 => new User(1, 'owner@example.test', 'Account Owner', 'hash-placeholder-1'),
            2 => new User(2, 'staff@example.test', 'Staff Member', 'hash-placeholder-2'),
        ];
    }

    public function findByEmail(string $email): ?User
    {
        foreach ($this->users as $user) {
            if ($user->email === $email) {
                return $user;
            }
        }

        return null;
    }

    public function findById(int $id): ?User
    {
        return $this->users[$id] ?? null;
    }
}
