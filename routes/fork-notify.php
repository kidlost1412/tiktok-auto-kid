<?php

declare(strict_types=1);

use App\Fork\Notify\Http\TelegramController;
use Illuminate\Support\Facades\Route;

// Trang "Telegram" trong Cài đặt (chỉ chủ tài khoản): nhập token bot, lấy chat id, bật/tắt từng loại tin, xem và gửi tin mẫu.
Route::middleware(['web', 'auth'])->prefix('settings/telegram')->name('fork.telegram.')->group(function (): void {
    Route::get('/', [TelegramController::class, 'index'])->name('index');
    Route::put('token', [TelegramController::class, 'saveToken'])->name('token');
    Route::post('detect-chat', [TelegramController::class, 'detectChat'])->name('detect-chat');
    Route::put('chat', [TelegramController::class, 'saveChat'])->name('chat');
    Route::patch('prefs', [TelegramController::class, 'savePrefs'])->name('prefs');
    Route::post('test', [TelegramController::class, 'test'])->name('test');
    Route::post('sample/{id}', [TelegramController::class, 'sample'])->where('id', '[a-z_]+')->name('sample');
    Route::delete('/', [TelegramController::class, 'disconnect'])->name('disconnect');
});
