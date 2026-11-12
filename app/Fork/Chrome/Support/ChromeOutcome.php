<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Support;

use Carbon\CarbonImmutable;

final readonly class ChromeOutcome
{
    public function __construct(
        public bool $ok,
        public bool $uncertain,
        public string $message,
        public ?string $videoId = null,
        public ?CarbonImmutable $scheduledFor = null,
    ) {}
}
