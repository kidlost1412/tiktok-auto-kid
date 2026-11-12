<?php

declare(strict_types=1);

use App\Fork\AutoPost\Http\AutoController;
use App\Fork\AutoPost\Http\GioHangController;
use App\Fork\AutoPost\Http\KhoController;
use App\Fork\AutoPost\Http\MediaController;
use App\Fork\AutoPost\Http\PersonaliseController;
use App\Fork\AutoPost\Http\StatsController;
use App\Fork\AutoPost\Http\SyncStatusController;
use App\Fork\Chrome\Http\Extension\AuthenticateExtension;
use App\Fork\Chrome\Http\Extension\ExtensionCors;
use Illuminate\Support\Facades\Route;

// Trang "Tự động đăng" (chỉ chủ tài khoản, bản tự host).
Route::middleware(['web', 'auth'])->prefix('auto')->name('fork.auto.')->group(function (): void {
    Route::get('/', [AutoController::class, 'index'])->name('index');
    Route::post('plan-now', [AutoController::class, 'planNow'])->middleware('throttle:10,1')->name('plan-now');
    Route::patch('accounts/{socialAccount}', [AutoController::class, 'updateAccount'])->name('accounts.update');
    Route::post('huong-dan/an', [AutoController::class, 'hideOnboarding'])->name('onboarding.hide');
    Route::post('videos/{video}/thu-lai', [AutoController::class, 'retryVideo'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.retry');
    Route::post('accounts/{socialAccount}/pause', [AutoController::class, 'pause'])->name('accounts.pause');
    Route::post('accounts/{socialAccount}/apply-hours', [AutoController::class, 'applyHours'])->name('accounts.apply-hours');
    // Giỏ hàng TikTok Shop: trang riêng, chọn sản phẩm theo từng kênh và từng quy cách.
    Route::get('gio-hang', [GioHangController::class, 'index'])->name('gio-hang');
    Route::post('accounts/{socialAccount}/shop/sync', [GioHangController::class, 'requestSync'])->name('accounts.shop.sync');
    Route::put('accounts/{socialAccount}/links/{code}', [GioHangController::class, 'saveLink'])->name('accounts.links.save');
    Route::delete('accounts/{socialAccount}/links/{code}', [GioHangController::class, 'clearLink'])->name('accounts.links.clear');
    Route::patch('accounts/{socialAccount}/shop-products/{productId}', [GioHangController::class, 'setHidden'])
        ->where('productId', '[0-9]{6,25}')->name('accounts.shop-products.hide');
    Route::patch('products/{code}', [AutoController::class, 'updateProduct'])->name('products.update');
    // Cá nhân hoá theo sản phẩm hub: ảnh bìa riêng và hashtag riêng.
    Route::put('products/{code}/personalise', [PersonaliseController::class, 'update'])->name('products.personalise');
    Route::post('products/{code}/personalise/preview', [PersonaliseController::class, 'preview'])->middleware('throttle:60,1')->name('products.personalise.preview');
    Route::post('products/{code}/covers', [PersonaliseController::class, 'upload'])->middleware('throttle:30,1')->name('products.covers.upload');
    Route::delete('products/{code}/covers/{file}', [PersonaliseController::class, 'destroy'])->name('products.covers.destroy');
    Route::get('anh-bia/{code}/{file}', [PersonaliseController::class, 'image'])->name('cover-image');
    Route::put('hashtag-mac-dinh', [PersonaliseController::class, 'updateDefault'])->name('hashtags.default');
    Route::post('hashtag-mac-dinh/preview', [PersonaliseController::class, 'previewDefault'])->middleware('throttle:60,1')->name('hashtags.default.preview');
    // Ảnh bìa sản phẩm TikTok Shop (tải về máy, link CDN gốc hết hạn).
    Route::get('anh-san-pham/{shopProduct}', [MediaController::class, 'productImage'])->whereNumber('shopProduct')->name('product-image');
    // Số liệu: video đã đăng, lượt xem và tương tác.
    Route::get('so-lieu', [StatsController::class, 'index'])->name('so-lieu');
});

// Kho video: chuẩn kho-dang, thống kê, xem trước video (chỉ chủ tài khoản).
Route::middleware(['web', 'auth'])->prefix('auto/kho')->name('fork.auto.kho.')->group(function (): void {
    Route::get('/', [KhoController::class, 'index'])->name('index');
    Route::patch('settings', [KhoController::class, 'settings'])->name('settings');
    Route::post('ping', [KhoController::class, 'ping'])->name('ping');
    Route::post('scan', [KhoController::class, 'scan'])->name('scan');
    Route::get('video/{video}', [KhoController::class, 'video'])->whereNumber('video')->name('video');
    Route::get('video/{video}/info', [KhoController::class, 'info'])->whereNumber('video')->name('info');
    Route::get('video/{video}/cover', [KhoController::class, 'cover'])->whereNumber('video')->name('cover');
});

// Tiện ích báo lỗi khi lấy sản phẩm shop (cùng xác thực với /api/ext/*, đặt ở đây để không đụng phần Chrome).
Route::prefix('api/ext')->middleware(['api', ExtensionCors::class, AuthenticateExtension::class])->group(function (): void {
    Route::post('sync_status', SyncStatusController::class);
});
