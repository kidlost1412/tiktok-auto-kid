<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/** Đường giữ chân của video (tỉ lệ người còn xem ở từng giây, đọc từ TikTok Studio) — để biết người xem bỏ ở hook hay ở thân bài. */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_video_stats', function (Blueprint $table): void {
            $table->jsonb('retention')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_video_stats', function (Blueprint $table): void {
            $table->dropColumn('retention');
        });
    }
};
