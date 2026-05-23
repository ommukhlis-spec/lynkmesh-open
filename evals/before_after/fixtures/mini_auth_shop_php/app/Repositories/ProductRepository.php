<?php

namespace App\Repositories;

use App\Models\Product;

/**
 * In-memory product store. Part of the non-auth product subsystem.
 */
class ProductRepository
{
    /** @var array<int, Product> */
    private array $products;

    public function __construct()
    {
        $this->products = [
            1 => new Product(1, 'SKU-001', 'Starter Widget', 1500),
            2 => new Product(2, 'SKU-002', 'Pro Widget', 4200),
        ];
    }

    public function all(): array
    {
        return array_values($this->products);
    }

    public function findById(int $id): ?Product
    {
        return $this->products[$id] ?? null;
    }
}
