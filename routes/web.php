<?php

declare(strict_types=1);

use Illuminate\Support\Facades\Route;

// Không có đăng nhập: chủ app được tự đăng nhập (AutoLoginOwner). Tên `login` để middleware `auth` có nơi chuyển hướng.
Route::redirect('/', '/auto');
Route::redirect('/login', '/auto')->name('login');
