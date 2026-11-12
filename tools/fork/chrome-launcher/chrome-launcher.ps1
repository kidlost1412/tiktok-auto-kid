<#
.SYNOPSIS
  Trợ lý mở Chrome cho app TikTok Auto Kid (Windows PowerShell 5.1).

.DESCRIPTION
  Cứ 30 giây hỏi app xem có bài nào đang chờ mà Chrome (profile) tương ứng chưa mở.
  Nếu có thì mở đúng profile đó ở chế độ không hiện cửa sổ để tiện ích TikTok Auto Kid chạy nền.
  Mỗi 5 phút báo danh sách profile Chrome trên máy cho trang "Kết nối Chrome".
  Cấu hình lấy APP_URL và FORK_CHROME_LAUNCHER_SECRET từ .env ở thư mục gốc dự án (setup.ps1 tạo sẵn).
  Máy chủ có thể ghi đè bằng -Server hoặc biến môi trường FORK_LAUNCHER_SERVER.

.PARAMETER DryRun
  Chỉ quét và in ra việc sẽ làm; không mở Chrome, không gửi POST nào lên máy chủ.

.PARAMETER Once
  Chạy đúng một vòng rồi thoát (dùng để thử).
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Once,
    [string]$Server
)

$ErrorActionPreference = 'Stop'
$script:Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:LogPath = Join-Path $script:Dir 'chrome-launcher.log'
$script:PollSeconds = 30
$script:ProfilesEverySeconds = 300
$script:LaunchEverySeconds = 180
$script:ProfileDirRe = '^(Default|Profile \d+|[A-Za-z0-9 _.\-]{1,64})$'
$script:LastLaunch = @{}

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.ServicePointManager]::SecurityProtocol } catch { }

function Write-Log {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    try {
        if ((Test-Path -LiteralPath $script:LogPath) -and ((Get-Item -LiteralPath $script:LogPath).Length -gt 512KB)) {
            Move-Item -LiteralPath $script:LogPath -Destination ($script:LogPath + '.1') -Force
        }
        [IO.File]::AppendAllText($script:LogPath, $line + "`r`n", (New-Object Text.UTF8Encoding($false)))
    } catch { }
    if ($DryRun -or $Once) { Write-Host $line }
}

