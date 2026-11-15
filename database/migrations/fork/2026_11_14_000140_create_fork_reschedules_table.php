<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * "Đổi giờ" một bài đã hẹn sẵn trên TikTok: TikTok không cho sửa giờ hẹn, nên app nhờ tiện ích Chrome xoá hẳn bài hẹn cũ
 * (kiểm lại bằng danh sách bài của TikTok Studio) rồi mới đặt giờ mới và tải lên lại. Mỗi dòng là một yêu cầu như vậy.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_reschedules', function (Blueprint $table): void {
            $table->string('id')->primary();
            $table->unsignedBigInteger('auto_video_id')->index();
            $table->uuid('post_id')->index();
            $table->uuid('social_account_id')->index();
            $table->string('chrome_job_id');
            $table->string('item_id', 32);
            $table->string('expect_user_id');
            $table->timestamp('old_at');
            $table->timestamp('new_at');
            $table->bigInteger('schedule_unix');
            $table->string('state', 16)->default('pending')->index();
            $table->string('nonce', 64);
            $table->unsignedBigInteger('claim_client_id')->nullable();
            $table->timestamp('claimed_at')->nullable();
            $table->jsonb('result')->nullable();
            $table->text('message')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });

        // Mỗi bài chỉ có một yêu cầu đổi giờ đang chạy.
        DB::statement("CREATE UNIQUE INDEX fork_reschedules_one_open_per_post ON fork_reschedules (post_id) WHERE state IN ('pending','claimed')");
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_reschedules');
    }
};
