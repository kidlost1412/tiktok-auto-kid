<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use Illuminate\Support\ServiceProvider;

/** "Khu Tự Trị": trang chủ hoạt hình, hiện ê-kíp đang làm gì theo dữ liệu thật. */
final class NhaServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadRoutesFrom(base_path('routes/fork-nha.php'));
    }
}
