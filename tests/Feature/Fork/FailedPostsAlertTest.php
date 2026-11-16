<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Platform;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

beforeEach(function () {
    Cache::flush();
    config()->set('trypost.self_hosted', true);
    config()->set('fork.telegram.bot_token', '123:TEST');
    config()->set('fork.telegram.chat_id', '999');
    config()->set('fork.telegram.min_interval_ms', 0);
    config()->set('fork.telegram.backoff_ms', [0, 0]);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->social = SocialAccount::factory()->create(['workspace_id' => $this->workspace->id, 'platform' => Platform::TikTok, 'username' => 'kenh1']);
});

function faMakeJob(object $t, int $n, array $result, string $state = 'failed', array $postMeta = []): ChromeJob
{
    $post = Post::factory()->create([
        'workspace_id' => $t->workspace->id, 'social_account_id' => $t->social->id, 'status' => PostStatus::Scheduled,
        'scheduled_at' => now()->addHours(5), 'meta' => $postMeta,
    ]);

    return ChromeJob::query()->create([
        'id' => 'ej_'.str_pad((string) $n, 24, 'a'), 'post_id' => $post->id, 'social_account_id' => $t->social->id, 'attempt' => 1,
        'expect_user_id' => '77', 'nonce' => 'n'.$n, 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1,
        'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => "Chú thích số {$n}", 'options' => [], 'state' => $state, 'result' => $result,
    ]);
}

function faTexts(): array
{
    return Http::recorded()->map(fn ($pair) => $pair[0]->data()['text'] ?? '')->values()->all();
}

const FA_OOS = ['detail' => 'out-of-stock', 'reason' => 'product-unavailable', 'outcome' => 'failed', 'definite' => true, 'not_sent' => true, 'elapsed_ms' => 800, 'schedule_time' => null];

test('an out-of-stock failed job is sent to telegram', function () {
    faMakeJob($this, 1, FA_OOS);

    $this->artisan('fork:alerts')->assertSuccessful();

    $texts = faTexts();
    expect($texts)->toHaveCount(1)->and($texts[0])->toContain('@kenh1');
});
