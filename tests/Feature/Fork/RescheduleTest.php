<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\Reschedule;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\PostEdits;
use App\Fork\AutoPost\Scheduling\Reschedules;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Media;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;

const RS_UID = '7012345678901234599';
const RS_ITEM = '7570000000000000777';

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.auto.hub_api.key', '');
    // Đĩa riêng cho mỗi test (các agent khác chạy song song).
    $this->disk = 'rs_test_'.bin2hex(random_bytes(4));
    $this->root = storage_path('framework/testing/disks/'.$this->disk);
    config(['filesystems.disks.'.$this->disk => ['driver' => 'local', 'root' => $this->root, 'throw' => false], 'filesystems.default' => $this->disk]);
    Cache::flush();

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->social = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_rs',
    ]);
    ChromeAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'tiktok_user_id' => RS_UID, 'chrome_only' => false]);
    AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 40, 'window_start' => 0, 'window_end' => 24]);

    $chrome = app(ChromeJobs::class);
    $made = $chrome->createClient($account->id, 'Chrome test', '1.4.6', 1);
    $chrome->touch($made['client'], 1, ['tiktok_user_id' => RS_UID, 'tiktok_username' => 'kenh_rs']);
    $this->client = $made['client']->refresh();
    $this->token = $made['token'];
});

afterEach(function (): void {
    File::deleteDirectory($this->root);
});

/** Bài hẹn giờ + video (hub hoặc riêng) của kênh, giờ cũ = $at. */
function rsPost(object $t, CarbonImmutable $at, string $source = 'hub', ?SocialAccount $social = null): array
{
    static $n = 0;
    $n++;
    $social ??= $t->social;
    $file = "v/rs{$n}.mp4";
    Storage::put($file, 'video-bytes');
    $post = Post::factory()->forAccount($social)->create([
        'content' => 'xin chào '.$n,
        'media' => [['id' => 'm'.$n, 'path' => $file, 'url' => 'http://x/'.$file, 'type' => 'video', 'mime_type' => 'video/mp4', 'original_filename' => "rs{$n}.mp4", 'size' => 11]],
        'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE', 'allow_comments' => true],
        'status' => PostStatus::Scheduled,
        'scheduled_at' => $at->utc(),
    ]);
    $video = AutoVideo::query()->create([
        'hash' => hash('sha256', 'rs'.$n.random_int(0, 99999)), 'path' => "/nonexistent/rs{$n}.mp4", 'batch_date' => '2026-11-14', 'file_name' => "rs{$n}.mp4",
        'product_code' => 'p1', 'status' => AutoVideo::SCHEDULED, 'source' => $source, 'caption' => 'Cap '.$n,
        'social_account_id' => $social->id, 'post_id' => $post->id, 'scheduled_for' => $at->utc(),
    ]);

    return [$post, $video];
}

function rsJob(Post $post, string $state, array $result = ['item_id' => RS_ITEM]): ChromeJob
{
    $attempt = (int) ChromeJob::query()->where('post_id', $post->id)->max('attempt') + 1;

    return ChromeJob::query()->create([
        'id' => 'ej_'.bin2hex(random_bytes(8)), 'post_id' => $post->id, 'social_account_id' => $post->social_account_id, 'attempt' => $attempt,
        'mode' => 'scheduled', 'expect_user_id' => RS_UID, 'media_path' => 'v/x.mp4', 'video_name' => 'x.mp4', 'caption' => 'x',
        'options' => ['visibility_type' => 0, 'schedule_time' => CarbonImmutable::instance($post->scheduled_at)->utc()->format('Y-m-d\TH:i:s\Z')],
        'state' => $state, 'nonce' => bin2hex(random_bytes(8)), 'claim_token' => $state === 'queued' ? null : bin2hex(random_bytes(8)),
        'result' => $state === 'posted' ? $result + ['outcome' => 'posted', 'schedule_time' => CarbonImmutable::instance($post->scheduled_at)->getTimestamp()] : null,
        'result_at' => $state === 'posted' ? now() : null,
    ])->refresh();
}

