<?php

declare(strict_types=1);

use App\Fork\AutoPost\Rieng\RiengClean;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

pest()->extend(TestCase::class)
    ->use(RefreshDatabase::class)
    ->beforeEach(function (): void {
        Http::preventStrayRequests();
        // File video trong test chỉ là chữ: bước làm sạch metadata Kho riêng chỉ chép nguyên (test thật: RiengCleanTest).
        app()->instance(RiengClean::class, new RiengClean(fn (string $from, string $to) => copy($from, $to)));
    })
    ->in('Feature');
