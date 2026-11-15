<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Rieng\RiengCovers;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\ScheduledDispatcher;
use App\Models\Media;
use App\Models\Post;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use InvalidArgumentException;
use RuntimeException;
use Throwable;

/**
 * Sửa một bài đã xếp lịch mà chưa đăng (khung xem video, Lịch đăng): giờ, kênh đăng, caption, hashtag, ảnh bìa;
 * hoặc "Bỏ xếp lịch" (video về kho để sửa rồi đăng sau).
 *
 *  - Bài chưa lên TikTok: sửa thẳng trong app (job Chrome còn xếp hàng bị thu hồi qua ChromePostWatcher, bộ giao bài gửi bản mới).
 *  - Bài đã hẹn sẵn trên TikTok: TikTok không cho sửa bài hẹn, nên nhờ Chrome xoá bài cũ và KIỂM LẠI (Reschedules,
 *    PROTOCOL.md mục 12). Chỉ khi đã xác minh xoá xong mới áp thay đổi; không xác minh được thì không đổi gì.
 *
 * Video AI bị bỏ xếp lịch được đánh dấu meta.owner_hold để bộ xếp lịch tự động không lấy lại ngay; chủ app bấm
 * "Cho xếp lịch lại" khi sửa xong. Video Kho riêng thì về Kho riêng như chưa từng đăng.
 */
final class PostEdits
{
    public const string HOLD_KEY = 'owner_hold';

    public function __construct(private readonly Reschedules $reschedules, private readonly ChromeJobs $chrome) {}

    /**
     * Dữ liệu cho form sửa: hiện trạng bài, cách sửa (local/tiktok), các kênh có thể chuyển sang.
     *
     * @return array<string, mixed>
     */
    public function describe(AutoVideo $video): array
    {
        // Video đã về kho (không còn kênh, không còn bài): không có gì để sửa ở đây.
        $base = $video->social_account_id !== null
            ? $this->reschedules->describe($video)
            : ['id' => $video->id, 'kind' => null, 'reason' => 'Video đang ở kho, chưa xếp lịch.', 'current_at' => null, 'rules' => null, 'request' => null];
        $post = $video->post_id ? Post::query()->find($video->post_id) : null;
        [$caption, $tags] = $post !== null ? self::splitContent((string) $post->content) : [(string) $video->caption, array_values((array) $video->hashtags)];
        $cover = $post !== null ? $this->coverInfo($video, $post) : null;

        return [
            ...$base,
            'account_id' => $video->social_account_id ? (string) $video->social_account_id : null,
            'caption' => $caption,
            'hashtags' => $tags,
            'cover' => $cover,
            'max_chars' => HubText::MAX_CHARS,
            'accounts' => $this->accountOptions($video),
            'held' => self::isHeld($video),
            'can_release' => self::isHeld($video) && $video->status === AutoVideo::NEW,
        ];
    }

    /**
     * Sửa bài. $changes: at (ISO), social_account_id, caption, hashtags (list), cover_token (ảnh mới) hoặc cover_reset (true: về bìa sản phẩm).
     *
     * @param  array<string, mixed>  $changes
     * @return array{state: string, message: string, id?: string}
     */
    public function edit(AutoVideo $video, array $changes): array
    {
        $info = $this->reschedules->inspect($video);

        if ($this->reschedules->openFor($video) !== null) {
            throw new RuntimeException('Bài này đang chờ xoá bài hẹn cũ trên TikTok — chờ xong rồi hãy sửa tiếp.');
        }

        if ($info['kind'] === null) {
            throw new RuntimeException((string) $info['reason']);
        }

        /** @var Post $post */
        $post = $info['post'];
        $clean = $this->normalize($video, $post, $changes);

        if ($clean === []) {
            throw new RuntimeException('Chưa có gì thay đổi.');
        }

        $at = isset($clean['at']) ? CarbonImmutable::parse($clean['at'])->utc() : CarbonImmutable::instance($post->scheduled_at)->utc();
        $this->guardAttempts($post, $info['job']);

        if ($info['kind'] === 'tiktok') {
            return $this->reschedules->requestDeleteFor($video, $post, $info['job'], $at, 'edit', $clean);
        }

        if (CarbonImmutable::instance($post->scheduled_at)->lessThan(CarbonImmutable::now()->addSeconds(Reschedules::LOCAL_MIN_AHEAD))) {
            throw new RuntimeException('Bài sắp tới giờ đăng — không sửa được nữa.');
        }

        $warning = DB::transaction(function () use ($video, $post, $clean, $at): ?string {
            $post = Post::query()->whereKey($post->id)->lockForUpdate()->first();
            $video = AutoVideo::query()->whereKey($video->id)->lockForUpdate()->first();
            $this->assertStillLocal($video, $post);

            return $this->applyNow($video, $post, $clean, $at);
        });

        if ($warning !== null) {
            throw new RuntimeException($warning);
        }

        Log::info('Sửa bài chưa lên TikTok.', ['video_id' => $video->id, 'fields' => array_keys($clean)]);
        $this->dispatch((string) Post::query()->whereKey($post->id)->value('social_account_id'));

        return ['state' => 'done', 'message' => 'Đã lưu thay đổi. App sẽ hẹn bài lên TikTok theo bản mới.'];
    }

