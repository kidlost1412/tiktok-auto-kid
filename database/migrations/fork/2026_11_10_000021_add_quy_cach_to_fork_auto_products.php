<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('fork_auto_products', function (Blueprint $table): void {
            // [{"ma":"1l","ten":"Chai 1L"}, ...]; rỗng/null = chỉ một quy cách.
            $table->jsonb('quy_cach')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('fork_auto_products', function (Blueprint $table): void {
            $table->dropColumn('quy_cach');
        });
    }
};
