<?php

declare(strict_types=1);

use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Paths;
use App\Fork\AutoPost\VideoLibrary;

it('chuẩn hoá dấu gạch chéo và bỏ gạch cuối', function (): void {
    expect(Paths::slash('P:\\hub\\ra/2026-11-09\\a.mp4'))->toBe('P:/hub/ra/2026-11-09/a.mp4')
        ->and(Paths::root('D:\\Video\\hub\\'))->toBe('D:/Video/hub')
        ->and(Paths::root('/hub/'))->toBe('/hub');
});

it('hub path trong VideoLibrary và KhoStore luôn dùng dấu /', function (): void {
    config()->set('fork.auto.hub_path', 'D:\\Video\\hub\\');

    expect(app(VideoLibrary::class)->hubPath())->toBe('D:/Video/hub')
        ->and(app(KhoStore::class)->hub())->toBe('D:/Video/hub')
        ->and(app(KhoStore::class)->khoPath())->toBe('D:/Video/hub/kho-dang');
});

it('glob trả đường dẫn / và giữ tên file tiếng Việt', function (): void {
    $dir = sys_get_temp_dir().DIRECTORY_SEPARATOR.'paths-'.bin2hex(random_bytes(4));
    mkdir($dir);
    $name = 'NanoĐồng_ra_mắt_bé.mp4';
    file_put_contents($dir.DIRECTORY_SEPARATOR.$name, 'x');

    try {
        $found = Paths::glob(str_replace('\\', '/', $dir).'/*.mp4');

        expect($found)->toHaveCount(1)
            ->and($found[0])->not->toContain('\\')
            ->and(basename($found[0]))->toBe($name)
            ->and(is_file($found[0]))->toBeTrue()
            ->and(filesize($found[0]))->toBe(1);
    } finally {
        @unlink($dir.DIRECTORY_SEPARATOR.$name);
        @rmdir($dir);
    }
});

it('isUnder chỉ nhận file nằm dưới thư mục gốc', function (): void {
    $sep = DIRECTORY_SEPARATOR;

    expect(Paths::isUnder("P:{$sep}hub{$sep}ra{$sep}a.mp4", "P:{$sep}hub"))->toBeTrue()
        ->and(Paths::isUnder("P:{$sep}hub-khac{$sep}a.mp4", "P:{$sep}hub"))->toBeFalse()
        ->and(Paths::isUnder("P:{$sep}hub", "P:{$sep}hub"))->toBeFalse()
        ->and(Paths::isUnder("P:{$sep}other{$sep}a.mp4", "P:{$sep}hub"))->toBeFalse();
});
