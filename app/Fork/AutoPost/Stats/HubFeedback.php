<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\SocialAccount;
use App\Fork\AutoPost\Paths;
use App\Fork\AutoPost\Sidecar;
use Carbon\CarbonImmutable;

/**
 * Ghi số liệu ngược về hub: so-lieu.csv mỗi ngày và cột luot_xem của bang-ghi.csv (ngày cũ).
 * Luôn ghi file tạm rồi rename; giữ BOM UTF-8.
 */
final class HubFeedback
{
    private const string BOM = "\xEF\xBB\xBF";

    private const array HEADER = ['file', 'tai_khoan', 'dang_luc', 'link', 'xem_24h', 'thich_24h', 'xem_72h', 'thich_72h', 'xem_moi_nhat', 'cap_nhat'];

    /** Không đụng vào bang-ghi.csv nếu mới sửa trong ngần này giây. */
    private const int QUIET_SECONDS = 3600;

    /**
     * @param  list<string>  $dates  Y-m-d
     * @return array{sheets: int, filled: int}
     */
    public function sync(array $dates, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $sheets = 0;
        $filled = 0;

        foreach ($dates as $date) {
            $dir = Paths::root((string) config('fork.auto.hub_path')).'/ra/'.$date;

            if (! is_dir($dir)) {
                continue;
            }

            $videos = AutoVideo::query()
                ->where('status', 'posted')
                ->notRieng()
                ->whereDate('batch_date', $date)
                ->orderBy('posted_at')
                ->get();

            if ($videos->isEmpty()) {
                continue;
            }

            if ($this->writeSheet(Sidecar::path($dir, 'so-lieu.csv'), $videos)) {
                $sheets++;
            }

            if ($date < $now->format('Y-m-d')) {
                $filled += $this->fillViews(Sidecar::path($dir, 'bang-ghi.csv'), $videos, $now);
            }
        }

        // Kho chuẩn mới: so-lieu.csv nằm cạnh .ket-qua.json trong da-dang/<ngày đăng>/.
        $byDir = AutoVideo::query()
            ->where('status', 'posted')
            ->where('source', 'kho')
            ->whereNotNull('stats')
            ->orderBy('posted_at')
            ->get()
            ->groupBy(fn (AutoVideo $v): string => dirname($v->path));

        foreach ($byDir as $dir => $videos) {
            if (is_dir($dir) && $this->writeSheet($dir.'/so-lieu.csv', $videos)) {
                $sheets++;
            }
        }

        return ['sheets' => $sheets, 'filled' => $filled];
    }

    /** @param  iterable<AutoVideo>  $videos */
    private function writeSheet(string $path, iterable $videos): bool
    {
        $accounts = SocialAccount::query()
            ->whereIn('id', collect($videos)->pluck('social_account_id')->filter()->unique()->all())
            ->get()
            ->keyBy('id');

        $rows = [self::HEADER];

        foreach ($videos as $v) {
            $s = (array) ($v->stats ?? []);
            $account = $accounts[$v->social_account_id] ?? null;
            $tz = $account?->timezone ?: 'Asia/Ho_Chi_Minh';
            $rows[] = [
                $v->file_name,
                (string) ($account?->username ?? ''),
                $v->posted_at ? CarbonImmutable::instance($v->posted_at)->setTimezone($tz)->format('Y-m-d H:i') : '',
                (string) ($s['link'] ?? ''),
                $s['h24']['views'] ?? '',
                $s['h24']['likes'] ?? '',
                $s['h72']['views'] ?? '',
                $s['h72']['likes'] ?? '',
                $s['latest']['views'] ?? '',
                $v->stats_written_at ? CarbonImmutable::instance($v->stats_written_at)->toIso8601String() : '',
            ];
        }

        return $this->atomicWrite($path, $this->encode($rows, "\r\n"));
    }

    /** @param  iterable<AutoVideo>  $videos */
    private function fillViews(string $path, iterable $videos, CarbonImmutable $now): int
    {
        if (! is_file($path)) {
            return 0;
        }

        $mtime = (int) filemtime($path);

        if ($now->getTimestamp() - $mtime < self::QUIET_SECONDS) {
            return 0;
        }

        $raw = (string) file_get_contents($path);
        $text = str_starts_with($raw, self::BOM) ? substr($raw, 3) : $raw;
        $eol = str_contains($text, "\r\n") ? "\r\n" : "\n";

        $rows = $this->decode($text);

        if (count($rows) < 2) {
            return 0;
        }

        $header = $rows[0];
        $fileCol = array_search('file', $header, true);
        $viewCol = array_search('luot_xem', $header, true);

        if ($fileCol === false || $viewCol === false) {
            return 0;
        }

        $views = [];
        foreach ($videos as $v) {
            $latest = ((array) ($v->stats ?? []))['latest']['views'] ?? null;
            if ($latest !== null) {
                $views[$v->file_name] = (string) $latest;
            }
        }

        $filled = 0;
        for ($i = 1, $n = count($rows); $i < $n; $i++) {
            $file = basename(str_replace('\\', '/', (string) ($rows[$i][$fileCol] ?? '')));

            if (! isset($views[$file])) {
                continue;
            }

            $rows[$i] = array_pad($rows[$i], count($header), '');

            if ($rows[$i][$viewCol] !== $views[$file]) {
                $rows[$i][$viewCol] = $views[$file];
                $filled++;
            }
        }

        if ($filled === 0) {
            return 0;
        }

        // Hub vừa sửa file trong lúc xử lý thì bỏ qua, lần sau làm lại.
        clearstatcache(true, $path);
        if ((int) filemtime($path) !== $mtime) {
            return 0;
        }

        return $this->atomicWrite($path, $this->encode($rows, $eol)) ? $filled : 0;
    }

    /** @return list<list<string>> */
    private function decode(string $text): array
    {
        $h = fopen('php://temp', 'r+');
        fwrite($h, $text);
        rewind($h);
        $rows = [];

        while (($row = fgetcsv($h, 0, ',', '"', '')) !== false) {
            if ($row === [null]) {
                continue;
            }
            $rows[] = array_map(fn ($c) => (string) $c, $row);
        }

        fclose($h);

        return $rows;
    }

    /** @param  list<list<string|int>>  $rows */
    private function encode(array $rows, string $eol): string
    {
        $out = self::BOM;

        foreach ($rows as $row) {
            $out .= implode(',', array_map(
                fn ($c): string => '"'.str_replace('"', '""', (string) $c).'"',
                $row,
            )).$eol;
        }

        return $out;
    }

    private function atomicWrite(string $path, string $content): bool
    {
        $tmp = $path.'.tmp'.getmypid();

        if (@file_put_contents($tmp, $content) === false) {
            return false;
        }

        if (! @rename($tmp, $path)) {
            @unlink($tmp);

            return false;
        }

        return true;
    }
}
