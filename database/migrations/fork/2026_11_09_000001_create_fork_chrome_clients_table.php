<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_chrome_clients', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('account_id')->constrained()->cascadeOnDelete();
            $table->string('label', 128);
            $table->string('token_hash', 64)->unique();
            $table->string('ext_version', 32);
            $table->integer('protocol');
            $table->string('tiktok_username')->nullable();
            $table->string('tiktok_user_id')->nullable()->index();
            $table->string('chrome_profile_dir')->nullable();
            $table->timestamp('last_seen_at')->nullable();
            $table->timestamp('last_launch_at')->nullable();
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_chrome_clients');
    }
};
