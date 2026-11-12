<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Users without a chosen clock get the one they already see: English a
     * 12-hour clock, every other language a 24-hour one.
     */
    public function up(): void
    {
        DB::table('users')
            ->whereNull('time_format')
            ->where('locale', 'en')
            ->update(['time_format' => '12h']);

        DB::table('users')
            ->whereNull('time_format')
            ->update(['time_format' => '24h']);

        Schema::table('users', function (Blueprint $table): void {
            $table->string('time_format', 8)->default('12h')->nullable(false)->change();
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table): void {
            $table->string('time_format', 8)->nullable()->default(null)->change();
        });
    }
};
