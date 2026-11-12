<?php

declare(strict_types=1);

use App\Fork\Chrome\Http\LauncherController;
use App\Fork\Chrome\Http\LauncherSecret;
use Illuminate\Support\Facades\Route;

// Trợ lý mở Chrome trên Windows (tools/fork/chrome-launcher) gọi các endpoint này.
Route::prefix('api/fork/chrome')
    ->middleware(['api', LauncherSecret::class])
    ->group(function (): void {
        Route::get('launch-requests', [LauncherController::class, 'launchRequests']);
        Route::post('launched', [LauncherController::class, 'launched']);
        Route::post('profiles', [LauncherController::class, 'profiles']);
    });
