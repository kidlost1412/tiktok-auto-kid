<?php

declare(strict_types=1);

use App\Fork\Nha\NhaController;
use Illuminate\Support\Facades\Route;

// Trang chủ "Xưởng nhỏ" + nguồn trạng thái (trang hỏi lại mỗi ~3 giây khi đang xem).
Route::middleware(['web', 'auth'])->prefix('nha')->group(function (): void {
    Route::get('/', [NhaController::class, 'index'])->name('fork.nha');
    Route::get('trang-thai', [NhaController::class, 'state'])->middleware('throttle:120,1')->name('fork.nha.state');
});
