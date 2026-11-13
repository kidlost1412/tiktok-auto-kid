<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Thư mục "Kho riêng": nơi chủ app để video tự làm. App chỉ đọc, không bao giờ dời hay xoá file trong đó.
        Schema::create('fork_rieng_folders', function (Blueprint $table): void {
            $table->id();
            $table->text('path');
            $table->string('name')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_rieng_folders');
    }
};
