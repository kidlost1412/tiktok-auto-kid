<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_chrome_clients', function (Blueprint $table): void {
            // "Giữ Chrome luôn chạy nền": trợ lý tự mở profile khi tiện ích im lặng quá lâu.
            $table->boolean('keep_alive')->default(true);
            $table->timestamp('keepalive_last_start_at')->nullable();
            $table->unsignedSmallInteger('keepalive_failures')->default(0);
            $table->string('keepalive_error', 255)->nullable();
            // Người dùng bấm "Mở Chrome nền ngay": bỏ qua thời gian chờ một lần.
            $table->timestamp('keepalive_requested_at')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_chrome_clients', function (Blueprint $table): void {
            $table->dropColumn(['keep_alive', 'keepalive_last_start_at', 'keepalive_failures', 'keepalive_error', 'keepalive_requested_at']);
        });
    }
};
