<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (! Schema::hasColumn('fork_product_links', 'quy_cach')) {
            Schema::table('fork_product_links', function (Blueprint $table): void {
                // Quy cách (mã `ma` trong fork_auto_products.quy_cach); null = sản phẩm chỉ có một quy cách.
                $table->string('quy_cach')->nullable();
            });
        }

        Schema::table('fork_product_links', function (Blueprint $table): void {
            $table->dropUnique(['social_account_id', 'auto_product_id']);
        });

        if (DB::getDriverName() === 'pgsql') {
            // NULL coi như một giá trị: mỗi (kênh, mã hub) chỉ có một liên kết "không quy cách".
            DB::statement('CREATE UNIQUE INDEX fork_product_links_account_product_qc_unique ON fork_product_links (social_account_id, auto_product_id, COALESCE(quy_cach, \'\'))');
        } else {
            Schema::table('fork_product_links', function (Blueprint $table): void {
                $table->unique(['social_account_id', 'auto_product_id', 'quy_cach'], 'fork_product_links_account_product_qc_unique');
            });
        }
    }

    public function down(): void
    {
        Schema::table('fork_product_links', function (Blueprint $table): void {
            $table->dropUnique('fork_product_links_account_product_qc_unique');
        });

        DB::table('fork_product_links')->whereNotNull('quy_cach')->delete();

        Schema::table('fork_product_links', function (Blueprint $table): void {
            $table->dropColumn('quy_cach');
            $table->unique(['social_account_id', 'auto_product_id']);
        });
    }
};
