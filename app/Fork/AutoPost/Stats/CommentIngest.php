<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Models\VideoStat;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;

/**
 * Nhận bình luận do tiện ích gửi (POST /api/ext/comments): lưu theo comment_id (gửi lại không nhân đôi, chỉ cập nhật
 * số tim / số trả lời), ghép với video trong kho theo item_id và gắn cờ "hỏi mua / hỏi giá".
 */
final class CommentIngest
{
    public const int MAX_COMMENTS = 300;

    /**
     * @param  array<int, mixed>  $comments
     * @return array{received: int, new: int, buy_new: int}
     */
    public function ingest(SocialAccount $account, array $comments, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $rows = $this->normalize($comments);

        if ($rows === []) {
            return ['received' => 0, 'new' => 0, 'buy_new' => 0];
        }

        $itemIds = array_values(array_unique(array_column($rows, 'item_id')));
        $videoByItem = VideoStat::query()
            ->where('social_account_id', (string) $account->id)->whereIn('item_id', $itemIds)->whereNotNull('auto_video_id')
            ->pluck('auto_video_id', 'item_id')->all();

        $missing = array_values(array_diff($itemIds, array_keys($videoByItem)));

        if ($missing !== []) {
            $videoByItem += AutoVideo::query()->where('social_account_id', (string) $account->id)->whereIn('tiktok_video_id', $missing)->pluck('id', 'tiktok_video_id')->all();
        }

        $existing = VideoComment::query()->whereIn('comment_id', array_column($rows, 'comment_id'))->get()->keyBy('comment_id');
        $own = mb_strtolower((string) $account->username);
        $new = 0;
        $buyNew = 0;

        foreach ($rows as $r) {
            $row = $existing->get($r['comment_id']);

            if ($row) {
                $row->forceFill(['like_count' => $r['like_count'], 'reply_count' => $r['reply_count']])->save();

                continue;
            }

            $intent = BuyIntent::detect($r['text']);
            // Chủ kênh tự trả lời "giá 99k, ship toàn quốc" thì không phải khách hỏi mua.
            $buy = $intent['buy'] && ($own === '' || mb_strtolower($r['author_handle']) !== $own);

            VideoComment::query()->create([
                'comment_id' => $r['comment_id'],
                'social_account_id' => (string) $account->id,
                'item_id' => $r['item_id'],
                'auto_video_id' => $videoByItem[$r['item_id']] ?? null,
                'author_id' => $r['author_id'] ?: null,
                'author_handle' => $r['author_handle'] ?: null,
                'author_name' => $r['author_name'] ?: null,
                'text' => $r['text'],
                'like_count' => $r['like_count'],
                'reply_count' => $r['reply_count'],
                'commented_at' => $r['created_at'] > 0 ? CarbonImmutable::createFromTimestampUTC($r['created_at']) : $now,
                'is_buy_intent' => $buy,
                'intent_keywords' => $buy ? implode(', ', $intent['keywords']) : null,
            ]);

            $new++;
            $buyNew += $buy ? 1 : 0;
        }

        return ['received' => count($rows), 'new' => $new, 'buy_new' => $buyNew];
    }

    /**
     * @param  array<int, mixed>  $comments
     * @return list<array{comment_id: string, item_id: string, text: string, created_at: int, like_count: int, reply_count: int, author_id: string, author_handle: string, author_name: string}>
     */
    private function normalize(array $comments): array
    {
        $out = [];
        $seen = [];
        $int = fn (mixed $v): int => is_numeric($v) && $v >= 0 ? (int) $v : 0;
        $str = fn (mixed $v, int $max): string => is_string($v) ? mb_substr(trim($v), 0, $max) : '';

        foreach (array_slice(array_values($comments), 0, self::MAX_COMMENTS) as $c) {
            if (! is_array($c)) {
                continue;
            }

            $id = $c['comment_id'] ?? null;
            $item = $c['item_id'] ?? null;
            $text = $str($c['text'] ?? null, 2000);

            if (! is_string($id) || ! is_string($item) || $text === ''
                || preg_match('/^[0-9]{5,25}$/', $id) !== 1 || preg_match('/^[0-9]{5,25}$/', $item) !== 1 || isset($seen[$id])) {
                continue;
            }

            $seen[$id] = true;
            $out[] = [
                'comment_id' => $id,
                'item_id' => $item,
                'text' => $text,
                'created_at' => $int($c['created_at'] ?? 0),
                'like_count' => $int($c['like_count'] ?? 0),
                'reply_count' => $int($c['reply_count'] ?? 0),
                'author_id' => preg_match('/^[0-9]{1,32}$/', (string) ($c['author_id'] ?? '')) === 1 ? (string) $c['author_id'] : '',
                'author_handle' => $str($c['author_handle'] ?? null, 64),
                'author_name' => $str($c['author_name'] ?? null, 128),
            ];
        }

        return $out;
    }
}
