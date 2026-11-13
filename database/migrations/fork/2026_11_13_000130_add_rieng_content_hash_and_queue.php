<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Chỉ thêm, không sửa gì cũ:
 *  - `content_hash`: sha256 nội dung thật của video riêng. Cột `hash` vẫn UNIQUE; bản trùng nội dung được nhận vào với
 *    `hash` riêng (dẫn xuất từ nội dung + đường dẫn) và `content_hash` = sha256 thật, để biết nó trùng với video nào.
 *  - `fork_rieng_queue`: "Giỏ chờ đăng" của chủ app (video riêng chọn sẵn, chưa hẹn giờ), giữ qua các lần tải lại trang.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            $table->string('content_hash', 64)->nullable()->index();
        });

        Schema::create('fork_rieng_queue', function (Blueprint $table): void {
            $table->id();
            $table->string('owner', 64);
            $table->foreignId('auto_video_id')->constrained('fork_auto_videos')->cascadeOnDelete();
            $table->timestamps();

            $table->unique(['owner', 'auto_video_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_rieng_queue');

        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            $table->dropColumn('content_hash');
        });
    }
};