function rsMove(object $t, AutoVideo $video, CarbonImmutable $at)
{
    return $t->actingAs($t->owner)->postJson("/auto/videos/{$video->id}/doi-gio", ['at' => $at->toIso8601String()]);
}

function rsExt(object $t): array
{
    return ['Authorization' => 'Bearer '.$t->token, 'X-Autotok-Protocol' => '1', 'X-Requested-With' => 'autotok'];
}

/** Giờ địa phương (Asia/Ho_Chi_Minh) ngày mai lúc $h:$m. */
function rsAt(int $h, int $m = 0): CarbonImmutable
{
    return CarbonImmutable::now('Asia/Ho_Chi_Minh')->addDay()->setTime($h, $m);
}

test('A: bài chưa lên TikTok đổi giờ ngay, job còn xếp hàng bị thu hồi và bài được giao lại với giờ mới', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $old = rsJob($post, 'queued');
    $new = rsAt(15, 30);

    rsMove($this, $video, $new)->assertOk()->assertJson(['ok' => true, 'state' => 'done', 'kind' => 'local']);

    expect($post->refresh()->scheduled_at->equalTo($new))->toBeTrue()
        ->and($video->refresh()->scheduled_for->equalTo($new))->toBeTrue()
        ->and($old->refresh()->state)->toBe('revoked')
        ->and($old->note)->toBe(ChromePostWatcher::EDIT_NOTE);

    $next = app(ChromeJobs::class)->latestForPost($post);
    expect($next->id)->not->toBe($old->id)
        ->and($next->state)->toBe('queued')
        ->and($next->options['schedule_time'])->toBe($new->utc()->format('Y-m-d\TH:i:s\Z'));
});

test('A: video Kho riêng cũng đổi giờ được', function (): void {
    [$post, $video] = rsPost($this, rsAt(9), 'rieng');

    rsMove($this, $video, rsAt(11))->assertOk()->assertJson(['state' => 'done']);
    expect($video->refresh()->scheduled_for->equalTo(rsAt(11)))->toBeTrue();
});

test('từ chối chỉ khi: Chrome đang tải lên, quá sát bây giờ, quá 10 ngày; gần bài khác hay ngoài khung giờ thì vẫn cho đổi', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $job = rsJob($post, 'uploading');

    rsMove($this, $video, rsAt(12))->assertStatus(422)->assertJson(['ok' => false, 'message' => Reschedules::BUSY_TEXT]);
    expect($post->refresh()->scheduled_at->equalTo(rsAt(10)))->toBeTrue();
    $job->update(['state' => 'revoked', 'note' => ChromePostWatcher::EDIT_NOTE]);

    rsMove($this, $video, CarbonImmutable::now()->addMinutes(10))->assertStatus(422)->assertJsonFragment(['ok' => false])
        ->assertJsonPath('message', fn ($m) => str_contains($m, '20 phút'));

    // Ngoài khung giờ đăng của kênh: không còn bị chặn.
    AutoAccount::query()->whereKey($this->social->id)->update(['window_start' => 8, 'window_end' => 20]);
    rsMove($this, $video, rsAt(21))->assertOk()->assertJson(['state' => 'done']);
    expect($post->refresh()->scheduled_at->equalTo(rsAt(21)))->toBeTrue();
    AutoAccount::query()->whereKey($this->social->id)->update(['window_start' => 0, 'window_end' => 24]);

    // Sát bài khác cùng kênh (10 phút): vẫn cho.
    rsPost($this, rsAt(14));
    rsMove($this, $video, rsAt(14, 10))->assertOk()->assertJson(['state' => 'done']);

    // Giờ mới cách bây giờ 25 phút (>= 20): cho.
    rsMove($this, $video, CarbonImmutable::now()->addMinutes(25))->assertOk();

    rsMove($this, $video, CarbonImmutable::now()->addDays(11))->assertStatus(422);
});

