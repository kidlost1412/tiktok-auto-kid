<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use RuntimeException;

/** File video trong hub không còn hoặc rỗng: không thử lại. */
final class MissingVideoFile extends RuntimeException {}
