<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\Reschedule;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\ScheduledDispatcher;
use App\Models\Post;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\Cache\LockTimeoutException;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Random\Engine\Mt19937;
use Random\Randomizer;
use RuntimeException;
use Throwable;

/**
 * "Trộn xen kẽ sản phẩm": các bài đã xếp lịch mà CHƯA gửi lên TikTok được đổi chỗ giờ cho nhau để hai bài liền nhau
 * khác sản phẩm (ví dụ 10 bọ, 10 tc, 10 đạm → bọ, tc, đạm, tc, bọ…), có chút ngẫu nhiên.
 *
 * Chỉ HOÁN ĐỔI các giờ đã có (không thêm/bớt giờ, không đổi số bài mỗi ngày, không ra ngoài khung giờ).
 * Không đụng: bài đã hẹn trên TikTok hoặc Chrome đang tải lên (đổi phải xoá trên TikTok), bài sắp tới giờ,
 * bài chủ app tự chỉnh giờ (meta.time_pinned) trừ khi chủ app chọn đổi cả những bài đó.
 */
final class ProductMix
{
    /** Bài phải còn cách giờ đăng ít nhất ngần này mới được đổi chỗ (bộ giao bài gửi trước SCHEDULE_LEAD + 2 phút). */
    public const int MIN_AHEAD = ChromeJobs::SCHEDULE_LEAD + 5 * 60;

    /** Đánh dấu giờ do chủ app tự chọn (đổi giờ, kéo thả, sửa giờ trong Đăng hàng loạt). */
    public const string PIN = 'time_pinned';

    private const array COUNTED = [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED];

    // ---------------------------------------------------------------- Thuật toán (thuần, không đọc DB)

    /**
     * Xếp lại thứ tự. `$timeline` theo thời gian, mỗi phần tử: ['fixed' => bool, 'product' => string, 'key' => int|null].
     * Phần tử cố định giữ nguyên, chỗ không cố định được điền lại từ chính các phần tử không cố định để hai bài liền nhau
     * khác sản phẩm khi có thể. Trả [vị trí => key] cho các chỗ không cố định. Cùng hạt giống thì cùng kết quả.
     *
     * @param  list<array{fixed: bool, product: string, key: int|null}>  $timeline
     * @return array<int, int>
     */
    public static function arrange(array $timeline, int $seed): array
    {
        $rand = new Randomizer(new Mt19937($seed));
        $queues = [];

        foreach ($timeline as $e) {
            if (! $e['fixed']) {
                $queues[$e['product']][] = (int) $e['key'];
            }
        }

        $history = [];
        $out = [];
        $n = count($timeline);

        for ($i = 0; $i < $n; $i++) {
            $e = $timeline[$i];

            if ($e['fixed']) {
                $history[] = $e['product'];

                continue;
            }

            $last1 = $history[count($history) - 1] ?? null;
            $last2 = $history[count($history) - 2] ?? null;
            $next = ($i + 1 < $n && $timeline[$i + 1]['fixed']) ? $timeline[$i + 1]['product'] : null;
            $avail = array_keys(array_filter($queues, fn (array $q): bool => $q !== []));
            $cands = $avail;

            // Nới dần: tránh 2 bài trước + bài cố định ngay sau → tránh bài trước + bài sau → chỉ bài trước → không ràng buộc.
            foreach ([[$last1, $last2, $next], [$last1, $next], [$last1], []] as $avoid) {
                $avoid = array_values(array_filter($avoid, fn (?string $p): bool => $p !== null));
                $try = array_values(array_filter($avail, fn (string|int $p): bool => ! in_array((string) $p, $avoid, true)));

                if ($try !== []) {
                    $cands = $try;
                    break;
                }
            }

            // Sản phẩm còn nhiều bài nhất đi trước (để cuối không bị dồn một loại); hoà thì bốc ngẫu nhiên.
            $max = max(array_map(fn (string|int $p): int => count($queues[$p]), $cands));
            $top = array_values(array_filter($cands, fn (string|int $p): bool => count($queues[$p]) === $max));
            sort($top);
            $pick = $top[count($top) === 1 ? 0 : $rand->getInt(0, count($top) - 1)];

            $out[$i] = array_shift($queues[$pick]);
            $history[] = (string) $pick;
        }

        return $out;
    }

