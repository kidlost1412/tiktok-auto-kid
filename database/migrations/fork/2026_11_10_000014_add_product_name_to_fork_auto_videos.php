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
            $table->string('product_name', 30)->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_videos', function (Blueprint $table): void {
            $table->dropColumn('product_name');
        });
    }
};
