<?php

declare(strict_types=1);

namespace App\Fork\Chrome;

use App\Fork\Chrome\Models\ChromeJob;

/**
 * MỘT chỗ duy nhất đổi mã lỗi của tiện ích Chrome (và vài mã phía máy chủ) thành câu tiếng Việt ngắn,
 * kèm việc chủ app nên làm. Dùng ở mọi nơi hiện hoặc gửi lỗi đăng bài: Tổng quan, Lịch, khung xem video, Telegram,
 * thông báo lỗi của bài. Mã lạ thì ra câu chung có kèm mã gốc.
 *
 * Mã lấy từ extension/autotok (reason, detail trong kết quả job; xem PROTOCOL.md).
 */
final class FailureReasons
{
    /** Chưa rõ bài đã lên TikTok hay chưa: không bao giờ tự đăng lại. */
    public const string UNCERTAIN = 'uncertain';

    /** Khoá "reason/detail" (khớp trước) hoặc nhóm => [tiêu đề, nhãn ngắn, việc cần làm]. */
    private const array MAP = [
        'product-unavailable/out-of-stock' => [
            'Sản phẩm trong giỏ đã hết hàng trên shop',
            'Hết hàng',
            'Nhập thêm hàng hoặc đổi giỏ rồi bấm Đăng lại.',
        ],
        'product-unavailable/not-found' => [
            'Sản phẩm trong giỏ không còn trong shop',
            'Giỏ không còn trong shop',
            'Vào Giỏ hàng, lấy lại sản phẩm từ shop và chọn lại giỏ, rồi bấm Đăng lại.',
        ],
        'product-unavailable/stock-unknown' => [
            'Không đọc được số hàng còn của sản phẩm trong giỏ',
            'Không rõ tồn kho',
            'Mở TikTok Shop xem sản phẩm còn hàng không, lấy lại sản phẩm từ shop, rồi bấm Đăng lại.',
        ],
        'product-unavailable' => [
            'Sản phẩm trong giỏ không dùng được trên shop',
            'Giỏ không dùng được',
            'Vào Giỏ hàng kiểm tra sản phẩm (còn hàng, còn trong shop), rồi bấm Đăng lại.',
        ],
        'product-check-failed' => [
            'Chrome chưa kiểm tra được sản phẩm trên shop (lỗi mạng hoặc TikTok)',
            'Chưa kiểm được giỏ',
            'Kiểm tra mạng và Chrome, rồi bấm Đăng lại.',
        ],
        'anchor-build-failed' => [
            'Không dựng được giỏ hàng cho bài này',
            'Lỗi giỏ hàng',
            'Đăng tay 1 bài mẫu có giỏ trong TikTok Studio, lưu lại giỏ ở trang Giỏ hàng, rồi bấm Đăng lại.',
        ],
        'product-id-unclear' => [
            'Không nhận ra sản phẩm trong bài mẫu giỏ hàng',
            'Mẫu giỏ không rõ',
            'Đăng tay 1 bài mẫu có đúng 1 giỏ trong TikTok Studio rồi lưu lại ở trang Giỏ hàng.',
        ],
        'identity' => [
            'Chrome đang đăng nhập sai tài khoản TikTok, hoặc chưa đăng nhập',
            'Sai tài khoản TikTok',
            'Mở đúng Chrome của kênh, đăng nhập đúng tài khoản TikTok, rồi bấm Đăng lại.',
        ],
        'unpaired' => [
            'Tiện ích Chrome chưa ghép với app',
            'Chrome chưa ghép',
            'Ghép lại ở Cài đặt > Kết nối Chrome, rồi bấm Đăng lại.',
        ],
        'mode-disabled' => [
            'Tiện ích Chrome đang tắt việc đăng bài',
            'Chrome tắt đăng bài',
            'Bật đăng bài trong tiện ích Chrome (Cài đặt > Kết nối Chrome), rồi bấm Đăng lại.',
        ],
        'open-window-failed' => [
            'Chrome không mở được cửa sổ TikTok Studio',
            'Chrome không mở được',
            'Mở Chrome của kênh, kiểm tra mạng, rồi bấm Đăng lại.',
        ],
        'tab-closed' => [
            'Cửa sổ đăng bài bị đóng giữa chừng (chưa đăng gì)',
            'Cửa sổ bị đóng',
            'Đừng đóng cửa sổ Chrome nhỏ khi đang đăng. Bấm Đăng lại.',
        ],
        'authorize' => [
            'App chưa cho Chrome đăng (mất kết nối giữa Chrome và app)',
            'Chrome mất kết nối app',
            'Kiểm tra app còn chạy và Chrome còn kết nối, rồi bấm Đăng lại.',
        ],
        'time' => [
            'Giờ hẹn của bài không còn hợp lệ',
            'Giờ hẹn không hợp lệ',
            'Sửa bài, chọn giờ mới (cách hiện tại ít nhất 20 phút), rồi bấm Đăng lại.',
        ],
        'media' => [
            'Video hoặc ảnh bìa không đạt yêu cầu của TikTok',
            'Video không đạt',
            'Mở bài, kiểm tra video và ảnh bìa; đổi sang video khác nếu cần.',
        ],
        'chrome-error' => [
            'Chrome gặp lỗi khi chuẩn bị đăng (chưa đăng gì)',
            'Lỗi Chrome',
            'Kiểm tra Chrome còn mở, tiện ích đã cập nhật, rồi bấm Đăng lại.',
        ],
        'cancelled' => [
            'Việc đăng đã bị huỷ',
            'Đã huỷ',
            'Bấm Đăng lại nếu vẫn muốn đăng bài này.',
        ],
        'rejected' => [
            'TikTok từ chối bài đăng',
            'TikTok từ chối',
            'Mở TikTok Studio xem chi tiết; sửa caption hoặc dùng video khác.',
        ],
        self::UNCERTAIN => [
            'Chưa rõ bài đã lên TikTok hay chưa',
            'Chưa rõ kết quả',
            'Mở TikTok Studio kiểm tra (cả mục bài hẹn giờ). App không tự đăng lại để khỏi trùng bài.',
        ],
    ];

