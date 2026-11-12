<#
 Chay test Pest tren Windows native, dung DB rieng tiktok_auto_test (Postgres 5433 phai dang chay).
 Vi du: test.ps1 tests/Feature/Fork   hoac   test.ps1 --filter=Kho
#>
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PestArgs)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rt = Join-Path $Root 'runtime'
Set-Location $Root
$pgBin = Join-Path $rt 'pgsql\bin'
$started = $false
function Test-Port([int]$p) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $p); $c.Close(); $true } catch { $false } }
if (-not (Test-Port 5433)) {
    & (Join-Path $pgBin 'pg_ctl.exe') start -w -t 60 -D (Join-Path $rt 'data\pg') -l (Join-Path $rt 'logs\postgres-test.log') -o '-p 5433 -c listen_addresses=127.0.0.1'
    $started = $true
}
try {
    $e = & (Join-Path $pgBin 'psql.exe') -h 127.0.0.1 -p 5433 -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='tiktok_auto_test'"
    if ("$e".Trim() -ne '1') { & (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p 5433 -U postgres tiktok_auto_test }
    $env:DB_HOST = '127.0.0.1'; $env:DB_PORT = '5433'; $env:DB_USERNAME = 'postgres'; $env:DB_PASSWORD = ''
    $env:DB_DATABASE = 'tiktok_auto_test'
    & (Join-Path $rt 'php\php.exe') artisan test @PestArgs
    exit $LASTEXITCODE
} finally {
    if ($started) { & (Join-Path $pgBin 'pg_ctl.exe') stop -D (Join-Path $rt 'data\pg') -m fast -w | Out-Null }
}
