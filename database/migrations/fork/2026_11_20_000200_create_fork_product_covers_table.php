<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Ảnh bìa riêng tách theo KÊNH: trước đây lưu trên sản phẩm hub (fork_auto_products.cover_*) nên cài bìa ở giỏ của một kênh
 * thì mọi kênh cùng sản phẩm đều dùng. Nay mỗi (kênh, mã hub) một bộ. Bộ cũ được chép sang mọi kênh đang gắn giỏ sản phẩm đó
 * (giữ nguyên cách đăng hiện tại, không mất ảnh); cột cũ để lại, không còn đọc.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('fork_product_covers', function (Blueprint $table): void {
            $table->id();
            $table->foreignUuid('social_account_id')->constrained('social_accounts')->cascadeOnDelete();
            $table->string('auto_product_id');
            $table->string('cover_mode', 16)->default('default');
            $table->jsonb('cover_images')->nullable();
            $table->string('cover_fixed')->nullable();
            $table->string('cover_last')->nullable();
            $table->timestamps();
            $table->unique(['social_account_id', 'auto_product_id']);
        });

        $now = now();
        $products = DB::table('fork_auto_products')
            ->where(fn ($q) => $q->where('cover_mode', '<>', 'default')->orWhereNotNull('cover_images'))
            ->get(['code', 'cover_mode', 'cover_images', 'cover_fixed', 'cover_last']);

        foreach ($products as $p) {
            $images = json_decode((string) $p->cover_images, true);

            if ($p->cover_mode === 'default' && (! is_array($images) || $images === [])) {
                continue;
            }

            $accounts = DB::table('fork_product_links')->where('auto_product_id', $p->code)->distinct()->pluck('social_account_id');

            foreach ($accounts as $acc) {
                DB::table('fork_product_covers')->insertOrIgnore([
                    'social_account_id' => $acc,
                    'auto_product_id' => $p->code,
                    'cover_mode' => $p->cover_mode,
                    'cover_images' => $p->cover_images,
                    'cover_fixed' => $p->cover_fixed,
                    'cover_last' => $p->cover_last,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]);
            }
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('fork_product_covers');
    }
};
