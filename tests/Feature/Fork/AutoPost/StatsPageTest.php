<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\Account;
use App\Models\AnalyticsPublication;
use App\Models\AnalyticsPublicationDailySnapshot;
use App\Models\Post;
use App\Models\SocialAccount;
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
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_a']);
    $this->sb = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_b']);

    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    AutoProduct::query()->create(['code' => 'dam-ca', 'name' => 'Đạm cá', 'short_name' => 'ĐạmCá', 'facts' => [], 'enabled' => true]);
});

function soLieuVideo(SocialAccount $sa, array $o = [], ?array $snap = null): AutoVideo
{
    static $n = 0;
    $n++;

    $postedAt = $o['posted_at'] ?? now()->subHours(30);
    $post = Post::factory()->create(['workspace_id' => $sa->workspace_id]);

    $v = AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'sl'.$n),
        'path' => "/x/{$n}.mp4",
        'batch_date' => '2026-01-05',
        'file_name' => "s{$n}.mp4",
        'product_code' => 'nano-dong',
        'status' => 'posted',
        'social_account_id' => $sa->id,
        'post_id' => $post->id,
        'posted_at' => $postedAt,
    ], $o));

    if ($snap !== null) {
        $pub = AnalyticsPublication::factory()->create([
            'workspace_id' => $sa->workspace_id,
            'social_account_id' => $sa->id,
            'post_id' => $post->id,
            'permalink' => 'https://www.tiktok.com/@a/video/'.$n,
        ]);
        AnalyticsPublicationDailySnapshot::factory()->create(array_merge([
            'publication_id' => $pub->id,
            'date' => now()->toDateString(),
            'collected_at' => now(),
            'provider_observed_at' => now(),
        ], $snap));
    }

    return $v;
}

test('stats page is forbidden for non owners and guests', function (): void {
    $this->get('/auto/so-lieu')->assertRedirect();

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->get('/auto/so-lieu')->assertForbidden();
});

test('stats aggregates views and engagement from snapshots with delta vs previous period', function (): void {
    soLieuVideo($this->sa, ['goc' => 'than-thien', 'giong' => 'nu'], ['views_count' => 1000, 'reactions_count' => 80, 'comments_count' => 10, 'shares_count' => 10]);
    soLieuVideo($this->sa, ['goc' => 'than-thien', 'giong' => 'nam'], ['views_count' => 500, 'reactions_count' => 20, 'comments_count' => 0, 'shares_count' => 0]);
    // Kỳ trước (7 ngày liền trước): 750 view.
    soLieuVideo($this->sa, ['posted_at' => now()->subDays(9)], ['views_count' => 750, 'reactions_count' => 0, 'comments_count' => 0, 'shares_count' => 0]);

    $this->actingAs($this->owner)->get('/auto/so-lieu?range=7d')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/SoLieu')
        ->where('kpis.posts.value', 2)
        ->where('kpis.views.value', 1500)
        ->where('kpis.avg_views.value', 750)
        ->where('kpis.likes.value', 100)
        ->where('kpis.engagement.value', 8)
        ->where('kpis.posts.prev', 1)
        ->where('kpis.views.delta_pct', 100)
        ->where('videos_total', 2)
        ->where('videos.0.link', fn ($l) => str_starts_with((string) $l, 'https://www.tiktok.com/'))
        ->has('daily', 7)
        ->where('breakdowns.goc.0.key', 'than-thien')
        ->where('breakdowns.goc.0.posts', 2)
    );
});

test('stats falls back to AutoVideo.stats when there is no snapshot', function (): void {
    soLieuVideo($this->sa, ['stats' => ['latest' => ['views' => 321, 'likes' => 3, 'comments' => 0, 'shares' => 0], 'h24' => ['views' => 200], 'link' => 'https://www.tiktok.com/@a/video/9']]);

    $this->actingAs($this->owner)->get('/auto/so-lieu')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('kpis.views.value', 321)
        ->where('videos.0.views_24h', 200)
        ->where('videos.0.link', 'https://www.tiktok.com/@a/video/9')
    );
});

test('stats filters by channel product goc giong and sorts', function (): void {
    soLieuVideo($this->sa, ['product_code' => 'nano-dong', 'goc' => 'g1', 'giong' => 'nu'], ['views_count' => 100]);
    soLieuVideo($this->sb, ['product_code' => 'dam-ca', 'goc' => 'g2', 'giong' => 'nam'], ['views_count' => 900]);
    soLieuVideo($this->sb, ['product_code' => 'nano-dong', 'goc' => 'g2', 'giong' => 'nam'], ['views_count' => 300]);

    $get = fn (string $q) => $this->actingAs($this->owner)->get('/auto/so-lieu?'.$q);

    $get('channel='.$this->sa->id)->assertInertia(fn (AssertableInertia $p) => $p->where('kpis.posts.value', 1)->where('kpis.views.value', 100));
    $get('product=dam-ca')->assertInertia(fn (AssertableInertia $p) => $p->where('kpis.views.value', 900));
    $get('goc=g2&giong=nam')->assertInertia(fn (AssertableInertia $p) => $p->where('kpis.posts.value', 2));
    $get('sort=view')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.0.views', 900)->where('videos.2.views', 100)->where('top.0.views', 900));
    $get('range=today')->assertInertia(fn (AssertableInertia $p) => $p->where('kpis.posts.value', 0)->has('daily', 1));
    $get('range=custom&from=2020-01-01&to=2020-01-03')->assertInertia(fn (AssertableInertia $p) => $p->where('kpis.posts.value', 0)->has('daily', 3));
});

test('stats only counts videos of the owners tiktok accounts', function (): void {
    $otherAccount = Account::factory()->create();
    $otherUser = User::factory()->create(['account_id' => $otherAccount->id]);
    $otherAccount->update(['owner_id' => $otherUser->id]);
    $otherWs = Workspace::factory()->create(['account_id' => $otherAccount->id, 'user_id' => $otherUser->id]);
    $other = SocialAccount::factory()->tiktok()->create(['workspace_id' => $otherWs->id]);

    soLieuVideo($this->sa, [], ['views_count' => 10]);
    soLieuVideo($other, [], ['views_count' => 99999]);

    $this->actingAs($this->owner)->get('/auto/so-lieu')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('kpis.views.value', 10)
        ->has('options.channels', 2)
    );

    $this->actingAs($this->owner)->get('/auto/so-lieu?channel='.$other->id)->assertInertia(fn (AssertableInertia $p) => $p->where('kpis.posts.value', 0));
});

test('stats page renders an empty state when there are no channels at all', function (): void {
    SocialAccount::query()->where('workspace_id', $this->workspace->id)->delete();

    $this->actingAs($this->owner)->get('/auto/so-lieu')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/SoLieu')
        ->where('videos_total', 0)
        ->where('options.channels', [])
        ->where('options.goc', [])
        ->where('metrics_count', 0)
    );
});

test('every auto page renders with zero channels', function (): void {
    SocialAccount::query()->where('workspace_id', $this->workspace->id)->delete();

    foreach (['/auto', '/auto/kho', '/auto/gio-hang', '/auto/so-lieu'] as $path) {
        $this->actingAs($this->owner)->get($path)->assertOk();
    }
});
