<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Models\AutoSetting;
use Throwable;

/**
 * Nhớ ảnh bìa đã chọn ở hộp "Đăng / hẹn giờ" của Kho riêng để lần sau tự dùng lại:
 *  - theo video: mọi ảnh chủ app tự chọn cho một video (tải lên hoặc lấy khung), nhớ ngay khi chọn;
 *  - theo kênh + sản phẩm: cách chọn bìa (sản phẩm / tải lên / khung) và ảnh chung của lượt đăng gần nhất;
 *  - theo kênh: như trên nhưng chỉ theo kênh (dùng khi kênh + sản phẩm này chưa có gì để nhớ).
 *
 * Ảnh nhớ nằm ở <thư mục bìa riêng>/_saved/<uuid>.jpg (không bị dọn như ảnh tạm), dùng chung đường token với ảnh tạm
 * (RiengCovers::tmpPath tìm cả ở đây). Bảng nhớ là một JSON trong fork_auto_settings.
 */
final class RiengCoverMemory
{
    public const string KEY = 'rieng.cover_memory';

    /** Giữ tối đa ngần này video trong bảng nhớ (bỏ video cũ nhất). */
    private const int MAX_VIDEOS = 2000;

    private const array MODES = [RiengBatch::COVER_PRODUCT, RiengBatch::COVER_UPLOAD, RiengBatch::COVER_FRAME];

    public function __construct(private readonly RiengCovers $covers) {}

    /** Nhớ ảnh đã chọn cho một video. Trả về false nếu token không còn. */
    public function rememberVideo(int $videoId, string $token): bool
    {
        $file = $this->keep($token);

        if ($videoId <= 0 || $file === null) {
            return false;
        }

        $m = $this->load();
        unset($m['video'][(string) $videoId]);
        $m['video'][(string) $videoId] = $file;

        if (count($m['video']) > self::MAX_VIDEOS) {
            $m['video'] = array_slice($m['video'], -self::MAX_VIDEOS, null, true);
        }

        $this->save($m);

        return true;
    }

    /** Bỏ ảnh đã nhớ của một video (chủ app bấm "Dùng bìa mặc định"). */
    public function forgetVideo(int $videoId): void
    {
        $m = $this->load();

        if (isset($m['video'][(string) $videoId])) {
            unset($m['video'][(string) $videoId]);
            $this->save($m);
        }
    }

    /** Nhớ cách chọn bìa (và ảnh chung nếu có) cho kênh + sản phẩm và cho kênh. */
    public function rememberChoice(string $accountId, string $code, ?string $quyCach, string $mode, ?string $batchToken): void
    {
        if ($accountId === '' || ! in_array($mode, self::MODES, true)) {
            return;
        }

        $file = $mode === RiengBatch::COVER_UPLOAD && $batchToken !== null && $batchToken !== '' ? $this->keep($batchToken) : null;
        $entry = ['mode' => $mode, 'file' => $file];
        $m = $this->load();
        $m['pair'][$this->pairKey($accountId, $code, $quyCach)] = $entry;
        $m['account'][$accountId] = $entry;
        $this->save($m);
    }

    /**
     * Những gì đã nhớ cho lượt đăng sắp mở.
     *
     * @param  list<int>  $videoIds
     * @return array{mode: ?string, from: ?string, batch: ?array{token: string, url: string}, rows: array<int, array{token: string, url: string}>}
     */
    public function recall(string $accountId, string $code, ?string $quyCach, array $videoIds): array
    {
        $m = $this->load();
        $pair = $m['pair'][$this->pairKey($accountId, $code, $quyCach)] ?? null;
        $acc = $m['account'][$accountId] ?? null;
        $pick = is_array($pair) ? $pair : (is_array($acc) ? $acc : null);
        $mode = is_array($pick) && in_array($pick['mode'] ?? null, self::MODES, true) ? (string) $pick['mode'] : null;
        $batch = null;

        if ($mode === RiengBatch::COVER_UPLOAD) {
            $batch = $this->asToken($pick['file'] ?? null);

            // Ảnh chung đã mất thì không ép "Tải ảnh lên" (sẽ báo thiếu ảnh) — để mặc định.
            if ($batch === null) {
                $mode = null;
            }
        }

        $rows = [];

        foreach (array_unique(array_map('intval', $videoIds)) as $id) {
            $t = $this->asToken($m['video'][(string) $id] ?? null);

            if ($t !== null) {
                $rows[$id] = $t;
            }
        }

        return ['mode' => $mode, 'from' => $mode === null ? null : (is_array($pair) ? 'pair' : 'account'), 'batch' => $batch, 'rows' => $rows];
    }

    /** Chép ảnh tạm sang chỗ nhớ (cùng tên). Ảnh đã nằm ở chỗ nhớ thì giữ nguyên. */
    private function keep(string $token): ?string
    {
        if (! RiengCovers::validName($token)) {
            return null;
        }

        $saved = $this->covers->savedDir().'/'.$token;

        if (is_file($saved)) {
            return $token;
        }

        $src = $this->covers->tmpPath($token);

        if ($src === null) {
            return null;
        }

        try {
            $this->covers->ensureSavedDir();

            return @copy($src, $saved) ? $token : null;
        } catch (Throwable) {
            return null;
        }
    }

    /** @return array{token: string, url: string}|null */
    private function asToken(mixed $file): ?array
    {
        if (! is_string($file) || ! RiengCovers::validName($file) || ! is_file($this->covers->savedDir().'/'.$file)) {
            return null;
        }

        return ['token' => $file, 'url' => '/auto/kho/rieng/anh-bia/tam/'.$file];
    }

    private function pairKey(string $accountId, string $code, ?string $quyCach): string
    {
        return $accountId.'|'.$code.'|'.($quyCach ?? '');
    }

    /** @return array{video: array<string, string>, pair: array<string, mixed>, account: array<string, mixed>} */
    private function load(): array
    {
        $raw = json_decode((string) AutoSetting::read(self::KEY, '{}'), true);
        $raw = is_array($raw) ? $raw : [];

        return [
            'video' => is_array($raw['video'] ?? null) ? $raw['video'] : [],
            'pair' => is_array($raw['pair'] ?? null) ? $raw['pair'] : [],
            'account' => is_array($raw['account'] ?? null) ? $raw['account'] : [],
        ];
    }

    /** @param  array{video: array<string, string>, pair: array<string, mixed>, account: array<string, mixed>}  $m */
    private function save(array $m): void
    {
        AutoSetting::write(self::KEY, (string) json_encode($m, JSON_UNESCAPED_UNICODE));
        $this->gc($m);
    }

    /** Xoá ảnh ở chỗ nhớ không còn ai dùng (để lâu hơn 1 ngày, tránh xoá ảnh vừa chép). */
    private function gc(array $m): void
    {
        $used = array_flip(array_filter([
            ...array_values($m['video']),
            ...array_map(fn ($e) => is_array($e) ? ($e['file'] ?? null) : null, array_values($m['pair'])),
            ...array_map(fn ($e) => is_array($e) ? ($e['file'] ?? null) : null, array_values($m['account'])),
        ], 'is_string'));

        foreach (glob($this->covers->savedDir().'/*.jpg') ?: [] as $f) {
            if (! isset($used[basename($f)]) && time() - (int) @filemtime($f) > 86400) {
                @unlink($f);
            }
        }
    }
}