test('describe trả channel_times: giờ các bài khác cùng kênh, không có bài của kênh khác hay của chính bài này', function (): void {
    [, $video] = rsPost($this, rsAt(10));
    rsPost($this, rsAt(14));
    $other = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh']);
    rsPost($this, rsAt(16), 'hub', $other);

    $res = $this->actingAs($this->owner)->getJson("/auto/videos/{$video->id}/doi-gio")->assertOk();
    $times = collect($res->json('channel_times'))->map(fn ($t) => CarbonImmutable::parse($t)->getTimestamp())->all();

    expect($times)->toBe([rsAt(14)->getTimestamp()])
        ->and($res->json('rules.min_lead_minutes'))->toBe(20);
});

test('B: bài đã hẹn trên TikTok chỉ đổi giờ khi Chrome báo đã xoá VÀ đã kiểm lại', function (): void {
    [$post, $video] = rsPost($this, rsAt(10), 'rieng');
    $posted = rsJob($post, 'posted');
    $new = rsAt(18);

    // Lịch đăng hiện bài là "đã hẹn trên TikTok", đổi giờ được.
    $info = app(Reschedules::class)->calendarInfo(collect([$video]));
    expect($info[$video->id]['on_tiktok'])->toBeTrue()->and($info[$video->id]['can_reschedule'])->toBeTrue();

    $res = rsMove($this, $video, $new)->assertOk()->assertJson(['ok' => true, 'state' => 'pending', 'kind' => 'tiktok']);
    $row = Reschedule::query()->firstOrFail();
    expect($row->item_id)->toBe(RS_ITEM)
        ->and($post->refresh()->scheduled_at->equalTo(rsAt(10)))->toBeTrue()
        ->and($posted->refresh()->state)->toBe('posted');

    // Đang chờ thì không cho đổi tiếp.
    rsMove($this, $video, rsAt(19))->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, 'đang chờ xoá'));

    // Tiện ích nhận việc qua /tasks + claim.
    $task = $this->getJson('/api/ext/tasks', rsExt($this))->assertOk()->json('delete_scheduled');
    expect($task['item_id'])->toBe(RS_ITEM)->and($task['expect_user_id'])->toBe(RS_UID)->and($task['schedule_unix'])->toBe(rsAt(10)->getTimestamp());
    $this->postJson('/api/ext/delete_scheduled/claim', ['id' => $task['id'], 'nonce' => 'sai'], rsExt($this))->assertStatus(403);
    $this->postJson('/api/ext/delete_scheduled/claim', ['id' => $task['id'], 'nonce' => $task['nonce']], rsExt($this))->assertOk()->assertJson(['ok' => true, 'state' => 'claimed']);

    // "deleted" nhưng KHÔNG verified, hoặc sai item_id: không đổi gì.
    $this->postJson('/api/ext/delete_scheduled/result', ['id' => $task['id'], 'nonce' => $task['nonce'], 'outcome' => 'deleted', 'verified' => false, 'item_id' => RS_ITEM], rsExt($this))
        ->assertOk()->assertJson(['state' => 'failed']);
    expect($post->refresh()->scheduled_at->equalTo(rsAt(10)))->toBeTrue()
        ->and($posted->refresh()->state)->toBe('posted')
        ->and($video->refresh()->scheduled_for->equalTo(rsAt(10)))->toBeTrue();

    // Lần hai: đã xoá + đã kiểm lại.
    $res = rsMove($this, $video, $new)->assertOk()->assertJson(['state' => 'pending']);
    $task = $this->getJson('/api/ext/tasks', rsExt($this))->json('delete_scheduled');
    $this->postJson('/api/ext/delete_scheduled/claim', ['id' => $task['id'], 'nonce' => $task['nonce']], rsExt($this))->assertJson(['ok' => true]);
    $this->postJson('/api/ext/delete_scheduled/result', ['id' => $task['id'], 'nonce' => $task['nonce'], 'outcome' => 'deleted', 'verified' => true, 'item_id' => RS_ITEM, 'delete_sent' => true], rsExt($this))
        ->assertOk()->assertJson(['state' => 'done', 'duplicate' => false]);

    expect($post->refresh()->scheduled_at->equalTo($new))->toBeTrue()
        ->and($video->refresh()->scheduled_for->equalTo($new))->toBeTrue()
        ->and($posted->refresh()->state)->toBe('revoked')
        ->and(ChromePostWatcher::isEditNote($posted->note))->toBeTrue();

    $next = app(ChromeJobs::class)->latestForPost($post);
    expect($next->id)->not->toBe($posted->id)->and($next->state)->toBe('queued')
        ->and($next->options['schedule_time'])->toBe($new->utc()->format('Y-m-d\TH:i:s\Z'));

    // Kết quả trùng không làm gì thêm.
    $this->postJson('/api/ext/delete_scheduled/result', ['id' => $task['id'], 'nonce' => $task['nonce'], 'outcome' => 'deleted', 'verified' => true, 'item_id' => RS_ITEM], rsExt($this))
        ->assertJson(['duplicate' => true]);
    expect($this->getJson('/api/ext/tasks', rsExt($this))->json('delete_scheduled'))->toBeNull();
});

