<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Rieng\Ai\ChatGptAccounts;
use App\Fork\AutoPost\Rieng\Ai\CodexLimited;
use App\Fork\AutoPost\Rieng\Ai\CodexRunner;
use App\Fork\AutoPost\Rieng\Ai\RiengAiStatus;
use App\Fork\AutoPost\Rieng\Ai\RiengAnalyzer;
use App\Fork\AutoPost\Rieng\Ai\RiengAutoPoster;
use App\Fork\AutoPost\Rieng\Ai\RiengAutoSettings;
use App\Fork\AutoPost\Rieng\Ai\RiengSpeech;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Rieng\RiengReady;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;

beforeEach(function (): void {
    Storage::fake();
    Cache::flush();
    $tmp = str_replace('\\', '/', sys_get_temp_dir());
    $this->hub = $tmp.'/rieng-auto-hub-'.bin2hex(random_bytes(4));
    $this->own = $tmp.'/rieng-auto-own-'.bin2hex(random_bytes(4));
    $this->gpt = $tmp.'/rieng-auto-gpt-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/san-pham/nano-dong');
    File::ensureDirectoryExists($this->own);
    File::ensureDirectoryExists($this->gpt);
    file_put_contents($this->hub.'/san-pham/nano-dong/san-pham.json', json_encode([
        'ma' => 'nano-dong', 'ten_goi' => 'Nano Đồng Toàn Cầu', 'nhan_dien_chai' => 'Chai trắng 500 ml',
        'su_that_duoc_noi' => ['Một chai pha một phuy 200 lít.'], 'khong_duoc_noi' => ['Giá tiền.'],
    ], JSON_UNESCAPED_UNICODE));
    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.chatgpt_dir' => $this->gpt, 'fork.auto.settle_seconds' => 0, 'fork.auto.hub_api.key' => '', 'trypost.self_hosted' => true]);
    app()->instance(RiengReady::class, new RiengReady(fn (string $p): ?float => 5.0, fn () => null));

    $acct = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $acct->id]);
    $acct->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $acct->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->now = CarbonImmutable::now('UTC')->addDays(2)->setTime(3, 0);

    AutoProduct::create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    AutoProduct::create(['code' => 'tc01', 'name' => 'TC01', 'short_name' => 'TC01', 'facts' => [], 'enabled' => true]);

    $this->account = function (array $auto = []): SocialAccount {
        $account = SocialAccount::factory()->tiktok()->create([
            'workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh',
        ]);
        ChromeAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'tiktok_user_id' => '777'.random_int(100, 999)]);
        AutoAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'daily_cap' => 3, 'window_start' => 6, 'window_end' => 23, ...$auto]);
        $pid = '17293847560'.random_int(10000000, 99999999);
        ShopProduct::create(['social_account_id' => $account->id, 'product_id' => $pid, 'source' => 'my_shop', 'title' => 'Nano Đồng 1L', 'stock_num' => 5, 'synced_at' => now()]);
        ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => $pid, 'display_name' => 'Nano Đồng 1L']);

        return $account;
    };

    $this->rieng = function (string $name, array $attrs = [], array $meta = []): AutoVideo {
        $path = $this->own.'/'.$name;
        file_put_contents($path, 'video-'.$name);

        return AutoVideo::create([
            'hash' => hash('sha256', $name), 'path' => $path, 'source' => 'rieng', 'batch_date' => '2026-11-09',
            'file_name' => $name, 'status' => 'new', 'meta' => ['folder_id' => 1, 'rel_path' => $name, ...$meta], ...$attrs,
        ]);
    };

    // Video AI đã xem xong và chắc chắn sản phẩm.
    $this->ready = fn (string $name, array $ai = [], array $meta = [], array $attrs = []): AutoVideo => ($this->rieng)($name, ['product_code' => 'nano-dong', ...$attrs], [
        'ai' => ['state' => 'ok', 'product_code' => 'nano-dong', 'chac' => 'cao', 'caption' => 'Rửa vườn sau thu hoạch cho sạch nấm', 'approved' => false, ...$ai], ...$meta,
    ]);

    // Tài khoản ChatGPT giả (đã đăng nhập).
    $this->gptAccount = function (string $id, string $email = 'a@example.test'): void {
        File::ensureDirectoryExists($this->gpt.'/'.$id);
        $claims = rtrim(strtr(base64_encode(json_encode(['email' => $email, 'https://api.openai.com/auth' => ['chatgpt_plan_type' => 'plus']])), '+/', '-_'), '=');
        file_put_contents($this->gpt.'/'.$id.'/auth.json', json_encode(['tokens' => ['id_token' => 'h.'.$claims.'.s', 'refresh_token' => 'r']]));
    };
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
    File::deleteDirectory($this->own);
    File::deleteDirectory($this->gpt);
});

// ---------------------------------------------------------------- Planner: kho riêng trước, chỉ khi bật

test('the planner posts a ready private video before hub videos, but only when auto posting for kho riêng is on', function () {
    $account = ($this->account)();
    $v = ($this->ready)('a.mp4', ['hashtags' => ['#nanodong', '#ruavuon']]);
    $hub = AutoVideo::create(['hash' => 'h1', 'path' => $this->own.'/h.mp4', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'NanoĐồng_x_MIXKIT_1.mp4', 'status' => 'new', 'product_code' => 'nano-dong', 'caption' => 'hub cap', 'hashtags' => []]);
    file_put_contents($this->own.'/h.mp4', 'h');

    // Chưa bật: chỉ kiểm, không chạy planner (planner sẽ lấy video hub).
    expect(app(RiengAutoPoster::class)->postNext(SocialAccount::query()->findOrFail($account->id), ['nano-dong' => [null]], $this->now->addHour()))->toBeFalse()
        ->and($v->refresh()->status)->toBe('new');

    RiengAutoSettings::update(['enabled' => true]);
    app(Planner::class)->planAll($this->now);

    $v->refresh();
    $hub->refresh();
    expect($v->status)->toBe('scheduled')->and($v->social_account_id)->toBe($account->id)
        ->and($v->caption)->toBe('Rửa vườn sau thu hoạch cho sạch nấm')
        ->and(Post::query()->findOrFail($v->post_id)->content)->toContain('#nanodong')->toContain('#ruavuon')
        ->and($hub->status)->toBe('scheduled')
        ->and($v->scheduled_for->lessThan($hub->scheduled_for))->toBeTrue();
});

