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
            $table->string('products_sync_request')->nullable();
            $table->timestamp('products_synced_at')->nullable();
            // Mặc định số bài/ngày: 8 (chủ app chọn). Hàng đã có giữ nguyên giá trị.
            $table->unsignedSmallInteger('daily_cap')->default(8)->change();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            $table->dropColumn(['products_sync_request', 'products_synced_at']);
            $table->unsignedSmallInteger('daily_cap')->default(20)->change();
        });
    }
};
