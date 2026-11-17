<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            // Thùng rác: video anh "xoá" nằm đây 30 ngày, khôi phục được; xoá trong thùng rác (hoặc quá 30 ngày) là xoá hẳn.
            // Dòng vẫn giữ (dấu vết) để lần quét sau không nạp lại video đó.
            $table->timestamp('trashed_at')->nullable()->index();
            $table->timestamp('purged_at')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            $table->dropIndex(['trashed_at']);
            $table->dropColumn(['trashed_at', 'purged_at']);
        });
    }
};