test('a channel set to "only kho riêng" never takes hub videos, and "only Xưởng" never takes private videos', function () {
    $account = ($this->account)(['video_source' => 'rieng']);
    $v = ($this->ready)('a.mp4');
    $hub = AutoVideo::create(['hash' => 'h1', 'path' => $this->own.'/h.mp4', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'NanoĐồng_x_MIXKIT_1.mp4', 'status' => 'new', 'product_code' => 'nano-dong', 'caption' => 'hub cap', 'hashtags' => []]);
    file_put_contents($this->own.'/h.mp4', 'h');
    RiengAutoSettings::update(['enabled' => true]);

    app(Planner::class)->planAll($this->now);
    expect($v->refresh()->status)->toBe('scheduled')->and($hub->refresh()->status)->toBe('new');

    // Chỉ Xưởng: video riêng mới không bị lấy, video hub được xếp.
    AutoAccount::query()->whereKey($account->id)->update(['video_source' => 'hub']);
    $v2 = ($this->ready)('b.mp4');
    app(Planner::class)->planAll($this->now);
    expect($v2->refresh()->status)->toBe('new')->and($hub->refresh()->status)->toBe('scheduled');

    // Lưu được từ hộp Chỉnh kênh, giá trị lạ bị từ chối.
    $this->actingAs($this->owner)->patch("/auto/accounts/{$account->id}", ['video_source' => 'rieng'])->assertSessionHasNoErrors();
    expect(AutoAccount::query()->find($account->id)->video_source)->toBe('rieng');
    $this->actingAs($this->owner)->patch("/auto/accounts/{$account->id}", ['video_source' => 'xyz'])->assertSessionHasErrors('video_source');
});

test('a video without a sure product, an unapproved caption or an unconfirmed duplicate waits', function () {
    ($this->account)();
    RiengAutoSettings::update(['enabled' => true, 'approve_first' => true]);
    $unsure = ($this->rieng)('unsure.mp4', [], ['ai' => ['state' => 'unsure', 'product_code' => 'nano-dong', 'chac' => 'vua', 'caption' => 'x']]);
    $unapproved = ($this->ready)('cho-duyet.mp4');
    $dup = ($this->ready)('trung.mp4', ['approved' => true], ['duplicate_of' => 999]);

    app(Planner::class)->planAll($this->now);

    expect($unsure->refresh()->status)->toBe('new')->and($unapproved->refresh()->status)->toBe('new')->and($dup->refresh()->status)->toBe('new');

    $s = RiengAutoSettings::get();
    $poster = app(RiengAutoPoster::class);
    expect($poster->blocker($unsure, null, null, $s))->toBe('Anh chọn sản phẩm')
        ->and($poster->blocker($unapproved, null, null, $s))->toBe('Chờ anh duyệt caption')
        ->and($poster->blocker($dup, null, null, $s))->toContain('Vẫn đăng');

    // Duyệt + cho đăng video trùng → lượt sau đăng cả hai.
    $owner = $this->owner;
    $this->actingAs($owner)->postJson('/auto/kho/rieng/video/'.$unapproved->id.'/tu-dong', ['approved' => true])->assertOk();
    $this->actingAs($owner)->postJson('/auto/kho/rieng/video/'.$dup->id.'/tu-dong', ['dup_ok' => true])->assertOk()->assertJsonPath('auto.ready', true);
    app(Planner::class)->planAll($this->now);

    expect($unapproved->refresh()->status)->toBe('scheduled')->and($dup->refresh()->status)->toBe('scheduled')->and($unsure->refresh()->status)->toBe('new');
});

test('duplicates may be set to post anyway, still flagged on the card', function () {
    ($this->account)();
    RiengAutoSettings::update(['enabled' => true, 'duplicates' => 'allow']);
    $dup = ($this->ready)('trung.mp4', [], ['duplicate_of' => 5]);

    app(Planner::class)->planAll($this->now);

    expect($dup->refresh()->status)->toBe('scheduled');
});

test('caption options: own caption wins, empty caption posts when allowed and waits when not', function () {
    ($this->account)();
    RiengAutoSettings::update(['enabled' => true, 'caption_mode' => 'kid', 'empty_caption_ok' => false]);
    $own = ($this->ready)('tu-viet.mp4', [], [], ['caption' => 'Anh tự viết', 'caption_source' => 'kid']);
    $none = ($this->ready)('khong-cap.mp4');

    app(Planner::class)->planAll($this->now);
    expect($own->refresh()->status)->toBe('scheduled')->and($own->caption)->toBe('Anh tự viết')
        ->and($none->refresh()->status)->toBe('new')
        ->and(app(RiengAutoPoster::class)->blocker($none, null, null, RiengAutoSettings::get()))->toBe('Chờ anh viết caption');

    RiengAutoSettings::update(['empty_caption_ok' => true]);
    app(Planner::class)->planAll($this->now);
    $post = Post::query()->findOrFail($none->refresh()->post_id);
    expect($none->status)->toBe('scheduled')->and($none->caption)->toBe('')->and($post->meta['fork_caption_optional'] ?? false)->toBeTrue();
});

test('channel choice: a video set to another channel or a folder set to another channel is never posted here', function () {
    $a = ($this->account)();
    $b = ($this->account)();
    RiengAutoSettings::update(['enabled' => true]);
    $forB = ($this->ready)('cho-b.mp4', [], ['channels' => [$b->id]]);
    $folderB = ($this->ready)('thu-muc-b.mp4', [], ['folder_id' => 7]);
    RiengAutoSettings::update(['folder_channels' => ['7' => [$b->id]]]);

    app(Planner::class)->planAll($this->now, [$a->id]);
    expect($forB->refresh()->status)->toBe('new')->and($folderB->refresh()->status)->toBe('new');

    app(Planner::class)->planAll($this->now, [$b->id]);
    expect($forB->refresh()->social_account_id)->toBe($b->id)->and($folderB->refresh()->social_account_id)->toBe($b->id);
});

test('a product with no valid cart on the channel is never attached there', function () {
    ($this->account)();
    RiengAutoSettings::update(['enabled' => true]);
    $tc = ($this->ready)('tc.mp4', ['product_code' => 'tc01'], [], ['product_code' => 'tc01']);

    app(Planner::class)->planAll($this->now);

    expect($tc->refresh()->status)->toBe('new');
});

// ---------------------------------------------------------------- AI xem video

