<?php

declare(strict_types=1);

namespace App\Fork\Notify\Http;

use App\Fork\Notify\Messages;
use App\Fork\Notify\Telegram;
use App\Fork\Notify\TelegramApi;
use App\Fork\Notify\TelegramSettings;
use App\Http\Controllers\Controller;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/** Cài đặt Telegram ngay trong app: token (mã hoá trong DB), chat id, bật/tắt từng loại tin, tin mẫu. */
final class TelegramController extends Controller
{
    private const string CANDIDATE = 'fork:telegram:candidate';

    public function index(Request $request): Response
    {
        $this->authorizeOwner($request);

        $bot = TelegramSettings::botUsername();
        $toggles = TelegramSettings::toggles();

        return Inertia::render('settings/fork/Telegram', [
            'configured' => TelegramSettings::configured(),
            'has_token' => TelegramSettings::hasToken(),
            'token_masked' => TelegramSettings::maskedToken(),
            'bot' => $bot ? ['username' => $bot, 'link' => "https://t.me/{$bot}"] : null,
            'chat' => TelegramSettings::chatId() !== '' ? ['id' => TelegramSettings::chatId(), 'name' => TelegramSettings::chatName()] : null,
            'candidate' => Cache::get(self::CANDIDATE),
            'types' => collect(TelegramSettings::TYPES)->map(fn (array $t, string $key): array => [
                'key' => $key, 'label' => $t[0], 'urgent' => $t[1], 'on' => $toggles[$key],
            ])->values()->all(),
            'summary_time' => TelegramSettings::summaryTime(),
            'quiet' => TelegramSettings::quiet(),
            'previews' => collect(Messages::samples())->map(fn (array $s, string $id): array => [
                'id' => $id, 'label' => $s['label'], 'html' => $s['message']->text,
            ])->values()->all(),
        ]);
    }

    public function saveToken(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        $token = trim((string) $request->input('token', ''));

        if (! preg_match('/^\d{6,}:[A-Za-z0-9_-]{30,}$/', $token)) {
            return back()->with('flash.error', 'Token chưa đúng dạng. Token có dạng 123456789:AAH... do BotFather gửi, hãy dán nguyên văn.');
        }

        $me = TelegramApi::getMe($token);

        if ($me === null) {
            return back()->with('flash.error', 'Telegram không nhận token này (hoặc máy chưa có mạng). Kiểm tra lại token rồi thử lại.');
        }

        TelegramSettings::saveToken($token, $me['username']);
        Cache::forget(self::CANDIDATE);

        return back()->with('flash.success', 'Đã lưu bot @'.$me['username'].'. Bước tiếp theo: bấm “Mở bot” và nhấn Start.');
    }

    /** Tự tìm chat riêng mới nhất đã nhắn cho bot; chờ chủ app xác nhận tên rồi mới lưu. */
    public function detectChat(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        if (! TelegramSettings::hasToken()) {
            return back()->with('flash.error', 'Hãy lưu token bot trước (bước 1).');
        }

        $chat = TelegramApi::latestPrivateChat(TelegramSettings::token());

        if ($chat === null) {
            Cache::forget(self::CANDIDATE);

            return back()->with('flash.error', 'Chưa thấy ai nhắn cho bot. Hãy bấm “Mở bot”, nhấn Start (hoặc gửi một tin bất kỳ), rồi bấm lại nút này.');
        }

        Cache::put(self::CANDIDATE, $chat, 600);

        return back()->with('flash.success', 'Đã tìm thấy: '.$chat['name'].'. Hãy xác nhận đúng là bạn.');
    }

    public function saveChat(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        $id = trim((string) $request->input('chat_id', ''));

        if (! preg_match('/^-?\d{4,20}$/', $id)) {
            return back()->with('flash.error', 'Chat id là một dãy số (ví dụ 123456789).');
        }

        $candidate = Cache::get(self::CANDIDATE);
        $name = is_array($candidate) && ($candidate['id'] ?? null) === $id ? (string) $candidate['name'] : null;

        TelegramSettings::saveChat($id, $name);
        Cache::forget(self::CANDIDATE);

        return back()->with('flash.success', 'Đã lưu chat'.($name ? " của {$name}" : '').'. Bấm “Gửi thử” để kiểm tra.');
    }

    public function savePrefs(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        $time = (string) $request->input('summary_time', '21:00');
        $quiet = (array) $request->input('quiet', []);

        foreach ([$time, (string) ($quiet['start'] ?? '23:00'), (string) ($quiet['end'] ?? '06:00')] as $t) {
            if (! TelegramSettings::validTime($t)) {
                return back()->with('flash.error', 'Giờ chưa đúng dạng HH:MM (ví dụ 21:00).');
            }
        }

        TelegramSettings::savePrefsFromForm(
            (array) $request->input('toggles', []),
            $time,
            (bool) ($quiet['enabled'] ?? false),
            (string) ($quiet['start'] ?? '23:00'),
            (string) ($quiet['end'] ?? '06:00'),
        );

        return back()->with('flash.success', 'Đã lưu cài đặt thông báo.');
    }

    public function test(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        if (! Telegram::configured()) {
            return back()->with('flash.error', 'Chưa cấu hình xong: cần token bot và chat id.');
        }

        return Telegram::send('✅ <b>Telegram đã nối thành công</b>'."\nTừ giờ bạn sẽ nhận thông báo đăng bài, lỗi và tổng kết ngày tại đây.", null, 0, null, true)
            ? back()->with('flash.success', 'Đã gửi tin thử, hãy kiểm tra Telegram.')
            : back()->with('flash.error', 'Gửi thất bại. Kiểm tra lại token và chat id (đã nhấn Start với bot chưa?).');
    }

    public function sample(Request $request, string $id): RedirectResponse
    {
        $this->authorizeOwner($request);

        $sample = Messages::samples()[$id] ?? null;
        abort_if($sample === null, SymfonyResponse::HTTP_NOT_FOUND);

        if (! Telegram::configured()) {
            return back()->with('flash.error', 'Chưa cấu hình xong: cần token bot và chat id.');
        }

        return Telegram::send("<i>🧪 Tin mẫu (dữ liệu giả)</i>\n".$sample['message']->text, null, 0, null, true)
            ? back()->with('flash.success', 'Đã gửi tin mẫu “'.$sample['label'].'”.')
            : back()->with('flash.error', 'Gửi thất bại. Kiểm tra lại token và chat id.');
    }

    public function disconnect(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        TelegramSettings::clear();
        Cache::forget(self::CANDIDATE);

        return back()->with('flash.success', 'Đã xoá cấu hình Telegram trong app.');
    }

    private function authorizeOwner(Request $request): void
    {
        abort_unless($request->user()?->isAccountOwner(), SymfonyResponse::HTTP_FORBIDDEN);
    }
}
