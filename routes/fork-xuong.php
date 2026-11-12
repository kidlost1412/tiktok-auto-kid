<?php

declare(strict_types=1);

use App\Fork\Xuong\ShopFeedController;
use App\Fork\Xuong\XuongController;
use Illuminate\Support\Facades\Route;

// Trang "Xưởng Video": nhúng hub sản xuất video.
Route::middleware(['web', 'auth'])->prefix('xuong')->group(function (): void {
    Route::get('/', [XuongController::class, 'index'])->name('fork.xuong');
    Route::get('health', [XuongController::class, 'health'])->name('fork.xuong.health');
    Route::post('restart', [XuongController::class, 'restart'])->middleware('throttle:6,1')->name('fork.xuong.restart');
});

// Máy gọi máy cho hub: sản phẩm TikTok Shop + ảnh thật. Xác thực X-Key (FORK_HUB_KEY), chỉ loopback, không CSRF.
Route::middleware('api')->prefix('api/xuong')->group(function (): void {
    Route::get('shop-products', [ShopFeedController::class, 'index']);
    Route::get('shop-products/{id}/image', [ShopFeedController::class, 'image'])->where('id', '[0-9]{1,32}');
});