/** Bộ nghe lời nói giả: trả sẵn lời nói (null = bộ nghe chưa sẵn sàng). */
function fakeSpeech(?string $text, bool $ready = false): RiengSpeech
{
    return new class($text, $ready) extends RiengSpeech
    {
        public int $calls = 0;

        public function __construct(private ?string $text, private bool $isReady) {}

        public function ready(): bool
        {
            return $this->isReady;
        }

        public function transcribe(string $video): ?string
        {
            $this->calls++;

            return $this->text;
        }
    };
}

/** Bộ xem video giả: không cần ffmpeg. */
function fakeAnalyzer(CodexRunner $codex, ?RiengSpeech $speech = null): RiengAnalyzer
{
    return new class(app(ChatGptAccounts::class), $codex, app(RiengThumbs::class), $speech ?? fakeSpeech(null)) extends RiengAnalyzer
    {
        protected function grids(AutoVideo $video, string $work): array
        {
            file_put_contents($work.'/luoi-1.jpg', 'jpg');
            file_put_contents($work.'/luoi-2.jpg', 'jpg');

            return [$work.'/luoi-1.jpg', $work.'/luoi-2.jpg'];
        }
    };
}

function fakeCodex(array $answers): CodexRunner
{
    return new class(app(ChatGptAccounts::class), $answers) extends CodexRunner
    {
        public array $calls = [];

        public function __construct(ChatGptAccounts $a, private array $answers)
        {
            parent::__construct($a);
        }

        public function ask(string $accountId, string $model, string $effort, string $prompt, array $images, string $workDir, bool $fast = false): string
        {
            $this->calls[] = [$accountId, $model, $effort, $prompt];
            $next = array_shift($this->answers);

            if ($next instanceof Throwable) {
                throw $next;
            }

            return (string) $next;
        }
    };
}

test('the AI attaches the product only when sure, writes a short caption without hashtags and never overrides the owner pick', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    $codex = fakeCodex([
        '{"ma":"nano-dong","chac":"cao","ly_do":"thấy nhãn","tom_tat":"rửa vườn","hashtag":["#nanođồng","vườn cà phê","#ruavuon","#thua"],"caption":"#rua Rửa vườn sau thu hoạch, sạch nấm hồng rong rêu trên thân cành cà phê cho mùa sau ra hoa đều hơn nhiều lắm"}',
    ]);
    $an = fakeAnalyzer($codex);
    $sure = ($this->rieng)('a.mp4');
    $vague = ($this->rieng)('b.mp4');
    $mine = ($this->rieng)('c.mp4', ['product_code' => 'nano-dong'], ['product_by' => 'kid']);

    $ai = $an->analyze($sure);
    expect($ai['state'])->toBe('ok')->and($sure->refresh()->product_code)->toBe('nano-dong')
        ->and($ai['caption'])->not->toContain('#')->and(mb_strlen($ai['caption']))->toBeLessThanOrEqual(90)
        ->and($codex->calls[0][3])->toContain('2 ẢNH LƯỚI')->not->toContain('LỜI NÓI')->toContain('Một chai pha một phuy 200 lít')->toContain('Giá tiền')
        ->and($codex->calls[0][1])->toBe('gpt-6-luna')
        ->and($ai['hashtags'])->toBe(['#nanodong', '#vuoncaphe', '#ruavuon']);

    // Mọi bậc đều chỉ "vừa chắc": giữ kết quả, không gắn sản phẩm.
    $vagueAi = fakeAnalyzer(fakeCodex(array_fill(0, 8, '{"ma":"nano-dong","chac":"vua","ly_do":"","tom_tat":"","caption":"c2"}')))->analyze($vague);
    expect($vagueAi['state'])->toBe('unsure')->and($vague->refresh()->product_code)->toBeNull();
    expect(fakeAnalyzer(fakeCodex(['{"ma":"tc01","chac":"cao","ly_do":"","tom_tat":"","caption":"c3"}']))->analyze($mine)['product_code'])->toBe('tc01')
        ->and($mine->refresh()->product_code)->toBe('nano-dong');
});

test('an account out of quota rests and the next account takes over; no account left means retry later', function () {
    ($this->gptAccount)('tk-aaaaaaaa', 'a@x.test');
    ($this->gptAccount)('tk-bbbbbbbb', 'b@x.test');
    $codex = fakeCodex([new CodexLimited(90), '{"ma":"nano-dong","chac":"cao","ly_do":"","tom_tat":"","caption":"ok"}']);
    $v = ($this->rieng)('a.mp4');

    $ai = fakeAnalyzer($codex)->analyze($v);

    $accounts = collect(app(ChatGptAccounts::class)->all())->keyBy('id');
    expect($ai['state'])->toBe('ok')->and($codex->calls[0][0])->not->toBe($codex->calls[1][0])
        ->and($accounts[$codex->calls[0][0]]['cooldown_until'])->not->toBeNull()
        ->and($accounts[$codex->calls[1][0]]['uses'])->toBe(1);

    // Cả hai tài khoản nghỉ → lỗi, hẹn thử lại, chưa bỏ cuộc.
    app(ChatGptAccounts::class)->markLimited($codex->calls[1][0]);
    $w = ($this->rieng)('b.mp4');
    $err = fakeAnalyzer(fakeCodex([]))->analyze($w);
    expect($err['state'])->toBe('error')->and($err['next_try_at'])->not->toBeNull()
        ->and(app(RiengAnalyzer::class)->pending(10, CarbonImmutable::now()))->toHaveCount(0)
        ->and(app(RiengAnalyzer::class)->pending(10, CarbonImmutable::now()->addHour()))->toHaveCount(1);
});

test('accounts rotate in turn and show the signed-in email', function () {
    ($this->gptAccount)('tk-aaaaaaaa', 'a@x.test');
    touch($this->gpt.'/tk-aaaaaaaa', time() - 100);
    ($this->gptAccount)('tk-bbbbbbbb', 'b@x.test');
    File::ensureDirectoryExists($this->gpt.'/tk-cccccccc'); // đang đăng nhập dở: chưa dùng
    $acc = app(ChatGptAccounts::class);

    $first = $acc->pick();
    $acc->markUsed($first);
    $second = $acc->pick();
    $acc->markUsed($second);

    expect([$first, $second])->toEqualCanonicalizing(['tk-aaaaaaaa', 'tk-bbbbbbbb'])->and($acc->pick())->toBe($first)
        ->and(collect($acc->all())->pluck('email')->filter()->values()->all())->toEqualCanonicalizing(['a@x.test', 'b@x.test'])
        ->and(collect($acc->all())->firstWhere('id', 'tk-cccccccc')['ready'])->toBeFalse();

    expect($acc->remove('tk-bbbbbbbb'))->toBeTrue()->and(is_dir($this->gpt.'/tk-bbbbbbbb'))->toBeFalse()
        ->and($acc->remove('../x'))->toBeFalse();
});

