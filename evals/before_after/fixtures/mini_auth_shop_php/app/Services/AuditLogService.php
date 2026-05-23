<?php

namespace App\Services;

/**
 * Records auth-related events. Part of the auth subsystem.
 */
class AuditLogService
{
    /** @var array<int, array{event: string, subject: string}> */
    private array $entries = [];

    public function record(string $event, string $subject): void
    {
        $this->entries[] = ['event' => $event, 'subject' => $subject];
    }

    public function entries(): array
    {
        return $this->entries;
    }
}
