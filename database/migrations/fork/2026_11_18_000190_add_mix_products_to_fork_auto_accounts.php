<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            // Tự trộn xen kẽ sản phẩm cho các bài đã xếp lịch mà chưa gửi lên TikTok (ProductMix).
            $table->boolean('mix_products')->default(false);
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            $table->dropColumn('mix_products');
        });
    }
};