    /**
     * Thứ tự xen kẽ cho một danh sách (Đăng hàng loạt Kho riêng): `$items` = [key => product], giữ thứ tự trong cùng sản phẩm.
     * `$before` = sản phẩm các bài ngay trước (cũ → mới).
     *
     * @param  array<int, string>  $items
     * @param  list<string>  $before
     * @return list<int>
     */
    public static function order(array $items, array $before, int $seed): array
    {
        $timeline = [];

        foreach ($before as $p) {
            $timeline[] = ['fixed' => true, 'product' => $p, 'key' => null];
        }

        foreach ($items as $key => $product) {
            $timeline[] = ['fixed' => false, 'product' => $product, 'key' => (int) $key];
        }

        return array_values(self::arrange($timeline, $seed));
    }

    /**
     * Có hai bài liền nhau cùng sản phẩm mà ít nhất một bài đổi chỗ được.
     *
     * @param  list<array{fixed: bool, product: string}>  $timeline
     */
    public static function hasAdjacentRepeat(array $timeline): bool
    {
        for ($i = 1, $n = count($timeline); $i < $n; $i++) {
            if ($timeline[$i]['product'] === $timeline[$i - 1]['product'] && (! $timeline[$i]['fixed'] || ! $timeline[$i - 1]['fixed'])) {
                return true;
            }
        }

        return false;
    }

    public static function productKey(AutoVideo $v): string
    {
        return (string) ($v->product_code ?? '');
    }

    // ---------------------------------------------------------------- Cài đặt kênh

    public static function enabledFor(?AutoAccount $a): bool
    {
        return (bool) ($a?->mix_products ?? false);
    }

    /** Đánh dấu giờ do chủ app tự chọn: trộn tự động không đổi bài này. */
    public static function pin(AutoVideo $video): void
    {
        $meta = (array) ($video->meta ?? []);

        if (($meta[self::PIN] ?? false) === true) {
            return;
        }

        $meta[self::PIN] = true;
        AutoVideo::query()->whereKey($video->id)->update(['meta' => json_encode($meta, JSON_UNESCAPED_UNICODE)]);
        $video->meta = $meta;
    }

    // ---------------------------------------------------------------- Kênh: xem trước + áp dụng

