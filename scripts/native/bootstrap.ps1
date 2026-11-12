<#
 Khoi tao / cap nhat CSDL (idempotent, chay moi lan khoi dong):
 initdb neu chua co, bat Postgres tam, tao database, migrate, tao chu app, tat Postgres.
 Neu Postgres da chay san (cong 5433) thi dung luon va khong tat.
#>
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rt = Join-Path $Root 'runtime'
$pgBin = Join-Path $rt 'pgsql\bin'
$data = Join-Path $rt 'data\pg'
$php = Join-Path $rt 'php\php.exe'
$port = 5433
$db = 'tiktok_auto'
$logs = Join-Path $rt 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
Set-Location $Root

function Test-Port([int]$p) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $p); $c.Close(); return $true } catch { return $false }
}
function Run([string]$exe, [string[]]$a) {
    & $exe @a
    if ($LASTEXITCODE -ne 0) { throw "Lenh that bai ($LASTEXITCODE): $exe $($a -join ' ')" }
}

# Caddy: snippet hub_ra_root (<FORK_HUB_PATH>/ra cho /media/ra), sinh lai tu .env moi lan khoi dong
# de doi thu muc du lieu co hieu luc (cung logic voi setup.ps1). Loi o day khong chan khoi dong.
try {
    $envPath = Join-Path $Root '.env'
    $envLines = if (Test-Path $envPath) { [IO.File]::ReadAllLines($envPath, [Text.Encoding]::UTF8) } else { @() }
    $envVal = { param($k) (($envLines | Where-Object { $_ -match "^$k=" } | Select-Object -First 1) -replace "^$k=", '').Trim().Trim('"') }
    $hubEnv = & $envVal 'FORK_HUB_PATH'
    if (-not $hubEnv) { $hubEnv = & $envVal 'XUONG_DATA' }
    if (-not $hubEnv) { $hubEnv = Join-Path $Root 'du-lieu\xuong-video' }
    $hubRa = ($hubEnv.Replace('\', '/').TrimEnd('/') + '/ra').Replace('"', '')
    $snippet = "(hub_ra_root) {`n`troot * `"$hubRa`"`n}`n"
    $snipPath = Join-Path $rt 'hub-root.caddy'
    $old = if (Test-Path $snipPath) { [IO.File]::ReadAllText($snipPath) } else { $null }
    if ($old -cne $snippet) {
        [IO.File]::WriteAllText($snipPath, $snippet, (New-Object Text.UTF8Encoding($false)))
        Write-Host '[bootstrap] cap nhat runtime/hub-root.caddy'
    }
} catch {
    Write-Host "[bootstrap] khong ghi duoc runtime/hub-root.caddy: $($_.Exception.Message)"
}

if (-not (Test-Path (Join-Path $data 'PG_VERSION'))) {
    Write-Host '[bootstrap] initdb'
    New-Item -ItemType Directory -Force (Split-Path $data) | Out-Null
    Run (Join-Path $pgBin 'initdb.exe') @('-D', $data, '-U', 'postgres', '-A', 'trust', '--encoding=UTF8', '--locale=C')
}

$started = $false
if (-not (Test-Port $port)) {
    Write-Host '[bootstrap] bat Postgres tam'
    Run (Join-Path $pgBin 'pg_ctl.exe') @('start', '-w', '-t', '60', '-D', $data, '-l', (Join-Path $logs 'postgres-bootstrap.log'), '-o', "-p $port -c listen_addresses=127.0.0.1")
    $started = $true
}

try {
    $psql = Join-Path $pgBin 'psql.exe'
    $exists = & $psql -h 127.0.0.1 -p $port -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'"
    if ("$exists".Trim() -ne '1') {
        Write-Host "[bootstrap] tao database $db"
        Run (Join-Path $pgBin 'createdb.exe') @('-h', '127.0.0.1', '-p', "$port", '-U', 'postgres', $db)
    }
    Write-Host '[bootstrap] migrate'
    Run $php @('artisan', 'migrate', '--force')
    # Chu app + workspace noi bo cho che do mot nguoi dung (idempotent; middleware cung tu tao neu thieu)
    Run $php @('artisan', 'fork:single-user')
} finally {
    if ($started) {
        Write-Host '[bootstrap] tat Postgres tam'
        & (Join-Path $pgBin 'pg_ctl.exe') stop -D $data -m fast -w | Out-Null
    }
}
Write-Host '[bootstrap] xong'
