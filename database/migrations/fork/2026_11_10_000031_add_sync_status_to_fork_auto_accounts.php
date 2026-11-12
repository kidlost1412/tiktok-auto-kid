<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            // Lúc chủ app bấm "Lấy sản phẩm từ shop": yêu cầu quá 10 phút thì hết hạn.
            $table->timestamp('products_sync_requested_at')->nullable();
            // Lý do tiện ích báo khi lấy sản phẩm lỗi (cho yêu cầu đang chờ).
            $table->string('products_sync_error', 500)->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            $table->dropColumn(['products_sync_requested_at', 'products_sync_error']);
        });
    }
};
