<#
 Chay PostgreSQL qua pg_ctl (pg_ctl tu ha quyen, nen chay duoc ca khi launcher dang o quyen Administrator,
 con postgres.exe chay thang thi bi tu choi). Script ben o lai cho den khi postmaster tat,
 de launcher giam sat nhu mot tien trinh binh thuong. Tat bang: pg_ctl stop -m fast (xem services.json).
#>
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rt = Join-Path $Root 'runtime'
$data = Join-Path $rt 'data\pg'
$pgCtl = Join-Path $rt 'pgsql\bin\pg_ctl.exe'
$log = Join-Path $rt 'logs\postgres-server.log'
New-Item -ItemType Directory -Force (Join-Path $rt 'logs') | Out-Null

& $pgCtl start -w -t 60 -D $data -l $log -o '-p 5433 -c listen_addresses=127.0.0.1 -c max_connections=100 -c shared_buffers=128MB -c log_timezone=UTC -c log_checkpoints=off'
if ($LASTEXITCODE -ne 0) { Write-Host "pg_ctl start loi ($LASTEXITCODE), xem $log"; exit 1 }
Write-Host 'PostgreSQL da chay (cong 5433)'

$pidFile = Join-Path $data 'postmaster.pid'
while ($true) {
    Start-Sleep -Seconds 2
    if (-not (Test-Path $pidFile)) { break }
    $first = Get-Content $pidFile -TotalCount 1 -ErrorAction SilentlyContinue
    if (-not $first -or -not (Get-Process -Id ([int]$first) -ErrorAction SilentlyContinue)) { break }
}
Write-Host 'PostgreSQL da dung'
exit 0
