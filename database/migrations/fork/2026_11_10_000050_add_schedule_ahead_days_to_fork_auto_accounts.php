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
            // Số ngày xếp lịch trước (1..9): bài được tạo và tải lên TikTok hẹn giờ sớm, không cần bật máy lúc đăng.
            $table->unsignedSmallInteger('schedule_ahead_days')->default(3);
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            $table->dropColumn('schedule_ahead_days');
        });
    }
};
