<?php

declare(strict_types=1);

use App\Fork\Chrome\Http\ChromeSettingsController;
use Illuminate\Support\Facades\Route;

// Trang "Kết nối Chrome" trong Cài đặt (chỉ chủ tài khoản, bản tự host).
Route::middleware(['web', 'auth'])->prefix('settings/chrome')->name('fork.chrome.')->group(function (): void {
    Route::get('/', [ChromeSettingsController::class, 'index'])->name('index');
    Route::get('jobs', [ChromeSettingsController::class, 'jobs'])->name('jobs');
    Route::post('pair-code', [ChromeSettingsController::class, 'pairCode'])->name('pair-code');
    Route::patch('clients/{client}', [ChromeSettingsController::class, 'updateClient'])->name('clients.update');
    Route::delete('clients/{client}', [ChromeSettingsController::class, 'revokeClient'])->name('clients.revoke');
    Route::post('accounts/from-client/{client}', [ChromeSettingsController::class, 'accountFromClient'])->name('accounts.from-client');
    Route::post('accounts/{socialAccount}/toggle', [ChromeSettingsController::class, 'toggleAccount'])->name('accounts.toggle');
    Route::post('telegram-test', [ChromeSettingsController::class, 'telegramTest'])->name('telegram-test');
});
