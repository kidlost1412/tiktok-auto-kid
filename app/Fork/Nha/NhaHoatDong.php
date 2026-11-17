<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Rieng\Ai\RiengAiStatus;
use App\Fork\Chrome\FailureReasons;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use DateTimeInterface;
use Illuminate\Support\Facades\Cache;
use Throwable;

/**
 * "Tự thoại" của các nhân vật lo việc app (Bưu tá, Chủ quầy, Thủ kho, Cú, Mèo) trong Khu Tự Trị.
 * CHỈ ĐỌC: dựng lại việc thật vừa xảy ra trong 30 phút qua từ các bảng sẵn có (job Chrome, giỏ hàng, AI Kho riêng,
 * bình luận hỏi mua, Chrome kết nối). Không ghi gì, không gọi mạng. Lời nói do trình duyệt ghép từ mẫu câu + số liệu này.
 *
 * Mỗi dòng: id (ổn định, để trình duyệt không nói lại), n (micro-giây, thời điểm việc xảy ra), vai (khoá nhân vật), loai + số liệu.
 */
final class NhaHoatDong
{
    private const int CUA_SO_PHUT = 30;

    private const array JOB_DANG = ['claimed', 'uploading', 'ready', 'authorized'];

    private const array JOB_LOI = ['failed', 'rejected', 'uncertain'];

    /** @return list<array<string, mixed>> */
    public static function build(CarbonImmutable $now): array
    {
        $out = [];
        foreach (['buuTa', 'chuQuay', 'thuKho', 'cu', 'meo'] as $fn) {
            try {
                array_push($out, ...self::$fn($now));
            } catch (Throwable) {
                // thiếu bảng/cột (bản cũ, test) thì nhân vật đó im, nhà vẫn chạy
            }
        }
        usort($out, static fn (array $a, array $b): int => $a['n'] <=> $b['n']);

        return array_slice($out, -60);
    }

    private static function n(DateTimeInterface|string|null $t, CarbonImmutable $now): int
    {
        $c = $t === null ? $now : CarbonImmutable::parse($t);

        return (int) ($c->getTimestamp() * 1_000_000 + (int) $c->format('u'));
    }

    private static function kenh(?SocialAccount $a): ?string
    {
        if ($a === null) {
            return null;
        }

        return filled($a->username) ? '@'.ltrim((string) $a->username, '@') : ((string) $a->display_name ?: null);
    }

    private static function ngan(?string $s, int $max): ?string
    {
        $s = trim(preg_replace('/\s+/u', ' ', (string) $s) ?? '');

        return $s === '' ? null : mb_substr($s, 0, $max);
    }

    /** Bưu tá: job đăng bài của Chrome vừa đổi trạng thái (nhận việc, đang tải, đã đăng, lỗi, xếp hàng). */
    private static function buuTa(CarbonImmutable $now): array
    {
        $out = [];
        $jobs = ChromeJob::query()->with('socialAccount')
            ->where('updated_at', '>=', $now->subMinutes(self::CUA_SO_PHUT))
            ->orderByDesc('updated_at')->limit(15)->get();
        foreach ($jobs as $j) {
            $st = (string) $j->state;
            $base = ['vai' => 'buuta', 'video' => self::ngan($j->video_name, 80), 'kenh' => self::kenh($j->socialAccount), 'lan' => (int) $j->attempt];
            if ($st === 'posted') {
                $out[] = $base + ['id' => "job:{$j->id}:posted", 'n' => self::n($j->result_at ?? $j->updated_at, $now), 'loai' => 'da-dang'];
            } elseif (in_array($st, self::JOB_LOI, true)) {
                $ly = FailureReasons::forJob($j);
                $out[] = $base + ['id' => "job:{$j->id}:{$st}", 'n' => self::n($j->result_at ?? $j->updated_at, $now), 'loai' => 'dang-loi',
                    'loi' => self::ngan((string) ($ly['title'] ?? ''), 90)];
            } elseif (in_array($st, self::JOB_DANG, true)) {
                $out[] = $base + ['id' => "job:{$j->id}:{$st}", 'n' => self::n($j->claimed_at ?? $j->updated_at, $now), 'loai' => 'dang-dang', 'buoc' => $st];
            } elseif ($st === 'queued') {
                $out[] = $base + ['id' => "job:{$j->id}:queued", 'n' => self::n($j->created_at, $now), 'loai' => 'xep-hang'];
            }
        }

        return $out;
    }