test('wrong answers are rejected and the retry wait grows', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    $v = ($this->rieng)('a.mp4');
    $an = fakeAnalyzer(fakeCodex(array_fill(0, 20, 'không phải json')));

    $one = $an->analyze($v, CarbonImmutable::parse('2026-11-16 10:00:00'));
    $two = $an->analyze($v->refresh(), CarbonImmutable::parse('2026-11-16 11:00:00'));

    expect($one['state'])->toBe('error')->and($one['error'])->toContain('sai định dạng')
        ->and(CarbonImmutable::parse($one['next_try_at'])->diffInMinutes(CarbonImmutable::parse('2026-11-16 10:00:00'), true))->toEqual(2)
        ->and(CarbonImmutable::parse($two['next_try_at'])->diffInMinutes(CarbonImmutable::parse('2026-11-16 11:00:00'), true))->toEqual(10)
        ->and($two['tries'])->toBe(2);
});

test('the quota reset time is read from the ChatGPT message', function () {
    expect(CodexRunner::retryAt("You've hit your usage limit. Try again in 2 hours 5 minutes."))->toBe(125)
        ->and(CodexRunner::retryAt('try again in 37 minutes'))->toBe(37)
        ->and(CodexRunner::retryAt('nothing'))->toBeNull();
});

test('codex runs with the Fast tier when chosen and "out of credits" counts as out of quota', function () {
    $bin = $this->gpt.'/fake-codex.cmd';
    file_put_contents($bin, "@echo off\r\necho %* > \"%~dp0args.txt\"\r\necho ERROR: Your workspace is out of credits. Add credits to continue. 1>&2\r\nexit /b 1\r\n");
    config(['fork.auto.codex_path' => $bin]);
    ($this->gptAccount)('tk-aaaaaaaa');
    $work = $this->gpt.'/work';
    File::ensureDirectoryExists($work);

    expect(fn () => app(CodexRunner::class)->ask('tk-aaaaaaaa', 'gpt-6.1-terra', 'low', 'hi', [], $work, true))->toThrow(CodexLimited::class);
    $args = (string) file_get_contents($this->gpt.'/args.txt');
    // Mỗi -c phải đi liền giá trị của nó (lỗi cũ: "-c -c service_tier=... model_reasoning_effort=low").
    expect($args)->toMatch('/-c\s+"?service_tier=\\\\?"?fast/')->toMatch('/-c\s+"?model_reasoning_effort=low/')->not->toMatch('/-c\s+-c/');

    expect(fn () => app(CodexRunner::class)->ask('tk-aaaaaaaa', 'gpt-6.1-terra', 'low', 'hi', [], $work, false))->toThrow(CodexLimited::class)
        ->and((string) file_get_contents($this->gpt.'/args.txt'))->not->toContain('service_tier');
})->skip(PHP_OS_FAMILY !== 'Windows', 'cmd script');

test('the app finds codex.exe it installed itself, without PATH or a global npm install', function () {
    $dir = $this->gpt.'/cli';
    $exe = $dir.'/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe';
    File::ensureDirectoryExists(dirname($exe));
    file_put_contents($exe, '');
    config(['fork.auto.codex_path' => '', 'fork.auto.codex_dir' => $dir]);

    $accounts = app(ChatGptAccounts::class);
    expect(str_replace('\\', '/', (string) $accounts->codexPath()))->toBe($exe)
        ->and($accounts->cliStatus())->toMatchArray(['installed' => true, 'installing' => false]);

    $this->actingAs($this->owner)->postJson('/auto/kho/rieng/tu-dong/codex-cli', ['check' => true])
        ->assertOk()->assertJsonPath('cli.installed', true);
    $this->actingAs($this->owner)->getJson('/auto/kho/rieng/tu-dong')->assertOk()->assertJsonPath('codex_installed', true)->assertJsonPath('cli.installed', true);
});

test('real Codex model names, efforts limited to what the model has, and the Fast switch', function () {
    $r = $this->actingAs($this->owner)->patchJson('/auto/kho/rieng/tu-dong', ['model' => 'gpt-6-luna', 'effort' => 'xhigh', 'fast' => true])->assertOk()->json();

    expect($r['settings'])->toMatchArray(['model' => 'gpt-6-luna', 'effort' => 'xhigh', 'fast' => true])
        ->and($r['models']['gpt-6.1-sol']['name'])->toBe('GPT-6.1-Sol')
        ->and($r['models']['gpt-6-luna']['efforts'])->not->toContain('ultra')
        ->and($r['efforts']['xhigh'])->toBe('Extra high');

    // Luna không có mức Ultra: về mức mặc định.
    expect(RiengAutoSettings::update(['effort' => 'ultra'])['effort'])->toBe('low');
});

// ---------------------------------------------------------------- Trang cài đặt + sửa video

test('settings save, folder channels keep only own channels and the cards carry the auto status', function () {
    $owner = $this->owner;
    $a = ($this->account)();
    $folder = RiengFolder::create(['path' => $this->own, 'name' => 'Của tôi']);

    $r = $this->actingAs($owner)->patchJson('/auto/kho/rieng/tu-dong', [
        'enabled' => true, 'caption_mode' => 'ai', 'approve_first' => true, 'model' => 'gpt-6.1-sol', 'effort' => 'high',
        'folder_channels' => [(string) $folder->id => [$a->id, 'kenh-la'], '999' => [$a->id]],
    ])->assertOk()->json();

    expect($r['settings']['model'])->toBe('gpt-6.1-sol')->and($r['settings']['folder_channels'])->toBe([(string) $folder->id => [$a->id]])
        ->and($r['channels'][0]['id'])->toBe($a->id)->and($r['products'])->toHaveCount(2);

    $this->actingAs($owner)->patchJson('/auto/kho/rieng/tu-dong', ['model' => 'gpt-4'])->assertUnprocessable();

    $v = ($this->ready)('a.mp4');
    $this->actingAs($owner)->postJson('/auto/kho/rieng/video/'.$v->id.'/tu-dong', ['product_code' => 'tc01', 'caption' => 'Của anh'])
        ->assertOk()->assertJsonPath('auto.product_by', 'kid')->assertJsonPath('auto.kid_caption', 'Của anh')->assertJsonPath('auto.final_caption', 'Của anh');

    // Về lại "theo AI".
    $this->actingAs($owner)->postJson('/auto/kho/rieng/video/'.$v->id.'/tu-dong', ['product_code' => null, 'caption' => ''])
        ->assertOk()->assertJsonPath('auto.product_code', 'nano-dong')->assertJsonPath('auto.product_by', 'ai')->assertJsonPath('auto.kid_caption', null);
});

