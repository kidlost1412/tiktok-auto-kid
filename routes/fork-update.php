<?php

declare(strict_types=1);

use App\Fork\Update\UpdateController;
use Illuminate\Support\Facades\Route;

// Trang "Cập nhật" trong Cài đặt (chỉ chủ tài khoản).
Route::middleware(['web', 'auth'])->prefix('settings/cap-nhat')->name('fork.update.')->group(function (): void {
    Route::get('/', [UpdateController::class, 'index'])->name('index');
    Route::post('check', [UpdateController::class, 'check'])->middleware('throttle:6,1')->name('check');
    Route::post('install', [UpdateController::class, 'install'])->middleware('throttle:6,1')->name('install');
    Route::post('rollback', [UpdateController::class, 'rollback'])->middleware('throttle:6,1')->name('rollback');
    Route::patch('prefs', [UpdateController::class, 'prefs'])->name('prefs');
});
