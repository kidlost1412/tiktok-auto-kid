<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\Reschedule;
use App\Fork\AutoPost\Scheduling\Reschedules;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
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

test('từ chối: Chrome đang tải lên, quá gần, ngoài khung giờ, sát bài khác cùng kênh; kênh khác thì không sao', function (): void {
    [$post, $video] = rsPost($this, rsAt(10));
    $job = rsJob($post, 'uploading');

    rsMove($this, $video, rsAt(12))->assertStatus(422)->assertJson(['ok' => false, 'message' => Reschedules::BUSY_TEXT]);
    expect($post->refresh()->scheduled_at->equalTo(rsAt(10)))->toBeTrue();
    $job->update(['state' => 'revoked', 'note' => ChromePostWatcher::EDIT_NOTE]);

    rsMove($this, $video, CarbonImmutable::now()->addMinutes(30))->assertStatus(422)->assertJsonFragment(['ok' => false])
        ->assertJsonPath('message', fn ($m) => str_contains($m, '45 phút'));

    AutoAccount::query()->whereKey($this->social->id)->update(['window_start' => 8, 'window_end' => 20]);
    rsMove($this, $video, rsAt(21))->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, 'khung giờ'));
    AutoAccount::query()->whereKey($this->social->id)->update(['window_start' => 0, 'window_end' => 24]);

    rsPost($this, rsAt(14));
    rsMove($this, $video, rsAt(14, 10))->assertStatus(422)->assertJsonPath('message', fn ($m) => str_contains($m, '20 phút'));

    $other = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh']);
    rsPost($this, rsAt(16), 'hub', $other);
    rsMove($this, $video, rsAt(16))->assertOk()->assertJson(['state' => 'done']);

    rsMove($this, $video, CarbonImmutable::now()->addDays(11))->assertStatus(422);
    expect($post->refresh()->scheduled_at->equalTo(rsAt(16)))->toBeTrue();
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

    [$soon, $soonVideo] = rsPost($this, CarbonImmutable::now()->addMinutes(40));
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
        ->assertJson(['kind' => 'tiktok', 'rules' => ['window_start' => 0, 'window_end' => 24, 'gap_minutes' => 20, 'min_lead_minutes' => 45]]);
});
