<?php

declare(strict_types=1);

use App\Enums\Post\PublishStatus;
use App\Enums\Post\Status;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\File;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/kho-ux-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/ra');
    config(['fork.auto.hub_path' => $this->hub, 'trypost.self_hosted' => true, 'fork.auto.hub_api.key' => null]);

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);

    $this->rieng = function (string $name, array $attrs = []): AutoVideo {
        static $n = 0;
        $n++;

        return AutoVideo::query()->create($attrs + [
            'hash' => hash('sha256', "ux{$n}{$name}"), 'path' => $this->hub."/own/{$name}", 'source' => 'rieng', 'batch_date' => '2026-11-09',
            'file_name' => $name, 'status' => 'new', 'meta' => ['folder_id' => 1, 'rel_path' => $name],
        ]);
    };
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
});

test('rieng list searches by file name (case-insensitive, wildcards are literal) and keeps q and sort in filters', function (): void {
    ($this->rieng)('Nano-Dong-01.mp4');
    ($this->rieng)('nano-dong-02.mp4');
    ($this->rieng)('khac_hay.mp4');

    $this->actingAs($this->owner)->get('/auto/kho/rieng?q=NANO-dong')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/KhoRieng')->where('videos.total', 2)->where('filters.q', 'NANO-dong')->where('filters.sort', 'moi')
        ->where('selectable_count', 2));

    // % và _ là ký tự thường, không phải ký tự đại diện.
    $this->actingAs($this->owner)->get('/auto/kho/rieng?q=_hay')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.total', 1));
    $this->actingAs($this->owner)->get('/auto/kho/rieng?q=%25')->assertInertia(fn (AssertableInertia $p) => $p->where('videos.total', 0));
});

test('rieng list sorts newest, oldest, by name and by soonest schedule, ignoring unknown sort values', function (): void {
    $b = ($this->rieng)('b.mp4', ['batch_date' => '2026-11-10']);
    $a = ($this->rieng)('A.mp4', ['batch_date' => '2026-11-08']);
    $c = ($this->rieng)('c.mp4', ['batch_date' => '2026-11-09', 'status' => 'scheduled', 'scheduled_for' => now()->addHours(5)]);
    $d = ($this->rieng)('d.mp4', ['batch_date' => '2026-11-09', 'status' => 'scheduled', 'scheduled_for' => now()->addHour()]);

    $ids = fn (string $query) => collect($this->actingAs($this->owner)->get('/auto/kho/rieng'.$query)->viewData('page')['props']['videos']['data'])->pluck('id')->all();

    expect($ids(''))->toBe([$b->id, $d->id, $c->id, $a->id])
        ->and($ids('?sort=cu'))->toBe([$a->id, $c->id, $d->id, $b->id])
        ->and($ids('?sort=ten'))->toBe([$a->id, $b->id, $c->id, $d->id])
        ->and($ids('?sort=sap-dang'))->toBe([$d->id, $c->id, $b->id, $a->id])
        ->and($ids('?sort=drop-table'))->toBe($ids(''));
});

test('select-all lists the selectable videos of the current filter with duplicate flags, capped and owner only', function (): void {
    ($this->rieng)('moi-1.mp4');
    ($this->rieng)('moi-2.mp4');
    ($this->rieng)('da-hen.mp4', ['status' => 'scheduled', 'scheduled_for' => now()->addDay()]);
    ($this->rieng)('mat-file.mp4', ['files_deleted_at' => now()]);
    ($this->rieng)('xoa.mp4', ['trashed_at' => now()]);
    ($this->rieng)('loi.mp4', ['status' => 'failed']);

    $r = $this->actingAs($this->owner)->getJson('/auto/kho/rieng/chon-tat-ca')->assertOk()
        ->assertJsonPath('ok', true)->assertJsonPath('total', 3)->assertJsonPath('capped', false)->assertJsonPath('max', 1000);
    expect(collect($r->json('items'))->pluck('file_name')->sort()->values()->all())->toBe(['loi.mp4', 'moi-1.mp4', 'moi-2.mp4']);

    $this->actingAs($this->owner)->getJson('/auto/kho/rieng/chon-tat-ca?q=moi-1')->assertJsonPath('total', 1);
    $this->actingAs($this->owner)->getJson('/auto/kho/rieng/chon-tat-ca?status=hen')->assertJsonPath('total', 0);

    $this->actingAs(User::factory()->create(['account_id' => $this->owner->account_id]))->getJson('/auto/kho/rieng/chon-tat-ca')->assertForbidden();
});

