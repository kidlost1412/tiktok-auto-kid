<#
.SYNOPSIS
  Cai ban chay tren Windows: tai PHP, PostgreSQL, Caddy, composer vao runtime\, cai thu vien, build giao dien, tao CSDL.
.PARAMETER HubPath
  Thu muc DU LIEU cua Xuong Video (XUONG_DATA = FORK_HUB_PATH). Mac dinh <repo>\du-lieu\xuong-video.
  Ma Xuong Video nam trong <repo>\xuong-video; venv Python o runtime\xuong-venv. Khoa ket noi hub (FORK_HUB_KEY) doc tu config.json trong thu muc du lieu.
.PARAMETER SkipBuild
  Bo qua npm ci + npm run build (da build roi).
Chay: powershell -ExecutionPolicy Bypass -File scripts\native\setup.ps1 [-HubPath "D:\Video\xuong-video"]
#>
param([string]$HubPath, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rt = Join-Path $Root 'runtime'
$dl = Join-Path $rt '_dl'
Set-Location $Root
New-Item -ItemType Directory -Force $rt, $dl, (Join-Path $rt 'logs') | Out-Null

# --- Phien ban da ghim ---
$PhpVer = '8.5.12-1'
$PhpUrl = "https://windows.php.net/downloads/releases/php-$PhpVer-nts-Win32-vs17-x64.zip"
$PhpSha = '2a36a2edcb7a5b9252f638fd5e4cf84d7f6e066092654220dc0b63e5cf4e9723'
$PhpUrlAlt = "https://windows.php.net/downloads/releases/archives/php-$PhpVer-nts-Win32-vs17-x64.zip"   # ban cu duoc chuyen vao archives/ khi co ban moi
$PgUrl = 'https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip'
$PgSha = '25E6FCDFB8CAEC38691BF461125E7564508760666F7B8E5DC6A5F0818F58F81E'
$CaddyUrl = 'https://github.com/caddyserver/caddy/releases/download/v2.11.9/caddy_2.11.9_windows_amd64.zip'
$CaddySha = 'AD93112D335EE687100C4C9F11BCED16CA590377976B7FE7883882B9E797E472'
$ComposerUrl = 'https://getcomposer.org/download/2.9.5/composer.phar'
$ComposerSha = 'c86ce603fe836bf0861a38c93ac566c8f1e69ac44b2445d9b7a6a17ea2e9972a'
$CacertUrl = 'https://curl.se/ca/cacert.pem'

function Get-File([string]$url, [string]$out, [string]$sha, [string]$alt = '') {
    # Tai bang curl (tiep tuc khi dut mang, thu lai), kiem SHA256. File da co ma sai hash -> xoa tai lai.
    if (Test-Path $out) {
        if (-not $sha -or (Get-FileHash $out -Algorithm SHA256).Hash -ieq $sha) { return }
        Remove-Item $out -Force
    }
    $urls = @($url); if ($alt) { $urls += $alt }
    foreach ($u in $urls) {
        for ($try = 1; $try -le 2; $try++) {
            Write-Host "Tai $u"
            & curl.exe -L --fail --retry 5 --retry-delay 3 -C - -o $out $u
            if ($LASTEXITCODE -eq 0 -and (Test-Path $out)) {
                if (-not $sha -or (Get-FileHash $out -Algorithm SHA256).Hash -ieq $sha) { return }
                Write-Warning "Sai SHA256: $out - tai lai"
            }
            if (Test-Path $out) { Remove-Item $out -Force }
        }
    }
    throw "Tai that bai (da thu moi dia chi): $url"
}

# --- PHP ---
$php = Join-Path $rt 'php\php.exe'
if (-not (Test-Path $php)) {
    Get-File $PhpUrl (Join-Path $dl 'php.zip') $PhpSha $PhpUrlAlt
    Expand-Archive (Join-Path $dl 'php.zip') (Join-Path $rt 'php') -Force
    Remove-Item (Join-Path $dl 'php.zip') -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path (Join-Path $rt 'php\cacert.pem'))) { Get-File $CacertUrl (Join-Path $rt 'php\cacert.pem') '' }
