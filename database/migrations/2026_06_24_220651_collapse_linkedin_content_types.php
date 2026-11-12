<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * LinkedIn no longer has per-format content types — the publish format is
     * inferred from the attached media. Collapse the old carousel/document
     * variants back onto the single post type for each account kind.
     */
    public function up(): void
    {
        DB::table('post_platforms')
            ->whereIn('content_type', ['linkedin_carousel', 'linkedin_document'])
            ->update(['content_type' => 'linkedin_post']);

        DB::table('post_platforms')
            ->whereIn('content_type', ['linkedin_page_carousel', 'linkedin_page_document'])
            ->update(['content_type' => 'linkedin_page_post']);
    }

    public function down(): void
    {
        // Irreversible: the per-format variants were merged into the single post
        // type and the original distinction is no longer recoverable.
    }
};
