<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_a']);
    $this->sb = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_b']);

    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    AutoProduct::query()->create(['code' => 'dam-ca', 'name' => 'Đạm cá', 'short_name' => 'ĐạmCá', 'facts' => [], 'enabled' => true]);
});

/** Bài đã đăng có số liệu dự phòng (AutoVideo.stats), không cần ảnh chụp số liệu. */
function sortVideo(SocialAccount $sa, int $hoursAgo, int $views, array $o = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'ss'.$n),
        'path' => "/x/ss{$n}.mp4",
        'batch_date' => '2026-01-05',
        'file_name' => "ss{$n}.mp4",
        'product_code' => 'nano-dong',
        'status' => 'posted',
        'social_account_id' => $sa->id,
        'posted_at' => now()->subHours($hoursAgo),
        'stats' => ['latest' => ['views' => $views, 'likes' => $views % 7, 'comments' => 0, 'shares' => 0]],
    ], $o));
}

test('sort runs over every row before the list is cut, with a whitelisted key and direction', function (): void {
    // 65 bài: bài CŨ NHẤT có nhiều view nhất (không nằm trong 60 bài mới nhất).
    for ($i = 1; $i <= 65; $i++) {
        sortVideo($this->sa, $i + 1, $i === 65 ? 100000 : $i * 10);
    }

    $get = fn (string $q) => $this->actingAs($this->owner)->get('/auto/so-lieu?range=7d&'.$q);

    $get('')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.sort', 'moi')->where('filters.dir', 'desc')->where('filters.limit', 60)
        ->where('videos_total', 65)->has('videos', 60)
        ->where('videos.0.views', 10));

    $get('sort=view')->assertInertia(fn (AssertableInertia $p) => $p
        ->has('videos', 60)->where('videos.0.views', 100000)->where('videos.1.views', 640));

    $get('sort=view&dir=asc')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.dir', 'asc')->has('videos', 60)->where('videos.0.views', 10)->where('videos.1.views', 20));

    $get('sort=moi&dir=asc')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('videos.0.views', 100000));

    $get('sort=view&limit=120')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.limit', 120)->has('videos', 65)->where('videos_total', 65));

    // Giá trị lạ rơi về mặc định, giới hạn bị chặn trên.
    $get('sort=evil&dir=sideways&limit=99999')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.sort', 'moi')->where('filters.dir', 'desc')->where('filters.limit', 600));
    $get('limit=-5')->assertInertia(fn (AssertableInertia $p) => $p->where('filters.limit', 60));
});

test('sort supports likes comments shares and engagement keys', function (): void {
    sortVideo($this->sa, 3, 1000, ['stats' => ['latest' => ['views' => 1000, 'likes' => 5, 'comments' => 1, 'shares' => 0]]]);
    sortVideo($this->sa, 4, 100, ['stats' => ['latest' => ['views' => 100, 'likes' => 50, 'comments' => 0, 'shares' => 9]]]);
    sortVideo($this->sa, 5, 500, ['stats' => ['latest' => ['views' => 500, 'likes' => 1, 'comments' => 40, 'shares' => 1]]]);

    $get = fn (string $q) => $this->actingAs($this->owner)->get('/auto/so-lieu?'.$q);

    $get('sort=tim')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.0.likes', 50));
    $get('sort=binh-luan')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.0.comments', 40));
    $get('sort=chia-se')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.0.shares', 9));
    $get('sort=ty-le')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.0.views', 100));
    $get('sort=tuong-tac&dir=asc')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.0.views', 1000));
});

test('new period presets and the channel breakdown', function (): void {
    $tz = Planner::zone()->getName();
    $today = CarbonImmutable::now($tz)->startOfDay();
    $get = fn (string $q) => $this->actingAs($this->owner)->get('/auto/so-lieu?'.$q);

    $get('range=yesterday')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.range', 'yesterday')
        ->where('filters.from', $today->subDay()->format('Y-m-d'))
        ->where('filters.to', $today->subDay()->format('Y-m-d')));
    $get('range=this-month')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.from', $today->startOfMonth()->format('Y-m-d'))
        ->where('filters.to', $today->format('Y-m-d')));
    $get('range=last-month')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('filters.from', $today->subMonthNoOverflow()->startOfMonth()->format('Y-m-d'))
        ->where('filters.to', $today->startOfMonth()->subDay()->format('Y-m-d')));

    sortVideo($this->sa, 3, 100);
    sortVideo($this->sa, 4, 300);
    sortVideo($this->sb, 5, 900);
    $get('range=7d')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('breakdowns.channel.0.label', '@kenh_b')
        ->where('breakdowns.channel.0.key', (string) $this->sb->id)
        ->where('breakdowns.channel.1.posts', 2));
});

test('comments follow the date range and the product filter', function (): void {
    $inRange = sortVideo($this->sa, 5, 100, ['product_code' => 'nano-dong']);
    $other = sortVideo($this->sa, 6, 100, ['product_code' => 'dam-ca']);

    $comment = function (AutoVideo $v, string $id, $at, bool $buy = false) {
        VideoComment::query()->create([
            'comment_id' => $id, 'social_account_id' => $this->sa->id, 'item_id' => 'i'.$id, 'auto_video_id' => $v->id,
            'text' => 'bình luận '.$id, 'commented_at' => $at, 'is_buy_intent' => $buy,
        ]);
    };
    $comment($inRange, 'c1', now()->subHours(2), true);
    $comment($inRange, 'c2', now()->subHours(3));
    $comment($other, 'c3', now()->subHours(4), true);
    $comment($inRange, 'c4', now()->subDays(40), true); // ngoài khoảng 7 ngày

    $get = fn (string $q) => $this->actingAs($this->owner)->get('/auto/so-lieu?'.$q);

    $get('range=7d')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('comments.counts.total', 3)->where('comments.counts.buy', 2)->has('comments.rows', 3));
    $get('range=7d&product=nano-dong')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('comments.counts.total', 2)->where('comments.counts.buy', 1)->has('comments.rows', 2));
    $get('range=30d&cm=mua')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('comments.counts.buy', 2)->has('comments.rows', 2));
    $get('range=custom&from=2000-01-01&to=2000-01-02')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('comments.counts.total', 0)->where('comments.counts.buy_24h', 2));
});