test('B: không rõ (đã gửi lệnh xoá mà không kiểm lại được) và kết quả "không xoá" giữ nguyên mọi thứ', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $posted = rsJob($post, 'posted');
    $svc = app(Reschedules::class);

    foreach (['unknown' => 'unknown', 'not_deleted' => 'failed', 'failed' => 'failed'] as $outcome => $state) {
        rsMove($this, $video, rsAt(18))->assertOk();
        $row = Reschedule::query()->where('state', 'pending')->firstOrFail();
        expect($svc->claim($row->id, $row->nonce, $this->client)['ok'])->toBeTrue();
        expect($svc->ingestResult($row->id, $row->nonce, ['outcome' => $outcome, 'reason' => $outcome, 'item_id' => RS_ITEM, 'delete_sent' => true])['state'])->toBe($state);
        expect($post->refresh()->scheduled_at->equalTo(rsAt(10)))->toBeTrue()
            ->and($posted->refresh()->state)->toBe('posted')
            ->and($row->refresh()->message)->not->toBeEmpty();
    }
});

test('B: từ chối khi thiếu item id, sát giờ cũ hoặc Chrome tắt; yêu cầu không ai nhận thì hết hạn', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $job = rsJob($post, 'posted', ['item_id' => null]);
    rsMove($this, $video, rsAt(18))->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, 'item id'));

    $job->update(['result' => ['item_id' => RS_ITEM, 'outcome' => 'posted']]);
    $this->client->update(['last_seen_at' => now()->subHour()]);
    rsMove($this, $video, rsAt(18))->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, 'Chrome'));
    $this->client->update(['last_seen_at' => now()]);

    [$soon, $soonVideo] = rsPost($this, CarbonImmutable::now()->addMinutes(3));
    rsJob($soon, 'posted');
    rsMove($this, $soonVideo, rsAt(19))->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, 'sắp tới giờ'));

    rsMove($this, $video, rsAt(18))->assertOk();
    $row = Reschedule::query()->firstOrFail();
    app(Reschedules::class)->reconcile(CarbonImmutable::now()->addMinutes(16));
    expect($row->refresh()->state)->toBe('expired')
        ->and($post->refresh()->scheduled_at->equalTo(rsAt(10)))->toBeTrue();
    expect(app(Reschedules::class)->claim($row->id, $row->nonce, $this->client)['ok'])->toBeFalse();
});

test('Lịch đăng hiện bài đã hẹn trên TikTok (hub và Kho riêng) kèm nút đổi giờ', function (): void {
    [$hubPost, $hubVideo] = rsPost($this, CarbonImmutable::now()->addHours(3));
    rsJob($hubPost, 'posted');
    [, $riengVideo] = rsPost($this, CarbonImmutable::now()->addHours(5), 'rieng');

    $page = $this->actingAs($this->owner)->get('/auto')->assertOk()->viewData('page');
    $items = collect($page['props']['lich']['channels'][$this->social->id]['items'])->keyBy('id');

    expect($items[$hubVideo->id]['state'])->toBe('tiktok_scheduled')
        ->and($items[$hubVideo->id]['can_reschedule'])->toBeTrue()
        ->and($items[$riengVideo->id]['state'])->toBe('scheduled')
        ->and($items[$riengVideo->id]['source'])->toBe('rieng')
        ->and($items[$riengVideo->id]['can_reschedule'])->toBeTrue();

    $this->actingAs($this->owner)->getJson("/auto/videos/{$hubVideo->id}/doi-gio")->assertOk()
        ->assertJson(['kind' => 'tiktok', 'rules' => ['min_lead_minutes' => 20]]);
});

