<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Số liệu do tiện ích TikTok Auto Kid đọc từ TikTok Studio:
 *  - fork_video_stats: số liệu mới nhất của từng video (theo item_id của TikTok), kèm chỉ số chi tiết của video ≤ 7 ngày;
 *  - fork_video_snapshots: lịch sử (để lấy mốc 24h / 72h);
 *  - fork_account_stats: số người theo dõi mỗi ngày của kênh.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_video_stats', function (Blueprint $table): void {
            $table->id();
            $table->uuid('social_account_id');
            $table->string('item_id', 32);
            $table->unsignedBigInteger('auto_video_id')->nullable()->index();
            $table->text('caption')->nullable();
            $table->timestamp('posted_at')->nullable();
            $table->unsignedInteger('duration_ms')->nullable();
            $table->unsignedBigInteger('views')->default(0);
            $table->unsignedBigInteger('likes')->default(0);
            $table->unsignedBigInteger('comments')->default(0);
            $table->unsignedBigInteger('shares')->default(0);
            $table->unsignedBigInteger('saves')->default(0);
            $table->float('avg_watch_s')->nullable();
            $table->float('finish_rate')->nullable();
            $table->float('total_watch_s')->nullable();
            $table->integer('new_followers')->nullable();
            $table->jsonb('traffic')->nullable();
            $table->timestamp('insight_at')->nullable();
            $table->timestamp('collected_at');
            $table->timestamps();

            $table->unique(['social_account_id', 'item_id']);
        });

        Schema::create('fork_video_snapshots', function (Blueprint $table): void {
            $table->id();
            $table->uuid('social_account_id');
            $table->string('item_id', 32);
            $table->timestamp('taken_at');
            $table->unsignedBigInteger('views')->default(0);
            $table->unsignedBigInteger('likes')->default(0);
            $table->unsignedBigInteger('comments')->default(0);
            $table->unsignedBigInteger('shares')->default(0);
            $table->unsignedBigInteger('saves')->default(0);

            $table->index(['item_id', 'taken_at']);
        });

        Schema::create('fork_account_stats', function (Blueprint $table): void {
            $table->id();
            $table->uuid('social_account_id');
            $table->date('date');
            $table->unsignedBigInteger('followers')->nullable();
            $table->jsonb('history')->nullable();
            $table->timestamp('collected_at');
            $table->timestamps();

            $table->unique(['social_account_id', 'date']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_account_stats');
        Schema::dropIfExists('fork_video_snapshots');
        Schema::dropIfExists('fork_video_stats');
    }
};
