<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_chrome_accounts', function (Blueprint $table): void {
            $table->foreignUuid('social_account_id')->primary()->constrained('social_accounts')->cascadeOnDelete();
            $table->boolean('enabled')->default(false);
            $table->string('tiktok_user_id')->nullable()->index();
            $table->boolean('chrome_only')->default(false);
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_chrome_accounts');
    }
};
