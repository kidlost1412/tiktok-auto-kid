<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use RuntimeException;

/** Không còn tài khoản ChatGPT nào dùng được lúc này (chưa đăng nhập hoặc tất cả đang hết lượt). */
final class NoAccount extends RuntimeException {}