    /**
     * Xem trước (không ghi gì).
     *
     * @return array{account_id: string, movable: int, changed: int, locked: int, pinned: int, products: int, before: list<array<string, mixed>>, after: list<array<string, mixed>>, changes: array<int, CarbonImmutable>, message: string}
     */
    public function plan(AutoAccount $a, bool $includePinned = false, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $videos = $this->upcoming($a, $now);
        $jobs = $this->latestJobs($videos);
        $postStatus = Post::query()->whereIn('id', $videos->pluck('post_id')->filter()->unique())->pluck('status', 'id');
        $open = Reschedule::query()->whereIn('auto_video_id', $videos->pluck('id'))->whereIn('state', Reschedule::OPEN)->pluck('auto_video_id')->flip();
        $cutoff = $now->addSeconds(self::MIN_AHEAD);
        $timeline = [];
        $locked = 0;
        $pinned = 0;

        foreach ($videos as $v) {
            $isFuture = $v->scheduled_for !== null && $v->scheduled_for->greaterThan($now);
            $why = $this->lockReason($v, $jobs[$v->post_id] ?? null, isset($open[$v->id]), $cutoff);

            if ($why === null && ! $this->isScheduledStatus($postStatus[$v->post_id] ?? null)) {
                $why = 'tiktok';
            }

            if ($why === null && ! $includePinned && (bool) data_get($v->meta, self::PIN, false)) {
                $why = 'pinned';
            }

            if ($isFuture && $why === 'pinned') {
                $pinned++;
            } elseif ($isFuture && $why !== null) {
                $locked++;
            }

            $timeline[] = ['fixed' => $why !== null, 'product' => self::productKey($v), 'key' => (int) $v->id, 'video' => $v];
        }

        $movable = collect($timeline)->where('fixed', false)->count();
        $products = collect($timeline)->where('fixed', false)->pluck('product')->unique()->count();
        // Đã xen kẽ sẵn (không có hai bài liền nhau cùng sản phẩm mà đổi được) thì để yên: không đảo lịch vô cớ mỗi lượt.
        $assign = $movable >= 2 && $products >= 2 && self::hasAdjacentRepeat($timeline)
            ? self::arrange(array_map(fn (array $t): array => ['fixed' => $t['fixed'], 'product' => $t['product'], 'key' => $t['key']], $timeline), crc32($a->social_account_id.'|mix|'.$now->format('Y-m-d H')))
            : [];

        $byId = $videos->keyBy('id');
        $changes = [];
        $after = $timeline;

        foreach ($assign as $i => $id) {
            $slot = $timeline[$i]['video']->scheduled_for;

            if ((int) $timeline[$i]['key'] !== $id) {
                $changes[$id] = CarbonImmutable::instance($slot)->utc();
            }

            $after[$i] = ['fixed' => false, 'product' => self::productKey($byId[$id]), 'key' => $id, 'video' => $byId[$id]];
        }

        $names = AutoProduct::query()->whereIn('code', $videos->pluck('product_code')->filter()->unique())->get(['code', 'short_name', 'name'])->keyBy('code');
        $label = fn (array $t, ?CarbonImmutable $at = null): array => [
            'id' => $t['key'],
            'at' => ($at ?? CarbonImmutable::instance($t['video']->scheduled_for))->toIso8601String(),
            'product' => $t['product'],
            'name' => $t['product'] === '' ? 'Chưa gắn sản phẩm' : (string) ($names->get($t['product'])?->short_name ?: $names->get($t['product'])?->name ?: $t['product']),
            'fixed' => $t['fixed'],
        ];
        $future = fn (array $t): bool => $t['video']->scheduled_for->greaterThan($now);
        $before = array_values(array_map($label, array_filter($timeline, $future)));
        $afterRows = [];

        foreach ($after as $i => $t) {
            if ($future($timeline[$i])) {
                $afterRows[] = $label($t, CarbonImmutable::instance($timeline[$i]['video']->scheduled_for));
            }
        }

        $message = match (true) {
            $movable < 2 => 'Chưa có đủ bài chưa gửi lên TikTok để trộn (cần ít nhất 2).',
            $products < 2 => 'Các bài chưa gửi lên TikTok đều cùng một sản phẩm — không có gì để trộn.',
            $changes === [] => 'Các bài đã xen kẽ sản phẩm rồi.',
            default => 'Sẽ đổi chỗ giờ của '.count($changes).' bài cho xen kẽ sản phẩm.',
        };

        return [
            'account_id' => (string) $a->social_account_id,
            'movable' => $movable,
            'changed' => count($changes),
            'locked' => $locked,
            'pinned' => $pinned,
            'products' => $products,
            'before' => $before,
            'after' => $afterRows,
            'changes' => $changes,
            'message' => $message,
        ];
    }

    /**
     * Trộn và ghi. Trả {moved, undo: list<{id, at}>, message}. Ném RuntimeException (câu tiếng Việt) khi không làm được.
     *
     * @return array{moved: int, undo: list<array{id: int, at: string}>, message: string}
     */
    public function apply(AutoAccount $a, bool $includePinned = false, ?CarbonImmutable $now = null): array
    {
        return $this->locked($a, function () use ($a, $includePinned, $now): array {
            $plan = $this->plan($a, $includePinned, $now);

            if ($plan['changes'] === []) {
                return ['moved' => 0, 'undo' => [], 'message' => $plan['message']];
            }

            return $this->write($a, $plan['changes'], $now, 'Đã trộn xen kẽ sản phẩm cho %d bài.');
        });
    }

    /**
     * "Hoàn tác": đặt lại đúng giờ cũ cho các bài vừa trộn (chỉ bài vẫn còn đổi được).
     *
     * @param  list<array{id: int|string, at: string}>  $undo
     * @return array{moved: int, undo: list<array{id: int, at: string}>, message: string}
     */
    public function restore(AutoAccount $a, array $undo, ?CarbonImmutable $now = null): array
    {
        $changes = [];

        foreach ($undo as $row) {
            $id = (int) ($row['id'] ?? 0);

            try {
                $at = CarbonImmutable::parse((string) ($row['at'] ?? ''))->utc();
            } catch (Throwable) {
                continue;
            }

            if ($id > 0) {
                $changes[$id] = $at;
            }
        }

        if ($changes === []) {
            throw new RuntimeException('Không có gì để hoàn tác.');
        }

        return $this->locked($a, fn (): array => $this->write($a, $changes, $now, 'Đã trả %d bài về giờ cũ.'));
    }

