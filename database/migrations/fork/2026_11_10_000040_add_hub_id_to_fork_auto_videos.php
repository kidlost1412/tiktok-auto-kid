<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            // id của video bên hub Xưởng Video (chế độ API); null = nhặt từ thư mục.
            $table->string('hub_id')->nullable()->unique();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            $table->dropUnique(['hub_id']);
            $table->dropColumn('hub_id');
        });
    }
};
