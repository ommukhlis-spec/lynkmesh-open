<?php

namespace App\Models;

/**
 * Plain product record used by the non-auth product subsystem.
 */
class Product
{
    public function __construct(
        public int $id,
        public string $sku,
        public string $name,
        public int $basePriceCents
    ) {
    }

    public function basePrice(): int
    {
        return $this->basePriceCents;
    }
}
