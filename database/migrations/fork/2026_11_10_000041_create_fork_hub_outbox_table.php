<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Hàng đợi báo ngược về hub (da-dang, loi, so-lieu): hub tắt thì giữ lại và thử lại sau.
        Schema::create('fork_hub_outbox', function (Blueprint $table): void {
            $table->id();
            $table->string('kind', 20);
            $table->string('hub_id');
            $table->jsonb('payload');
            $table->unsignedInteger('attempts')->default(0);
            $table->timestamp('next_attempt_at')->nullable();
            $table->string('last_error')->nullable();
            $table->timestamps();
            $table->index(['next_attempt_at', 'id']);
            $table->index(['kind', 'hub_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_hub_outbox');
    }
};