function Get-ExtensionIdFromManifest {
    param([string]$ManifestPath)
    if (-not (Test-Path -LiteralPath $ManifestPath)) { return $null }
    $manifest = [IO.File]::ReadAllText($ManifestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
    if (-not $manifest.key) { return $null }
    $der = [Convert]::FromBase64String([string]$manifest.key)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash($der) } finally { $sha.Dispose() }
    $hex = (($hash | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0, 32)
    $sb = New-Object Text.StringBuilder
    foreach ($ch in $hex.ToCharArray()) {
        [void]$sb.Append([char]([int][char]'a' + [Convert]::ToInt32([string]$ch, 16)))
    }
    return $sb.ToString()
}

function Read-DotEnv {
    # Đọc vài khoá từ .env ở thư mục gốc dự án (không cần PHP).
    $path = Join-Path $script:Dir '..\..\..\.env'
    $map = @{}
    if (Test-Path -LiteralPath $path) {
        foreach ($line in [IO.File]::ReadAllLines($path, [Text.Encoding]::UTF8)) {
            if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$') {
                $map[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
            }
        }
    }
    return $map
}

function Read-LauncherConfig {
    $dotenv = Read-DotEnv
    $server = $Server
    if (-not $server) { $server = $env:FORK_LAUNCHER_SERVER }
    if (-not $server -and $dotenv['APP_URL']) { $server = $dotenv['APP_URL'] }
    if (-not $server) { $server = 'http://localhost:8010' }
    $server = $server.TrimEnd('/')
    $secret = [string]$dotenv['FORK_CHROME_LAUNCHER_SECRET']
    if (-not $secret) { throw 'Chưa có FORK_CHROME_LAUNCHER_SECRET trong .env (chạy lại scripts\native\setup.ps1).' }
    $manifest = Join-Path (Get-BundleExtensionDir) 'manifest.json'
    try { $extId = [string](Get-ExtensionIdFromManifest -ManifestPath $manifest) } catch { $extId = '' }
    $chromePath = ''
    $edgePath = ''
    return @{ Server = $server; Secret = $secret; ExtensionId = $extId; ChromePath = $chromePath; EdgePath = $edgePath }
}

function Get-BundleExtensionDir {
    # Thư mục tiện ích TikTok Auto Kid của chính bản cài này (ID của tiện ích unpacked phụ thuộc đường dẫn này).
    return [IO.Path]::GetFullPath((Join-Path $script:Dir '..\..\..\extension\autotok'))
}

function Get-Browsers {
    return @(
        @{ id = 'chrome'; label = 'Chrome'; exeName = 'chrome.exe'; rel = 'Google\Chrome\Application\chrome.exe'; userData = (Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data') },
        @{ id = 'edge'; label = 'Edge'; exeName = 'msedge.exe'; rel = 'Microsoft\Edge\Application\msedge.exe'; userData = (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data') }
    )
}

function Find-BrowserExe {
    param([string]$Browser, [string]$Override)
    $b = Get-Browsers | Where-Object { $_.id -eq $Browser } | Select-Object -First 1
    if (-not $b) { return $null }
    if ($Override -and (Test-Path -LiteralPath $Override -PathType Leaf) -and ((Split-Path -Leaf $Override) -ieq $b.exeName)) { return $Override }
    foreach ($name in 'ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA') {
        $root = [Environment]::GetEnvironmentVariable($name)
        if ($root) {
            $candidate = Join-Path $root $b.rel
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        }
    }
    return $null
}

function Find-ChromeExe {
    param([string]$Override)
    return Find-BrowserExe -Browser 'chrome' -Override $Override
}

function ConvertTo-NormPath {
    param([string]$Path)
    if (-not $Path) { return '' }
    try { $full = [IO.Path]::GetFullPath(($Path -replace '/', '\')) } catch { $full = ($Path -replace '/', '\') }
    return $full.TrimEnd('\').ToLowerInvariant()
}

function Get-ExtensionEntryKind {
    # 'bundle' nếu mục tiện ích trỏ đúng thư mục extension\autotok của bản cài này,
    # 'id' nếu trùng ID đã biết, 'name' nếu là tiện ích tên TikTok Auto Kid ở nơi khác (vd. bản cài cũ), $null nếu không phải.
    param([string]$Id, $Entry, [string]$BundleDir, [string]$KnownId)
    if (-not ($Entry -is [System.Collections.IDictionary])) { return $null }
    # Chrome để lại mục rỗng sau khi gỡ tiện ích: coi như chưa cài.
    if ($Entry.Count -eq 0 -or (-not $Entry['path'] -and -not $Entry['manifest'])) { return $null }
    $path = [string]$Entry['path']
    if ($path -and ((ConvertTo-NormPath $path) -eq (ConvertTo-NormPath $BundleDir))) { return 'bundle' }
    if ($KnownId -and $Id -ceq $KnownId) { return 'id' }
    $name = ''
    $m = $Entry['manifest']
    if ($m -is [System.Collections.IDictionary] -and $m['name']) { $name = [string]$m['name'] }
    if (-not $name -and $path) {
        $mf = Join-Path ($path -replace '/', '\') 'manifest.json'
        try { if (Test-Path -LiteralPath $mf -PathType Leaf) { $name = [string](([IO.File]::ReadAllText($mf, [Text.Encoding]::UTF8) | ConvertFrom-Json).name) } } catch { }
    }
    if ($name -match '^(AutoTok|TikTok Auto Kid)') { return 'name' }
    return $null
}

function Read-JsonFile {
    param([string]$Path)
    # Preferences có thể đang bị Chrome giữ: mở chia sẻ đọc.
    # JavaScriptSerializer phân biệt hoa thường (ConvertFrom-Json của PS 5.1 thì không).
    $fs = New-Object IO.FileStream($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)
        $text = $sr.ReadToEnd()
    } finally { $fs.Dispose() }
    Add-Type -AssemblyName System.Web.Extensions
    $ser = New-Object Web.Script.Serialization.JavaScriptSerializer
    $ser.MaxJsonLength = [int]::MaxValue
    $ser.RecursionLimit = 200
    return $ser.DeserializeObject($text)
}

function Get-ChromeProfiles {
    # Quét profile của cả Chrome và Edge. Tiện ích TikTok Auto Kid được nhận ra bằng đường dẫn thư mục tiện ích
    # (hoặc tên "TikTok Auto Kid") trong extensions.settings của Preferences / Secure Preferences,
    # không phụ thuộc ID cố định.
    param([string]$ExtensionId)
    $bundleDir = Get-BundleExtensionDir
    $result = @()
    foreach ($br in Get-Browsers) {
        $userData = $br.userData
        if (-not (Test-Path -LiteralPath $userData)) { continue }
        foreach ($d in Get-ChildItem -LiteralPath $userData -Directory -ErrorAction SilentlyContinue) {
            if ($d.Name -cnotmatch '^(Default|Profile \d+)$') { continue }
            $prefs = Join-Path $d.FullName 'Preferences'
            if (-not (Test-Path -LiteralPath $prefs)) { continue }
            $name = $d.Name
            $has = $false
            $inBundle = $false
            $foundId = ''
            $sources = @()
            try {
                $p = Read-JsonFile -Path $prefs
                $sources += , $p
                $prof = $p['profile']
                if ($prof -is [System.Collections.IDictionary] -and $prof['name']) { $name = [string]$prof['name'] }
            } catch {
                Write-Log ("Không đọc được Preferences của {0}/{1}: {2}" -f $br.label, $d.Name, $_.Exception.Message)
            }
            $secure = Join-Path $d.FullName 'Secure Preferences'
            if (Test-Path -LiteralPath $secure) {
                try { $sources += , (Read-JsonFile -Path $secure) }
                catch { Write-Log ("Không đọc được Secure Preferences của {0}/{1}: {2}" -f $br.label, $d.Name, $_.Exception.Message) }
            }
            foreach ($src in $sources) {
                $ext = $src['extensions']
                if (-not ($ext -is [System.Collections.IDictionary])) { continue }
                $settings = $ext['settings']
                if (-not ($settings -is [System.Collections.IDictionary])) { continue }
                foreach ($id in @($settings.Keys)) {
                    $kind = Get-ExtensionEntryKind -Id ([string]$id) -Entry $settings[$id] -BundleDir $bundleDir -KnownId $ExtensionId
                    if (-not $kind) { continue }
                    $has = $true
                    if ($kind -eq 'bundle') { $inBundle = $true; $foundId = [string]$id }
                    elseif (-not $foundId) { $foundId = [string]$id }
                }
            }
            if (-not $has -and $ExtensionId -and (Test-Path -LiteralPath (Join-Path $d.FullName ('Extensions\' + $ExtensionId)))) { $has = $true; $foundId = $ExtensionId }
            $result += @{ browser = $br.id; dir = $d.Name; name = $name; has_extension = $has; bundle_extension = $inBundle; extension_id = $foundId }
        }
    }
    return $result
}

function ConvertTo-JsonText {
    param($Value)
    Add-Type -AssemblyName System.Web.Extensions
    $ser = New-Object Web.Script.Serialization.JavaScriptSerializer
    return $ser.Serialize($Value)
}

function Invoke-Api {
    param([string]$Method, [string]$Path, $Body, [hashtable]$Cfg)
    $params = @{
        Uri             = $Cfg.Server + $Path
        Method          = $Method
        Headers         = @{ 'X-Fork-Launcher-Secret' = $Cfg.Secret; 'Accept' = 'application/json' }
        TimeoutSec      = 20
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $params.ContentType = 'application/json; charset=utf-8'
        $params.Body = [Text.Encoding]::UTF8.GetBytes((ConvertTo-JsonText $Body))
    }
    return Invoke-RestMethod @params
}

function Start-ChromeProfile {
    # Dùng cho cả Chrome lẫn Edge (cùng tham số dòng lệnh).
    param([string]$Exe, [string]$ProfileDir)
    # Không hiện cửa sổ; tiện ích có quyền "background" vẫn chạy.
    # Tiến trình tách rời, script không giữ vòng đời của Chrome.
    Start-Process -FilePath $Exe -ArgumentList ('--profile-directory="{0}" --no-startup-window' -f $ProfileDir) | Out-Null
}

function Invoke-Cycle {
    param([hashtable]$Cfg, [bool]$SendProfiles)
    if ($SendProfiles) {
        $profiles = @(Get-ChromeProfiles -ExtensionId $Cfg.ExtensionId)
        Write-Log ("Quét thấy {0} profile (Chrome + Edge); tiện ích ở {1}." -f $profiles.Count, (Get-BundleExtensionDir))
        foreach ($p in $profiles) { Write-Log ("  {0} | {1} | {2} | co_tien_ich={3} | dung_thu_muc_nay={4}" -f $p.browser, $p.dir, $p.name, $p.has_extension, $p.bundle_extension) }
        if (-not $DryRun) {
            try { [void](Invoke-Api -Method POST -Path '/api/fork/chrome/profiles' -Body @{ profiles = $profiles } -Cfg $Cfg) }
            catch { Write-Log ("Gửi danh sách profile lỗi: {0}" -f $_.Exception.Message) }
        }
    }

    try { $resp = Invoke-Api -Method GET -Path '/api/fork/chrome/launch-requests' -Body $null -Cfg $Cfg }
    catch { Write-Log ("Hỏi launch-requests lỗi: {0}" -f $_.Exception.Message); return }

    foreach ($r in @($resp.requests)) {
        if ($null -eq $r) { continue }
        $dir = [string]$r.profile_dir
        $clientId = [int]$r.client_id
        $jobId = [string]$r.job_id
        if ($dir -cnotmatch $script:ProfileDirRe -or $dir.Trim(' ', '.') -ne $dir) {
            Write-Log ("Bỏ qua profile không hợp lệ: '{0}'" -f $dir)
            continue
        }
        $browser = [string]$r.browser
        if ($browser -ne 'edge') { $browser = 'chrome' }
        $key = $browser + '|' + $dir
        $last = $script:LastLaunch[$key]
        if ($last -and ((Get-Date) - $last).TotalSeconds -lt $script:LaunchEverySeconds) { continue }
        $override = $Cfg.ChromePath
        if ($browser -eq 'edge') { $override = $Cfg.EdgePath }
        $exe = Find-BrowserExe -Browser $browser -Override $override
        if (-not $exe) { Write-Log ("Không tìm thấy trình duyệt {0} trên máy." -f $browser); continue }
        if ($DryRun) {
            Write-Log ("[DryRun] Sẽ mở: `"{0}`" --profile-directory=`"{1}`" --no-startup-window (job {2}, client {3})" -f $exe, $dir, $jobId, $clientId)
            continue
        }
        try {
            Start-ChromeProfile -Exe $exe -ProfileDir $dir
            $script:LastLaunch[$key] = Get-Date
            Write-Log ("Đã mở {0} profile '{1}' cho job {2}." -f $browser, $dir, $jobId)
        } catch {
            Write-Log ("Mở Chrome lỗi: {0}" -f $_.Exception.Message)
            continue
        }
        try { [void](Invoke-Api -Method POST -Path '/api/fork/chrome/launched' -Body @{ client_id = $clientId; job_id = $jobId } -Cfg $Cfg) }
        catch { Write-Log ("Báo launched lỗi: {0}" -f $_.Exception.Message) }
    }
}

# ---- main ----
$mutex = $null
if (-not $DryRun -and -not $Once) {
    $created = $false
    $mutex = New-Object Threading.Mutex($true, ('Local\TikTokAutoChromeLauncher-' + [Math]::Abs($script:Dir.ToLowerInvariant().GetHashCode())), [ref]$created)
    if (-not $created) { Write-Log 'Đã có một trợ lý khác đang chạy, thoát.'; exit 0 }
}

try {
    $mode = if ($DryRun) { ' (dry-run)' } else { '' }
    Write-Log ('Trợ lý mở Chrome bắt đầu' + $mode + '.')
    $nextProfiles = Get-Date
    while ($true) {
        try {
            $cfg = Read-LauncherConfig
            $send = ((Get-Date) -ge $nextProfiles)
            if ($send) { $nextProfiles = (Get-Date).AddSeconds($script:ProfilesEverySeconds) }
            Invoke-Cycle -Cfg $cfg -SendProfiles $send
        } catch {
            Write-Log ("Lỗi vòng lặp: {0}" -f $_.Exception.Message)
            if ($Once -or $DryRun) { exit 1 }
        }
        if ($Once -or $DryRun) { break }
        Start-Sleep -Seconds $script:PollSeconds
    }
} finally {
    if ($mutex) { try { $mutex.ReleaseMutex() } catch { }; $mutex.Dispose() }
}
