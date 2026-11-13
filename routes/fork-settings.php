<?php

declare(strict_types=1);

use App\Fork\Settings\Http\SettingsController;
use Illuminate\Support\Facades\Route;

// Trang "Cài đặt" hợp nhất (chỉ chủ tài khoản, bản tự host): Kết nối Chrome, Telegram, Cập nhật
// trong một trang với các mục/tab bên trong. Các route hành động (pair-code, telegram/token,
// cap-nhat/check...) vẫn nằm ở routes/fork-chrome-app.php, fork-notify.php, fork-update.php.
Route::middleware(['web', 'auth'])->get('settings', [SettingsController::class, 'index'])->name('fork.settings.index');
