<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;

/** Cài đặt chung của tự động đăng (khoá => giá trị chuỗi). */
class AutoSetting extends Model
{
    protected $table = 'fork_auto_settings';

    protected $primaryKey = 'key';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    public static function read(string $key, ?string $default = null): ?string
    {
        $value = self::query()->whereKey($key)->value('value');

        return $value === null ? $default : (string) $value;
    }

    public static function write(string $key, ?string $value): void
    {
        self::query()->updateOrCreate(['key' => $key], ['value' => $value]);
    }
}
