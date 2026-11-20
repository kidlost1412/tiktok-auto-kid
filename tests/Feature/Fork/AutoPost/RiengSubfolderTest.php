<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Inertia\Testing\AssertableInertia;

test('a folder lists its subfolders with counts and filters to the root, one subfolder or all', function () {
    $folder = RiengFolder::create(['path' => sys_get_temp_dir().'/rieng-sub-'.bin2hex(random_bytes(4))]);
    $other = RiengFolder::create(['path' => sys_get_temp_dir().'/rieng-sub-'.bin2hex(random_bytes(4))]);
    $make = fn (RiengFolder $f, string $rel): AutoVideo => AutoVideo::create([
        'hash' => hash('sha256', $f->id.$rel), 'path' => $f->path.'/'.$rel, 'source' => 'rieng', 'batch_date' => '2026-11-20',
        'file_name' => basename($rel), 'status' => 'new', 'meta' => ['folder_id' => $f->id, 'rel_path' => $rel],
    ]);
    $make($folder, 'a.mp4');
    $make($folder, 'b.mp4');
    $make($folder, 'test/c.mp4');
    $make($folder, 'test/sau/d.mp4');
    $make($folder, 'test_2/e.mp4');
    $make($other, 'test/f.mp4');
    // Chủ tài khoản (giống ownerUser() của RiengTest, viết lại để chạy riêng được file này).
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $owner->update(['current_workspace_id' => Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id])->id]);
    $ids = fn (string $q) => $this->actingAs($owner)->get('/auto/kho/rieng?'.$q)->viewData('page')['props']['videos']['data'];
    $ids = fn (string $q) => array_column($ids($q), 'file_name');

    $this->actingAs($owner)->get('/auto/kho/rieng?folder='.$folder->id)->assertInertia(fn (AssertableInertia $p) => $p
        ->where('subfolders', [['dir' => '', 'count' => 2], ['dir' => 'test', 'count' => 1], ['dir' => 'test/sau', 'count' => 1], ['dir' => 'test_2', 'count' => 1]])
        ->where('filters.sub', '')->where('videos.total', 5));

    expect(collect($ids('folder='.$folder->id.'&sub=:'))->sort()->values()->all())->toBe(['a.mp4', 'b.mp4'])
        // "test" gồm cả thư mục con của nó, không lẫn "test_2" (dấu _ không phải ký tự đại diện) hay thư mục khác.
        ->and(collect($ids('folder='.$folder->id.'&sub=test'))->sort()->values()->all())->toBe(['c.mp4', 'd.mp4'])
        ->and($ids('folder='.$folder->id.'&sub=test_2'))->toBe(['e.mp4'])
        // Không chọn thư mục thì bỏ qua lọc thư mục con.
        ->and($ids('sub=test'))->toHaveCount(6);

    $this->actingAs($owner)->getJson('/auto/kho/rieng/chon-tat-ca?folder='.$folder->id.'&sub=test')->assertOk()->assertJsonPath('total', 2);
});