    /**
     * Bỏ xếp lịch: video về kho. Bài đã hẹn trên TikTok thì xoá trên TikTok trước (đã kiểm lại) rồi mới bỏ.
     *
     * @return array{state: string, message: string, id?: string}
     */
    public function unschedule(AutoVideo $video): array
    {
        if ($this->reschedules->openFor($video) !== null) {
            throw new RuntimeException('Bài này đang chờ xoá bài hẹn cũ trên TikTok — chờ xong rồi hãy làm tiếp.');
        }

        $info = $this->reschedules->inspect($video);

        if ($info['kind'] === null) {
            throw new RuntimeException((string) $info['reason']);
        }

        /** @var Post $post */
        $post = $info['post'];

        if ($info['kind'] === 'tiktok') {
            return $this->reschedules->requestDeleteFor($video, $post, $info['job'], CarbonImmutable::instance($post->scheduled_at), 'unschedule');
        }

        if (CarbonImmutable::instance($post->scheduled_at)->lessThan(CarbonImmutable::now()->addSeconds(Reschedules::LOCAL_MIN_AHEAD))) {
            throw new RuntimeException('Bài sắp tới giờ đăng — không bỏ xếp lịch được nữa.');
        }

        DB::transaction(function () use ($video, $post): void {
            $post = Post::query()->whereKey($post->id)->lockForUpdate()->first();
            $video = AutoVideo::query()->whereKey($video->id)->lockForUpdate()->first();
            $this->assertStillLocal($video, $post);
            $this->unscheduleNow($video, $post);
        });

        $video->refresh();

        if (! $video->isRieng()) {
            app(HubReporter::class)->released($video);
        }

        Log::info('Bỏ xếp lịch bài chưa lên TikTok, video về kho.', ['video_id' => $video->id]);

        return ['state' => 'done', 'message' => $video->isRieng()
            ? 'Đã bỏ xếp lịch. Video đã về Kho riêng — sửa xong anh đăng lại từ đó.'
            : 'Đã bỏ xếp lịch. Video đã về kho và tạm không tự xếp lịch — sửa xong bấm "Cho xếp lịch lại".'];
    }

    /** Video AI đã bỏ xếp lịch: cho bộ xếp lịch tự động lấy lại. */
    public function release(AutoVideo $video): void
    {
        if (! self::isHeld($video)) {
            return;
        }

        $meta = (array) $video->meta;
        unset($meta[self::HOLD_KEY]);
        $video->forceFill(['meta' => $meta === [] ? null : $meta])->save();
    }

    public static function isHeld(AutoVideo $video): bool
    {
        return data_get($video->meta, self::HOLD_KEY) !== null;
    }

    // ---------------------------------------------------------------- Áp thay đổi (gọi trong giao dịch, hàng đã khoá)

