<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_product_links', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('social_account_id')->constrained('social_accounts')->cascadeOnDelete();
            // Mã hub (fork_auto_products.code).
            $table->string('auto_product_id');
            $table->string('shop_product_id', 32);
            $table->string('display_name', 30);
            // Có giá trị = mã này tạm dừng trên kênh cho tới khi chủ app lưu lại liên kết.
            $table->string('paused_reason')->nullable();
            $table->timestamps();

            $table->unique(['social_account_id', 'auto_product_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_product_links');
    }
};
