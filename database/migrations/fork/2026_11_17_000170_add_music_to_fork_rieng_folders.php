<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_rieng_folders', function (Blueprint $table): void {
            // Ghép nhạc hàng loạt: {enabled, dir, mode: replace|mix, gain_db}.
            $table->json('music')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_rieng_folders', function (Blueprint $table): void {
            $table->dropColumn('music');
        });
    }
};