    /**
     * Áp thay đổi đã kiểm vào bài + video. null = xong; ngược lại là câu cảnh báo (không đổi gì).
     *
     * @param  array<string, mixed>  $clean
     */
    public function applyNow(AutoVideo $video, Post $post, array $clean, CarbonImmutable $at): ?string
    {
        $meta = (array) $post->meta;
        $videoMeta = (array) $video->meta;
        $postFill = [];
        $videoFill = [];

        if (isset($clean['social_account_id']) && (string) $clean['social_account_id'] !== (string) $post->social_account_id) {
            $social = SocialAccount::query()->find((string) $clean['social_account_id']);
            $link = $social ? $this->cartLink($video, $social) : null;

            if ($social === null || $link === null) {
                return 'Kênh mới không còn sẵn sàng (chưa chọn sản phẩm giỏ hàng) — chưa đổi kênh.';
            }

            $postFill['social_account_id'] = $social->id;
            $postFill += $social->channelSnapshot();
            $meta['fork_shop_product_id'] = (string) $link->shop_product_id;

            if (($meta['fork_shop_name_src'] ?? 'link') !== 'video') {
                $meta['fork_shop_product_name'] = CartRules::limitName((string) $link->display_name);
            }

            $videoFill['social_account_id'] = $social->id;
        }

        if (array_key_exists('caption', $clean) || array_key_exists('hashtags', $clean)) {
            [$oldCaption, $oldTags] = self::splitContent((string) $post->content);
            $caption = array_key_exists('caption', $clean) ? (string) $clean['caption'] : $oldCaption;
            $tags = array_key_exists('hashtags', $clean) ? array_values((array) $clean['hashtags']) : $oldTags;
            $postFill['content'] = HubText::compose($caption, $tags);
            $videoFill += ['caption' => $caption, 'hashtags' => $tags, 'caption_source' => 'owner'];
        }

        if (! empty($clean['cover_token'])) {
            try {
                $c = app(RiengCovers::class)->attach($video, (string) $clean['cover_token']);
            } catch (InvalidArgumentException $e) {
                return 'Ảnh bìa lỗi: '.$e->getMessage();
            }

            $meta['fork_cover'] = $c['file'];
            $meta['fork_cover_src'] = RiengCovers::SOURCE;
            $videoMeta['cover'] = ['file' => $c['file'], 'kind' => 'own', 'w' => $c['w'], 'h' => $c['h']];
        } elseif (! empty($clean['cover_reset'])) {
            app(RiengCovers::class)->forget((int) $video->id);
            unset($meta['fork_cover'], $meta['fork_cover_src'], $videoMeta['cover']);
            $product = filled($video->product_code) ? AutoProduct::query()->find($video->product_code) : null;
            $pick = $product !== null ? app(CoverStore::class)->pick($product) : null;

            if ($pick !== null) {
                $meta['fork_cover'] = $pick;
            }
        }

        $postFill['meta'] = $meta;
        $postFill['scheduled_at'] = $at->utc();
        $videoFill['scheduled_for'] = $at->utc();
        $videoFill['meta'] = $videoMeta === [] ? null : $videoMeta;

        $post->forceFill($postFill)->save();
        $video->forceFill($videoFill)->save();

        return null;
    }

    /** Bỏ bài trong app, video về kho. Gọi trong giao dịch, hàng đã khoá. */
    public function unscheduleNow(AutoVideo $video, Post $post): void
    {
        Media::query()->where('post_id', $post->id)->get()->each(function (Media $m): void {
            try {
                if (filled($m->path)) {
                    Storage::delete((string) $m->path);
                }
            } catch (Throwable) {
            }

            $m->delete();
        });

        // Xoá bài: ChromePostWatcher thu hồi mọi job còn trước bước cấp quyền.
        $post->delete();

        $meta = (array) $video->meta;
        unset($meta['hub_claimed_at']);

        if (! $video->isRieng()) {
            $meta[self::HOLD_KEY] = now()->toIso8601String();
        }

        $video->forceFill([
            'status' => AutoVideo::NEW,
            'social_account_id' => null,
            'post_id' => null,
            'scheduled_for' => null,
            'posted_at' => null,
            'skip_reason' => null,
            'meta' => $meta === [] ? null : $meta,
        ])->save();
    }

    // ---------------------------------------------------------------- Kiểm tra