// ---------------------------------------------------------------- Sửa bài / bỏ xếp lịch (PostEdits)

function rsLink(SocialAccount $social, string $shopId = '1729384756001234567'): void
{
    ProductLink::query()->create([
        'social_account_id' => $social->id, 'auto_product_id' => 'p1', 'shop_product_id' => $shopId, 'display_name' => 'Giỏ '.$social->username,
    ]);
}

function rsOther(object $t, bool $link = true): SocialAccount
{
    $other = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $t->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_hai',
    ]);
    ChromeAccount::query()->create(['social_account_id' => $other->id, 'enabled' => true, 'tiktok_user_id' => '7012345678901234500', 'chrome_only' => false]);
    AutoAccount::query()->create(['social_account_id' => $other->id, 'enabled' => true, 'daily_cap' => 40, 'window_start' => 0, 'window_end' => 24]);

    if ($link) {
        rsLink($other, '1729384756009999999');
    }

    return $other;
}

function rsDeleteVerified(object $t): void
{
    $task = $t->getJson('/api/ext/tasks', rsExt($t))->assertOk()->json('delete_scheduled');
    $t->postJson('/api/ext/delete_scheduled/claim', ['id' => $task['id'], 'nonce' => $task['nonce']], rsExt($t))->assertJson(['ok' => true]);
    $t->postJson('/api/ext/delete_scheduled/result', ['id' => $task['id'], 'nonce' => $task['nonce'], 'outcome' => 'deleted', 'verified' => true, 'item_id' => RS_ITEM, 'delete_sent' => true], rsExt($t))
        ->assertOk()->assertJson(['state' => 'done']);
}

test('sửa bài chưa lên TikTok: giờ, kênh, caption và hashtag đổi ngay, job cũ bị thu hồi', function (): void {
    rsLink($this->social);
    $other = rsOther($this);
    [$post, $video] = rsPost($this, rsAt(10));
    $post->forceFill(['content' => "Caption cũ\n\n#cu #hai"])->save();
    $old = rsJob($post, 'queued');

    $this->actingAs($this->owner)->getJson("/auto/videos/{$video->id}/sua")->assertOk()
        ->assertJson(['kind' => 'local', 'caption' => 'Caption cũ', 'hashtags' => ['#cu', '#hai']]);

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/sua", [
        'at' => rsAt(16)->toIso8601String(), 'social_account_id' => $other->id,
        'caption' => 'Caption mới', 'hashtags' => ['#moi', 'ba bon', '#moi'],
    ])->assertOk()->assertJson(['ok' => true, 'state' => 'done']);

    $post->refresh();
    $video->refresh();
    expect($post->content)->toBe("Caption mới\n\n#moi #ba #bon")
        ->and((string) $post->social_account_id)->toBe((string) $other->id)
        ->and(data_get($post->meta, 'fork_shop_product_id'))->toBe('1729384756009999999')
        ->and($post->scheduled_at->equalTo(rsAt(16)))->toBeTrue()
        ->and((string) $video->social_account_id)->toBe((string) $other->id)
        ->and($video->caption)->toBe('Caption mới')
        ->and($video->hashtags)->toBe(['#moi', '#ba', '#bon'])
        ->and($old->refresh()->state)->toBe('revoked');
});

test('sửa bài: từ chối kênh chưa gắn giỏ, caption rỗng và khi không có gì đổi', function (): void {
    rsLink($this->social);
    $other = rsOther($this, false);
    [$post, $video] = rsPost($this, rsAt(10));

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/sua", ['social_account_id' => $other->id])
        ->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, 'chưa chọn sản phẩm giỏ hàng'));
    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/sua", ['caption' => '   ', 'hashtags' => []])
        ->assertStatus(422)->assertJsonPath('message', 'Caption không được để trống.');
    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/sua", [])
        ->assertStatus(422)->assertJsonPath('message', 'Chưa có gì thay đổi.');

    expect((string) $post->refresh()->social_account_id)->toBe((string) $this->social->id);
});

