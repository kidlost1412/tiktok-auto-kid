<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Nhật ký "đã xét" lựa chọn sản phẩm Shop của hub cho từng ô giỏ hàng (kênh, mã hub, quy cách).
        // Mỗi lựa chọn chỉ được tự gắn MỘT lần: chủ app bỏ chọn sau đó thì app không gắn lại.
        Schema::create('fork_cart_auto_attach', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('social_account_id')->constrained('social_accounts')->cascadeOnDelete();
            $table->string('auto_product_id');
            // '' = sản phẩm không có quy cách (không dùng NULL để chỉ mục duy nhất chạy giống nhau trên mọi CSDL).
            $table->string('quy_cach')->default('');
            $table->string('shop_product_id', 32);
            // true = app đã tạo liên kết; false = ô đã có liên kết chủ app chọn tay nên không đụng.
            $table->boolean('attached')->default(false);
            $table->timestamps();

            $table->unique(['social_account_id', 'auto_product_id', 'quy_cach', 'shop_product_id'], 'fork_cart_auto_attach_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_cart_auto_attach');
    }
};