    /**
     * Chỉ giữ những gì thật sự đổi, kiểm từng thứ. Ném RuntimeException (câu tiếng Việt) khi không hợp lệ.
     *
     * @param  array<string, mixed>  $changes
     * @return array<string, mixed>
     */
    private function normalize(AutoVideo $video, Post $post, array $changes): array
    {
        $clean = [];
        $currentAt = CarbonImmutable::instance($post->scheduled_at)->utc()->second(0);
        $at = $currentAt;

        if (filled($changes['at'] ?? null)) {
            try {
                $at = CarbonImmutable::parse((string) $changes['at'])->utc()->second(0);
            } catch (Throwable) {
                throw new RuntimeException('Giờ mới không hợp lệ.');
            }

            if (! $at->equalTo($currentAt)) {
                $clean['at'] = $at->toIso8601String();
            }
        }

        $target = $video;

        if (filled($changes['social_account_id'] ?? null) && (string) $changes['social_account_id'] !== (string) $post->social_account_id) {
            $social = $this->accountOptions($video, (string) $changes['social_account_id'])[0] ?? null;

            if ($social === null) {
                throw new RuntimeException('Không tìm thấy kênh này.');
            }

            if (! $social['ok']) {
                throw new RuntimeException((string) $social['reason']);
            }

            $clean['social_account_id'] = $social['id'];
            $target = $video->replicate();
            $target->id = $video->id;
            $target->social_account_id = $social['id'];
        }

        // Giờ phải hợp lệ với kênh đích (đổi giờ, hoặc đổi kênh mà giữ giờ).
        if (isset($clean['at']) || isset($clean['social_account_id'])) {
            $probe = $post->replicate();
            $probe->id = $post->id;

            if (! isset($clean['at'])) {
                $probe->scheduled_at = null;
            }

            if (($refusal = $this->reschedules->timeRefusal($target, $probe, $at)) !== null) {
                throw new RuntimeException($refusal);
            }
        }

        [$oldCaption, $oldTags] = self::splitContent((string) $post->content);

        // Laravel đổi chuỗi rỗng thành null: gửi caption null nghĩa là xoá trắng caption.
        if (array_key_exists('caption', $changes) && (is_string($changes['caption']) || $changes['caption'] === null)) {
            $caption = trim(str_replace("\r\n", "\n", (string) $changes['caption']));

            if ($caption !== $oldCaption) {
                $clean['caption'] = $caption;
            }
        }

        if (array_key_exists('hashtags', $changes) && is_array($changes['hashtags'])) {
            $tags = self::cleanTags($changes['hashtags']);

            if ($tags !== $oldTags) {
                $clean['hashtags'] = $tags;
            }
        }

        if (array_key_exists('caption', $clean) || array_key_exists('hashtags', $clean)) {
            $content = HubText::compose($clean['caption'] ?? $oldCaption, $clean['hashtags'] ?? $oldTags);

            if (trim($content) === '') {
                throw new RuntimeException('Caption không được để trống.');
            }

            if (mb_strlen($content) > HubText::MAX_CHARS) {
                throw new RuntimeException('Caption và hashtag dài quá '.HubText::MAX_CHARS.' ký tự (giới hạn TikTok).');
            }
        }

        if (filled($changes['cover_token'] ?? null)) {
            if (app(RiengCovers::class)->tmpPath((string) $changes['cover_token']) === null) {
                throw new RuntimeException('Ảnh bìa đã chọn không còn nữa, hãy chọn lại.');
            }

            $clean['cover_token'] = (string) $changes['cover_token'];
        } elseif (! empty($changes['cover_reset']) && data_get($post->meta, 'fork_cover_src') === RiengCovers::SOURCE) {
            $clean['cover_reset'] = true;
        }

        return $clean;
    }

    private function guardAttempts(Post $post, ?ChromeJob $job): void
    {
        if ($job === null) {
            return;
        }

        $tries = ChromeJob::query()->where('post_id', $post->id)->get(['state', 'result'])
            ->reject(fn (ChromeJob $j): bool => ChromeJobs::isQuotaRejection($j))->count();

        if ($tries >= ChromeJobs::MAX_ATTEMPTS) {
            throw new RuntimeException('Bài này đã được giao cho Chrome '.ChromeJobs::MAX_ATTEMPTS.' lần — không sửa thêm được (giới hạn chống đăng trùng). Hãy bỏ xếp lịch rồi đăng lại.');
        }
    }

