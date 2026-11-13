<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoSetting;

/**
 * Hình dáng nhân vật trong "Khu Tự Trị" do chủ app tự đặt (tên + ngoại hình), lưu trên máy chủ để đổi trình duyệt vẫn giữ.
 * Hiện chỉ có nhân vật chính ("chinh" = Kid); sau này thêm nhân vật khác chỉ cần thêm vào WHO.
 * Mọi lựa chọn đều phải nằm trong danh sách cho phép (giao diện 3D dùng đúng các khoá này).
 */
final class Avatar
{
    /** Nhân vật được phép tuỳ biến. */
    public const WHO = ['chinh'];

    public const GIOI = ['nam', 'nu'];

    public const DA = ['da1', 'da2', 'da3', 'da4', 'da5'];

    public const MAU = [
        'den', 'nau', 'nau-sang', 'vang', 'cam', 'do', 'hong', 'tim', 'tim-nhat',
        'xanh-duong', 'xanh-dam', 'bac-ha', 'xanh-la', 'trang', 'xam', 'kem',
    ];

    public const TOC = ['short', 'messy', 'spiky', 'bob', 'long', 'pony', 'bun'];

    public const MU = ['none', 'cap', 'beret', 'headband', 'hood', 'postcap'];

    public const AO = ['tee', 'hoodie', 'shirt', 'sweater'];

    public const QUAN = ['pants', 'shorts', 'skirt', 'dress'];

    public const PHU_KIEN = ['none', 'glasses', 'scarf', 'backpack', 'headphones'];

    public const MAT = ['happy', 'joy', 'cocky', 'focus', 'love', 'sleepy'];

    public const BIEU_TUONG = ['none', 'star', 'heart', 'crown'];

    public const TEN_MAX = 20;

    /** Kid mặc định (giống bản dựng sẵn ban đầu). */
    public static function defaults(): array
    {
        return [
            'v' => 1,
            'ten' => 'Kid',
            'gioi' => 'nam',
            'da' => 'da2',
            'toc' => 'short',
            'mau_toc' => 'den',
            'mu' => 'cap',
            'mau_mu' => 'vang',
            'ao' => 'tee',
            'mau_ao' => 'tim',
            'quan' => 'pants',
            'mau_quan' => 'xanh-dam',
            'mau_giay' => 'trang',
            'phu_kien' => 'scarf',
            'mat' => 'happy',
            'bieu_tuong' => 'star',
        ];
    }

    /** Luật kiểm tra (Laravel validate) cho một cấu hình gửi lên. */
    public static function rules(): array
    {
        $in = static fn (array $list): string => 'in:'.implode(',', $list);

        return [
            'ten' => ['required', 'string', 'max:'.self::TEN_MAX, 'regex:/^[\pL\pN][\pL\pN \'._-]*$/u'],
            'gioi' => ['required', $in(self::GIOI)],
            'da' => ['required', $in(self::DA)],
            'toc' => ['required', $in(self::TOC)],
            'mau_toc' => ['required', $in(self::MAU)],
            'mu' => ['required', $in(self::MU)],
            'mau_mu' => ['required', $in(self::MAU)],
            'ao' => ['required', $in(self::AO)],
            'mau_ao' => ['required', $in(self::MAU)],
            'quan' => ['required', $in(self::QUAN)],
            'mau_quan' => ['required', $in(self::MAU)],
            'mau_giay' => ['required', $in(self::MAU)],
            'phu_kien' => ['required', $in(self::PHU_KIEN)],
            'mat' => ['required', $in(self::MAT)],
            'bieu_tuong' => ['required', $in(self::BIEU_TUONG)],
        ];
    }

    private static function key(string $who): string
    {
        return 'nha.avatar.'.$who;
    }

    /** Đọc cấu hình đã lưu; thiếu hoặc hỏng thì dùng mặc định (từng ô sai cũng thay bằng mặc định). */
    public static function read(string $who = 'chinh'): array
    {
        $base = self::defaults();
        $raw = json_decode((string) AutoSetting::read(self::key($who), ''), true);
        if (! is_array($raw)) {
            return $base;
        }
        $lists = [
            'gioi' => self::GIOI, 'da' => self::DA, 'toc' => self::TOC, 'mau_toc' => self::MAU, 'mu' => self::MU,
            'mau_mu' => self::MAU, 'ao' => self::AO, 'mau_ao' => self::MAU, 'quan' => self::QUAN, 'mau_quan' => self::MAU,
            'mau_giay' => self::MAU, 'phu_kien' => self::PHU_KIEN, 'mat' => self::MAT, 'bieu_tuong' => self::BIEU_TUONG,
        ];
        foreach ($lists as $k => $list) {
            if (isset($raw[$k]) && in_array($raw[$k], $list, true)) {
                $base[$k] = $raw[$k];
            }
        }
        $ten = isset($raw['ten']) && is_string($raw['ten']) ? trim($raw['ten']) : '';
        if ($ten !== '' && mb_strlen($ten) <= self::TEN_MAX) {
            $base['ten'] = $ten;
        }

        return $base;
    }

    /** Lưu cấu hình đã kiểm tra. */
    public static function write(string $who, array $data): array
    {
        $clean = ['v' => 1];
        foreach (array_keys(self::rules()) as $k) {
            $clean[$k] = is_string($data[$k]) ? trim($data[$k]) : $data[$k];
        }
        AutoSetting::write(self::key($who), json_encode($clean, JSON_UNESCAPED_UNICODE));

        return self::read($who);
    }
}
