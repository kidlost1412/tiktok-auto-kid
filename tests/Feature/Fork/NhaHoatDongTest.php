<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Nha\NhaHoatDong;
use App\Fork\Nha\NhaState;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $ws->id, 'username' => 'vuonxanh', 'timezone' => 'Asia/Ho_Chi_Minh']);
});

function nhdJob(object $t, string $id, string $state, array $extra = []): ChromeJob
{
    $p = Post::factory()->forAccount($t->sa)->create(['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHour()]);

    return ChromeJob::query()->create(array_merge([
        'id' => str_pad($id, 26, 'x'), 'post_id' => $p->id, 'social_account_id' => $t->sa->id, 'attempt' => 1,
        'expect_user_id' => '777123', 'nonce' => 'n'.$id, 'media_path' => 'x.mp4', 'video_name' => 'nano-dong_cong-dung_9.mp4', 'video_size' => 1,
        'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => $state,
    ], $extra));
}

test('posting jobs of the last 30 minutes become postman activity with channel and result', function (): void {
    nhdJob($this, 'a1', 'posted', ['result_at' => now()->subMinutes(2)]);
    nhdJob($this, 'a2', 'failed', ['result_at' => now()->subMinute(), 'result' => ['reason' => 'upload_failed']]);

    $out = collect(NhaHoatDong::build(CarbonImmutable::now()))->where('vai', 'buuta')->keyBy('loai');

    expect($out['da-dang']['kenh'])->toBe('@vuonxanh')
        ->and($out['da-dang']['video'])->toBe('nano-dong_cong-dung_9.mp4')
        ->and($out['dang-loi']['loi'])->toBeString()->not->toBe('');
});

test('old jobs are not talked about again', function (): void {
    $j = nhdJob($this, 'b1', 'posted', ['result_at' => now()->subHours(3)]);
    ChromeJob::query()->whereKey($j->id)->update(['updated_at' => now()->subHours(3)]);

    expect(collect(NhaHoatDong::build(CarbonImmutable::now()))->where('vai', 'buuta'))->toBeEmpty();
});

test('kho rieng AI results become storekeeper activity', function (): void {
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'nhd1'), 'path' => '/x/nhd1.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'vuon-tieu.mp4',
        'product_code' => 'nano-dong', 'product_name' => 'Nano Đồng', 'source' => AutoVideo::SOURCE_RIENG, 'status' => AutoVideo::NEW,
        'meta' => ['ai' => ['state' => 'ok', 'chac' => 'cao', 'product_code' => 'nano-dong', 'ly_do' => 'thấy chai nhãn trắng chữ đỏ', 'at' => now()->subMinute()->toIso8601String()]],
    ]);

    $ai = collect(NhaHoatDong::build(CarbonImmutable::now()))->firstWhere('vai', 'thukho');

    expect($ai['loai'])->toBe('ai-xem')
        ->and($ai['san_pham'])->toBe('Nano Đồng')
        ->and($ai['chac'])->toBe('cao')
        ->and($ai['video'])->toBe('vuon-tieu.mp4');
});

test('thought events from the hub do not stop a role from looking busy', function (): void {
    $hub = ['up' => true, 'dang_chay' => true, 'tien_do' => ['xong' => 0, 'tong' => 6], 'bay_gio' => 1_800_000_000, 'su_kien' => [
        ['n' => 1_799_999_900_000_000, 'vai' => 'he-thong', 'loai' => 'bat-dau-lo', 'ten' => 'Nano Đồng', 'so_video' => 6],
        ['n' => 1_799_999_950_000_000, 'vai' => 'bien-kich', 'loai' => 'bat-dau', 'so' => 3],
        ['n' => 1_799_999_990_000_000, 'vai' => 'bien-kich', 'loai' => 'nghi', 'buoc' => 'dat', 'hook' => 'Tám trăm nghìn một bao phân', 'diem' => 8],
    ]];

    $s = NhaState::build($hub, [], CarbonImmutable::createFromTimestamp(1_800_000_000));

    expect($s['vai']['bienkich']['state'])->toBe('working')
        ->and(collect($s['events'])->last()['hook'])->toBe('Tám trăm nghìn một bao phân');
});
