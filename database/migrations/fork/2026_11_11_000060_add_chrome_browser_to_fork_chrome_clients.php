<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_chrome_clients', function (Blueprint $table): void {
            // chrome | edge; null = chrome (bản ghi cũ).
            $table->string('chrome_browser', 16)->nullable()->after('chrome_profile_dir');
        });
    }

    public function down(): void
    {
        Schema::table('fork_chrome_clients', function (Blueprint $table): void {
            $table->dropColumn('chrome_browser');
        });
    }
};
