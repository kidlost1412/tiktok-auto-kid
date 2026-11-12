# runtime/ - ban chay tren Windows 10/11

Thu muc nay chua toan bo "dong co" de app chay doc lap, co the chep ca thu muc du an sang may Windows khac.
Moi thu ngoai file nay deu bi git bo qua (binary, du lieu, log).

## Thanh phan

| Thanh phan | Vai tro | Vi tri / cong |
|---|---|---|
| PHP 8.5.12 NTS x64 (`php\`) | PHP cli / FastCGI | `runtime\php\php.exe`, `php-cgi.exe` |
| 2 tien trinh `php-cgi` (FastCGI) | ung dung web | 127.0.0.1:9101..9102 |
| Caddy 2.11.9 (`caddy\`) | web server | http://localhost:8010 (chi loopback) |
| PostgreSQL 16.15 (`pgsql\`) | co so du lieu | 127.0.0.1:5433, du lieu `data\pg`, DB `tiktok_auto`, user `postgres` (trust, chi loopback) |
| `queue:work` x2 (database queue) | hang doi cong viec | `queue-main`, `queue-social` |
| `schedule:work` | lich chay dinh ky | `schedule:work` |
| chrome-launcher.ps1 | tools/fork/chrome-launcher | mo Chrome profile cho tien ich TikTok Auto Kid |
| `public\build` (dung `npm run build`) | Vite dev | khong can Node khi chay |

Khong dung: Redis, Horizon, websocket, gui mail.
Cache/session/queue deu nam trong Postgres (`CACHE_STORE=database`, `SESSION_DRIVER=database`, `QUEUE_CONNECTION=database`).

Cac dich vu va thu tu khoi dong duoc mo ta trong `runtime\services.json` (do `TikTokAuto.exe` doc).

## Cai lan dau (can Internet, can Node.js chi luc build giao dien)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\native\setup.ps1 -HubPath "D:\Video\xuong-video"
```

`setup.ps1` tai PHP/PostgreSQL/Caddy/composer (phien ban ghim, kiem SHA256), `composer install`, `npm ci && npm run build`,
tao `.env` (APP_KEY moi, secret launcher moi, FORK_HUB_KEY tu dong doc tu `config.json` cua hub; token Telegram nhap trong trang Cai dat > Telegram),
`initdb`, tao DB, `migrate`. Chay lai an toan (bo qua phan da co).

## Chay / dung

- Khuyen nghi: `TikTokAuto.exe` o thu muc goc (khay he thong, tu khoi dong lai dich vu, sao luu moi ngay).
- Thu cong: `powershell -ExecutionPolicy Bypass -File scripts\native\start.ps1` va `...\stop.ps1`.
- Mo http://localhost:8010 . Log: `runtime\logs\`. Dung chay bang quyen Administrator (PostgreSQL tu choi).

## Chep sang may khac

Chep nguyen thu muc du an (gom `runtime\`, `vendor\`, `public\build\`, `.env`, `storage\`) - nen tat dich vu truoc.
Khong can cai gi them (khong PHP/Postgres/Node); neu may moi thieu Microsoft Visual C++ Redistributable 2015-2022 x64 thi cai no (PHP va Postgres can).
Duong dan trong `services.json` deu tuong doi. Chi can sua `FORK_HUB_PATH` trong `.env` neu thu muc hub o cho khac.

## Ghi chu

- `composer install` chay voi `--ignore-platform-req=ext-pcntl --ignore-platform-req=ext-posix` (Windows khong co hai ext nay).
- `/storage/*` duoc Caddy phuc vu truc tiep tu `storage\app\public` (khong can symlink).
- Test: `powershell -ExecutionPolicy Bypass -File scripts\native\test.ps1` (DB rieng `tiktok_auto_test` tren cung may chu 5433).
