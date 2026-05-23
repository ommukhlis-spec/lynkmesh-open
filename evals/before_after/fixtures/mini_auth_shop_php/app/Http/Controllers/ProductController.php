<?php

namespace App\Http\Controllers;

use App\Repositories\ProductRepository;
use App\Services\PricingService;

/**
 * Public product listing. Non-auth distractor subsystem: it does not depend on
 * the auth services.
 */
class ProductController
{
    public function __construct(
        private ProductRepository $products,
        private PricingService $pricing
    ) {
    }

    public function index(): array
    {
        $items = [];
        foreach ($this->products->all() as $product) {
            $items[] = [
                'sku' => $product->sku,
                'name' => $product->name,
                'price' => $this->pricing->priceFor($product->id),
            ];
        }

        return ['status' => 'ok', 'items' => $items];
    }
}
