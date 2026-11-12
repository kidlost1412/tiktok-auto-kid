<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /** Đánh dấu onboarding đã xong cho các account có sẵn (bảng accounts không còn model onboarding). */
    public function up(): void
    {
        $now = now();

        DB::table('accounts')
            ->whereNull('onboarding_dismissed_at')
            ->whereNull('onboarding_completed_at')
            ->update(['onboarding_completed_at' => $now, 'updated_at' => $now]);
    }

    public function down(): void
    {
        DB::table('accounts')
            ->whereNull('onboarding_dismissed_at')
            ->whereNotNull('onboarding_completed_at')
            ->update(['onboarding_completed_at' => null, 'updated_at' => now()]);
    }
};