    /** Chủ quầy: lấy giỏ TikTok Shop đang chạy / vừa xong (bao nhiêu sản phẩm) / vừa lỗi. */
    private static function chuQuay(CarbonImmutable $now): array
    {
        $out = [];
        $from = $now->subMinutes(self::CUA_SO_PHUT);
        $accs = AutoAccount::query()->with('socialAccount')
            ->where(fn ($q) => $q->where('products_synced_at', '>=', $from)->orWhere('products_sync_requested_at', '>=', $from))
            ->limit(10)->get();
        foreach ($accs as $a) {
            $kenh = self::kenh($a->socialAccount);
            $req = $a->products_sync_requested_at;
            $done = $a->products_synced_at;
            if ($req !== null && $req >= $from) {
                $out[] = ['id' => 'gio:'.$a->social_account_id.':'.$req->getTimestamp(), 'n' => self::n($req, $now), 'vai' => 'chuquay', 'loai' => 'lay-gio', 'kenh' => $kenh];
            }
            if (filled($a->products_sync_error) && $req !== null && $req >= $from && ($done === null || $done < $req)) {
                $out[] = ['id' => 'gio-loi:'.$a->social_account_id.':'.$req->getTimestamp(), 'n' => self::n($a->updated_at ?? $req, $now) + 1, 'vai' => 'chuquay', 'loai' => 'lay-gio-loi',
                    'kenh' => $kenh, 'loi' => self::ngan((string) $a->products_sync_error, 90)];
            } elseif ($done !== null && $done >= $from) {
                $so = ShopProduct::query()->where('social_account_id', $a->social_account_id)
                    ->where('synced_at', '>=', CarbonImmutable::parse($done)->subMinutes(5))->count();
                $out[] = ['id' => 'gio-xong:'.$a->social_account_id.':'.$done->getTimestamp(), 'n' => self::n($done, $now), 'vai' => 'chuquay', 'loai' => 'lay-gio-xong',
                    'kenh' => $kenh, 'so' => $so];
            }
        }

        return $out;
    }

    /** Thủ kho: AI Kho riêng vừa xem xong video nào, ra sản phẩm gì, chắc tới đâu; hoặc đang xem. */
    private static function thuKho(CarbonImmutable $now): array
    {
        $out = [];
        $from = $now->subMinutes(self::CUA_SO_PHUT);
        $vids = AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG)
            ->where('updated_at', '>=', $from)->orderByDesc('updated_at')->limit(30)
            ->get(['id', 'file_name', 'product_name', 'meta', 'updated_at']);
        foreach ($vids as $v) {
            $ai = is_array($v->meta['ai'] ?? null) ? $v->meta['ai'] : null;
            if ($ai === null || ! filled($ai['at'] ?? null)) {
                continue;
            }
            $at = CarbonImmutable::parse((string) $ai['at']);
            if ($at < $from) {
                continue;
            }
            $state = (string) ($ai['state'] ?? '');
            $out[] = ['id' => 'ai:'.$v->id.':'.$at->getTimestamp(), 'n' => self::n($at, $now), 'vai' => 'thukho',
                'loai' => in_array($state, ['error', 'gave_up'], true) ? 'ai-loi' : 'ai-xem',
                'video' => self::ngan((string) $v->file_name, 80), 'san_pham' => self::ngan((string) $v->product_name, 40),
                'chac' => $ai['chac'] ?? null, 'state' => $state, 'y' => self::ngan((string) ($ai['ly_do'] ?? $ai['tom_tat'] ?? ''), 90),
                'loi' => self::ngan((string) ($ai['error'] ?? ''), 90)];
            if (count($out) >= 10) {
                break;
            }
        }
        $beat = Cache::get(RiengAiStatus::KEY);
        if (is_array($beat) && ($beat['dang'] ?? false) && filled($beat['luc'] ?? null)) {
            $luc = CarbonImmutable::parse((string) $beat['luc']);
            if ($luc >= $now->subMinutes(RiengAiStatus::STALE_MINUTES)) {
                $ten = null;
                if (filled($beat['video'] ?? null)) {
                    $ten = AutoVideo::query()->whereKey($beat['video'])->value('file_name');
                }
                $out[] = ['id' => 'ai-dang:'.($beat['video'] ?? '').':'.$luc->getTimestamp(), 'n' => self::n($luc, $now), 'vai' => 'thukho', 'loai' => 'ai-dang',
                    'video' => self::ngan((string) $ten, 80), 'y' => self::ngan((string) ($beat['note'] ?? ''), 90)];
            }
        }

        return $out;
    }

    /** Cú: bình luận hỏi mua mới vào. */
    private static function cu(CarbonImmutable $now): array
    {
        $out = [];
        $rows = VideoComment::query()->where('is_buy_intent', true)
            ->where('created_at', '>=', $now->subMinutes(self::CUA_SO_PHUT))
            ->orderByDesc('created_at')->limit(5)->get(['id', 'text', 'author_handle', 'created_at']);
        foreach ($rows as $c) {
            $out[] = ['id' => 'bl:'.$c->id, 'n' => self::n($c->created_at, $now), 'vai' => 'cu', 'loai' => 'hoi-mua',
                'y' => self::ngan((string) $c->text, 80), 'ai' => self::ngan((string) $c->author_handle, 30)];
        }

        return $out;
    }

    /** Mèo (quản gia): Chrome mất kết nối bao lâu rồi. Mỗi lần mất kết nối chỉ một dòng. */
    private static function meo(CarbonImmutable $now): array
    {
        $c = ChromeClient::query()->whereNull('revoked_at')->whereNotNull('last_seen_at')->orderByDesc('last_seen_at')->first();
        if ($c === null) {
            return [];
        }
        $seen = CarbonImmutable::parse($c->last_seen_at);
        $phut = (int) floor(($now->getTimestamp() - $seen->getTimestamp()) / 60);
        if ($phut < 2 || $phut > 24 * 60) {
            return [];
        }

        return [['id' => 'chrome-tat:'.$seen->getTimestamp(), 'n' => self::n($seen, $now) + 90_000_000, 'vai' => 'meo', 'loai' => 'chrome-tat', 'so' => $phut]];
    }
}
