<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Persona;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Models\Post;
use Illuminate\Support\Carbon;

/**
 * Gợi ý hashtag cho ô "Hashtag chung" khi đăng hàng loạt: hashtag đã dùng ở các bài trước (trong caption),
 * hashtag đã cài cho từng sản phẩm và hashtag mặc định chung. Xếp theo mức dùng nhiều và mới.
 */
final class HashtagSuggestions
{
    /** Số bài gần nhất được đọc caption (đủ rộng để thấy xu hướng, đủ nhẹ để không chậm trang). */
    private const int POST_LIMIT = 400;

    /** Nửa đời của độ "mới": bài cũ hơn ngần này ngày chỉ còn nửa điểm. */
    private const float HALF_LIFE_DAYS = 30.0;

    /** Điểm cộng cho hashtag người dùng chủ động cài (sản phẩm / mặc định chung): đáng tin hơn hashtag lẫn trong caption. */
    private const float PRODUCT_BONUS = 2.0;

    private const float DEFAULT_BONUS = 3.0;

    /**
     * @return list<array{tag: string, uses: int}> hashtag (có # đứng đầu), nhiều điểm nhất trước
     */
    public static function top(int $limit = 40): array
    {
        /** @var array<string, array{tag: string, score: float, uses: int}> $stats */
        $stats = [];
        $add = function (string $tag, float $score, int $uses = 1) use (&$stats): void {
            $key = mb_strtolower(ltrim($tag, '#'));

            if ($key === '') {
                return;
            }

            $stats[$key] ??= ['tag' => '#'.ltrim($tag, '#'), 'score' => 0.0, 'uses' => 0];
            $stats[$key]['score'] += $score;
            $stats[$key]['uses'] += $uses;
        };

        $now = Carbon::now();

        Post::query()
            ->where('content', 'like', '%#%')
            ->latest('created_at')
            ->limit(self::POST_LIMIT)
            ->get(['content', 'created_at'])
            ->each(function (Post $p) use ($add, $now): void {
                $days = max(0.0, (float) $now->diffInDays($p->created_at ?? $now, true));
                $weight = 1.0 + 2.0 * (0.5 ** ($days / self::HALF_LIFE_DAYS));

                // Một hashtag lặp nhiều lần trong cùng một bài chỉ tính một lần.
                $seen = [];

                foreach (Hashtags::tagsIn((string) $p->content) as $tag) {
                    $key = mb_strtolower($tag);

                    if (! isset($seen[$key])) {
                        $seen[$key] = true;
                        $add($tag, $weight);
                    }
                }
            });

        AutoProduct::query()->get(['hashtags'])->each(function (AutoProduct $p) use ($add): void {
            foreach (Hashtags::normalize($p->hashtags) as $tag) {
                $add($tag, self::PRODUCT_BONUS);
            }
        });

        foreach (Hashtags::defaults()['tags'] as $tag) {
            $add($tag, self::DEFAULT_BONUS);
        }

        uasort($stats, fn (array $a, array $b): int => [$b['score'], $a['tag']] <=> [$a['score'], $b['tag']]);

        return array_values(array_map(
            fn (array $s): array => ['tag' => $s['tag'], 'uses' => $s['uses']],
            array_slice($stats, 0, max(1, $limit)),
        ));
    }
}
