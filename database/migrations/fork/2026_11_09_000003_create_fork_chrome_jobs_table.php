<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_chrome_jobs', function (Blueprint $table): void {
            $table->string('id')->primary();
            $table->foreignUuid('post_id')->constrained('posts')->cascadeOnDelete();
            $table->uuid('social_account_id')->index();
            $table->integer('attempt');
            $table->string('mode', 16);
            $table->string('expect_user_id');
            $table->string('media_path', 1024);
            $table->string('video_name');
            $table->unsignedBigInteger('video_size')->nullable();
            $table->string('video_mime', 64)->nullable();
            $table->text('caption')->nullable();
            $table->jsonb('options');
            $table->string('state', 16)->default('queued')->index();
            $table->string('nonce', 64);
            $table->string('claim_token', 64)->nullable();
            $table->unsignedBigInteger('claim_client_id')->nullable();
            $table->timestamp('claimed_at')->nullable();
            $table->timestamp('heartbeat_at')->nullable();
            $table->timestamp('authorized_at')->nullable();
            $table->string('auth_sha', 64)->nullable();
            $table->string('auth_creation_id')->nullable();
            $table->boolean('cancel_requested')->default(false);
            $table->jsonb('result')->nullable();
            $table->timestamp('result_at')->nullable();
            $table->integer('duplicate_results')->default(0);
            $table->text('note')->nullable();
            $table->timestamp('launched_at')->nullable();
            $table->timestamp('deliver_by')->nullable();
            $table->timestamps();

            $table->unique(['post_id', 'attempt']);
        });

        // Mỗi tài khoản chỉ có một job mở (chưa tới trạng thái cuối).
        DB::statement(
            "CREATE UNIQUE INDEX fork_chrome_jobs_one_open_per_account ON fork_chrome_jobs (social_account_id) WHERE state IN ('queued','claimed','uploading','ready','authorized')"
        );
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_chrome_jobs');
    }
};