// ---------------------------------------------------------------- Thư mục: đổi tên, thêm video, mở thư mục

test('a folder can be renamed in the app and reset to its real name', function () {
    $folder = RiengFolder::create(['path' => $this->own, 'name' => null]);

    $this->actingAs($this->owner)->patchJson("/auto/kho/rieng/thu-muc/{$folder->id}", ['name' => '  Video tháng 11 '])
        ->assertOk()->assertJsonPath('name', 'Video tháng 11');
    expect($folder->refresh()->name)->toBe('Video tháng 11');

    $this->actingAs($this->owner)->patchJson("/auto/kho/rieng/thu-muc/{$folder->id}", ['name' => ''])
        ->assertOk()->assertJsonPath('name', basename($this->own));
});

test('videos added to a folder are copied in without overwriting and only video files are accepted', function () {
    $folder = RiengFolder::create(['path' => $this->own, 'name' => null]);
    file_put_contents($this->own.'/clip.mp4', 'old');

    $this->actingAs($this->owner)->post("/auto/kho/rieng/thu-muc/{$folder->id}/video", ['file' => UploadedFile::fake()->create('clip.mp4', 20)], ['Accept' => 'application/json'])
        ->assertOk()->assertJsonPath('name', 'clip (2).mp4');
    expect(file_get_contents($this->own.'/clip.mp4'))->toBe('old')->and(is_file($this->own.'/clip (2).mp4'))->toBeTrue();

    $this->actingAs($this->owner)->post("/auto/kho/rieng/thu-muc/{$folder->id}/video", ['file' => UploadedFile::fake()->create('note.txt', 1)], ['Accept' => 'application/json'])
        ->assertStatus(422);
    expect(is_file($this->own.'/note.txt'))->toBeFalse();
});

test('opening a folder that is gone says so', function () {
    $folder = RiengFolder::create(['path' => $this->own.'/khong-co', 'name' => null]);

    $this->actingAs($this->owner)->postJson("/auto/kho/rieng/thu-muc/{$folder->id}/mo")->assertStatus(422);
});

test('reads ChatGPT quota windows from codex app-server', function () {
    $msg = ['id' => 2, 'result' => ['ordinaryUsageAllowed' => true, 'rateLimits' => [
        'primary' => ['usedPercent' => 12.6, 'windowDurationMins' => 300, 'resetsAt' => 1797435673],
        'secondary' => ['usedPercent' => 40, 'windowDurationMins' => 10080, 'resetsAt' => 1797435673],
        'planType' => 'plus', 'rateLimitReachedType' => null,
    ]]];

    $l = ChatGptAccounts::parseLimits($msg);
    expect($l['plan'])->toBe('plus')->and($l['reached'])->toBeFalse()
        ->and($l['windows'])->toHaveCount(2)
        ->and($l['windows'][0])->toMatchArray(['used' => 13, 'minutes' => 300])
        ->and($l['windows'][1]['used'])->toBe(40)
        ->and(ChatGptAccounts::parseLimits(['id' => 2, 'error' => ['message' => 'x']]))->toBeNull();

    $this->actingAs($this->owner)->getJson('/auto/kho/rieng/tu-dong/chatgpt/tk-zzzzzzzz/han-muc')->assertOk()->assertJson(['ok' => false, 'limits' => null]);
});

// ---------------------------------------------------------------- Model theo tài khoản, thử lại

test('model list from codex keeps image models, translates notes and knows Fast', function () {
    $msg = ['id' => 3, 'result' => ['data' => [
        ['id' => 'gpt-6-luna', 'displayName' => 'GPT-6-Luna', 'description' => 'Fast and affordable', 'hidden' => false, 'isDefault' => true, 'inputModalities' => ['text', 'image'],
            'supportedReasoningEfforts' => [['reasoningEffort' => 'low'], ['reasoningEffort' => 'medium']], 'serviceTiers' => [], 'additionalSpeedTiers' => []],
        ['id' => 'gpt-5.6-terra', 'displayName' => 'GPT-5.6-Terra', 'description' => 'Older balanced model', 'hidden' => false, 'isDefault' => false, 'inputModalities' => ['text', 'image'],
            'supportedReasoningEfforts' => [['reasoningEffort' => 'low']], 'serviceTiers' => ['priority'], 'additionalSpeedTiers' => []],
        ['id' => 'text-only', 'displayName' => 'T', 'hidden' => false, 'inputModalities' => ['text'], 'supportedReasoningEfforts' => []],
        ['id' => 'secret', 'displayName' => 'S', 'hidden' => true, 'inputModalities' => ['text', 'image'], 'supportedReasoningEfforts' => []],
    ]]];

    $m = ChatGptAccounts::parseModels($msg);
    expect(array_keys($m))->toBe(['gpt-6-luna', 'gpt-5.6-terra'])
        ->and($m['gpt-6-luna'])->toMatchArray(['name' => 'GPT-6-Luna', 'efforts' => ['low', 'medium'], 'fast' => false, 'default' => true])
        ->and($m['gpt-5.6-terra']['fast'])->toBeTrue()
        ->and($m['gpt-5.6-terra']['note'])->toContain('đời cũ');
});

test('an account without the chosen model uses its own default model, and a "not supported" answer switches model once', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    Cache::put('fork-rieng:chatgpt-models:tk-aaaaaaaa', [
        'gpt-6-luna' => ['name' => 'GPT-6-Luna', 'note' => '', 'efforts' => ['low', 'medium'], 'fast' => false, 'default' => true],
    ], now()->addHour());
    RiengAutoSettings::update(['model' => 'gpt-6.1-terra', 'effort' => 'high', 'fast' => true]);
    $acc = app(ChatGptAccounts::class);

    expect($acc->modelFor('tk-aaaaaaaa', 'gpt-6.1-terra'))->toBe(['gpt-6-luna', false])
        ->and($acc->modelFor('tk-aaaaaaaa', 'gpt-6-luna'))->toBe(['gpt-6-luna', false])
        ->and($acc->modelFor('tk-bbbbbbbb', 'gpt-6.1-terra'))->toBe(['gpt-6.1-terra', true]); // chưa biết: giữ nguyên

    $codex = fakeCodex(['{"ma":"nano-dong","chac":"cao","ly_do":"","tom_tat":"","caption":"c"}']);
    $v = ($this->rieng)('m.mp4');
    $ai = fakeAnalyzer($codex)->analyze($v);

    // Model tài khoản có, mức nghĩ "high" không có thì hạ xuống mức gần nhất.
    expect($ai['state'])->toBe('ok')->and($ai['model'])->toBe('gpt-6-luna')
        ->and($codex->calls[0][1])->toBe('gpt-6-luna')->and($codex->calls[0][2])->toBe('medium');
});

