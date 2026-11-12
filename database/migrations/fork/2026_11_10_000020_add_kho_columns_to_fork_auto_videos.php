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
            // Quy cách (vd "1l", "5l"); null = sản phẩm chỉ có một quy cách, hoặc video cũ.
            $table->string('quy_cach')->nullable()->index();
            // 'kho' = từ kho-dang (chuẩn mới), 'ra' = từ ra/<ngày>/ (cũ).
            $table->string('source', 10)->default('ra');
            $table->string('json_path')->nullable();
            $table->unsignedInteger('phien_ban')->nullable();
            // Phần còn lại của file .json đi kèm, giữ nguyên.
            $table->jsonb('meta')->nullable();
            // Đã xoá file mp4/json theo cài đặt lưu giữ.
            $table->timestamp('files_deleted_at')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            $table->dropColumn(['quy_cach', 'source', 'json_path', 'phien_ban', 'meta', 'files_deleted_at']);
        });
    }
};
