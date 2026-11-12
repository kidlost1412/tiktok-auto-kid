<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_auto_videos', function (Blueprint $table): void {
            $table->id();
            $table->string('hash', 64)->unique();
            $table->text('path');
            $table->date('batch_date');
            $table->string('file_name');
            $table->string('product_code')->nullable()->index();
            foreach (['goc', 'giong', 'nhac', 'font', 'phu_de', 'chuyen_canh', 'chuyen_dong', 'mau'] as $column) {
                $table->string($column)->nullable();
            }
            $table->float('duration')->nullable();
            $table->text('script')->nullable();
            $table->string('status')->default('new');
            $table->string('skip_reason')->nullable();
            $table->uuid('social_account_id')->nullable();
            $table->uuid('post_id')->nullable()->index();
            $table->text('caption')->nullable();
            $table->jsonb('hashtags')->nullable();
            $table->string('caption_source')->nullable();
            $table->timestamp('scheduled_for')->nullable();
            $table->timestamp('posted_at')->nullable();
            $table->string('tiktok_video_id')->nullable();
            $table->jsonb('stats')->nullable();
            $table->timestamp('stats_written_at')->nullable();
            $table->timestamps();

            $table->index(['status', 'batch_date']);
            $table->index(['social_account_id', 'scheduled_for']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_auto_videos');
    }
};
