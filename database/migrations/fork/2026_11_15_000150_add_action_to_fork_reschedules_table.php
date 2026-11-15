<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Yêu cầu xoá bài hẹn trên TikTok không chỉ để đổi giờ: còn để sửa bài (kênh, caption, hashtag, ảnh bìa) hoặc bỏ xếp lịch.
 * action: time | edit | unschedule. changes: thay đổi sẽ áp khi đã xác minh xoá xong.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_reschedules', function (Blueprint $table): void {
            $table->string('action', 16)->default('time');
            $table->jsonb('changes')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_reschedules', function (Blueprint $table): void {
            $table->dropColumn(['action', 'changes']);
        });
    }
};