test('sửa bài đã hẹn trên TikTok: chỉ áp thay đổi khi Chrome đã xoá và kiểm lại', function (): void {
    rsLink($this->social);
    [$post, $video] = rsPost($this, rsAt(10), 'rieng');
    $posted = rsJob($post, 'posted');

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/sua", ['caption' => 'Bản sửa', 'hashtags' => ['#x']])
        ->assertOk()->assertJson(['state' => 'pending', 'kind' => 'tiktok']);
    expect($post->refresh()->content)->not->toContain('Bản sửa')->and($posted->refresh()->state)->toBe('posted')
        ->and(Reschedule::query()->value('action'))->toBe('edit');

    rsDeleteVerified($this);

    expect($post->refresh()->content)->toBe("Bản sửa\n\n#x")
        ->and($post->scheduled_at->equalTo(rsAt(10)))->toBeTrue()
        ->and($posted->refresh()->state)->toBe('revoked')
        ->and(app(ChromeJobs::class)->latestForPost($post)->state)->toBe('queued');
});

test('bỏ xếp lịch video AI: bài bị bỏ, video về kho và không tự xếp lại cho tới khi chủ app cho phép', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $job = rsJob($post, 'queued');

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/bo-xep-lich")->assertOk()->assertJson(['state' => 'done']);

    $video->refresh();
    expect(Post::query()->find($post->id))->toBeNull()
        // Job còn xếp hàng không bao giờ được Chrome nhận nữa (bị thu hồi, hoặc xoá theo bài).
        ->and(ChromeJob::query()->whereKey($job->id)->whereIn('state', ChromeJob::OPEN)->exists())->toBeFalse()
        ->and($video->status)->toBe(AutoVideo::NEW)->and($video->post_id)->toBeNull()->and($video->social_account_id)->toBeNull()
        ->and(data_get($video->meta, 'owner_hold'))->not->toBeNull()
        ->and(AutoVideo::query()->notHeld()->whereKey($video->id)->exists())->toBeFalse();

    $this->actingAs($this->owner)->getJson("/auto/videos/{$video->id}/sua")->assertOk()->assertJson(['held' => true, 'can_release' => true]);
    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/cho-xep-lai")->assertOk();
    expect(AutoVideo::query()->notHeld()->whereKey($video->id)->exists())->toBeTrue();
});

test('bỏ xếp lịch bài Kho riêng đã hẹn trên TikTok: chỉ bỏ sau khi đã xoá và kiểm lại', function (): void {
    [$post, $video] = rsPost($this, rsAt(10), 'rieng');
    rsJob($post, 'posted');

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/bo-xep-lich")->assertOk()->assertJson(['state' => 'pending']);
    expect($video->refresh()->status)->toBe(AutoVideo::SCHEDULED);

    rsDeleteVerified($this);

    $video->refresh();
    expect($video->status)->toBe(AutoVideo::NEW)->and(Post::query()->find($post->id))->toBeNull()
        ->and(data_get($video->meta, 'owner_hold'))->toBeNull();
});

test('tách caption và dòng hashtag cuối của nội dung bài', function (): void {
    expect(PostEdits::splitContent("Một\n\nHai dòng\n\n#a #b"))->toBe(["Một\n\nHai dòng", ['#a', '#b']])
        ->and(PostEdits::splitContent("Chỉ chữ\n\ncó #tag giữa"))->toBe(["Chỉ chữ\n\ncó #tag giữa", []]);
});

test('xoá hẳn bài chưa lên TikTok: bài bị bỏ, video thành đã bỏ qua và không bao giờ tự xếp lại', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $job = rsJob($post, 'queued');

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/xoa")->assertOk()->assertJson(['ok' => true, 'state' => 'done']);

    $video->refresh();
    expect(Post::query()->find($post->id))->toBeNull()
        ->and(ChromeJob::query()->whereKey($job->id)->whereIn('state', ChromeJob::OPEN)->exists())->toBeFalse()
        ->and($video->status)->toBe(AutoVideo::SKIPPED)
        ->and($video->post_id)->toBeNull()->and($video->social_account_id)->toBeNull()->and($video->scheduled_for)->toBeNull()
        ->and(data_get($video->meta, 'removed_by_owner'))->not->toBeNull();
});