    /** Mã của tiện ích => nhóm trong MAP. */
    private const array GROUPS = [
        'identity-unknown' => 'identity', 'identity-mismatch' => 'identity', 'identity-missing' => 'identity',
        'no-identity' => 'identity', 'identity-conflict' => 'identity',
        'mode-unsupported' => 'mode-disabled', 'post-disabled' => 'mode-disabled',
        'tab-closed-before-authorization' => 'tab-closed', 'job-tab' => 'tab-closed',
        'authorize-timeout' => 'authorize', 'ready-not-confirmed' => 'authorize', 'denied' => 'authorize',
        'already-authorized' => 'authorize', 'server-unreachable' => 'authorize', 'no-active-job' => 'authorize',
        'not-a-post-job' => 'authorize',
        'time-mismatch' => 'time', 'too-late' => 'time', 'too-close-or-published' => 'time', 'no-time' => 'time',
        'schedule-expired' => 'time',
        'no-cover' => 'media', 'bad-size' => 'media', 'bad-mime' => 'media', 'bad-sha256' => 'media',
        'bad-dimensions' => 'media', 'bad-url' => 'media', 'bad-id' => 'media', 'too-big' => 'media',
        'publish-setup-failed' => 'chrome-error', 'blocked-by-hook' => 'chrome-error', 'exception' => 'chrome-error',
        'gave-up' => 'chrome-error', 'sync-timeout' => 'chrome-error', 'bad_task' => 'chrome-error',
        'incomplete' => 'chrome-error', 'unexpected-response' => 'chrome-error', 'non-json' => 'chrome-error',
        'status_code' => 'rejected',
        'cancelled' => 'cancelled', 'owner-cleared' => 'cancelled',
        'error-after-send' => self::UNCERTAIN, 'tab-closed-after-authorization' => self::UNCERTAIN,
        'tab-reloaded-after-authorization' => self::UNCERTAIN,
    ];

    /**
     * @param  string|null  $product  tên sản phẩm trong giỏ (nếu biết) để chèn vào câu lỗi giỏ hàng
     * @return array{code: string, title: string, short: string, fix: string, text: string}
     */
    public static function describe(?string $reason, ?string $detail = null, ?string $state = null, ?string $product = null): array
    {
        $reason = trim((string) $reason);
        $detail = trim((string) $detail);

        if ($state === 'uncertain') {
            return self::build(self::UNCERTAIN, self::UNCERTAIN, $reason, null);
        }

        if ($reason === '') {
            return self::generic('');
        }

        $key = self::lookup($reason, $detail);

        return $key === null ? self::generic($reason.($detail !== '' ? '/'.$detail : '')) : self::build($key, $reason, $detail, $product);
    }

