<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\Nha\Avatar;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
});

function avatarPayload(array $over = []): array
{
    return array_merge([
        'ten' => 'Bé Na',
        'gioi' => 'nu',
        'da' => 'da3',
        'toc' => 'pony',
        'mau_toc' => 'nau',
        'mu' => 'beret',
        'mau_mu' => 'hong',
        'ao' => 'sweater',
        'mau_ao' => 'bac-ha',
        'quan' => 'skirt',
        'mau_quan' => 'tim',
        'mau_giay' => 'trang',
        'phu_kien' => 'glasses',
        'mat' => 'joy',
        'bieu_tuong' => 'crown',
    ], $over);
}

test('avatar falls back to the default Kid look', function (): void {
    $this->actingAs($this->owner)->getJson('/nha/nhan-vat/chinh')
        ->assertOk()
        ->assertJsonPath('avatar.ten', 'Kid')
        ->assertJsonPath('avatar.gioi', 'nam')
        ->assertJsonPath('avatar.bieu_tuong', 'star');

    $this->actingAs($this->owner)->get('/nha')->assertOk()
        ->assertInertia(fn (AssertableInertia $p) => $p->component('fork/Nha')->where('avatar.ten', 'Kid'));
});

test('avatar saves and loads back (including gender)', function (): void {
    $this->actingAs($this->owner)->putJson('/nha/nhan-vat/chinh', avatarPayload())
        ->assertOk()
        ->assertJsonPath('avatar.ten', 'Bé Na')
        ->assertJsonPath('avatar.gioi', 'nu')
        ->assertJsonPath('avatar.quan', 'skirt');

    $this->actingAs($this->owner)->getJson('/nha/nhan-vat/chinh')
        ->assertOk()
        ->assertJsonPath('avatar', array_merge(['v' => 1], avatarPayload()));

    $this->actingAs($this->owner)->get('/nha')
        ->assertInertia(fn (AssertableInertia $p) => $p->where('avatar.ten', 'Bé Na')->where('avatar.gioi', 'nu'));
});

test('avatar rejects options outside the allowlist', function (array $bad, string $field): void {
    $this->actingAs($this->owner)->putJson('/nha/nhan-vat/chinh', avatarPayload($bad))
        ->assertUnprocessable()
        ->assertJsonValidationErrors($field);

    expect(AutoSetting::read('nha.avatar.chinh'))->toBeNull();
})->with([
    'gender' => [['gioi' => 'khac'], 'gioi'],
    'hair' => [['toc' => 'mohawk'], 'toc'],
    'colour' => [['mau_ao' => '#ff0000'], 'mau_ao'],
    'hat' => [['mu' => 'crown'], 'mu'],
    'icon' => [['bieu_tuong' => 'skull'], 'bieu_tuong'],
    'empty name' => [['ten' => ''], 'ten'],
    'long name' => [['ten' => str_repeat('a', Avatar::TEN_MAX + 1)], 'ten'],
    'markup name' => [['ten' => '<b>x</b>'], 'ten'],
    'missing' => [['mat' => null], 'mat'],
]);

test('only the main character can be customised for now', function (): void {
    $this->actingAs($this->owner)->getJson('/nha/nhan-vat/meo')->assertNotFound();
    $this->actingAs($this->owner)->putJson('/nha/nhan-vat/thuam', avatarPayload())->assertNotFound();
});

test('a corrupted stored avatar is repaired field by field', function (): void {
    AutoSetting::write('nha.avatar.chinh', json_encode(['ten' => 'Tí', 'toc' => 'mohawk', 'mau_ao' => 'do', 'gioi' => 'nu']));

    $a = Avatar::read();
    expect($a['ten'])->toBe('Tí')
        ->and($a['toc'])->toBe('short')
        ->and($a['mau_ao'])->toBe('do')
        ->and($a['gioi'])->toBe('nu');

    AutoSetting::write('nha.avatar.chinh', 'not json');
    expect(Avatar::read())->toBe(Avatar::defaults());
});
