<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use RuntimeException;

/** Tài khoản ChatGPT đã hết lượt; `minutes` = số phút tới khi mở lại (nếu ChatGPT cho biết). */
final class CodexLimited extends RuntimeException
{
    public function __construct(public readonly ?int $minutes = null)
    {
        parent::__construct('Tài khoản ChatGPT hết lượt.');
    }
}
