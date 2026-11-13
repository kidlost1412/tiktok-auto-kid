<?php

declare(strict_types=1);

namespace App\Fork\Settings\Http;

use App\Fork\Chrome\Http\ChromeSettingsController;
use App\Fork\Notify\Http\TelegramController;
use App\Fork\Update\UpdateController;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

/**
 * Trang "Cài đặt" hợp nhất: ghép ba trang cũ (Kết nối Chrome, Telegram, Cập nhật) vào một
 * trang với các mục bên trong, để đỡ phải có 3 tab riêng trên thanh điều hướng chính.
 * Mỗi mục vẫn dùng đúng dữ liệu/route của trang cũ (các nút bấm post/patch/delete không đổi).
 */
final class SettingsController
{
    private const array TABS = ['chrome', 'telegram', 'cap-nhat'];

    public function __construct(
        private readonly ChromeSettingsController $chrome,
        private readonly TelegramController $telegram,
        private readonly UpdateController $update,
    ) {}

    public function index(Request $request): Response
    {
        $tab = (string) $request->query('tab', 'chrome');
        $tab = in_array($tab, self::TABS, true) ? $tab : 'chrome';

        return Inertia::render('fork/Settings', [
            'tab' => $tab,
            'chrome' => fn (): array => $this->chrome->props($request),
            'telegram' => fn (): array => $this->telegram->props($request),
            'update' => fn (): array => $this->update->props($request),
        ]);
    }
}
