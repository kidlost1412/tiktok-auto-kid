<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_auto_accounts', function (Blueprint $table): void {
            $table->foreignUuid('social_account_id')->primary()->constrained('social_accounts')->cascadeOnDelete();
            $table->boolean('enabled')->default(false);
            $table->unsignedSmallInteger('daily_cap')->default(20);
            $table->unsignedSmallInteger('window_start')->default(6);
            $table->unsignedSmallInteger('window_end')->default(23);
            $table->string('mode')->default('explore');
            $table->jsonb('preferred_hours')->nullable();
            $table->float('explore_ratio')->default(0.2);
            $table->string('paused_reason')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_auto_accounts');
    }
};
