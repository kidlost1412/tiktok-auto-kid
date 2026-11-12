<?php

declare(strict_types=1);

namespace App\Fork\Notify;

use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Models\VideoStat;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Cache;
use Throwable;

/**
 * Đọc trạng thái trong DB (chỉ đọc) và báo chủ app qua Telegram khi có chuyện: mỗi sự kiện một tin
 * (quá 5 tin cùng loại trong một lượt thì gộp một tin). Mỗi sự kiện chỉ báo một lần (khoá chống trùng trong Cache).
 * Tin bị giữ lại (loại tin đang tắt, giờ yên tĩnh) không dùng khoá nên lượt sau giờ yên tĩnh sẽ gửi bù.
 */
final class AlertsCommand extends Command
{
    protected $signature = 'fork:alerts';

    protected $description = 'Kiểm tra hệ thống và gửi cảnh báo Telegram';

    private const int OFFLINE_AFTER_MINUTES = 15;

    private const int HOUR = 3600;

    private const int PERSISTENT_TTL = 6 * self::HOUR;

    private const int ONCE_TTL = 7 * 24 * self::HOUR;

    private const string DOWN_CLIENTS = 'fork:notify:down-clients';

    private const string HUB_STATE = 'fork:notify:hub';

    public function handle(): int
    {
        if (! Telegram::configured()) {
            $this->line('Chưa cấu hình Telegram (vào Cài đặt > Telegram).');

            return self::SUCCESS;
        }

        $since = TelegramSettings::since();

        $sent = 0;

        foreach ([
            fn () => $this->offlineClients(),
            fn () => $this->hub(),
            fn () => $this->badJobs(),
            fn () => $this->failedVideos(),
            fn () => $this->pausedLinks(),
            fn () => $this->lowStock(),
            fn () => $this->posted($since),
            fn () => $this->buyComments(),
            fn () => $this->highlights($since),
            fn () => $this->dailySummary(),
        ] as $step) {
            try {
                $sent += $step();
            } catch (Throwable $e) {
                // Một loại tin lỗi không được chặn các loại còn lại.
                report($e);
            }
        }

        $this->info("Đã gửi {$sent} tin.");

        return self::SUCCESS;
    }

    /** Chrome mất kết nối quá 15 phút trong khi tài khoản của nó đang có việc chờ; và báo khi đã kết nối lại. */
    private function offlineClients(): int
    {
        $sent = 0;
        $limit = now()->subMinutes(self::OFFLINE_AFTER_MINUTES);
        $down = (array) Cache::get(self::DOWN_CLIENTS, []);

        $clients = ChromeClient::query()
            ->whereNull('revoked_at')
            ->whereNotNull('tiktok_user_id')
            ->where(fn ($q) => $q->whereNull('last_seen_at')->orWhere('last_seen_at', '<', $limit))
            ->get();

        $messages = [];
        $keys = [];

        foreach ($clients as $client) {
            $accountIds = ChromeAccount::query()
                ->where('enabled', true)
                ->where('tiktok_user_id', $client->tiktok_user_id)
                ->pluck('social_account_id');

            if ($accountIds->isEmpty() || ! $this->hasPendingWork($accountIds->all())) {
                continue;
            }

            $key = "offline:{$client->id}";
            $messages[] = Messages::chromeOffline($this->who($client), $client->last_seen_at?->copy()->timezone($this->tz()), $key);
            $keys[$key] = [$client->id, $client->last_seen_at?->getTimestamp() ?? now()->getTimestamp()];
        }

        $sent += Notifier::dispatch('chrome_offline', $messages);

        foreach ($keys as $key => [$id, $ts]) {
            if (Telegram::wasSent($key)) {
                $down[$id] ??= $ts;
            }
        }

        // Đã báo mất kết nối mà nay thấy lại: báo "đã kết nối lại" kèm thời gian mất.
        $back = [];

        foreach ($down as $id => $ts) {
            $client = ChromeClient::query()->find($id);

            if (! $client || $client->revoked_at !== null) {
                unset($down[$id]);

                continue;
            }

            if ($client->last_seen_at && $client->last_seen_at->gte($limit)) {
                $back[$id] = Messages::chromeBack($this->who($client), (int) max(1, round((now()->getTimestamp() - (int) $ts) / 60)), "back:{$id}:{$ts}");
            }
        }

        if ($back !== []) {
            $sent += Notifier::dispatch('chrome_offline', $back);

            foreach ($back as $id => $m) {
                if (Telegram::wasSent($m->key)) {
                    unset($down[$id]);
                }
            }
        }

        Cache::put(self::DOWN_CLIENTS, $down, self::ONCE_TTL);

        return $sent;
    }

