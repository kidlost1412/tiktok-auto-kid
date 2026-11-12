<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/** Bình luận trên video của kênh (tiện ích đọc từ TikTok Studio), kèm cờ "hỏi mua / hỏi giá". */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_comments', function (Blueprint $table): void {
            $table->id();
            $table->string('comment_id', 32)->unique();
            $table->uuid('social_account_id')->nullable()->index();
            $table->string('item_id', 32)->index();
            $table->unsignedBigInteger('auto_video_id')->nullable()->index();
            $table->string('author_id', 32)->nullable();
            $table->string('author_handle', 64)->nullable();
            $table->string('author_name', 128)->nullable();
            $table->text('text');
            $table->unsignedInteger('like_count')->default(0);
            $table->unsignedInteger('reply_count')->default(0);
            $table->timestamp('commented_at')->nullable()->index();
            $table->boolean('is_buy_intent')->default(false);
            $table->string('intent_keywords')->nullable();
            // Đã báo Telegram chưa (chống báo trùng, bổ sung cho khoá chống trùng trong Cache).
            $table->timestamp('notified_at')->nullable();
            $table->timestamps();

            $table->index(['is_buy_intent', 'commented_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_comments');
    }
};
