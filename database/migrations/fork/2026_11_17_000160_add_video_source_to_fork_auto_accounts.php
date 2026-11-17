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
            // Nguồn video của kênh: both = Xưởng + Kho riêng, rieng = chỉ Kho riêng, hub = chỉ Xưởng.
            $table->string('video_source', 10)->default('both');
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_accounts', function (Blueprint $table): void {
            $table->dropColumn('video_source');
        });
    }
};
