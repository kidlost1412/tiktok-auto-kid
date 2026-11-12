<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Carbon\CarbonImmutable;

/**
 * Ghép video của TikTok (item_id) với video trong kho (AutoVideo). Thứ tự tin cậy:
 *  1. AutoVideo.tiktok_video_id hoặc meta.tiktok_item_id đã bằng item_id;
 *  2. bài (Post.platform_post_id) hoặc kết quả job Chrome (item_id) của đúng bài đó;
 *  3. cùng kênh, giờ đăng lệch tối đa 15 phút, video chưa có id TikTok (mỗi video chỉ ghép một lần).
 * Ghép được bằng cách 2 hoặc 3 thì ghi luôn tiktok_video_id để các nơi khác dùng chung.
 */
final class VideoMatcher
{
    private const int WINDOW_SECONDS = 15 * 60;

    /**
     * @param  list<array{item_id: string, post_time: int}>  $items
     * @return array<string, AutoVideo> item_id => video
     */
    public function match(string $socialAccountId, array $items): array
    {
        $ids = array_values(array_unique(array_map(fn (array $i): string => $i['item_id'], $items)));

        if ($ids === []) {
            return [];
        }

        $found = [];

        // 1. Đã có id.
        $direct = AutoVideo::query()
            ->where('social_account_id', $socialAccountId)
            ->where(fn ($q) => $q->whereIn('tiktok_video_id', $ids)->orWhereIn('meta->tiktok_item_id', $ids))
            ->get();

        foreach ($direct as $video) {
            foreach ([$video->tiktok_video_id, data_get($video->meta, 'tiktok_item_id')] as $candidate) {
                if (is_string($candidate) && in_array($candidate, $ids, true)) {
                    $found[$candidate] ??= $video;
                }
            }
        }

        $rest = array_values(array_diff($ids, array_keys($found)));

        // 2. Bài / job Chrome.
        if ($rest !== []) {
            $postByItem = Post::query()->whereIn('platform_post_id', $rest)->pluck('id', 'platform_post_id')->all();

            $jobByItem = ChromeJob::query()
                ->where('social_account_id', $socialAccountId)
                ->where('state', 'posted')
                ->whereNotNull('post_id')
                ->whereIn('result->item_id', $rest)
                ->get(['post_id', 'result'])
                ->mapWithKeys(fn (ChromeJob $j): array => [(string) data_get($j->result, 'item_id') => $j->post_id])
                ->all();

            $postIds = array_values(array_unique(array_merge(array_values($postByItem), array_values($jobByItem))));
            $videos = $postIds === [] ? collect() : AutoVideo::query()
                ->where('social_account_id', $socialAccountId)->whereIn('post_id', $postIds)->get()->keyBy('post_id');

            foreach ($rest as $rawId) {
                $itemId = (string) $rawId;
                $postId = $postByItem[$itemId] ?? $jobByItem[$itemId] ?? null;
                $video = $postId ? $videos->get($postId) : null;

                if ($video && ! $this->hasOtherId($video, $itemId)) {
                    $this->adopt($video, $itemId);
                    $found[$itemId] = $video;
                }
            }
        }

        // 3. Giờ đăng.
        $rest = array_values(array_diff($ids, array_keys($found)));

        if ($rest !== []) {
            $times = [];

            foreach ($items as $i) {
                if (in_array($i['item_id'], $rest, true) && $i['post_time'] > 0) {
                    $times[$i['item_id']] = CarbonImmutable::createFromTimestampUTC($i['post_time']);
                }
            }

            if ($times !== []) {
                $min = min($times)->subSeconds(self::WINDOW_SECONDS);
                $max = max($times)->addSeconds(self::WINDOW_SECONDS);

                $candidates = AutoVideo::query()
                    ->where('social_account_id', $socialAccountId)
                    ->where('status', AutoVideo::POSTED)
                    ->where(fn ($q) => $q->whereNull('tiktok_video_id')->orWhere('tiktok_video_id', ''))
                    ->whereBetween('posted_at', [$min, $max])
                    ->get();

                foreach ($times as $key => $at) {
                    $itemId = (string) $key;
                    $best = $candidates
                        ->filter(fn (AutoVideo $v): bool => abs($v->posted_at->getTimestamp() - $at->getTimestamp()) <= self::WINDOW_SECONDS)
                        ->sortBy(fn (AutoVideo $v): int => abs($v->posted_at->getTimestamp() - $at->getTimestamp()))
                        ->first();

                    if ($best) {
                        $this->adopt($best, $itemId);
                        $found[$itemId] = $best;
                        $candidates = $candidates->reject(fn (AutoVideo $v): bool => $v->id === $best->id)->values();
                    }
                }
            }
        }

        return $found;
    }

    private function hasOtherId(AutoVideo $video, string $itemId): bool
    {
        return filled($video->tiktok_video_id) && (string) $video->tiktok_video_id !== $itemId;
    }

    private function adopt(AutoVideo $video, string $itemId): void
    {
        if (blank($video->tiktok_video_id)) {
            $video->forceFill(['tiktok_video_id' => $itemId])->save();
        }
    }
}
