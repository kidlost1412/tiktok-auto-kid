<?php

declare(strict_types=1);

namespace App\Providers;

use App\Models\Account;
use App\Models\Media;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\Relation;
use Illuminate\Support\Facades\Date;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        Date::use(CarbonImmutable::class);
        Model::shouldBeStrict(! $this->app->isProduction());
        DB::prohibitDestructiveCommands($this->app->isProduction());

        // PHP bản native (Windows) để curl.cainfo là đường dẫn tương đối, tính theo thư mục chạy nên không tìm thấy:
        // mọi cuộc gọi https (ảnh sản phẩm, avatar, Telegram) lỗi cURL 77. Trỏ thẳng tới cacert.pem cạnh php.exe.
        $cacert = dirname(PHP_BINARY).DIRECTORY_SEPARATOR.'cacert.pem';

        if (PHP_OS_FAMILY === 'Windows' && is_file($cacert) && ! is_file((string) ini_get('curl.cainfo'))) {
            Http::globalOptions(['verify' => $cacert]);
        }

        Relation::enforceMorphMap([
            'account' => Account::class,
            'media' => Media::class,
            'post' => Post::class,
            'socialAccount' => SocialAccount::class,
            'user' => User::class,
            'workspace' => Workspace::class,
        ]);
    }
}