    /**
     * Trộn tự động sau khi xếp lịch (kênh bật "Tự trộn xen kẽ"). Không bao giờ ném lỗi.
     */
    public function autoMix(AutoAccount $a): int
    {
        if (! self::enabledFor($a)) {
            return 0;
        }

        try {
            $plan = $this->plan($a);

            if ($plan['changes'] === []) {
                return 0;
            }

            // Gọi từ trong khoá xếp lịch của kênh (Planner / Đăng hàng loạt): ghi thẳng, không lấy khoá lần nữa.
            return $this->write($a, $plan['changes'], null, '%d')['moved'];
        } catch (Throwable $e) {
            Log::info('Trộn xen kẽ sản phẩm tự động: bỏ qua lượt này.', ['account' => $a->social_account_id, 'error' => $e->getMessage()]);

            return 0;
        }
    }

    // ---------------------------------------------------------------- Nội bộ

    /**
     * @template T
     *
     * @param  callable(): T  $fn
     * @return T
     */
    private function locked(AutoAccount $a, callable $fn): mixed
    {
        $lock = Cache::lock('fork:auto-plan:'.$a->social_account_id, 300);

        try {
            $lock->block(15);
        } catch (LockTimeoutException) {
            throw new RuntimeException('Kênh đang được xếp lịch bởi lượt khác — thử lại sau ít phút.');
        }

        try {
            return $fn();
        } finally {
            $lock->release();
        }
    }

    /**
     * @param  array<int, CarbonImmutable>  $changes  video id => giờ mới (UTC)
     * @return array{moved: int, undo: list<array{id: int, at: string}>, message: string}
     */
    private function write(AutoAccount $a, array $changes, ?CarbonImmutable $now, string $message): array
    {
        $now ??= CarbonImmutable::now();
        $cutoff = $now->addSeconds(self::MIN_AHEAD);
        $videos = AutoVideo::query()->whereIn('id', array_keys($changes))->where('social_account_id', $a->social_account_id)->get()->keyBy('id');

        foreach ($changes as $id => $at) {
            if (! isset($videos[$id]) || $at->lessThan($cutoff) || $at->greaterThan($now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD))) {
                unset($changes[$id]);
            }
        }

        $this->reclaim($a, $videos, $changes);

        $undo = [];

        DB::transaction(function () use ($changes, $cutoff, &$undo): void {
            foreach ($changes as $id => $at) {
                $video = AutoVideo::query()->whereKey($id)->lockForUpdate()->first();
                $post = $video?->post_id ? Post::query()->whereKey($video->post_id)->lockForUpdate()->first() : null;

                if ($video === null || $post === null || $post->status !== PostStatus::Scheduled
                    || ! in_array($video->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)
                    || $post->scheduled_at === null || CarbonImmutable::instance($post->scheduled_at)->lessThan($cutoff)) {
                    throw new RuntimeException('Một bài vừa đổi trạng thái — tải lại trang rồi thử lại.');
                }

                $job = ChromeJob::query()->where('post_id', $post->id)->orderByDesc('attempt')->first();

                if ($job !== null && $job->state === 'queued') {
                    $won = ChromeJob::query()->whereKey($job->id)->where('state', 'queued')
                        ->update(['state' => 'revoked', 'note' => ChromePostWatcher::EDIT_NOTE, 'updated_at' => now()]);

                    if ($won !== 1) {
                        throw new RuntimeException(Reschedules::BUSY_TEXT);
                    }
                } elseif (! $this->jobAllowsMove($job)) {
                    throw new RuntimeException('Một bài vừa được gửi lên TikTok — tải lại trang rồi thử lại.');
                }

                $undo[] = ['id' => (int) $video->id, 'at' => CarbonImmutable::instance($post->scheduled_at)->utc()->toIso8601String()];
                $post->scheduled_at = $at;
                $post->save();
                $video->forceFill(['scheduled_for' => $at])->save();
            }
        });

        if ($changes !== []) {
            Log::info('Trộn xen kẽ sản phẩm: đổi chỗ giờ đăng.', ['account' => $a->social_account_id, 'moved' => count($changes)]);
            $this->dispatch((string) $a->social_account_id);
        }

