<# Tat cac dich vu do start.ps1 khoi dong (nguoc thu tu), postgres tat bang pg_ctl stop. #>
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rt = Join-Path $Root 'runtime'
$pidFile = Join-Path $rt 'pids.json'
if (-not (Test-Path $pidFile)) { Write-Host 'Khong co gi dang chay (khong thay pids.json).'; exit 0 }
$list = @((Get-Content $pidFile -Raw | ConvertFrom-Json).pids)
[array]::Reverse($list)
foreach ($p in $list) {
    if (-not (Get-Process -Id $p.pid -ErrorAction SilentlyContinue)) { continue }
    Write-Host "[stop] $($p.name)"
    if ($p.name -eq 'postgres') {
        & (Join-Path $rt 'pgsql\bin\pg_ctl.exe') stop -D (Join-Path $rt 'data\pg') -m fast -w | Out-Null
        Start-Sleep -Seconds 1
    }
    if (Get-Process -Id $p.pid -ErrorAction SilentlyContinue) { & taskkill.exe /PID $p.pid /T /F | Out-Null }
}
Remove-Item $pidFile -Force
Write-Host 'Da tat.'