    private function assertStillLocal(?AutoVideo $video, ?Post $post): void
    {
        if ($post === null || $video === null || $post->status !== PostStatus::Scheduled
            || ! in_array($video->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)) {
            throw new RuntimeException('Bài vừa thay đổi trạng thái — tải lại rồi thử lại.');
        }

        $job = $this->chrome->latestForPost($post);

        if ($job !== null && $job->state === 'queued') {
            return;   // ChromePostWatcher thu hồi khi bài được sửa/xoá.
        }

        if ($job !== null && ! in_array($job->state, ['revoked', 'failed'], true) && ! ChromeJobs::isQuotaRejection($job)) {
            throw new RuntimeException($job->state === 'posted' ? 'Bài vừa được hẹn lên TikTok — tải lại rồi thử lại.' : Reschedules::BUSY_TEXT);
        }
    }

    /**
     * Kênh TikTok có thể đăng bài này: đã bật Chrome và đã chọn sản phẩm giỏ hàng cho sản phẩm của video.
     *
     * @return list<array{id: string, username: ?string, name: ?string, avatar: ?string, ok: bool, reason: ?string, current: bool}>
     */
    private function accountOptions(AutoVideo $video, ?string $only = null): array
    {
        $enabled = ChromeAccount::query()->where('enabled', true)->pluck('social_account_id')->map(fn ($id): string => (string) $id)->all();
        /** @var Collection<int, SocialAccount> $accounts */
        $accounts = SocialAccount::query()
            ->whereIn('id', $enabled)
            ->when($only !== null, fn ($q) => $q->whereKey($only))
            ->orderBy('username')
            ->get();

        return $accounts->map(function (SocialAccount $a) use ($video): array {
            $link = $this->cartLink($video, $a);
            $reason = $link === null
                ? 'Kênh @'.($a->username ?: $a->display_name).' chưa chọn sản phẩm giỏ hàng cho sản phẩm của video này — vào Giỏ hàng gắn trước.'
                : null;

            return [
                'id' => (string) $a->id,
                'username' => $a->username,
                'name' => $a->display_name,
                'avatar' => $a->avatar_url,
                'ok' => $reason === null,
                'reason' => $reason,
                'current' => (string) $a->id === (string) $video->social_account_id,
            ];
        })->values()->all();
    }

    private function cartLink(AutoVideo $video, SocialAccount $social): ?ProductLink
    {
        if (! filled($video->product_code)) {
            return null;
        }

        $link = ProductLink::slot((string) $social->id, (string) $video->product_code, $video->quy_cach)->first();

        return $link !== null && preg_match(ShopSync::ID_PATTERN, (string) $link->shop_product_id) === 1
            && CartRules::limitName((string) $link->display_name) !== '' ? $link : null;
    }

    /** @return array{own: bool, url: ?string}|null */
    private function coverInfo(AutoVideo $video, Post $post): ?array
    {
        $own = data_get($post->meta, 'fork_cover_src') === RiengCovers::SOURCE && filled(data_get($post->meta, 'fork_cover'));

        return ['own' => $own, 'url' => '/auto/kho/video/'.$video->id.'/bia'];
    }

    // ---------------------------------------------------------------- Chữ

    /**
     * Tách nội dung bài thành caption + dòng hashtag cuối (HubText::compose nối bằng một dòng trống).
     *
     * @return array{0: string, 1: list<string>}
     */
    public static function splitContent(string $content): array
    {
        $content = trim(str_replace("\r\n", "\n", $content));
        $pos = strrpos($content, "\n\n");

        if ($pos !== false) {
            $tail = trim(substr($content, $pos + 2));
            $words = preg_split('/\s+/u', $tail) ?: [];

            if ($words !== [] && collect($words)->every(fn (string $w): bool => preg_match('/^#[^#\s]+$/u', $w) === 1)) {
                return [trim(substr($content, 0, $pos)), array_values($words)];
            }
        }

        return [$content, []];
    }

    /**
     * @param  array<int, mixed>  $raw
     * @return list<string>
     */
    public static function cleanTags(array $raw): array
    {
        $out = [];
        $seen = [];

        foreach ($raw as $t) {
            if (! is_string($t)) {
                continue;
            }

            foreach (preg_split('/[\s,]+/u', $t) ?: [] as $w) {
                $w = ltrim(trim($w), '#');

                if ($w === '') {
                    continue;
                }

                $key = mb_strtolower($w);

                if (! isset($seen[$key])) {
                    $seen[$key] = true;
                    $out[] = '#'.$w;
                }
            }
        }

        return $out;
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
