<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_anchor_templates', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('social_account_id')->unique()->constrained('social_accounts')->cascadeOnDelete();
            // product_id của bài mẫu: để biết chỗ nào trong anchors phải thay.
            $table->string('product_id', 32);
            $table->jsonb('anchors');
            $table->timestamp('captured_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_anchor_templates');
    }
};