    private function who(ChromeClient $client): string
    {
        return $client->tiktok_username ? '@'.ltrim((string) $client->tiktok_username, '@') : (string) $client->label;
    }

    /** @param  list<string>  $socialAccountIds */
    private function hasPendingWork(array $socialAccountIds): bool
    {
        if (ChromeJob::query()->whereIn('social_account_id', $socialAccountIds)->whereIn('state', ChromeJob::OPEN)->exists()) {
            return true;
        }

        return AutoVideo::query()
            ->whereIn('social_account_id', $socialAccountIds)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])
            ->where('scheduled_for', '<=', now()->addHours(3))
            ->exists();
    }

    /** Hub tắt hoặc lỗi từ 2 lượt kiểm tra liên tiếp thì báo; hub trở lại thì báo kèm thời gian mất. */
    private function hub(): int
    {
        if (! HubApi::enabled()) {
            return 0;
        }

        $state = (new HubApi)->ping();
        $st = (array) Cache::get(self::HUB_STATE, []);

        if ($state === HubApi::OK) {
            $sent = 0;

            if (! empty($st['alerted'])) {
                $m = Messages::hubBack((int) max(1, round((now()->getTimestamp() - (int) $st['since']) / 60)), 'hub-back:'.$st['since']);
                $sent = Notifier::dispatch('hub_offline', [$m]);

                if (! Telegram::wasSent($m->key)) {
                    return $sent; // chưa gửi được (đang tắt loại tin, giờ yên tĩnh...): giữ trạng thái, lượt sau thử lại
                }
            }

            Cache::forget(self::HUB_STATE);

            return $sent;
        }

        $st['since'] ??= now()->getTimestamp();
        $st['runs'] = (int) ($st['runs'] ?? 0) + 1;
        $st['alerted'] = $st['alerted'] ?? false;
        $sent = 0;

        if ($st['runs'] >= 2 && ! $st['alerted']) {
            $label = match ($state) {
                HubApi::OFFLINE => 'Hub đang tắt (mở Xưởng Video để lấy video mới)',
                HubApi::BAD_KEY => 'Sai khoá kết nối hub',
                default => 'Hub trả lời lỗi',
            };
            $sent = Notifier::dispatch('hub_offline', [Messages::hubOffline($label, 'hub:'.$st['since'])]);
            $st['alerted'] = $sent > 0;
        }

        Cache::put(self::HUB_STATE, $st, self::ONCE_TTL);

        return $sent;
    }

    /** Bài đã lên TikTok (kể từ lúc bật theo dõi, tối đa 24 giờ qua), mỗi bài một tin. */
    private function posted(CarbonImmutable $since): int
    {
        $from = $since->max(now()->subDay()->toImmutable());

        $videos = AutoVideo::query()
            ->livePosted()
            ->where('posted_at', '>=', $from)
            ->orderBy('posted_at')
            ->limit(60)
            ->get();

        if ($videos->isEmpty()) {
            return 0;
        }

        $names = $this->usernames($videos->pluck('social_account_id'));
        $messages = [];

        foreach ($videos as $v) {
            $link = $v->social_account_id && $v->product_code
                ? ProductLink::slot((string) $v->social_account_id, (string) $v->product_code, $v->quy_cach)->whereNull('paused_reason')->first()
                : null;

            $messages[] = Messages::posted([
                'user' => $names[$v->social_account_id] ?? null,
                'at' => $v->posted_at->copy()->timezone($this->tz()),
                'product' => $v->product_name,
                'cart' => $link?->display_name,
                'item_id' => $v->tiktok_video_id,
                'video_id' => $v->id,
                'caption' => $v->caption,
            ], "posted:{$v->id}");
        }

        return Notifier::dispatch('posted', $messages);
    }

    /** Job Chrome thất bại, bị TikTok từ chối hoặc chưa rõ kết quả: báo một lần cho mỗi job. */
    private function badJobs(): int
    {
        $jobs = ChromeJob::query()
            ->whereIn('state', ['failed', 'rejected', 'uncertain'])
            ->where('updated_at', '>=', now()->subDay())
            ->orderBy('updated_at')
            ->get();

        $names = $this->usernames($jobs->pluck('social_account_id'));

        return Notifier::dispatch('failed', $jobs->map(fn (ChromeJob $job): Message => Messages::failed([
            'user' => $names[$job->social_account_id] ?? null,
            'state' => $job->state,
            'reason' => trim((string) ($job->note ?: data_get($job->result, 'message', data_get($job->result, 'reason', '')))),
            'caption' => $job->caption,
        ], "job:{$job->id}:{$job->state}")));
    }

    private function failedVideos(): int
    {
        $videos = AutoVideo::query()
            ->where('status', AutoVideo::FAILED)
            ->where('updated_at', '>=', now()->subDay())
            ->orderBy('updated_at')
            ->get();

        // Cùng một bài đã báo qua job Chrome lỗi thì khỏi báo lần nữa.
        $reported = ChromeJob::query()
            ->whereIn('post_id', $videos->pluck('post_id')->filter())
            ->whereIn('state', ['failed', 'rejected', 'uncertain'])
            ->pluck('post_id')
            ->all();

        $videos = $videos->reject(fn (AutoVideo $v): bool => $v->post_id !== null && in_array($v->post_id, $reported, true));
        $names = $this->usernames($videos->pluck('social_account_id'));

        return Notifier::dispatch('failed', $videos->map(fn (AutoVideo $v): Message => Messages::failed([
            'user' => $names[$v->social_account_id] ?? null,
            'reason' => (string) $v->skip_reason,
            'caption' => $v->caption,
            'file' => $v->file_name,
            'link' => Messages::appUrl("/auto/kho?tab=loi&video={$v->id}"),
        ], "video:{$v->id}:failed")));
    }

    /** Liên kết giỏ hàng bị tạm dừng (chủ app phải lưu lại liên kết). */
    private function pausedLinks(): int
    {
        $links = ProductLink::query()->whereNotNull('paused_reason')->get();
        $names = $this->usernames($links->pluck('social_account_id'));

        return Notifier::dispatch('cart', $links->map(fn (ProductLink $l): Message => Messages::cartPaused([
            'user' => $names[$l->social_account_id] ?? null,
            'product' => $l->display_name,
            'code' => (string) $l->auto_product_id,
            'reason' => (string) $l->paused_reason,
        ], "link:{$l->id}:".md5((string) $l->paused_reason))));
    }

    /** Kho video mới ít hơn số bài/ngày của một kênh đang bật tự động đăng. */
    private function lowStock(): int
    {
        $accounts = AutoAccount::query()->where('enabled', true)->get();

        if ($accounts->isEmpty()) {
            return 0;
        }

        // Cùng điều kiện với VideoLibrary::reserveNext.
        $available = AutoVideo::query()
            ->where('status', AutoVideo::NEW)
            ->where('file_name', 'like', '%\_MIXKIT\_%')
            ->whereIn('product_code', AutoProduct::query()->where('enabled', true)->select('code'))
            ->count();

        if ($available >= (int) $accounts->max('daily_cap')) {
            return 0;
        }

        $perDay = (int) $accounts->sum('daily_cap');

        return Notifier::dispatch('stock', [Messages::stockLow($available, $perDay, $perDay > 0 ? $available / $perDay : null, 'stock')]);
    }

    /** Bình luận "hỏi mua / hỏi giá" mới (tiện ích thu về): mỗi bình luận một tin. */
    private function buyComments(): int
    {
        $pending = VideoComment::query()
            ->where('is_buy_intent', true)
            ->whereNull('notified_at')
            ->where('created_at', '>=', now()->subDay())
            ->orderBy('id')
            ->limit(40)
            ->get();

        if ($pending->isEmpty()) {
            return 0;
        }

        $names = $this->usernames($pending->pluck('social_account_id'));
        $captions = VideoStat::query()->whereIn('item_id', $pending->pluck('item_id')->unique())->pluck('caption', 'item_id');

        $messages = $pending->map(fn (VideoComment $c): Message => Messages::buyComment([
            'user' => $names[$c->social_account_id] ?? null,
            'author' => $c->author_name ?: $c->author_handle,
            'text' => (string) $c->text,
            'caption' => $captions[$c->item_id] ?? null,
            'item_id' => $c->item_id,
            'video_id' => $c->auto_video_id,
        ], "comment:{$c->comment_id}"));

        $sent = Notifier::dispatch('buy_comment', $messages);

        // Đã gửi (hoặc khoá chống trùng báo đã gửi trước đó): đánh dấu để lượt sau không xét lại.
        $done = $pending->filter(fn (VideoComment $c): bool => Telegram::wasSent("comment:{$c->comment_id}"));
        VideoComment::query()->whereIn('id', $done->pluck('id'))->update(['notified_at' => now()]);

        return $sent;
    }

    /** Video có lượt xem 24 giờ vượt xa mức trung bình (từ 1,5 lần, tối thiểu 200 lượt). */
    private function highlights(CarbonImmutable $since): int
    {
        $recent = AutoVideo::query()->livePosted()->whereNotNull('stats')->where('posted_at', '>=', now()->subDays(30))->get()
            ->filter(fn (AutoVideo $v): bool => data_get($v->stats, 'h24.views') !== null);

        if ($recent->count() < 4) {
            return 0;
        }

        $names = $this->usernames($recent->pluck('social_account_id'));
        $messages = [];

        foreach ($recent->filter(fn (AutoVideo $v): bool => $v->posted_at->gte($since)) as $v) {
            $views = (int) data_get($v->stats, 'h24.views');
            $others = $recent->reject(fn (AutoVideo $o): bool => $o->id === $v->id);
            $avg = (int) round($others->avg(fn (AutoVideo $o): int => (int) data_get($o->stats, 'h24.views')));

            if ($views < 200 || $avg <= 0 || $views < 1.5 * $avg) {
                continue;
            }

            $messages[] = Messages::highlight([
                'user' => $names[$v->social_account_id] ?? null,
                'views' => $views,
                'average' => $avg,
                'caption' => $v->caption,
                'item_id' => $v->tiktok_video_id,
                'video_id' => $v->id,
            ], "highlight:{$v->id}");
        }

        return Notifier::dispatch('highlight', $messages);
    }

    /** Tổng kết ngày vào giờ đã chọn (mặc định 21:00, giờ địa phương), gửi trong 3 giờ sau đó và chỉ một lần mỗi ngày. */
    private function dailySummary(): int
    {
        $now = now()->timezone($this->tz());
        [$h, $m] = array_map('intval', explode(':', TelegramSettings::summaryTime()));
        $at = $now->copy()->setTime($h, $m);

        if ($now->lt($at) || $now->gte($at->copy()->addHours(3))) {
            return 0;
        }

        $accounts = AutoAccount::query()->where('enabled', true)->get();

        if ($accounts->isEmpty()) {
            return 0;
        }

        $dayStart = $now->copy()->startOfDay()->utc();
        $stats = VideoStat::query()->where('posted_at', '>=', now()->subDay())->orderByDesc('views')->get();
        $names = $this->usernames($accounts->pluck('social_account_id')->merge($stats->pluck('social_account_id')));

        $posted = AutoVideo::query()->livePosted()->where('posted_at', '>=', $dayStart)->get();
        $failedVideos = AutoVideo::query()->where('status', AutoVideo::FAILED)->where('updated_at', '>=', $dayStart)->get();
        $failedJobs = ChromeJob::query()->whereIn('state', ['failed', 'rejected'])->where('updated_at', '>=', $dayStart)
            ->whereNotIn('post_id', $failedVideos->pluck('post_id')->filter())->count();

        $videos = AutoVideo::query()->whereIn('id', $stats->pluck('auto_video_id')->filter())->get()->keyBy('id');

        $top = $stats->take(3)->map(fn (VideoStat $s): array => [
            'views' => (int) $s->views,
            'user' => $names[$s->social_account_id] ?? null,
            'caption' => $s->caption,
            'url' => Messages::tiktokUrl($names[$s->social_account_id] ?? null, $s->item_id),
        ])->values()->all();

        $byProduct = [];

        foreach ($stats as $s) {
            $name = $videos[$s->auto_video_id]->product_name ?? null;

            if (filled($name)) {
                $byProduct[$name] = ($byProduct[$name] ?? 0) + (int) $s->views;
            }
        }

        arsort($byProduct);
        $best = $byProduct === [] ? null : ['name' => (string) array_key_first($byProduct), 'views' => (int) reset($byProduct)];

        $tomorrowStart = $now->copy()->addDay()->startOfDay();
        $planned = AutoVideo::query()
            ->where(fn ($q) => $q->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])->orWhere(fn ($h2) => $h2->heldOnTikTok()))
            ->get()
            ->map(fn (AutoVideo $v): ?CarbonImmutable => ($v->status === AutoVideo::POSTED ? $v->posted_at : $v->scheduled_for)?->toImmutable()->timezone($this->tz()))
            ->filter(fn (?CarbonImmutable $t): bool => $t !== null && $t->gte($tomorrowStart) && $t->lt($tomorrowStart->addDay()))
            ->sort()->values();

        $channels = $accounts->map(fn (AutoAccount $a): array => [
            'user' => (string) ($names[$a->social_account_id] ?? '?'),
            'posted' => $posted->where('social_account_id', $a->social_account_id)->count(),
        ])->values()->all();

        $message = Messages::daily([
            'date' => $now,
            'posted' => $posted->count(),
            'target' => (int) $accounts->sum('daily_cap'),
            'failed' => $failedVideos->count() + $failedJobs,
            'views' => (int) $stats->sum('views'),
            'top' => $top,
            'product' => $best,
            'buy_comments' => VideoComment::query()->where('is_buy_intent', true)->where('created_at', '>=', $dayStart)->count(),
            'tomorrow' => $planned->isEmpty() ? null : ['count' => $planned->count(), 'first' => $planned->first()->format('H:i'), 'last' => $planned->last()->format('H:i')],
            'channels' => $channels,
        ], 'daily:'.$now->format('Y-m-d'));

        return Notifier::dispatch('daily', [$message]);
    }

    /**
     * @param  iterable<string|null>  $ids
     * @return array<string, string>
     */
    private function usernames(iterable $ids): array
    {
        $ids = collect($ids)->filter()->unique()->values();

        return $ids->isEmpty() ? [] : SocialAccount::query()->whereIn('id', $ids)->pluck('username', 'id')->all();
    }

    private function tz(): string
    {
        return (string) config('fork.telegram.timezone', 'Asia/Ho_Chi_Minh');
    }
}
