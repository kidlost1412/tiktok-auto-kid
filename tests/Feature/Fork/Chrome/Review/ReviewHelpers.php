<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\PostPlatform\ContentType;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Storage;

const RV_USER_ID = '7012345678901234567';

/** Dựng môi trường chung: user, workspace, disk giả có video. */
function rvEnv(object $t): void
{
    ChromePostWatcher::register();
    config()->set('fork.chrome.next_max_wait', 0);
    Cache::forget('fork:chrome:pair');
    Storage::fake();
    Storage::put('media/v.mp4', 'video-bytes');

    $t->tpAccount = Account::factory()->create();
    $t->user = User::factory()->create(['account_id' => $t->tpAccount->id]);
    $t->tpAccount->update(['owner_id' => $t->user->id]);
    $t->workspace = Workspace::factory()->create(['account_id' => $t->tpAccount->id, 'user_id' => $t->user->id]);
    $t->chrome = app(ChromeJobs::class);
}

function rvSocial(object $t, bool $chrome = true, bool $chromeOnly = false, string $userId = RV_USER_ID, string $username = 'tiktoker'): SocialAccount
{
    $a = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $t->workspace->id,
        'username' => $username,
        'status' => AccountStatus::Connected,
    ]);

    if ($chrome) {
        ChromeAccount::create([
            'social_account_id' => $a->id,
            'enabled' => true,
            'tiktok_user_id' => $userId,
            'chrome_only' => $chromeOnly,
        ]);
    }

    return $a;
}

function rvPost(object $t, SocialAccount $a, array $attrs = [], array $meta = []): Post
{
    $post = Post::factory()->forAccount($a)->tiktok()->create([
        'user_id' => $t->user->id,
        'content' => 'Xin chào TikTok',
        'content_type' => ContentType::TikTokVideo,
        'status' => PostStatus::Scheduled,
        'media' => [[
            'id' => 'm1', 'path' => 'media/v.mp4', 'url' => 'https://example.com/media/v.mp4',
            'mime_type' => 'video/mp4', 'original_filename' => 'v.mp4',
        ]],
        'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE', ...$meta],
        ...$attrs,
    ]);
    $post->setRelation('socialAccount', $a);

    return $post;
}

/** Chrome đã ghép nối, đã hello danh tính; trả [ChromeClient, token]. */
function rvClient(object $t, string $userId = RV_USER_ID, string $username = 'tiktoker'): array
{
    $made = $t->chrome->createClient($t->tpAccount->id, 'Chrome', '1.0.0', 1);
    $t->chrome->touch($made['client'], 1, ['tiktok_user_id' => $userId, 'tiktok_username' => $username]);

    return [$made['client']->refresh(), $made['token']];
}

function rvHeaders(string $token): array
{
    return ['Authorization' => 'Bearer '.$token, 'X-Autotok-Protocol' => '1', 'X-Requested-With' => 'autotok'];
}

/** Đưa job tới trạng thái ready qua API thật; trả payload của /next. */
function rvClaimAndReady(object $t, string $token): array
{
    $payload = $t->getJson('/api/ext/next?wait=0', rvHeaders($token))->assertOk()->json();
    $t->postJson('/api/ext/progress', ['id' => $payload['id'], 'nonce' => $payload['nonce'], 'claim_token' => $payload['claim_token'], 'phase' => 'ready'], rvHeaders($token))
        ->assertOk()->assertJsonPath('state', 'ready');

    return $payload;
}

function rvAuthBody(array $payload, array $over = []): array
{
    return [
        'id' => $payload['id'], 'nonce' => $payload['nonce'], 'claim_token' => $payload['claim_token'],
        'body_sha256' => str_repeat('a', 64), 'creation_id' => 'c1',
        'visibility_type' => 0, 'schedule_time' => null,
        'identity' => ['username' => 'tiktoker', 'user_id' => RV_USER_ID],
        ...$over,
    ];
}
