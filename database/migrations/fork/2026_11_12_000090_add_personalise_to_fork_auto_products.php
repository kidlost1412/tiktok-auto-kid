<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_products', function (Blueprint $table): void {
            // Ảnh bìa: default (bìa mặc định của TikTok) | fixed (một ảnh cố định) | random (ngẫu nhiên trong bộ ảnh).
            $table->string('cover_mode', 16)->default('default');
            // [{"file":"<uuid>.jpg","name":"anh-goc.png","w":1080,"h":1920,"size":123456,"sha256":"..."}]
            $table->jsonb('cover_images')->nullable();
            $table->string('cover_fixed')->nullable();
            $table->string('cover_last')->nullable();
            // Hashtag riêng: danh sách, chế độ append (thêm vào cuối) | replace (thay toàn bộ), chọn ngẫu nhiên N cái (0 = tất cả).
            $table->jsonb('hashtags')->nullable();
            $table->string('hashtag_mode', 16)->default('append');
            $table->unsignedSmallInteger('hashtag_pick')->default(0);
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_products', function (Blueprint $table): void {
            $table->dropColumn(['cover_mode', 'cover_images', 'cover_fixed', 'cover_last', 'hashtags', 'hashtag_mode', 'hashtag_pick']);
        });
    }
};