test('xoá hẳn video còn trong kho (chưa xếp lịch)', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $video->forceFill(['status' => AutoVideo::NEW, 'post_id' => null, 'social_account_id' => null, 'scheduled_for' => null])->save();
    $post->delete();

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/xoa")->assertOk()->assertJson(['state' => 'done']);
    expect($video->refresh()->status)->toBe(AutoVideo::SKIPPED);
});

test('xoá hẳn bài đã hẹn trên TikTok: chỉ xoá sau khi Chrome đã xoá bài hẹn và kiểm lại', function (): void {
    [$post, $video] = rsPost($this, rsAt(10), 'rieng');
    rsJob($post, 'posted');

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/xoa")->assertOk()->assertJson(['state' => 'pending', 'kind' => 'tiktok']);
    expect($video->refresh()->status)->toBe(AutoVideo::SCHEDULED)
        ->and(Reschedule::query()->value('action'))->toBe('remove');

    // Đang chờ xoá thì không cho xoá / sửa thêm lần nữa.
    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/xoa")->assertStatus(422);

    rsDeleteVerified($this);

    $video->refresh();
    expect($video->status)->toBe(AutoVideo::SKIPPED)->and(Post::query()->find($post->id))->toBeNull()
        ->and(data_get($video->meta, 'removed_by_owner'))->not->toBeNull();
});

test('xoá hẳn bị từ chối khi bài sắp tới giờ đăng', function (): void {
    [$post, $video] = rsPost($this, CarbonImmutable::now()->addMinute());

    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/xoa")->assertStatus(422);
    expect($video->refresh()->status)->toBe(AutoVideo::SCHEDULED)->and(Post::query()->find($post->id))->not->toBeNull();
});

test('nghe bản sẽ đăng và nghe thử nhạc: chỉ chủ app, chỉ file trong thư mục nhạc', function (): void {
    [$post, $video] = rsPost($this, rsAt(10), 'rieng');
    Media::query()->where('post_id', $post->id)->delete();

    // Bài không có file đăng / nhạc không thuộc thư mục nhạc → 404.
    $this->actingAs($this->owner)->get("/auto/videos/{$video->id}/ban-dang")->assertNotFound();
    $this->actingAs($this->owner)->get("/auto/videos/{$video->id}/nhac?rel=".urlencode('../../.env'))->assertNotFound();

    // Không có bài nhạc nào → đổi nhạc báo lỗi, không đổi gì.
    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/sua", ['music' => '*'])->assertStatus(422);

    // Người lạ không xem được.
    $stranger = User::factory()->create(['account_id' => Account::factory()->create()->id]);
    expect($this->actingAs($stranger)->get("/auto/videos/{$video->id}/ban-dang")->status())->toBeIn([302, 403, 404]);
});

// ---------------------------------------------------------------- Thùng rác

test('video xoá vào thùng rác: không còn trong kho, khôi phục được về kho', function (): void {
    [, $video] = rsPost($this, rsAt(10), 'rieng');
    $this->actingAs($this->owner)->postJson("/auto/videos/{$video->id}/xoa")->assertOk()->assertJson(['state' => 'done']);

    expect($video->refresh()->trashed_at)->not->toBeNull();
    $this->actingAs($this->owner)->getJson('/auto/thung-rac')->assertOk()
        ->assertJson(['days' => 30])->assertJsonPath('items.0.id', $video->id)->assertJsonPath('items.0.days_left', 30);

    // Kho riêng không còn hiện video đã xoá.
    $ids = collect($this->actingAs($this->owner)->get('/auto/kho/rieng?status=loi')->viewData('page')['props']['videos']['data'] ?? [])->pluck('id');
    expect($ids)->not->toContain($video->id);

    $this->actingAs($this->owner)->postJson("/auto/thung-rac/{$video->id}/khoi-phuc")->assertOk()->assertJson(['ok' => true]);
    $video->refresh();
    expect($video->status)->toBe(AutoVideo::NEW)->and($video->trashed_at)->toBeNull()
        ->and(data_get($video->meta, 'removed_by_owner'))->toBeNull();
    $this->actingAs($this->owner)->getJson('/auto/thung-rac')->assertJsonCount(0, 'items');
    $ids = collect($this->actingAs($this->owner)->get('/auto/kho/rieng?status=chua')->viewData('page')['props']['videos']['data'])->pluck('id');
    expect($ids)->toContain($video->id);
});

