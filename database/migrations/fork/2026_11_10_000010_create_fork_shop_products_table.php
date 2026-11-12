<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_shop_products', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('social_account_id')->constrained('social_accounts')->cascadeOnDelete();
            // Luôn là chuỗi: ID TikTok Shop dài 19 chữ số, ép sang số sẽ mất chính xác.
            $table->string('product_id', 32);
            $table->string('source', 16)->default('my_shop');
            $table->text('title');
            $table->string('price')->nullable();
            $table->text('cover_url')->nullable();
            $table->integer('stock_num')->default(0);
            $table->string('stock_status', 32)->nullable();
            $table->boolean('hidden')->default(false);
            $table->boolean('missing')->default(false);
            $table->timestamp('synced_at')->nullable();
            $table->timestamps();

            $table->unique(['social_account_id', 'product_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_shop_products');
    }
};