/** Video lỗi của Kho Xưởng, kèm bài đã chốt lỗi và (tuỳ chọn) một job Chrome. */
function kuxFailed(object $t, ?string $jobState = 'failed', ?SocialAccount $sa = null): AutoVideo
{
    static $n = 0;
    $n++;
    $sa ??= $t->sa;

    $post = Post::factory()->forAccount($sa)->create(['status' => Status::Failed, 'scheduled_at' => now()->subHour()]);
    $post->forceFill(['publish_status' => PublishStatus::Failed])->saveQuietly();

    if ($jobState !== null) {
        ChromeJob::query()->create([
            'id' => 'kux_'.str_pad((string) $n, 23, 'f'), 'post_id' => $post->id, 'social_account_id' => $sa->id, 'attempt' => 1,
            'expect_user_id' => '777123', 'nonce' => 'k'.$n, 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1,
            'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => $jobState,
        ]);
    }

    return AutoVideo::query()->create([
        'hash' => hash('sha256', 'kux'.$n), 'path' => "/x/kux{$n}.mp4", 'batch_date' => '2026-01-05', 'file_name' => "kux{$n}.mp4",
        'product_code' => 'nano-dong', 'source' => 'hub', 'status' => AutoVideo::FAILED, 'caption' => 'xin chào',
        'social_account_id' => $sa->id, 'post_id' => $post->id, 'scheduled_for' => now()->subHour(),
        'skip_reason' => 'Đăng bài thất bại.', 'meta' => ['hub_claimed_at' => now()->toIso8601String()],
    ]);
}

test('bulk retry puts safe failed videos back in stock and refuses the uncertain ones, per video', function (): void {
    $safe1 = kuxFailed($this, 'failed');
    $safe2 = kuxFailed($this, null);
    $unsure = kuxFailed($this, 'uncertain');
    $fresh = AutoVideo::query()->create([
        'hash' => hash('sha256', 'fresh'), 'path' => '/x/fresh.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'fresh.mp4',
        'product_code' => 'nano-dong', 'source' => 'hub', 'status' => AutoVideo::NEW,
    ]);

    $r = $this->actingAs($this->owner)->postJson('/auto/kho/thu-lai-nhieu', ['ids' => [$safe1->id, $safe2->id, $unsure->id, $fresh->id, 999999]])
        ->assertOk()->assertJsonPath('retried', 2);

    expect(collect($r->json('refused'))->pluck('id')->sort()->values()->all())->toBe(collect([$unsure->id, $fresh->id, 999999])->sort()->values()->all());
    expect($safe1->fresh()->status)->toBe(AutoVideo::NEW)->and($safe2->fresh()->status)->toBe(AutoVideo::NEW)
        ->and($unsure->fresh()->status)->toBe(AutoVideo::FAILED)->and($fresh->fresh()->status)->toBe(AutoVideo::NEW);
});

test('bulk retry never touches videos of a channel that is not the owner’s, ignores private videos and needs the owner', function (): void {
    $otherAccount = Account::factory()->create();
    $otherUser = User::factory()->create(['account_id' => $otherAccount->id]);
    $otherWs = Workspace::factory()->create(['account_id' => $otherAccount->id, 'user_id' => $otherUser->id]);
    $foreignSa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $otherWs->id, 'timezone' => 'Asia/Ho_Chi_Minh']);

    $foreign = kuxFailed($this, 'failed', $foreignSa);
    $private = kuxFailed($this, 'failed');
    $private->forceFill(['source' => 'rieng'])->save();

    $this->actingAs($this->owner)->postJson('/auto/kho/thu-lai-nhieu', ['ids' => [$foreign->id, $private->id]])
        ->assertOk()->assertJsonPath('retried', 0);
    expect($foreign->fresh()->status)->toBe(AutoVideo::FAILED)->and($private->fresh()->status)->toBe(AutoVideo::FAILED);

    $this->actingAs($this->owner)->postJson('/auto/kho/thu-lai-nhieu', ['ids' => []])->assertUnprocessable();
    $this->actingAs(User::factory()->create(['account_id' => $this->owner->account_id]))->postJson('/auto/kho/thu-lai-nhieu', ['ids' => [1]])->assertForbidden();
});