test('xoá trong thùng rác là xoá hẳn; quá 30 ngày cũng hết khôi phục; dọn sạch', function (): void {
    [, $a] = rsPost($this, rsAt(10));
    [, $b] = rsPost($this, rsAt(11));
    [, $c] = rsPost($this, rsAt(12));
    foreach ([$a, $b, $c] as $v) {
        $this->actingAs($this->owner)->postJson("/auto/videos/{$v->id}/xoa")->assertOk();
    }
    $c->refresh()->forceFill(['trashed_at' => now()->subDays(31)])->save();

    $this->actingAs($this->owner)->getJson('/auto/thung-rac')->assertJsonCount(2, 'items');
    $this->actingAs($this->owner)->postJson("/auto/thung-rac/{$c->id}/khoi-phuc")->assertStatus(422);

    $this->actingAs($this->owner)->postJson("/auto/thung-rac/{$a->id}/xoa")->assertOk();
    expect($a->refresh()->purged_at)->not->toBeNull()->and($a->status)->toBe(AutoVideo::SKIPPED);
    $this->actingAs($this->owner)->postJson("/auto/thung-rac/{$a->id}/khoi-phuc")->assertStatus(422);

    $this->actingAs($this->owner)->postJson('/auto/thung-rac/don-sach')->assertOk();
    expect($b->refresh()->purged_at)->not->toBeNull();
    $this->actingAs($this->owner)->getJson('/auto/thung-rac')->assertJsonCount(0, 'items');
});

// ---------------------------------------------------------------- Kiểm giỏ trước giờ đăng

test('kiểm giỏ trước giờ đăng: cả bài đã hẹn trên TikTok, giỏ hết hàng / không còn trong shop; dữ liệu shop cũ thì báo', function (): void {
    $pid = '1729384756001234567';
    ShopProduct::query()->create(['social_account_id' => $this->social->id, 'product_id' => $pid, 'source' => 'my_shop', 'title' => 'Giỏ A', 'stock_num' => 0, 'synced_at' => now()]);
    AutoAccount::query()->whereKey($this->social->id)->update(['products_synced_at' => now()->subDays(5)]);

    [$p1, $onTikTok] = rsPost($this, CarbonImmutable::now()->addHours(3));
    $p1->forceFill(['meta' => [...$p1->meta, 'fork_shop_product_id' => $pid]])->save();
    rsJob($p1, 'posted');
    [$p2, $gone] = rsPost($this, CarbonImmutable::now()->addHours(5));
    $p2->forceFill(['meta' => [...$p2->meta, 'fork_shop_product_id' => '1729384756009999999']])->save();
    [, $noCart] = rsPost($this, CarbonImmutable::now()->addHours(6));

    $lich = $this->actingAs($this->owner)->get('/auto')->assertOk()->viewData('page')['props']['lich']['channels'][$this->social->id];
    $items = collect($lich['items'])->keyBy('id');

    expect($items[$onTikTok->id]['state'])->toBe('tiktok_scheduled')
        ->and($items[$onTikTok->id]['cart_warn'])->toContain('hết hàng')
        ->and($items[$gone->id]['cart_warn'])->toContain('Không thấy giỏ')
        ->and($items[$noCart->id]['cart_warn'])->toBeNull()
        ->and($lich['cart_stale'])->toContain('cập nhật lần cuối');

    AutoAccount::query()->whereKey($this->social->id)->update(['products_synced_at' => now()]);
    $lich = $this->actingAs($this->owner)->get('/auto')->viewData('page')['props']['lich']['channels'][$this->social->id];
    expect($lich['cart_stale'])->toBeNull();
});