test('retry now resets failed videos, clears account errors, and runs again after an app update', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    $acc = app(ChatGptAccounts::class);
    $acc->markError('tk-aaaaaaaa', 'lỗi cũ');
    $later = CarbonImmutable::now()->addHours(5)->utc()->toIso8601String();
    $err = ($this->rieng)('e.mp4', [], ['ai' => ['state' => 'error', 'tries' => 3, 'next_try_at' => $later, 'error' => 'x']]);
    $gave = ($this->rieng)('g.mp4', [], ['ai' => ['state' => 'gave_up', 'tries' => 5, 'error' => 'x']]);
    $ok = ($this->ready)('o.mp4');
    $an = app(RiengAnalyzer::class);

    expect($an->pending(10))->toHaveCount(0);

    $r = $this->actingAs($this->owner)->postJson('/auto/kho/rieng/tu-dong/ai-thu-lai')->assertOk()->json();

    expect($r['retried'])->toBe(2)->and($r['counts']['cho'] ?? 0)->toBe(2)->and($r['counts'])->not->toHaveKey('error')
        ->and(collect($an->pending(10))->pluck('id')->all())->toEqualCanonicalizing([$err->id, $gave->id])
        ->and(data_get($gave->refresh()->meta, 'ai.tries'))->toBe(0)
        ->and(data_get($ok->refresh()->meta, 'ai.state'))->toBe('ok')
        ->and(collect($acc->all())->firstWhere('id', 'tk-aaaaaaaa')['last_error'])->toBeNull();

    // Đổi model: thử lại ngay.
    $err->forceFill(['meta' => ['ai' => ['state' => 'error', 'tries' => 2, 'next_try_at' => $later]] + (array) $err->meta])->save();
    $this->actingAs($this->owner)->patchJson('/auto/kho/rieng/tu-dong', ['model' => 'gpt-6.1-sol', 'effort' => 'low'])->assertOk();
    expect(data_get($err->refresh()->meta, 'ai.tries'))->toBe(0);

    // App lên bản mới: lượt AI đầu tiên cho video lỗi thử lại ngay (mỗi bản một lần).
    $err->forceFill(['meta' => ['ai' => ['state' => 'error', 'tries' => 2, 'next_try_at' => $later]] + (array) $err->meta])->save();
    $ver = $this->gpt.'/VERSION';
    file_put_contents($ver, '9.9.9');
    config(['fork-update.version_file' => $ver]);
    Cache::forget('fork-rieng:ai-version');
    RiengAutoSettings::update(['enabled' => true]);
    app()->instance(RiengAnalyzer::class, $spy = new class(app(ChatGptAccounts::class), app(CodexRunner::class), app(RiengThumbs::class)) extends RiengAnalyzer
    {
        public int $retries = 0;

        public function retryNow(?CarbonImmutable $now = null): int
        {
            $this->retries++;

            return parent::retryNow($now);
        }

        public function pending(int $limit, ?CarbonImmutable $now = null): array
        {
            return [];
        }
    });
    $this->artisan('fork:rieng-ai')->assertSuccessful();
    $this->artisan('fork:rieng-ai')->assertSuccessful();
    expect($spy->retries)->toBe(1)->and(data_get($err->refresh()->meta, 'ai.tries'))->toBe(0);
});

test('the settings payload offers the models the signed-in accounts really have', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    RiengAutoSettings::update(['model' => 'gpt-6.1-terra']);

    $r = $this->actingAs($this->owner)->getJson('/auto/kho/rieng/tu-dong')->assertOk()->json();
    expect($r['models_from_accounts'])->toBeFalse()->and($r['models'])->toHaveKey('gpt-6.1-terra')->and($r['model_effective'])->toBeNull();

    Cache::put('fork-rieng:chatgpt-models:tk-aaaaaaaa', [
        'gpt-6-luna' => ['name' => 'GPT-6-Luna', 'note' => '', 'efforts' => ['low'], 'fast' => false, 'default' => true],
        'gpt-5.6-terra' => ['name' => 'GPT-5.6-Terra', 'note' => '', 'efforts' => ['low'], 'fast' => false, 'default' => false],
    ], now()->addHour());

    $r = $this->actingAs($this->owner)->getJson('/auto/kho/rieng/tu-dong')->assertOk()->json();
    expect($r['models_from_accounts'])->toBeTrue()->and(array_keys($r['models']))->toBe(['gpt-6-luna', 'gpt-5.6-terra'])
        ->and($r['model_effective'])->toBe('gpt-6-luna');

    $this->actingAs($this->owner)->patchJson('/auto/kho/rieng/tu-dong', ['model' => 'gpt-5.6-terra'])->assertOk()->assertJsonPath('settings.model', 'gpt-5.6-terra')->assertJsonPath('model_effective', null);
});

test('when ChatGPT says the model is not available the app switches to another model of that account and retries once', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    Cache::put('fork-rieng:chatgpt-models:tk-aaaaaaaa', [
        'gpt-6.1-terra' => ['name' => 'T', 'note' => '', 'efforts' => ['low'], 'fast' => true, 'default' => false],
        'gpt-6-luna' => ['name' => 'L', 'note' => '', 'efforts' => ['low'], 'fast' => false, 'default' => true],
    ], now()->addHour());
    RiengAutoSettings::update(['model' => 'gpt-6.1-terra', 'effort' => 'low']);
    // Codex giả không trả lời gì: app dùng danh sách đã nhớ, bỏ model bị từ chối.
    file_put_contents($this->gpt.'/dummy-codex.cmd', "@echo off\r\nexit /b 1\r\n");
    config(['fork.auto.codex_path' => $this->gpt.'/dummy-codex.cmd']);
    $codex = fakeCodex([new RuntimeException('Tài khoản ChatGPT không dùng được model gpt-6.1-terra.'), '{"ma":"nano-dong","chac":"cao","ly_do":"","tom_tat":"","caption":"c"}']);

    $ai = fakeAnalyzer($codex)->analyze(($this->rieng)('f.mp4'));

    expect($ai['state'])->toBe('ok')->and(array_column($codex->calls, 1))->toBe(['gpt-6.1-terra', 'gpt-6-luna'])
        ->and(app(ChatGptAccounts::class)->knownModels('tk-aaaaaaaa'))->not->toHaveKey('gpt-6.1-terra');
});

