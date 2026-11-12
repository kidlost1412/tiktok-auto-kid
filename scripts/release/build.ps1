<#
 Tao goi phat hanh dist/tiktok-auto-kid-<ver>.zip (+ .sha256) cho tinh nang Cap nhat cua TikTok Auto Kid.

 Noi dung goi = `git archive HEAD` (da bo tests, launcher, nguon JS) + vendor/ (composer --no-dev, tao trong thu muc tam)
 + public/build (npm run build) + TikTokAuto.exe + TikTokAuto.new.exe (build tu launcher\) + VERSION + release-manifest.txt.
 KHONG bao gio chua: .env, runtime/, noi dung storage/ (chi giu khung thu muc .gitignore), node_modules, du-lieu/, dist/.

 Cach chay (tu thu muc goc repo, sau khi commit moi thu va sua file VERSION):
     powershell -ExecutionPolicy Bypass -File scripts\release\build.ps1
     powershell -ExecutionPolicy Bypass -File scripts\release\build.ps1 -SkipNpm      # dung public\build san co
     powershell -ExecutionPolicy Bypass -File scripts\release\build.ps1 -SkipVendor   # chay thu nhanh (khong co vendor)
 Script tu build launcher (go build -> launcher\dist\TikTokAuto.exe, KHONG chay test: chay test rieng truoc khi phat hanh).
 Goi chua TikTokAuto.exe (cai moi) va TikTokAuto.new.exe (cap nhat: launcher tu thay o lan mo ke tiep).
 Ngoai goi zip, script con chep CAI-DAT.bat va cai-dat.ps1 vao dist\ de dinh kem Release (CAI-DAT.bat tai rieng se tu tai cai-dat.ps1 cua ban moi nhat).

 Dang len GitHub (repo cong khai trong .env: UPDATE_REPO=owner/tiktok-auto-kid):
     git tag v<ver> ; git push origin v<ver>
     gh release create v<ver> dist\tiktok-auto-kid-<ver>.zip dist\tiktok-auto-kid-<ver>.zip.sha256 `
         --repo owner/tiktok-auto-kid --title "TikTok Auto Kid <ver>" --notes-file ghi-chu.md
 (ten file asset phai dung dinh dang tiktok-auto-kid-<ver>.zip va .zip.sha256; tag dang v<ver>; phan notes hien tren trang Cap nhat.)
#>
param(
    [string]$Version = '',
    [switch]$SkipNpm,
    [switch]$SkipVendor,
    [switch]$SkipLauncher    # dung launcher\dist\TikTokAuto.exe san co, khong build lai
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
if (-not $Version) { $Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim() }
if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$') { throw "Phien ban khong hop le: $Version" }

$dist = Join-Path $Root 'dist'
$stage = Join-Path $dist ".stage-$Version"
$zipPath = Join-Path $dist "tiktok-auto-kid-$Version.zip"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null

function Native([string]$exe, [string[]]$a) {
    & $exe @a
    if ($LASTEXITCODE -ne 0) { throw "Lenh that bai ($LASTEXITCODE): $exe $($a -join ' ')" }
}

# 1. Ma nguon da commit
$dirty = git status --porcelain --untracked-files=no
if ($dirty) { Write-Warning 'Cay lam viec con thay doi chua commit: goi chi chua noi dung cua HEAD.' }
$tar = Join-Path $dist "src-$Version.tar"
Native git @('archive', '--format=tar', '-o', $tar, 'HEAD')
Native tar @('-xf', $tar, '-C', $stage)
Remove-Item $tar -Force

# 2. Bo nhung thu khong dua vao goi
foreach ($p in @('tests', 'launcher', 'resources/js', 'docs', '.github', 'scripts/release', 'dist', 'runtime', 'du-lieu', 'node_modules', 'vendor', 'public/build')) {
    $t = Join-Path $stage $p
    if (Test-Path $t) { Remove-Item $t -Recurse -Force }
}
Get-ChildItem $stage -Force -File | Where-Object { $_.Name -eq '.env' -or ($_.Name -like '.env.*' -and $_.Name -ne '.env.example') } | Remove-Item -Force
Get-ChildItem $stage -Recurse -Force -Directory | Where-Object { $_.Name -in 'node_modules', '__pycache__', '.venv' } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
# storage: chi giu khung thu muc (.gitignore)
$st = Join-Path $stage 'storage'
if (Test-Path $st) {
    Get-ChildItem $st -Recurse -Force -File | Where-Object { $_.Name -ne '.gitignore' } | Remove-Item -Force
}

# 3. vendor (--no-dev) tao trong ban sao tam
if (-not $SkipVendor) {
    $tmp = Join-Path $dist ".vendor-$Version"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    New-Item -ItemType Directory -Force $tmp | Out-Null
    Copy-Item (Join-Path $stage 'composer.json'), (Join-Path $stage 'composer.lock') $tmp
    foreach ($d in @('app', 'bootstrap', 'config', 'database', 'routes', 'resources', 'public')) {
        if (Test-Path (Join-Path $stage $d)) { Copy-Item (Join-Path $stage $d) (Join-Path $tmp $d) -Recurse }
    }
    Copy-Item (Join-Path $stage 'artisan') $tmp
    $php = Join-Path $Root 'runtime\php\php.exe'
    if (-not (Test-Path $php)) { $php = (Get-Command php).Source }
    $composer = Join-Path $Root 'runtime\composer.phar'
    Push-Location $tmp
    try {
        $env:COMPOSER_HOME = Join-Path $Root 'runtime\composer-home'
        Native $php @($composer, 'install', '--no-dev', '--optimize-autoloader', '--no-interaction', '--no-progress', '--prefer-dist', '--no-scripts')
    } finally { Pop-Location }
    Copy-Item (Join-Path $tmp 'vendor') (Join-Path $stage 'vendor') -Recurse
    Remove-Item $tmp -Recurse -Force
}

# 4. public/build
if (-not $SkipNpm) { Native npm.cmd @('run', 'build') }
$pb = Join-Path $Root 'public\build'
if (Test-Path $pb) { Copy-Item $pb (Join-Path $stage 'public\build') -Recurse } else { Write-Warning 'Khong co public/build' }

# 5. Launcher: build tu launcher\ (go build, khong cua so console). Goi chua:
#    - TikTokAuto.exe     : cho ban CAI MOI (CAI-DAT.bat)
#    - TikTokAuto.new.exe : cho ban CAP NHAT (launcher tu thay o lan mo ke tiep; TikTokAuto.exe duoc bao ve khi cap nhat)
if (-not $SkipLauncher) {
    $go = (Get-Command go -ErrorAction SilentlyContinue)
    $goExe = if ($go) { $go.Source } else { 'C:\Program Files\Go\bin\go.exe' }
    if (-not (Test-Path $goExe)) { throw 'Khong thay Go (can de build launcher). Cai Go hoac dung -SkipLauncher.' }
    New-Item -ItemType Directory -Force (Join-Path $Root 'launcher\dist') | Out-Null
    Push-Location (Join-Path $Root 'launcher')
    try { Native $goExe @('build', '-trimpath', '-ldflags', '-H=windowsgui -s -w', '-o', 'dist\TikTokAuto.exe', '.') } finally { Pop-Location }
}
$exe = Join-Path $Root 'launcher\dist\TikTokAuto.exe'
if (Test-Path $exe) {
    Copy-Item $exe (Join-Path $stage 'TikTokAuto.exe')
    Copy-Item $exe (Join-Path $stage 'TikTokAuto.new.exe')
} else { Write-Warning 'Khong co launcher\dist\TikTokAuto.exe: goi khong chua exe.' }

# 6. VERSION + manifest
[IO.File]::WriteAllText((Join-Path $stage 'VERSION'), "$Version`n")
$stageFull = (Resolve-Path $stage).Path.TrimEnd('\')
$files = @(Get-ChildItem $stage -Recurse -Force -File | ForEach-Object { $_.FullName.Substring($stageFull.Length + 1).Replace('\', '/') } | Where-Object { $_ -ne 'release-manifest.txt' } | Sort-Object)
[IO.File]::WriteAllText((Join-Path $stage 'release-manifest.txt'), (($files + 'release-manifest.txt') -join "`n") + "`n")
$files += 'release-manifest.txt'

# 7. Kiem tra an toan truoc khi nen
$bad = @($files | Where-Object { $_ -match '(^|/)\.env$' -or $_ -match '(^|/)\.env\.(?!example$)' -or $_ -match '^(runtime|du-lieu|dist|tests)/' -or $_ -match '(^|/)node_modules/' -or ($_ -match '^storage/' -and $_ -notmatch '/\.gitignore$') })
if ($bad.Count -gt 0) { throw "Goi chua file khong duoc phep: $($bad | Select-Object -First 5)" }

# 8. Nen (dung ZipArchive de ten entry luon la dau /)
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
$zip = [IO.Compression.ZipFile]::Open($zipPath, 'Create')
try {
    foreach ($rel in $files) {
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $stage ($rel.Replace('/', '\'))), $rel, [IO.Compression.CompressionLevel]::Optimal)
    }
} finally { $zip.Dispose() }
$hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllText("$zipPath.sha256", "$hash  tiktok-auto-kid-$Version.zip`n")
Remove-Item $stage -Recurse -Force
Copy-Item (Join-Path $Root 'CAI-DAT.bat') (Join-Path $dist 'CAI-DAT.bat') -Force
Copy-Item (Join-Path $Root 'scripts\install\cai-dat.ps1') (Join-Path $dist 'cai-dat.ps1') -Force

$mb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "Xong: $zipPath ($mb MB, $($files.Count) file)"
Write-Host "sha256: $hash"
Write-Host "Dang len: gh release create v$Version `"$zipPath`" `"$zipPath.sha256`" dist\CAI-DAT.bat dist\cai-dat.ps1 --repo kidlost1412/tiktok-auto-kid --title `"TikTok Auto Kid $Version`" --notes-file <ghi-chu.md>"
