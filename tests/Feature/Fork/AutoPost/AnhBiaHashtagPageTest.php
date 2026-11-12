<?php

declare(strict_types=1);

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
});

test('the Ảnh bìa & hashtag page lists enabled products with cover, hashtag and caption preview', function (): void {
    AutoProduct::query()->create([
        'code' => 'bon-la', 'name' => 'Bón lá nguyên chất', 'short_name' => 'Bón lá', 'facts' => [], 'enabled' => true,
        'quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']],
        'cover_mode' => 'random',
        'cover_images' => [
            ['file' => 'a.jpg', 'name' => 'a', 'w' => 1080, 'h' => 1440, 'size' => 1000],
            ['file' => 'b.jpg', 'name' => 'b', 'w' => 1080, 'h' => 1440, 'size' => 1000],
        ],
        'hashtags' => ['#rieng'], 'hashtag_mode' => 'append', 'hashtag_pick' => 0,
    ]);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    AutoProduct::query()->create(['code' => 'tat', 'name' => 'Đã tắt', 'short_name' => 'Đã tắt', 'facts' => [], 'enabled' => false]);
    Hashtags::saveDefaults('#chung', 'append', 0);

    AutoVideo::query()->create([
        'hash' => 'h1', 'path' => '/x.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'x.mp4', 'product_code' => 'bon-la',
        'quy_cach' => '1l', 'status' => 'new', 'caption' => 'Cây khoẻ #damca', 'hashtags' => ['#hub'],
    ]);

    $expected = HubText::compose('Cây khoẻ #damca', ['#hub', '#rieng']);

    $this->actingAs($this->owner)->get('/auto/anh-bia-hashtag')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/AnhBiaHashtag')
        ->has('products', 2)
        ->where('products.0.code', 'bon-la')
        ->where('products.0.name', 'Bón lá')
        ->where('products.0.quy_cach', ['Chai 1L', 'Can 5L'])
        ->where('products.0.videos_waiting', 1)
        ->where('products.0.caption.text', $expected)
        ->where('products.0.caption.source', 'video')
        ->where('products.0.caption.source_hashtags', 'product')
        ->where('products.1.code', 'nano-dong')
        ->where('products.1.caption.source', 'sample')
        ->where('products.1.caption.source_hashtags', 'default')
        ->where('personalise.bon-la.cover_mode', 'random')
        ->has('personalise.bon-la.covers', 2)
        ->where('personalise.bon-la.covers.0.url', '/auto/anh-bia/bon-la/a.jpg')
        ->where('personalise.bon-la.hashtags', ['#rieng'])
        ->where('personalise.nano-dong.cover_mode', 'default')
        ->missing('personalise.tat')
        ->where('personalise_default.tags', ['#chung']));
});

test('the sample caption picks up the default hashtags for products without their own', function (): void {
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    Hashtags::saveDefaults('#chung', 'append', 0);

    $this->actingAs($this->owner)->get('/auto/anh-bia-hashtag')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('products.0.caption.text', fn (string $t): bool => str_contains($t, 'NanoĐồng') && str_ends_with($t, '#chung')));
});

test('the page renders an empty list when no product is enabled', function (): void {
    AutoProduct::query()->create(['code' => 'tat', 'name' => 'Đã tắt', 'short_name' => 'Đã tắt', 'facts' => [], 'enabled' => false]);

    $this->actingAs($this->owner)->get('/auto/anh-bia-hashtag')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/AnhBiaHashtag')
        ->has('products', 0)
        ->where('personalise', [])
        ->where('personalise_default.tags', []));
});

test('the Ảnh bìa & hashtag page is owner-only', function (): void {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->get('/auto/anh-bia-hashtag')->assertForbidden();
});