test('when the AI is not sure it listens to the speech, thinks harder, then switches model, and stops as soon as it is sure', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    Cache::put('fork-rieng:chatgpt-models:tk-aaaaaaaa', [
        'gpt-6-luna' => ['name' => 'GPT-6-Luna', 'note' => '', 'efforts' => ['low', 'medium', 'high', 'xhigh', 'max'], 'fast' => false, 'default' => true],
        'gpt-5.6-terra' => ['name' => 'GPT-5.6-Terra', 'note' => '', 'efforts' => ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'], 'fast' => false, 'default' => false],
        'gpt-5.6-luna' => ['name' => 'GPT-5.6-Luna', 'note' => '', 'efforts' => ['low', 'max'], 'fast' => false, 'default' => false],
    ], now()->addHour());
    RiengAutoSettings::update(['model' => 'gpt-6-luna', 'effort' => 'low']);
    $an = fakeAnalyzer(fakeCodex([]));

    expect(array_map(fn ($s) => [$s['model'], $s['effort'], $s['loi']], $an->plan(RiengAutoSettings::get())))->toBe([
        ['gpt-6-luna', 'low', false],
        ['gpt-6-luna', 'low', true],
        ['gpt-6-luna', 'max', true],
        ['gpt-5.6-terra', 'ultra', true],
        ['gpt-5.6-luna', 'max', true],
    ]);

    $vague = '{"ma":null,"chac":"thap","ly_do":"","tom_tat":"","caption":"c"}';
    $codex = fakeCodex([$vague, 'không phải json', $vague, '{"ma":"tc01","chac":"cao","ly_do":"nghe tên","tom_tat":"","caption":"c4"}', 'không dùng tới']);
    $speech = fakeSpeech('Hôm nay em giới thiệu TC01 cho bà con');
    $v = ($this->rieng)('l.mp4');

    $ai = fakeAnalyzer($codex, $speech)->analyze($v);

    expect($ai['state'])->toBe('ok')->and($ai['product_code'])->toBe('tc01')->and($v->refresh()->product_code)->toBe('tc01')
        ->and(array_map(fn ($c) => [$c[1], $c[2]], $codex->calls))->toBe([['gpt-6-luna', 'low'], ['gpt-6-luna', 'low'], ['gpt-6-luna', 'max'], ['gpt-5.6-terra', 'ultra']])
        ->and($codex->calls[0][3])->not->toContain('LỜI NÓI trong video')
        ->and($codex->calls[1][3])->toContain('Hôm nay em giới thiệu TC01')
        ->and($speech->calls)->toBe(1)
        ->and($ai['loi'])->toBe('Hôm nay em giới thiệu TC01 cho bà con')
        ->and($ai['buoc'])->toHaveCount(4)
        ->and($ai['model'])->toBe('gpt-5.6-terra');

    // Xem lại lần sau dùng lại lời nói đã nghe, không nghe lại.
    $speech2 = fakeSpeech('khác');
    fakeAnalyzer(fakeCodex(array_fill(0, 6, $vague)), $speech2)->analyze($v->refresh());
    expect($speech2->calls)->toBe(0);
});

test('without speech the listen step is skipped and product photos go with the grids', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    file_put_contents($this->hub.'/san-pham/nano-dong/anh.jpg', 'jpg');
    $codex = fakeCodex(array_fill(0, 10, '{"ma":null,"chac":"thap","ly_do":"","tom_tat":"","caption":"c"}'));
    $v = ($this->rieng)('n.mp4');
    $an = new class(app(ChatGptAccounts::class), $codex, app(RiengThumbs::class), fakeSpeech(null)) extends RiengAnalyzer
    {
        public array $images = [];

        protected function grids(AutoVideo $video, string $work): array
        {
            file_put_contents($work.'/luoi-1.jpg', 'jpg');

            return [$work.'/luoi-1.jpg'];
        }
    };

    $ai = $an->analyze($v);
    $plan = $an->plan(RiengAutoSettings::get());

    // Bậc "nghe thêm" bỏ qua (không tốn lượt), các bậc khác vẫn chạy.
    expect($ai['state'])->toBe('unsure')->and($codex->calls)->toHaveCount(count($plan) - 1)
        ->and($codex->calls[0][3])->toContain('ẢNH MẪU')->toContain('Ảnh 2: sản phẩm `nano-dong`');
});

test('the owner can edit the AI hashtags of a video, and reset them to the AI ones', function () {
    $v = ($this->ready)('h.mp4', ['hashtags' => ['#ai1', '#ai2']]);
    $poster = app(RiengAutoPoster::class);

    $r = $this->actingAs($this->owner)->postJson("/auto/kho/rieng/video/{$v->id}/tu-dong", ['hashtags' => ['vườn cà phê', '#NanoĐồng', '', '#nanodong']])->assertOk()->json();
    expect($r['auto']['kid_hashtags'])->toBe(['#vuoncaphe', '#NanoDong'])
        ->and($poster->hashtagsFor($v->refresh(), 'cap'))->toBe(['#vuoncaphe', '#NanoDong']);

    $this->actingAs($this->owner)->postJson("/auto/kho/rieng/video/{$v->id}/tu-dong", ['hashtags' => []])->assertOk();
    expect($poster->hashtagsFor($v->refresh(), 'cap'))->toBe([]);

    $this->actingAs($this->owner)->postJson("/auto/kho/rieng/video/{$v->id}/tu-dong", ['hashtags' => null])->assertOk()->assertJsonPath('auto.kid_hashtags', null);
    expect($poster->hashtagsFor($v->refresh(), 'cap'))->toBe(['#ai1', '#ai2']);
});

test('asking the AI to look again queues the video right away and keeps the heard speech', function () {
    $v = ($this->rieng)('q.mp4', [], ['ai' => ['state' => 'unsure', 'product_code' => null, 'loi' => 'lời cũ', 'tries' => 1]]);

    $r = $this->actingAs($this->owner)->postJson("/auto/kho/rieng/video/{$v->id}/ai-xem-lai")->assertOk()->json();

    expect($r['auto']['ai_state'])->toBeNull()->and($r['auto']['ai_progress']['viec'])->toBe('Đang chờ AI')
        ->and(data_get($v->refresh()->meta, 'ai.loi'))->toBe('lời cũ')
        ->and(collect(app(RiengAnalyzer::class)->pending(10))->pluck('id')->all())->toContain($v->id);

    $this->actingAs($this->owner)->getJson("/auto/kho/rieng/video/{$v->id}/trang-thai")->assertOk()->assertJsonPath('auto.ai_heard', 'lời cũ');
});

