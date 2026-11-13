<?php

declare(strict_types=1);

use App\Fork\Nha\NhaController;
use Illuminate\Support\Facades\Route;

// Trang chủ "Khu Tự Trị" + nguồn trạng thái (trang hỏi lại mỗi ~3 giây khi đang xem).
Route::middleware(['web', 'auth'])->prefix('nha')->group(function (): void {
    Route::get('/', [NhaController::class, 'index'])->name('fork.nha');
    Route::get('trang-thai', [NhaController::class, 'state'])->middleware('throttle:120,1')->name('fork.nha.state');
    // Nhân vật của tôi: tên + ngoại hình (lưu trên máy chủ).
    Route::get('nhan-vat/{who}', [NhaController::class, 'avatar'])->name('fork.nha.avatar');
    Route::put('nhan-vat/{who}', [NhaController::class, 'saveAvatar'])->middleware('throttle:30,1')->name('fork.nha.avatar.save');
});
