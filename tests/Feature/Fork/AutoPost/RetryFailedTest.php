<?php

declare(strict_types=1);

use App\Enums\Post\PublishStatus;
use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.auto.hub_api.key', null);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
});

/** Video lỗi kèm bài TikTok Auto Kid đã chốt lỗi và (tuỳ chọn) một job Chrome. */
function rfFailed(object $t, ?string $jobState = 'failed', array $post = [], ?PublishStatus $publish = PublishStatus::Failed): AutoVideo
{
    static $n = 0;
    $n++;

    $p = Post::factory()->forAccount($t->sa)->create(array_merge(['status' => PostStatus::Failed, 'scheduled_at' => now()->subHour()], $post));

    if ($publish !== null) {
        $p->forceFill(['publish_status' => $publish])->saveQuietly();
    }

    if ($jobState !== null) {
        ChromeJob::query()->create([
            'id' => 'rf_'.str_pad((string) $n, 24, 'f'), 'post_id' => $p->id, 'social_account_id' => $t->sa->id, 'attempt' => 1,
            'expect_user_id' => '777123', 'nonce' => 'n'.$n, 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1,
            'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => $jobState,
        ]);
    }

    return AutoVideo::query()->create([
        'hash' => hash('sha256', 'rf'.$n), 'path' => "/x/rf{$n}.mp4", 'batch_date' => '2026-01-05', 'file_name' => "rf{$n}.mp4",
        'product_code' => 'nano-dong', 'source' => 'kho', 'status' => AutoVideo::FAILED, 'caption' => 'xin chào',
        'social_account_id' => $t->sa->id, 'post_id' => $p->id, 'scheduled_for' => now()->subHour(),
        'skip_reason' => 'Đăng bài thất bại.', 'meta' => ['hub_claimed_at' => now()->toIso8601String(), 'anh_bia' => 'a.jpg'],
    ]);
}

test('owner can retry a failed video that was definitely not sent: it goes back to the stock', function (): void {
    $v = rfFailed($this, 'failed');

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertRedirect()->assertSessionHas('flash.success');

    $v->refresh();
    expect($v->status)->toBe(AutoVideo::NEW)
        ->and($v->social_account_id)->toBeNull()
        ->and($v->post_id)->toBeNull()
        ->and($v->scheduled_for)->toBeNull()
        ->and($v->skip_reason)->toBeNull()
        ->and($v->meta)->toBe(['anh_bia' => 'a.jpg']);

    expect(AutoVideo::query()->eligibleNew()->whereKey($v->id)->exists())->toBeTrue();
});

test('revoked or rejected Chrome jobs, or no job at all, are safe to retry', function (?string $state): void {
    $v = rfFailed($this, $state);

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertSessionHas('flash.success');

    expect($v->fresh()->status)->toBe(AutoVideo::NEW);
})->with(['revoked', 'rejected', null]);

test('retry is refused whenever the post might be on TikTok', function (?string $state): void {
    $v = rfFailed($this, $state);

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertRedirect()->assertSessionHas('flash.error');

    expect($v->fresh()->status)->toBe(AutoVideo::FAILED)->and($v->fresh()->post_id)->not->toBeNull();
})->with(['uncertain', 'posted', 'authorized', 'queued']);

test('retry is refused when the post has a TikTok id, is published, not settled or waiting for an automatic retry', function (array $post, ?PublishStatus $publish): void {
    $v = rfFailed($this, 'failed', $post, $publish);

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertSessionHas('flash.error');

    expect($v->fresh()->status)->toBe(AutoVideo::FAILED);
})->with([
    'platform id' => [['platform_post_id' => '7700000000000000009'], PublishStatus::Failed],
    'still scheduled' => [['status' => PostStatus::Scheduled], PublishStatus::Pending],
    'limit retry' => [[], PublishStatus::Retrying],
    'publishing' => [[], PublishStatus::Publishing],
]);

test('retry is refused for videos with a TikTok id, a hub claim conflict, or not in failed state', function (): void {
    $withId = rfFailed($this, 'failed');
    $withId->forceFill(['tiktok_video_id' => '7700000000000000001'])->save();
    $conflict = rfFailed($this, 'failed');
    $conflict->forceFill(['meta' => ['hub_claim_conflict' => 'may-2']])->save();
    $posted = rfFailed($this, 'failed');
    $posted->forceFill(['status' => AutoVideo::POSTED])->save();

    foreach ([$withId, $conflict, $posted] as $v) {
        $before = $v->fresh()->status;
        $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertSessionHas('flash.error');
        expect($v->fresh()->status)->toBe($before);
    }
});

test('retry is owner only and limited to the owner channels', function (): void {
    $v = rfFailed($this, 'failed');

    $this->actingAs(User::factory()->create(['account_id' => $this->account->id]))->post("/auto/videos/{$v->id}/thu-lai")->assertForbidden();

    $other = Account::factory()->create();
    $otherWs = Workspace::factory()->create(['account_id' => $other->id]);
    $otherSa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $otherWs->id]);
    $v->forceFill(['social_account_id' => $otherSa->id])->save();

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertNotFound();

    expect($v->fresh()->status)->toBe(AutoVideo::FAILED);
});

test('the auto page lists recent failures with a retry flag and the reason when it is unsafe', function (): void {
    $safe = rfFailed($this, 'failed');
    $unsafe = rfFailed($this, 'uncertain');

    $this->actingAs($this->owner)->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->has('failed_recent', 2)
        ->where('failed_recent', fn ($rows) => collect($rows)->firstWhere('id', $safe->id)['can_retry'] === true
            && collect($rows)->firstWhere('id', $unsafe->id)['can_retry'] === false
            && filled(collect($rows)->firstWhere('id', $unsafe->id)['retry_note'])));
});

test('kho cards expose can_retry for failed videos', function (): void {
    $safe = rfFailed($this, 'failed');

    $this->actingAs($this->owner)->get('/auto/kho?tab=loi')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('videos.data.0.id', $safe->id)
        ->where('videos.data.0.can_retry', true));
});

test('an uncertain post can be re-queued only after the owner confirms it is not on TikTok', function (): void {
    $v = rfFailed($this, 'uncertain');

    $this->actingAs($this->owner)->get('/auto')->assertInertia(fn (AssertableInertia $page) => $page
        ->where('failed_recent.0.can_retry', false)
        ->where('failed_recent.0.can_confirm_retry', true));

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai")->assertSessionHas('flash.error');
    expect($v->fresh()->status)->toBe(AutoVideo::FAILED);

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai", ['da_kiem_tra' => true])->assertSessionHas('flash.success');

    $v->refresh();
    expect($v->status)->toBe(AutoVideo::NEW)
        ->and($v->post_id)->toBeNull()
        ->and(data_get($v->meta, 'owner_confirmed_not_posted_at'))->not->toBeNull();
});

test('owner confirmation never re-queues a post Chrome reported as posted or still running', function (string $state): void {
    $v = rfFailed($this, $state);

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/thu-lai", ['da_kiem_tra' => true])->assertSessionHas('flash.error');

    expect($v->fresh()->status)->toBe(AutoVideo::FAILED);
})->with(['posted', 'authorized', 'queued']);
