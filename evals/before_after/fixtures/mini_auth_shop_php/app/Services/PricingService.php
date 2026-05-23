<?php

namespace App\Services;

use App\Repositories\ProductRepository;

/**
 * Computes product prices. Part of the non-auth product subsystem.
 */
class PricingService
{
    public function __construct(
        private ProductRepository $products
    ) {
    }

    public function priceFor(int $productId): ?int
    {
        $product = $this->products->findById($productId);
        if ($product === null) {
            return null;
        }

        return $this->applyMarkup($product->basePrice());
    }

    private function applyMarkup(int $baseCents): int
    {
        return (int) round($baseCents * 1.2);
    }
}
