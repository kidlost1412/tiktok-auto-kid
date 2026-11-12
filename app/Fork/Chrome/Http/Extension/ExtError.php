<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http\Extension;

use Exception;
use Illuminate\Http\JsonResponse;

/**
 * Lỗi của giao thức tiện ích: {"ok":false,"error":code,"message":...,...extra}.
 */
final class ExtError extends Exception
{
    /** @param array<string, mixed> $extra */
    public function __construct(
        public readonly int $status,
        public readonly string $errorCode,
        string $message = '',
        public readonly array $extra = [],
    ) {
        parent::__construct($message);
    }

    public function report(): bool
    {
        return false;
    }

    public function render(): JsonResponse
    {
        return response()->json(
            ['ok' => false, 'error' => $this->errorCode, 'message' => $this->getMessage(), ...$this->extra],
            $this->status,
        );
    }
}
