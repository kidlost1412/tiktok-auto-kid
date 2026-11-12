<?php

declare(strict_types=1);

use App\Fork\Chrome\Http\Extension\AuthenticateExtension;
use App\Fork\Chrome\Http\Extension\ExtensionController;
use App\Fork\Chrome\Http\Extension\ExtensionCors;
use Illuminate\Support\Facades\Route;

// API cho tiện ích Chrome (TikTok Auto Kid), giao thức v1. Không session, không CSRF.
// ExtensionCors còn được đặt lên đầu middleware toàn cục trong ChromeServiceProvider,
// để chỉ origin của tiện ích mới nhận header CORS (kể cả preflight).

Route::prefix('api/ext')->middleware(['api', ExtensionCors::class])->group(function (): void {
    Route::options('{any}', [ExtensionController::class, 'preflight'])->where('any', '.*');

    Route::post('pair', [ExtensionController::class, 'pair']);

    Route::middleware(AuthenticateExtension::class)->group(function (): void {
        Route::post('hello', [ExtensionController::class, 'hello']);
        Route::get('next', [ExtensionController::class, 'next']);
        Route::get('tasks', [ExtensionController::class, 'tasks']);
        Route::post('products', [ExtensionController::class, 'products']);
        Route::post('anchor_template', [ExtensionController::class, 'anchorTemplate']);
        Route::post('stats', [ExtensionController::class, 'stats']);
        Route::post('comments', [ExtensionController::class, 'comments']);
        Route::get('video/meta', [ExtensionController::class, 'videoMeta']);
        Route::get('video', [ExtensionController::class, 'video']);
        Route::get('cover', [ExtensionController::class, 'cover']);
        Route::post('progress', [ExtensionController::class, 'progress']);
        Route::post('authorize', [ExtensionController::class, 'authorize']);
        Route::post('result', [ExtensionController::class, 'result']);
        Route::post('cancel', [ExtensionController::class, 'cancel']);
        Route::get('job_state', [ExtensionController::class, 'jobState']);
    });
});