Copy-Item (Join-Path $PSScriptRoot 'php.ini.template') (Join-Path $rt 'php\php.ini') -Force
$cacertPath = (Join-Path $rt 'php\cacert.pem').Replace([string][char]92, '/')
(Get-Content (Join-Path $rt 'php\php.ini')) -replace '"cacert\.pem"', ('"' + $cacertPath + '"') | Set-Content (Join-Path $rt 'php\php.ini')
Add-Content (Join-Path $rt 'php\php.ini') ("`r`n[PHP]`r`nerror_log = `"" + (Join-Path $rt 'logs\php-errors.log') + "`"")

# --- Composer ---
if (-not (Test-Path (Join-Path $rt 'composer.phar'))) { Get-File $ComposerUrl (Join-Path $rt 'composer.phar') $ComposerSha }

# --- PostgreSQL ---
if (-not (Test-Path (Join-Path $rt 'pgsql\bin\postgres.exe'))) {
    Get-File $PgUrl (Join-Path $dl 'pg.zip') $PgSha
    $tmp = Join-Path $dl 'pgx'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive (Join-Path $dl 'pg.zip') $tmp -Force
    Move-Item (Join-Path $tmp 'pgsql') (Join-Path $rt 'pgsql')
    Remove-Item $tmp -Recurse -Force
    Remove-Item (Join-Path $dl 'pg.zip') -Force -ErrorAction SilentlyContinue
    # bo phan khong can de nhe bundle
    foreach ($d in 'pgAdmin 4', 'StackBuilder', 'doc', 'include', 'symbols') {
        $p = Join-Path $rt "pgsql\$d"; if (Test-Path $p) { Remove-Item $p -Recurse -Force }
    }
}

# --- Caddy ---
if (-not (Test-Path (Join-Path $rt 'caddy\caddy.exe'))) {
    Get-File $CaddyUrl (Join-Path $dl 'caddy.zip') $CaddySha
    Expand-Archive (Join-Path $dl 'caddy.zip') (Join-Path $rt 'caddy') -Force
    Remove-Item (Join-Path $dl 'caddy.zip') -Force -ErrorAction SilentlyContinue
}

# --- Xuong Video: venv Python + thu muc du lieu (tao tu xuong-video\mau) + Remotion ---
$envPath = Join-Path $Root '.env'
function Get-EnvVal([string]$k) {
    if (-not (Test-Path $envPath)) { return '' }
    $l = Get-Content $envPath -Encoding UTF8 | Where-Object { $_ -match "^$k=" } | Select-Object -First 1
    if ($l) { return (($l -replace "^$k=", '').Trim().Trim('"')) } else { return '' }
}
$bs = [string][char]92
$dataDir = if ($HubPath) { $HubPath } elseif (Get-EnvVal 'XUONG_DATA') { Get-EnvVal 'XUONG_DATA' } elseif (Get-EnvVal 'FORK_HUB_PATH') { Get-EnvVal 'FORK_HUB_PATH' } else { Join-Path $Root 'du-lieu\xuong-video' }
$dataDir = $dataDir.Replace($bs, '/').TrimEnd('/')
$xvPy = Get-EnvVal 'XUONG_PYTHON'
if (-not $xvPy) { $xvPy = Join-Path $Root 'runtime\xuong-venv\Scripts\python.exe' }
if (-not (Test-Path $xvPy)) {
    $sysPy = $null
    foreach ($try in @(@('py', '-3.11'), @('python'))) {
        if (-not (Get-Command $try[0] -ErrorAction SilentlyContinue)) { continue }
        # 'python' co the la ban gia cua Microsoft Store: chi nhan khi tra ve Python 3.10+
        $ver = (& $try[0] @($try | Select-Object -Skip 1) --version 2>&1 | Out-String)
        if ($ver -match 'Python 3\.(1[0-9])') { $sysPy = $try; break }
    }
    if ($sysPy) {
        Write-Host 'Tao venv Xuong Video (runtime\xuong-venv)...'
        & $sysPy[0] @($sysPy | Select-Object -Skip 1) -m venv (Join-Path $Root 'runtime\xuong-venv')
        if ($LASTEXITCODE -eq 0) {
            & $xvPy -m pip install --no-compile --disable-pip-version-check -r (Join-Path $Root 'xuong-video\requirements.txt')
            if ($LASTEXITCODE -ne 0) { Write-Warning 'pip install cho Xuong Video loi - dich vu xuong-video co the khong chay.' }
        }
    }
    else { Write-Warning 'Khong thay Python 3.11 - bo qua Xuong Video (cai Python roi chay lai setup.ps1).' }
}
if (Test-Path $xvPy) {
    $env:XUONG_DATA = $dataDir
    & $xvPy -c ("import sys; sys.path.insert(0, r'" + (Join-Path $Root 'xuong-video\engine') + "'); import duong_dan; duong_dan.khoi_tao()")
}
$rem = Join-Path $Root 'xuong-video\remotion'
if ((Test-Path (Join-Path $rem 'package-lock.json')) -and -not (Test-Path (Join-Path $rem 'node_modules')) -and (Get-Command npm -ErrorAction SilentlyContinue)) {
    Push-Location $rem; try { npm ci --no-audit --no-fund } finally { Pop-Location }
}

# --- .env ---
# Khoa ket noi hub: doc tu <hub>\config.json (trypost.khoa), khong in ra man hinh.
function Get-HubKey([string]$hub) {
    $cfg = Join-Path $hub 'config.json'
    if (-not (Test-Path $cfg)) { return '' }
    try { return [string]((Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).trypost.khoa) } catch { return '' }
}
if (-not (Test-Path $envPath)) {
    $lines = [IO.File]::ReadAllLines((Join-Path $PSScriptRoot 'env.template'), [Text.Encoding]::UTF8)
    $set = @{}
    $set['FORK_CHROME_LAUNCHER_SECRET'] = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
    $set['FORK_HUB_PATH'] = '"' + $dataDir + '"'
    $set['XUONG_DATA'] = '"' + $dataDir + '"'
    $hubKey = Get-HubKey $dataDir
    if ($hubKey) { $set['FORK_HUB_KEY'] = $hubKey }
    $seen = @{}
    $out = foreach ($l in $lines) {
        if ($l -match '^([A-Z0-9_]+)=') { $k = $Matches[1]; $seen[$k] = $true; if ($set.ContainsKey($k)) { "$k=$($set[$k])" } else { $l } } else { $l }
    }
    $out = @($out) + @($set.Keys | Where-Object { -not $seen.ContainsKey($_) } | ForEach-Object { "$_=$($set[$_])" })
    [IO.File]::WriteAllLines($envPath, $out, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Da tao .env'
}
elseif ((Get-Content $envPath -Raw) -notmatch '(?m)^FORK_HUB_KEY=\S') {
    # .env da co nhung chua co khoa hub: lay tu hub (khong ghi de khoa da co).
    $hubKey = Get-HubKey $dataDir
    if ($hubKey) {
        $envLines = [IO.File]::ReadAllLines($envPath, [Text.Encoding]::UTF8)
        $has = $envLines | Where-Object { $_ -match '^FORK_HUB_KEY=' }
        $envLines = if ($has) { $envLines | ForEach-Object { if ($_ -match '^FORK_HUB_KEY=') { "FORK_HUB_KEY=$hubKey" } else { $_ } } } else { @($envLines) + "FORK_HUB_KEY=$hubKey" }
        [IO.File]::WriteAllLines($envPath, $envLines, (New-Object Text.UTF8Encoding($false)))
        Write-Host 'Da lay khoa hub tu config.json cua hub'
    }
}

if (-not (Get-EnvVal 'XUONG_DATA')) {      # .env cu chua co XUONG_DATA: dung cung thu muc voi FORK_HUB_PATH
    $envLines = [IO.File]::ReadAllLines($envPath, [Text.Encoding]::UTF8)
    $envLines = @($envLines | Where-Object { $_ -notmatch '^XUONG_DATA=' }) + ('XUONG_DATA="' + $dataDir + '"')
    [IO.File]::WriteAllLines($envPath, $envLines, (New-Object Text.UTF8Encoding($false)))
}

# Goi phat hanh da co san vendor + public/build (khong co ma nguon giao dien): khong can composer/npm cho giao dien.
$isRelease = (Test-Path (Join-Path $Root 'vendor/autoload.php')) -and (Test-Path (Join-Path $Root 'public/build/manifest.json')) -and -not (Test-Path (Join-Path $Root 'resources/js'))
if ($isRelease) { $SkipBuild = $true }

# .env cu thieu UPDATE_REPO: them kho mac dinh (nut Cap nhat trong app)
if ((Get-Content $envPath -Raw) -notmatch '(?m)^UPDATE_REPO=\S') {
    Add-Content $envPath "`r`nUPDATE_REPO=kidlost1412/tiktok-auto-kid" -Encoding UTF8
}

# --- Composer install ---
$env:COMPOSER_HOME = Join-Path $rt 'composer-home'
if (-not $isRelease) {
    & $php (Join-Path $rt 'composer.phar') install --no-interaction --prefer-dist --no-progress --ignore-platform-req=ext-pcntl --ignore-platform-req=ext-posix
    if ($LASTEXITCODE -ne 0) { throw 'composer install loi' }
}
if (-not ((Get-Content $envPath -Raw) -match 'APP_KEY=base64:')) { & $php artisan key:generate --force }

# --- Giao dien (can Node, chi luc cai) ---
if (-not $SkipBuild) {

    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm ci loi' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'npm run build loi' }
}

# --- Caddy: thu muc media hub (<FORK_HUB_PATH>/ra) cho /media/ra, doc tu .env ---
$hubEnv = ((Get-Content $envPath -Encoding UTF8 | Where-Object { $_ -match '^FORK_HUB_PATH=' } | Select-Object -First 1) -replace '^FORK_HUB_PATH=', '').Trim().Trim('"')
if (-not $hubEnv) { $hubEnv = $dataDir }
$hubRa = ($hubEnv.Replace($bs, '/').TrimEnd('/') + '/ra').Replace('"', '')
[IO.File]::WriteAllText((Join-Path $rt 'hub-root.caddy'), "(hub_ra_root) {`n`troot * `"$hubRa`"`n}`n", (New-Object Text.UTF8Encoding($false)))

# --- services.json + CSDL ---
Copy-Item (Join-Path $PSScriptRoot 'services.json') (Join-Path $rt 'services.json') -Force
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'bootstrap.ps1')
if ($LASTEXITCODE -ne 0) { throw 'bootstrap CSDL loi' }
# --- Loi tat TikTok Auto Kid tren Desktop (thay loi tat TikTok Auto cu neu co) ---
try {
    $exe = Join-Path $Root 'TikTokAuto.exe'
    $desk = [Environment]::GetFolderPath('Desktop')
    $oldLnk = Join-Path $desk 'TikTok Auto.lnk'
    $newLnk = Join-Path $desk 'TikTok Auto Kid.lnk'
    if (Test-Path $oldLnk) { Rename-Item $oldLnk $newLnk -ErrorAction SilentlyContinue }
    if ((Test-Path $exe) -and -not (Test-Path $newLnk)) {
        $sh = New-Object -ComObject WScript.Shell
        $lk = $sh.CreateShortcut($newLnk); $lk.TargetPath = $exe; $lk.WorkingDirectory = $Root; $lk.Description = 'TikTok Auto Kid'; $lk.Save()
    }
}
catch { Write-Warning "Khong tao duoc loi tat: $_" }
Write-Host 'Xong. Chay: scripts\native\start.ps1 (hoac TikTokAuto.exe), mo http://localhost:8010'