test('when the speech tool is installed the AI hears the speech from the first step', function () {
    ($this->gptAccount)('tk-aaaaaaaa');
    $codex = fakeCodex(['{"ma":null,"chac":"thap","ly_do":"","tom_tat":"","caption":"c"}', '{"ma":"tc01","chac":"cao","ly_do":"","tom_tat":"","caption":"c"}']);
    $speech = fakeSpeech('em giới thiệu TC01', true);

    $ai = fakeAnalyzer($codex, $speech)->analyze(($this->rieng)('s.mp4'));

    // Bậc 1 đã có lời nói; bậc "nghe thêm" bị bỏ; bậc 2 là nghĩ kỹ nhất.
    expect($ai['state'])->toBe('ok')->and($speech->calls)->toBe(1)
        ->and($codex->calls[0][3])->toContain('em giới thiệu TC01')
        ->and($codex->calls[1][2])->not->toBe($codex->calls[0][2]);
});

test('the AI status line tells what the AI is doing, what is missing and when it retries', function () {
    // Trang hỏi lại sau vài giây; ở đây bỏ bộ nhớ đệm 3 giây để mỗi lần hỏi thấy ngay trạng thái mới.
    $status = function (): array {
        Cache::forget('fork-rieng:ai-status');

        return $this->actingAs($this->owner)->getJson('/auto/kho/rieng/tu-dong/ai-trang-thai')->assertOk()->json();
    };
    $a = ($this->rieng)('a.mp4');

    // Chưa cài ChatGPT CLI.
    config(['fork.auto.codex_path' => '', 'fork.auto.codex_dir' => $this->gpt.'/cli']);
    expect($status())->toMatchArray(['tone' => 'warn', 'fix' => 'settings', 'queued' => 1, 'can_run' => false]);

    // Có CLI, chưa có tài khoản.
    $exe = $this->gpt.'/cli/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe';
    File::ensureDirectoryExists(dirname($exe));
    file_put_contents($exe, '');
    config(['fork.auto.codex_path' => $exe]);
    expect($status()['title'])->toContain('chưa có tài khoản ChatGPT');

    // Có tài khoản, AI chưa chạy lượt nào: nhắc bấm "Cho AI xem ngay".
    ($this->gptAccount)('tk-aaaaaaaa');
    $r = $status();
    expect($r)->toMatchArray(['tone' => 'warn', 'can_run' => true, 'queued' => 1])->and($r['detail'])->toContain('Cho AI xem ngay');

    // Lượt vừa chạy: chỉ báo đang chờ lượt tới.
    RiengAiStatus::beat(['dang' => false, 'note' => 'không có video mới']);
    expect($status())->toMatchArray(['tone' => 'info'])->and($status()['detail'])->toContain('2 phút');

    // Đang xem.
    $a->forceFill(['meta' => ['ai' => ['dang' => ['buoc' => 2, 'tong' => 4, 'viec' => 'Đang nghe lời nói', 'luc' => now()->toIso8601String()]]] + (array) $a->meta])->save();
    $r = $status();
    expect($r['running'])->toMatchArray(['id' => $a->id, 'buoc' => 2, 'tong' => 4])->and($r['title'])->toContain('a.mp4')->and($r['title'])->toContain('2/4');

    // Lỗi, chờ thử lại: thẻ và dòng trạng thái đều nói giờ thử lại và lỗi gì.
    $later = now()->addMinutes(30)->utc()->toIso8601String();
    $a->forceFill(['meta' => ['ai' => ['state' => 'error', 'tries' => 1, 'error' => 'ChatGPT trả lời sai định dạng.', 'next_try_at' => $later]] + (array) $a->meta])->save();
    $r = $status();
    expect($r)->toMatchArray(['waiting' => 1, 'queued' => 0])->and($r['title'])->toContain('thử lại lúc')->and($r['detail'])->toContain('sai định dạng')
        ->and(app(RiengAutoPoster::class)->blocker($a->refresh(), null, null, RiengAutoSettings::get()))->toStartWith('AI chưa xem được, thử lại lúc');

    // Xong hết.
    $a->forceFill(['product_code' => 'nano-dong', 'meta' => ['ai' => ['state' => 'ok', 'product_code' => 'nano-dong']] + (array) $a->meta])->save();
    expect($status())->toMatchArray(['tone' => 'success', 'queued' => 0, 'waiting' => 0]);
});

test('the AI watches new videos even before auto-posting is turned on, and leaves a heartbeat', function () {
    expect(RiengAutoSettings::get()['enabled'])->toBeFalse();
    app()->instance(RiengAnalyzer::class, $spy = new class(app(ChatGptAccounts::class), app(CodexRunner::class), app(RiengThumbs::class)) extends RiengAnalyzer
    {
        public int $asked = 0;

        public function pending(int $limit, ?CarbonImmutable $now = null): array
        {
            $this->asked++;

            return [];
        }
    });

    $this->artisan('fork:rieng-ai')->assertSuccessful();
    expect($spy->asked)->toBe(1)
        ->and(Cache::get(RiengAiStatus::KEY))->toMatchArray(['dang' => false, 'note' => 'không có video mới']);
});

test('a busy page polling one route does not use up the limit of another button', function () {
    $v = ($this->rieng)('a.mp4');

    foreach (range(1, 25) as $i) {
        expect($this->actingAs($this->owner)->postJson("/auto/kho/rieng/video/{$v->id}/tu-dong", [])->status())->not->toBe(429);
    }

    // "Chọn thư mục" giới hạn 20/phút riêng của nó: không bị chặn vì các lần gọi ở trên.
    expect($this->actingAs($this->owner)->postJson('/auto/kho/rieng/chon-thu-muc')->status())->not->toBe(429);
});

test('the CLI install progress has its own GET route that a 3-second poll never gets blocked on', function () {
    foreach (range(1, 12) as $i) {
        $this->actingAs($this->owner)->getJson('/auto/kho/rieng/tu-dong/codex-cli')->assertOk()->assertJsonStructure(['cli' => ['installed', 'installing']]);
    }
});