        return ['moved' => count($changes), 'undo' => $undo, 'message' => sprintf($message, count($changes))];
    }

    /**
     * Video Xưởng được giữ chỗ trên hub tới (giờ cũ + 1 ngày). Dời muộn hơn thì gia hạn giữ chỗ trước; hub không xác nhận thì
     * KHÔNG dời bài đó (bỏ khỏi danh sách), tránh máy khác lấy mất video rồi đăng trùng.
     *
     * @param  Collection<int, AutoVideo>  $videos
     * @param  array<int, CarbonImmutable>  $changes
     */
    private function reclaim(AutoAccount $a, Collection $videos, array &$changes): void
    {
        if (! HubApi::enabled()) {
            return;
        }

        $api = null;
        $social = null;

        foreach ($changes as $id => $at) {
            $v = $videos[$id];

            if (blank($v->hub_id) || $v->scheduled_for === null || $at->lessThanOrEqualTo(CarbonImmutable::instance($v->scheduled_for))) {
                continue;
            }

            $api ??= new HubApi;
            $social ??= SocialAccount::query()->find($a->social_account_id);
            $claim = $api->claim((string) $v->hub_id, '@'.($social?->username ?: $social?->display_name), $at->addDay());

            if (! in_array($claim['state'], [HubApi::CLAIM_OK, HubApi::CLAIM_NO_ROUTE], true)) {
                throw new RuntimeException('Hub chưa xác nhận giữ chỗ video cho giờ mới — chưa trộn gì. Mở Xưởng Video rồi thử lại.');
            }
        }
    }

    /** @return Collection<int, AutoVideo> */
    private function upcoming(AutoAccount $a, CarbonImmutable $now): Collection
    {
        // Lấy cả 2 bài vừa đăng gần nhất để bài đầu tiên không trùng sản phẩm với bài vừa lên.
        $recent = AutoVideo::query()->where('social_account_id', $a->social_account_id)->whereIn('status', self::COUNTED)
            ->whereNotNull('scheduled_for')->where('scheduled_for', '<=', $now)->where('scheduled_for', '>=', $now->subDays(2))
            ->orderByDesc('scheduled_for')->limit(2)->get()->reverse();
        $future = AutoVideo::query()->where('social_account_id', $a->social_account_id)->whereIn('status', self::COUNTED)
            ->where('scheduled_for', '>', $now)->where('scheduled_for', '<=', $now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD))
            ->orderBy('scheduled_for')->orderBy('id')->get();

        return $recent->concat($future)->values();
    }

    /**
     * @param  Collection<int, AutoVideo>  $videos
     * @return Collection<int|string, ChromeJob>
     */
    private function latestJobs(Collection $videos): Collection
    {
        $ids = $videos->pluck('post_id')->filter()->unique()->values();

        return $ids->isEmpty() ? collect() : ChromeJob::query()->whereIn('post_id', $ids)->orderByDesc('attempt')->get()->unique('post_id')->keyBy('post_id');
    }

    /** null = đổi chỗ được. */
    private function lockReason(AutoVideo $v, ?ChromeJob $job, bool $openRequest, CarbonImmutable $cutoff): ?string
    {
        if ($v->scheduled_for === null || $v->scheduled_for->lessThan($cutoff)) {
            return 'soon';
        }

        if (! in_array($v->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true) || $v->post_id === null || $openRequest) {
            return 'tiktok';
        }

        return $this->jobAllowsMove($job) || $job?->state === 'queued' ? null : 'tiktok';
    }

    private function isScheduledStatus(mixed $status): bool
    {
        return $status === PostStatus::Scheduled || $status === PostStatus::Scheduled->value;
    }

    private function jobAllowsMove(?ChromeJob $job): bool
    {
        return $job === null
            || ChromeJobs::isQuotaRejection($job)
            || ($job->state === 'revoked' && ! $job->cancel_requested && ChromePostWatcher::isEditNote($job->note));
    }

    private function dispatch(string $accountId): void
    {
        try {
            $account = SocialAccount::query()->find($accountId);

            if ($account !== null) {
                app(ScheduledDispatcher::class)->dispatchForAccount($account);
            }
        } catch (Throwable $e) {
            report($e);
        }
    }
}