    /** Lý do của một job Chrome (reason/detail trong result, hoặc ghi chú của job). */
    public static function forJob(ChromeJob $job, ?string $product = null): array
    {
        $r = is_array($job->result) ? $job->result : [];
        $desc = self::describe((string) ($r['reason'] ?? ''), (string) ($r['detail'] ?? ''), (string) $job->state, $product);

        if ($job->state === 'rejected' && filled($r['status_msg'] ?? null) && $desc['code'] === 'status_code') {
            $desc['title'] .= ': '.mb_substr((string) $r['status_msg'], 0, 120);
            $desc['text'] = $desc['title'].' — '.lcfirst($desc['fix']);
        }

        // Job không có result (vd. hết hạn không báo kết quả): dùng ghi chú của máy chủ.
        if (($r['reason'] ?? '') === '' && filled($job->note) && $job->state !== 'uncertain') {
            $desc['title'] = (string) $job->note;
            $desc['text'] = (string) $job->note;
        }

        return $desc;
    }

    /**
     * Nhận ra mã trong câu lỗi cũ lưu sẵn. Không nhận ra thì trả null (người gọi giữ câu gốc).
     */
    public static function fromText(?string $text, ?string $product = null): ?array
    {
        $text = trim((string) $text);

        if ($text === '') {
            return null;
        }

        if (preg_match('/(product-unavailable|product-check-failed|anchor-build-failed)(?:\W+(out-of-stock|not-found|stock-unknown))?/i', $text, $m) === 1) {
            return self::describe(strtolower($m[1]), strtolower($m[2] ?? ''), null, $product);
        }

        if (preg_match('/hết hàng|out[- ]of[- ]stock/iu', $text) === 1) {
            return self::describe('product-unavailable', 'out-of-stock', null, $product);
        }

        return null;
    }

    private static function lookup(string $reason, string $detail): ?string
    {
        $reason = strtolower($reason);

        if ($detail !== '' && isset(self::MAP[$reason.'/'.strtolower($detail)])) {
            return $reason.'/'.strtolower($detail);
        }

        if (isset(self::MAP[$reason])) {
            return $reason;
        }

        if (isset(self::GROUPS[$reason])) {
            return self::GROUPS[$reason];
        }

        if (str_starts_with($reason, 'step:')) {
            $step = substr($reason, 5);

            return isset(self::MAP[$step]) ? $step : (self::GROUPS[$step] ?? 'chrome-error');
        }

        if (str_starts_with($reason, 'http-') || str_starts_with($reason, 'server-unreachable')) {
            return 'authorize';
        }

        if (str_starts_with($reason, 'xhr-')) {
            return self::UNCERTAIN;
        }

        if (str_starts_with($reason, 'tab-closed') || str_starts_with($reason, 'tab-reloaded')) {
            return str_contains($reason, 'after-authorization') ? self::UNCERTAIN : 'tab-closed';
        }

        return null;
    }

    /** @return array{code: string, title: string, short: string, fix: string, text: string} */
    private static function build(string $key, string $reason, string $detail, ?string $product): array
    {
        [$title, $short, $fix] = self::MAP[$key];
        $product = trim((string) $product);

        if ($product !== '' && str_starts_with($title, 'Sản phẩm trong giỏ')) {
            $title = 'Sản phẩm trong giỏ ('.mb_strimwidth($product, 0, 60, '…').')'.substr($title, strlen('Sản phẩm trong giỏ'));
        }

        return [
            'code' => trim($reason.($detail !== '' && $reason !== $detail ? '/'.$detail : ''), '/') ?: $key,
            'title' => $title,
            'short' => $short,
            'fix' => $fix,
            'text' => $title.' — '.lcfirst($fix),
        ];
    }

    /** @return array{code: string, title: string, short: string, fix: string, text: string} */
    private static function generic(string $code): array
    {
        $title = $code !== '' ? "Đăng bài không được (mã lỗi: {$code})" : 'Đăng bài không được (không rõ nguyên nhân)';
        $fix = 'Mở khung xem bài rồi bấm Đăng lại; nếu vẫn lỗi, xem Cài đặt > Kết nối Chrome.';

        return ['code' => $code, 'title' => $title, 'short' => 'Lỗi khác', 'fix' => $fix, 'text' => $title.' — '.lcfirst($fix)];
    }
}
