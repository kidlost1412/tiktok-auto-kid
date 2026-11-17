<?php

declare(strict_types=1);

use App\Fork\AutoPost\Http\AutoController;
use App\Fork\AutoPost\Http\GioHangController;
use App\Fork\AutoPost\Http\KhoController;
use App\Fork\AutoPost\Http\MediaController;
use App\Fork\AutoPost\Http\PersonaliseController;
use App\Fork\AutoPost\Http\PostEditController;
use App\Fork\AutoPost\Http\RescheduleController;
use App\Fork\AutoPost\Http\RiengAutoController;
use App\Fork\AutoPost\Http\RiengController;
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
    Route::put('dang-thang', [AutoController::class, 'saveDirectWindow'])->name('direct-window');
    Route::post('videos/{video}/thu-lai', [AutoController::class, 'retryVideo'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.retry');
    // "Đăng lại" bài hẹn giờ mà Chrome báo lỗi (hết hàng...): giao lượt mới cho Chrome, chỉ khi chắc chắn chưa đăng gì.
    Route::post('videos/{video}/dang-lai', [AutoController::class, 'retryPost'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.repost');
    // "Đổi giờ" bài đã xếp lịch mà chưa đăng (bài đã hẹn trên TikTok: xoá bài hẹn cũ qua Chrome rồi hẹn lại).
    Route::get('videos/{video}/doi-gio', [RescheduleController::class, 'show'])->whereNumber('video')->name('videos.reschedule.show');
    Route::post('videos/{video}/doi-gio', [RescheduleController::class, 'store'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.reschedule');
    // Sửa bài đã xếp lịch (giờ, kênh, caption, hashtag, ảnh bìa), bỏ xếp lịch, cho xếp lịch lại (khung xem video, Lịch đăng).
    Route::get('videos/{video}/sua', [PostEditController::class, 'show'])->whereNumber('video')->name('videos.edit.show');
    Route::post('videos/{video}/sua', [PostEditController::class, 'update'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.edit');
    Route::post('videos/{video}/bo-xep-lich', [PostEditController::class, 'unschedule'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.unschedule');
    Route::post('videos/{video}/cho-xep-lai', [PostEditController::class, 'release'])->whereNumber('video')->middleware('throttle:30,1')->name('videos.release');
    Route::post('accounts/{socialAccount}/pause', [AutoController::class, 'pause'])->name('accounts.pause');
    Route::post('accounts/{socialAccount}/apply-hours', [AutoController::class, 'applyHours'])->name('accounts.apply-hours');
    // Giỏ hàng TikTok Shop: trang riêng, chọn sản phẩm theo từng kênh và từng quy cách.
    Route::get('gio-hang', [GioHangController::class, 'index'])->name('gio-hang');
    Route::post('accounts/{socialAccount}/shop/sync', [GioHangController::class, 'requestSync'])->name('accounts.shop.sync');
    Route::put('accounts/{socialAccount}/links/{code}', [GioHangController::class, 'saveLink'])->name('accounts.links.save');
    Route::delete('accounts/{socialAccount}/links/{code}', [GioHangController::class, 'clearLink'])->name('accounts.links.clear');
    Route::patch('accounts/{socialAccount}/shop-products/{productId}', [GioHangController::class, 'setHidden'])
        ->where('productId', '[0-9]{6,25}')->name('accounts.shop-products.hide');
    // "+ Thêm sản phẩm": tạo sản phẩm hub từ sản phẩm shop (qua API Xưởng Video) và gắn giỏ một lần; đổi tên / xoá sản phẩm hub.
    Route::post('accounts/{socialAccount}/hub-products', [GioHangController::class, 'addProduct'])->middleware('throttle:20,1')->name('accounts.hub-products.add');
    Route::patch('hub-products/{code}', [GioHangController::class, 'renameProduct'])->where('code', '[a-z0-9-]+')->name('hub-products.rename');
    Route::delete('hub-products/{code}', [GioHangController::class, 'deleteProduct'])->where('code', '[a-z0-9-]+')->name('hub-products.delete');
    Route::patch('products/{code}', [AutoController::class, 'updateProduct'])->name('products.update');
    // Cá nhân hoá theo sản phẩm hub: ảnh bìa riêng và hashtag riêng (trang tổng hợp + các thao tác).
    Route::get('anh-bia-hashtag', [PersonaliseController::class, 'index'])->name('anh-bia-hashtag');
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

    // Kho riêng: video chủ app tự làm (thư mục, quét, danh sách, đăng hàng loạt).
    Route::prefix('rieng')->name('rieng.')->group(function (): void {
        Route::get('/', [RiengController::class, 'index'])->name('index');
        Route::post('thu-muc', [RiengController::class, 'addFolder'])->middleware('throttle:30,1')->name('folders.add');
        Route::post('chon-thu-muc', [RiengController::class, 'pickFolder'])->middleware('throttle:20,1')->name('folders.pick');
        Route::post('chon-thu-muc/ket-qua', [RiengController::class, 'pickFolderResult'])->middleware('throttle:120,1')->name('folders.pick.result');
        Route::delete('video/{video}', [RiengController::class, 'forgetVideo'])->whereNumber('video')->middleware('throttle:60,1')->name('video.forget');
        Route::delete('thu-muc/{folder}', [RiengController::class, 'removeFolder'])->whereNumber('folder')->name('folders.remove');
        Route::patch('thu-muc/{folder}', [RiengController::class, 'renameFolder'])->whereNumber('folder')->name('folders.rename');
        Route::patch('thu-muc/{folder}/nhac', [RiengController::class, 'saveMusic'])->whereNumber('folder')->middleware('throttle:60,1')->name('folders.music');
        Route::post('nhac/dem', [RiengController::class, 'countMusic'])->middleware('throttle:60,1')->name('folders.music.count');
        Route::post('thu-muc/{folder}/mo', [RiengController::class, 'openFolder'])->whereNumber('folder')->middleware('throttle:30,1')->name('folders.open');
        Route::post('thu-muc/{folder}/video', [RiengController::class, 'uploadToFolder'])->whereNumber('folder')->middleware('throttle:120,1')->name('folders.upload');
        Route::post('quet', [RiengController::class, 'scan'])->middleware('throttle:20,1')->name('scan');
        // Quét nhanh cho trang đang mở (tự giới hạn ~8 giây/lần bằng khoá bộ nhớ đệm, không ngủ chờ).
        Route::post('quet-nhanh', [RiengController::class, 'quickScan'])->middleware('throttle:60,1')->name('scan.quick');
        // "Giỏ chờ đăng": video riêng chọn sẵn để đăng sau (khác giỏ hàng TikTok Shop).
        Route::post('gio-cho/them', [RiengController::class, 'queueAdd'])->middleware('throttle:60,1')->name('queue.add');
        Route::post('gio-cho/bo', [RiengController::class, 'queueRemove'])->middleware('throttle:60,1')->name('queue.remove');
        Route::get('video/{video}/thumb', [RiengController::class, 'thumb'])->whereNumber('video')->name('thumb');
        Route::post('anh-bia/tai-len', [RiengController::class, 'coverUpload'])->middleware('throttle:60,1')->name('cover.upload');
        Route::get('anh-bia/tam/{token}', [RiengController::class, 'coverTemp'])->name('cover.temp');
        Route::post('video/{video}/khung', [RiengController::class, 'coverFrame'])->whereNumber('video')->middleware('throttle:60,1')->name('cover.frame');
        Route::post('anh-bia/nho', [RiengController::class, 'coverRecall'])->middleware('throttle:120,1')->name('cover.recall');
        Route::post('video/{video}/quen-bia', [RiengController::class, 'coverForget'])->whereNumber('video')->middleware('throttle:120,1')->name('cover.forget');
        Route::post('dat-lich/goi-y', [RiengController::class, 'batchPropose'])->middleware('throttle:120,1')->name('batch.propose');
        Route::post('dat-lich/xem', [RiengController::class, 'batchPreview'])->middleware('throttle:60,1')->name('batch.preview');
        Route::post('dat-lich', [RiengController::class, 'batchCommit'])->middleware('throttle:20,1')->name('batch.commit');
        // Kho riêng tự đăng theo khung: cài đặt, tài khoản ChatGPT, chỉnh sản phẩm/caption/kênh từng video.
        Route::get('tu-dong', [RiengAutoController::class, 'show'])->name('auto.show');
        Route::patch('tu-dong', [RiengAutoController::class, 'update'])->middleware('throttle:60,1')->name('auto.update');
        Route::get('tu-dong/codex-cli', [RiengAutoController::class, 'cliStatus'])->middleware('throttle:120,1')->name('auto.codex.status');
        Route::post('tu-dong/codex-cli', [RiengAutoController::class, 'installCli'])->middleware('throttle:6,1')->name('auto.codex.install');
        Route::get('tu-dong/ai-trang-thai', [RiengAutoController::class, 'aiStatus'])->name('auto.rieng.ai.status');
        Route::post('tu-dong/ai-chay-ngay', [RiengAutoController::class, 'aiRunNow'])->middleware('throttle:10,1')->name('auto.rieng.ai.run');
        Route::post('tu-dong/ai-thu-lai', [RiengAutoController::class, 'retryAi'])->middleware('throttle:10,1')->name('auto.rieng.ai.retry');
        Route::post('tu-dong/chatgpt', [RiengAutoController::class, 'addChatGpt'])->middleware('throttle:10,1')->name('auto.chatgpt.add');
        Route::get('tu-dong/chatgpt/{id}', [RiengAutoController::class, 'chatGptStatus'])->where('id', 'tk-[a-z0-9]{8}')->name('auto.chatgpt.status');
        Route::get('tu-dong/chatgpt/{id}/han-muc', [RiengAutoController::class, 'chatGptLimits'])->where('id', 'tk-[a-z0-9]{8}')->middleware('throttle:30,1')->name('auto.chatgpt.limits');
        Route::delete('tu-dong/chatgpt/{id}', [RiengAutoController::class, 'removeChatGpt'])->where('id', 'tk-[a-z0-9]{8}')->name('auto.chatgpt.remove');
        Route::post('video/{video}/tu-dong', [RiengAutoController::class, 'updateVideo'])->whereNumber('video')->middleware('throttle:120,1')->name('auto.video');
        Route::get('video/{video}/trang-thai', [RiengAutoController::class, 'videoState'])->whereNumber('video')->name('auto.rieng.video.state');
        Route::post('video/{video}/ai-xem-lai', [RiengAutoController::class, 'reanalyze'])->whereNumber('video')->middleware('throttle:20,1')->name('auto.reanalyze');
    });
});

// Tiện ích báo lỗi khi lấy sản phẩm shop (cùng xác thực với /api/ext/*, đặt ở đây để không đụng phần Chrome).
Route::prefix('api/ext')->middleware(['api', ExtensionCors::class, AuthenticateExtension::class])->group(function (): void {
    Route::post('sync_status', SyncStatusController::class);
});
