<#
 Chay thu cong toan bo dich vu trong runtime\services.json (khong can TikTokAuto.exe).
 Dich vu chay an, log o runtime\logs\<ten>.log, PID ghi o runtime\pids.json. Dung stop.ps1 de tat.
#>
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$rt = Join-Path $Root 'runtime'
$cfgPath = Join-Path $rt 'services.json'
$pidFile = Join-Path $rt 'pids.json'
$logs = Join-Path $rt 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
Set-Location $Root

if (Test-Path $pidFile) {
    $old = Get-Content $pidFile -Raw | ConvertFrom-Json
    $alive = @($old.pids | Where-Object { Get-Process -Id $_.pid -ErrorAction SilentlyContinue })
    if ($alive.Count -gt 0) { Write-Host 'Dang chay roi. Chay stop.ps1 truoc.'; exit 1 }
}

$cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Expand([string]$s) { $s.Replace('${ROOT}', $Root) }
function Resolve-Exe([string]$cmd) {
    $cmd = Expand $cmd
    if ($cmd -match '[\/]') { if ([IO.Path]::IsPathRooted($cmd)) { return $cmd } else { return (Join-Path $Root $cmd) } }
    return $cmd
}
function Quote([string]$a) { if ($a -match '[\s"]') { '"' + $a.Replace('"', '\"') + '"' } else { $a } }
function Test-Tcp([int]$p) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $p); $c.Close(); $true } catch { $false } }
function Wait-Health($h) {
    if ($null -eq $h) { Start-Sleep -Seconds 1; return $true }
    $limit = if ($h.timeout_sec) { [int]$h.timeout_sec } else { 90 }
    $end = (Get-Date).AddSeconds($limit)
    while ((Get-Date) -lt $end) {
        if ($h.type -eq 'tcp') { if (Test-Tcp ([int]$h.port)) { return $true } }
        else { try { $r = Invoke-WebRequest -UseBasicParsing -Uri $h.url -TimeoutSec 5; if ($r.StatusCode -lt 500) { return $true } } catch { if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -lt 500) { return $true } } }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

foreach ($s in $cfg.first_run) {
    if ($s.only_if_missing -and (Test-Path (Join-Path $Root $s.only_if_missing))) { continue }
    Write-Host "[first_run] $($s.name)"
    $a = @($s.args | ForEach-Object { Expand "$_" })
    & (Resolve-Exe $s.cmd) @a
    if ($LASTEXITCODE -ne 0) { throw "first_run $($s.name) that bai ($LASTEXITCODE)" }
}

$pids = @()
foreach ($s in $cfg.services) {
    Write-Host "[start] $($s.name)"
    $saved = @{}
    if ($s.env) { foreach ($p in $s.env.PSObject.Properties) { $saved[$p.Name] = [Environment]::GetEnvironmentVariable($p.Name); [Environment]::SetEnvironmentVariable($p.Name, (Expand "$($p.Value)")) } }
    $cwd = if ($s.cwd) { Join-Path $Root (Expand $s.cwd) } else { $Root }
    $argStr = (@($s.args | ForEach-Object { Quote (Expand "$_") })) -join ' '
    $proc = Start-Process -FilePath (Resolve-Exe $s.cmd) -ArgumentList $argStr -WorkingDirectory $cwd -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logs "$($s.name).log") -RedirectStandardError (Join-Path $logs "$($s.name).err.log")
    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
    $pids += @{ name = $s.name; pid = $proc.Id }
    @{ pids = $pids } | ConvertTo-Json -Depth 4 | Set-Content $pidFile -Encoding UTF8
    if (-not (Wait-Health $s.health)) { Write-Warning "$($s.name) chua san sang (xem runtime\logs\$($s.name).err.log)" }
}
Write-Host "Da chay. Mo $($cfg.app_url)"
