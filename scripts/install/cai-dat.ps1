<#
.SYNOPSIS
  Trình cài đặt một chạm cho TikTok Auto Kid (Windows 10 64-bit bản 1809 trở lên, hoặc Windows 11).
.DESCRIPTION
  Chạy từ bất kỳ đâu:
    - Nếu chạy trong thư mục đã giải nén từ bản phát hành -> dùng chính thư mục đó.
    - Nếu không -> hỏi thư mục cài (mặc định %LOCALAPPDATA%\TikTok Auto Kid), tải bản phát hành mới nhất
      từ GitHub, kiểm SHA256, giải nén.
  Sau đó: cài thứ còn thiếu bằng winget (Python 3.11, Node.js LTS, ffmpeg, Claude Code CLI), chạy
  scripts\native\setup.ps1 (PHP/PostgreSQL/Caddy portable, .env, venv Python, Remotion, CSDL),
  tạo lối tắt Desktop + Start Menu (+ tùy chọn chạy cùng Windows), mở app.
  Chạy lại = sửa chữa (không đụng dữ liệu, không tải lại mã nguồn nếu đã có bản cài).
  Không cần quyền Administrator (winget tự xin nếu một gói bắt buộc).
  Nhật ký: <thư mục cài>\runtime\logs\cai-dat.log
.PARAMETER ThuMuc
  Thư mục cài (bỏ qua câu hỏi).
.PARAMETER ThuKhong
  Chạy thử: in mọi bước sẽ làm, KHÔNG thay đổi gì (không tải, không cài, không ghi file).
.PARAMETER KiemTra
  Chỉ kiểm tra sức khỏe cài đặt (phần mềm cần có, dịch vụ, cổng, hub, tiện ích Chrome). Không thay đổi gì.
.PARAMETER KhongHoi
  Không hỏi gì cả, dùng giá trị mặc định (dành cho chạy tự động).
.PARAMETER ChayCungWindows
  Tạo lối tắt trong Startup để app tự mở khi đăng nhập Windows (mặc định hỏi; -KhongHoi thì tắt).
.PARAMETER ThuMucDuLieu
  Thư mục dữ liệu của Xưởng Video (XUONG_DATA). Mặc định <thư mục cài>\du-lieu\xuong-video.
.PARAMETER TienDo
  Chế độ cho trình cài GUI: không hỏi gì (như -KhongHoi), in thêm dòng tiến độ ##TD / ##TD-CB / ##TD-LOI,
  không mở trình duyệt, không khởi động app. Ghi <thư mục cài>\runtime\install.json khi xong.
.PARAMETER BoQuaPhanMem
  Không cài Python/Node/ffmpeg/Claude bằng winget (tự cài tay).
.PARAMETER Repo
  Kho GitHub chứa bản phát hành (owner/repo).
#>
param(
    [string]$ThuMuc,
    [switch]$ThuKhong,
    [switch]$KiemTra,
    [switch]$KhongHoi,
    [switch]$ChayCungWindows,
    [string]$ThuMucDuLieu,
    [switch]$BoQuaPhanMem,
    [switch]$TienDo,
    [string]$Repo = 'kidlost1412/tiktok-auto-kid'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
try { $OutputEncoding = [Text.Encoding]::UTF8 } catch {}
if ($TienDo) { $KhongHoi = [switch]$true }

# -TienDo: in thêm các dòng máy đọc được (trình cài GUI phân tích):
#   ##TD <0-100>|<chặng>|<thông điệp>   tiến độ (chặng: tai-app, phan-mem, du-lieu, loi-tat, khoi-dong, xong)
#   ##TD-CB <thông điệp>                 cảnh báo
#   ##TD-LOI <thông điệp>                lỗi
$script:TdMax = 0
function TD([int]$pct, [string]$chang, [string]$msg) {
    if (-not $TienDo) { return }
    if ($pct -lt $script:TdMax) { $pct = $script:TdMax }
    if ($pct -gt 100) { $pct = 100 }
    $script:TdMax = $pct
    Write-Host ("##TD {0}|{1}|{2}" -f $pct, $chang, $msg)
}
trap {
    if ($TienDo) { Write-Host ("##TD-LOI Lỗi không mong đợi: " + ($_.Exception.Message -replace '[\r\n]+', ' ')) }
    break
}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$script:LogFile = $null
$script:LogBuffer = New-Object System.Collections.Generic.List[string]
$script:SoCanhBao = 0
$script:SoLoi = 0
$script:BuocSo = 0

# ---------------------------------------------------------------- tiện ích chung
function Ghi-Log([string]$msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    if ($script:LogFile -and -not $ThuKhong) {
        try {
            if ($script:LogBuffer.Count -gt 0) {
                [IO.File]::AppendAllText($script:LogFile, (($script:LogBuffer -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding($false)))
                $script:LogBuffer.Clear()
            }
            [IO.File]::AppendAllText($script:LogFile, $line + "`r`n", (New-Object Text.UTF8Encoding($false)))
        } catch {}
    } else { $script:LogBuffer.Add($line) }
}
function Noi([string]$msg, [string]$mau = 'Gray') { Write-Host $msg -ForegroundColor $mau; Ghi-Log $msg }
function Tieu-De([string]$msg) {
    $script:BuocSo++
    Write-Host ''
    Write-Host ("[{0}] {1}" -f $script:BuocSo, $msg) -ForegroundColor Cyan
    Ghi-Log ("== [{0}] {1}" -f $script:BuocSo, $msg)
}
function Ok([string]$msg) { Noi "  [OK] $msg" 'Green' }
function Canh-Bao([string]$msg) { $script:SoCanhBao++; Noi "  [!] $msg" 'Yellow'; if ($TienDo) { Write-Host "##TD-CB $msg" } }
function Loi([string]$msg) { $script:SoLoi++; Noi "  [LỖI] $msg" 'Red'; if ($TienDo) { Write-Host "##TD-LOI $msg" } }
function Thu-Khong([string]$msg) { Noi "  [THỬ KHÔNG] $msg" 'Magenta' }

function Hoi-CoKhong([string]$cauHoi, [bool]$macDinh) {
    if ($KhongHoi -or $ThuKhong) { return $macDinh }
    $hint = if ($macDinh) { 'C/k' } else { 'c/K' }
    $a = Read-Host ("{0} [{1}]" -f $cauHoi, $hint)
    if (-not $a) { return $macDinh }
    return ($a.Trim().ToLower() -in @('c', 'co', 'có', 'y', 'yes'))
}

function Cap-Nhat-Path {
    # Sau khi winget/npm cài xong, PATH của phiên này chưa có lối mới: nạp lại từ registry.
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $extra = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links'),
        (Join-Path $env:ProgramFiles 'nodejs'),
        (Join-Path $env:APPDATA 'npm')
    )
    if ($script:GocCai) {   # Node/ffmpeg tải trực tiếp (không có winget) nằm trong runtime\
        $extra += (Join-Path $script:GocCai 'runtime\node')
        $extra += (Join-Path $script:GocCai 'runtime\ffmpeg\bin')
    }
    $env:Path = (@($m, $u) + $extra | Where-Object { $_ }) -join ';'
}

function Co-Lenh([string]$ten) { return [bool](Get-Command $ten -ErrorAction SilentlyContinue) }

function Chay-Lay([string]$exe, [string[]]$a) {
    # Chạy lệnh, trả về chuỗi đầu ra (kể cả stderr); không ném lỗi.
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { return ((& $exe @a 2>&1 | Out-String).Trim()) } catch { return '' } finally { $ErrorActionPreference = $old }
}

function Tim-Python {
    # Trả về mảng lệnh (vd @('py','-3.11')) nếu có Python 3.10+ thật (không phải bản giả của Microsoft Store).
    foreach ($t in @(@('py', '-3.11'), @('python'))) {
        if (-not (Co-Lenh $t[0])) { continue }
        $v = Chay-Lay $t[0] (@($t | Select-Object -Skip 1) + '--version')
        if ($v -match 'Python 3\.(1[0-9])') { return $t }
    }
    return $null
}
function Tim-Node {
    if (-not (Co-Lenh 'node')) { return $null }
    $v = Chay-Lay 'node' @('--version')
    if ($v -match '^v(\d+)\.' -and [int]$Matches[1] -ge 18) { return $v }
    return $null
}
function Co-VCRedist {
    # PHP và PostgreSQL portable cần Microsoft Visual C++ 2015-2022 x64.
    try { return ((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction Stop).Installed -eq 1) } catch { return $false }
}
function Tim-Chrome {
    foreach ($p in @(
            (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
            (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
            (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'))) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}
function Tim-Antigravity {
    foreach ($p in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Antigravity\Antigravity.exe'),
            (Join-Path $env:ProgramFiles 'Antigravity\Antigravity.exe'))) {
        if (Test-Path $p) { return $p }
    }
    if (Co-Lenh 'antigravity') { return 'antigravity' }
    return $null
}

function Cong-Mo([int]$port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(600) -and $c.Connected
        $c.Close()
        return $ok
    } catch { return $false }
}
function Http-Ok([string]$url, [int]$giay = 5) {
    try { $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec $giay; return ($r.StatusCode -lt 500) }
    catch { if ($_.Exception.Response) { return ([int]$_.Exception.Response.StatusCode -lt 500) } return $false }
}

function Doc-Env([string]$root, [string]$khoa) {
    $f = Join-Path $root '.env'
    if (-not (Test-Path $f)) { return '' }
    $l = [IO.File]::ReadAllLines($f, [Text.Encoding]::UTF8) | Where-Object { $_ -match "^$khoa=" } | Select-Object -First 1
    if ($l) { return (($l -replace "^$khoa=", '').Trim().Trim('"')) }
    return ''
}

function La-ThuMucCai([string]$p) {
    return ($p -and (Test-Path (Join-Path $p 'artisan')) -and (Test-Path (Join-Path $p 'VERSION')))
}

# ---------------------------------------------------------------- xác định thư mục cài
$macDinhCai = Join-Path $env:LOCALAPPDATA 'TikTok Auto Kid'
$trongBanPhatHanh = $null
try {
    $cand = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if (La-ThuMucCai $cand) { $trongBanPhatHanh = $cand }
} catch {}

function Chon-ThuMuc {
    if ($ThuMuc) { return [IO.Path]::GetFullPath($ThuMuc) }
    if ($trongBanPhatHanh) { return $trongBanPhatHanh }
    if ($KiemTra) { return $macDinhCai }
    if ($KhongHoi -or $ThuKhong) { return $macDinhCai }
    Write-Host ''
    Write-Host "Thư mục cài đặt TikTok Auto Kid (gõ đường dẫn, vd D:\TikTok Auto Kid; Enter = mặc định)" -ForegroundColor White
    $a = Read-Host ("[{0}]" -f $macDinhCai)
    if ($a) { return [IO.Path]::GetFullPath($a.Trim().Trim('"')) }
    return $macDinhCai
}

# ================================================================ KIỂM TRA SỨC KHỎE
function Kiem-Tra-Suc-Khoe {
    $root = Chon-ThuMuc
    $script:GocCai = $root
    $kq = [ordered]@{ ok = 0; canhbao = 0; loi = 0 }
    function Dat([string]$mucDo, [string]$msg) {
        switch ($mucDo) {
            'ok' { $kq.ok++; Write-Host "  [OK]  $msg" -ForegroundColor Green }
            'cb' { $kq.canhbao++; Write-Host "  [!]   $msg" -ForegroundColor Yellow }
            'loi' { $kq.loi++; Write-Host "  [LỖI] $msg" -ForegroundColor Red }
        }
    }
    Cap-Nhat-Path
    Write-Host ''
    Write-Host "KIỂM TRA TikTok Auto Kid - thư mục: $root" -ForegroundColor Cyan
    Write-Host ''
    Write-Host '1. Hệ thống' -ForegroundColor Cyan
    $wv = [Environment]::OSVersion.Version
    $tenWin = ''
    try { $tenWin = (Get-CimInstance Win32_OperatingSystem).Caption } catch {}
    $moTa = "{0} (build {1}), {2}, PowerShell {3}" -f $tenWin, $wv.Build, $(if ([Environment]::Is64BitOperatingSystem) { '64-bit' } else { '32-bit' }), $PSVersionTable.PSVersion
    if ($wv.Major -lt 10 -or $wv.Build -lt 17763 -or -not [Environment]::Is64BitOperatingSystem) { Dat 'loi' "Windows không được hỗ trợ: $moTa. Cần Windows 10 64-bit bản 1809 (build 17763) trở lên hoặc Windows 11." }
    else { Dat 'ok' "Windows phát hiện: $moTa" }
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
        $totGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
        if ($freeGB -lt 1.5) { Dat 'cb' "RAM trống chỉ $freeGB / $totGB GB - dễ treo máy khi dựng video (đóng bớt ứng dụng, đặt pagefile tự động)." }
        else { Dat 'ok' "RAM trống $freeGB / $totGB GB" }
        $pf = @(Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue)
        if ($pf.Count -eq 0) { Dat 'cb' 'Chưa bật pagefile (bộ nhớ ảo): vào Cài đặt > Hệ thống > Giới thiệu > Cài đặt nâng cao > Hiệu suất > Nâng cao > Bộ nhớ ảo, chọn tự động.' }
        else { Dat 'ok' ("Pagefile: {0} MB đang dùng / {1} MB" -f $pf[0].CurrentUsage, $pf[0].AllocatedBaseSize) }
        $o = [IO.DriveInfo]::new((Split-Path $root -Qualifier))
        $freeDisk = [math]::Round($o.AvailableFreeSpace / 1GB, 1)
        if ($freeDisk -lt 10) { Dat 'cb' "Ổ $($o.Name) còn $freeDisk GB trống (nên >= 10 GB cho video)." } else { Dat 'ok' "Ổ $($o.Name) còn $freeDisk GB trống" }
    } catch { Dat 'cb' "Không đọc được thông tin hệ thống: $($_.Exception.Message)" }

    Write-Host ''
    Write-Host '2. Phần mềm cần có' -ForegroundColor Cyan
    if (Co-Lenh 'winget') { Dat 'ok' 'winget có sẵn' } else { Dat 'cb' 'Không có winget (cài "App Installer" từ Microsoft Store) - trình cài không tự cài được phần mềm.' }
    if (Co-VCRedist) { Dat 'ok' 'Visual C++ 2015-2022 x64 đã cài' } else { Dat 'loi' 'Thiếu Visual C++ Redistributable 2015-2022 x64 (PHP/PostgreSQL cần). Cài: winget install -e --id Microsoft.VCRedist.2015+.x64' }
    $py = Tim-Python
    if ($py) { Dat 'ok' ("Python: " + (Chay-Lay $py[0] (@($py | Select-Object -Skip 1) + '--version'))) } else { Dat 'loi' 'Thiếu Python 3.11 (Xưởng Video cần). Cài: winget install -e --id Python.Python.3.11 --scope user' }
    $nv = Tim-Node
    if ($nv) { Dat 'ok' "Node.js $nv" } else { Dat 'loi' 'Thiếu Node.js >= 18 (Remotion cần). Cài: winget install -e --id OpenJS.NodeJS.LTS' }
    if (Co-Lenh 'ffmpeg') { Dat 'ok' 'ffmpeg có sẵn' } else { Dat 'loi' 'Thiếu ffmpeg. Cài: winget install -e --id Gyan.FFmpeg' }
    if (Co-Lenh 'claude') { Dat 'ok' ("Claude Code CLI: " + (Chay-Lay 'claude' @('--version'))) } else { Dat 'loi' 'Thiếu Claude Code CLI (sản xuất video cần). Cài: npm i -g @anthropic-ai/claude-code, rồi đăng nhập từng tài khoản trong Xưởng Video.' }
    if (Tim-Chrome) { Dat 'ok' 'Google Chrome có sẵn' } else { Dat 'cb' 'Không thấy Google Chrome (tiện ích đăng bài chạy trên Chrome).' }
    if (Tim-Antigravity) { Dat 'ok' 'Google Antigravity có sẵn (cho "Học cảnh")' } else { Dat 'cb' 'Chưa có Google Antigravity - chỉ cần cho "Học cảnh". Tải: https://antigravity.google' }

    Write-Host ''
    Write-Host '3. Tệp của app' -ForegroundColor Cyan
    if (-not (La-ThuMucCai $root)) {
        Dat 'loi' "Không thấy bản cài ở $root (thiếu artisan/VERSION). Chạy TikTokAutoKid-Setup.exe để cài."
        return $kq
    }
    Dat 'ok' ("Phiên bản " + (Get-Content (Join-Path $root 'VERSION') -Raw).Trim())
    $must = [ordered]@{
        'TikTokAuto.exe'                    = 'launcher (khay hệ thống)'
        'vendor\autoload.php'               = 'thư viện PHP (composer)'
        'public\build\manifest.json'        = 'giao diện đã build'
        'runtime\php\php.exe'               = 'PHP portable'
        'runtime\pgsql\bin\postgres.exe'    = 'PostgreSQL portable'
        'runtime\caddy\caddy.exe'           = 'Caddy (web server)'
        'runtime\services.json'             = 'danh sách dịch vụ'
        'xuong-video\remotion\node_modules' = 'Remotion (npm ci)'
        'extension\autotok\manifest.json'   = 'tiện ích Chrome'
    }
    foreach ($k in $must.Keys) {
        if (Test-Path (Join-Path $root $k)) { Dat 'ok' "$k ($($must[$k]))" } else { Dat 'loi' "Thiếu $k ($($must[$k])) - chạy lại TikTokAutoKid-Setup.exe để sửa." }
    }
    $xvPy = Doc-Env $root 'XUONG_PYTHON'
    if (-not $xvPy) { $xvPy = Join-Path $root 'runtime\xuong-venv\Scripts\python.exe' }
    if (Test-Path $xvPy) { Dat 'ok' 'Python của Xưởng Video (venv hoặc XUONG_PYTHON) có sẵn' } else { Dat 'loi' "Thiếu Python của Xưởng Video: $xvPy - chạy lại TikTokAutoKid-Setup.exe để sửa." }
    foreach ($k in 'APP_KEY','FORK_HUB_KEY', 'FORK_CHROME_LAUNCHER_SECRET', 'XUONG_DATA', 'UPDATE_REPO') {
        if (Doc-Env $root $k) { Dat 'ok' ".env có $k" } else { Dat 'loi' ".env thiếu $k (chạy lại TikTokAutoKid-Setup.exe; không chép khóa này lên mạng)." }
    }
    $data = Doc-Env $root 'XUONG_DATA'
    $dataAbs = $null
    if ($data) { $dataAbs = if ([IO.Path]::IsPathRooted($data)) { $data } else { Join-Path $root $data } }
    if ($dataAbs -and (Test-Path $dataAbs)) { Dat 'ok' 'Thư mục dữ liệu Xưởng Video tồn tại' } elseif ($data) { Dat 'loi' "Thư mục dữ liệu Xưởng Video không tồn tại: $dataAbs" }
    $hubPath = Doc-Env $root 'FORK_HUB_PATH'
    if ($hubPath -and $data -and ($hubPath.Replace('\', '/').TrimEnd('/') -ine $data.Replace('\', '/').TrimEnd('/'))) { Dat 'cb' 'FORK_HUB_PATH khác XUONG_DATA trong .env (phải cùng một thư mục).' }
    # khóa hub trong .env phải khớp config.json của hub (không in giá trị)
    $envKey = Doc-Env $root 'FORK_HUB_KEY'
    if ($dataAbs -and (Test-Path (Join-Path $dataAbs 'config.json')) -and $envKey) {
        try {
            $hubKey = [string]((Get-Content (Join-Path $dataAbs 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json).trypost.khoa)
            if ($hubKey -ceq $envKey) { Dat 'ok' 'Khóa hub trong .env khớp config.json của hub' } else { Dat 'loi' 'FORK_HUB_KEY trong .env KHÁC khóa trypost.khoa trong config.json của hub -> app không nhận được video. Sửa cho trùng rồi khởi động lại.' }
        } catch { Dat 'cb' 'Không đọc được config.json của hub.' }
    }

    Write-Host ''
    Write-Host '4. Dịch vụ và cổng' -ForegroundColor Cyan
    $launcherUp = Http-Ok 'http://127.0.0.1:8009/api/status' 3
    if ($launcherUp) { Dat 'ok' 'Launcher đang chạy (127.0.0.1:8009)' } else { Dat 'cb' 'Launcher chưa chạy: mở TikTok Auto Kid (lối tắt Desktop hoặc TikTokAuto.exe).' }
    $cong = [ordered]@{ '5433' = 'PostgreSQL'; '8010' = 'Web (Caddy)'; '8765' = 'Xưởng Video (hub)'; '8766' = 'Cổng hub cho app' }
    foreach ($p in $cong.Keys) {
        if (Cong-Mo ([int]$p)) { Dat 'ok' "Cổng $p mở ($($cong[$p]))" }
        elseif ($launcherUp) { Dat 'cb' "Cổng $p đóng ($($cong[$p])) - xem runtime\logs\ hoặc trang trạng thái http://127.0.0.1:8009" }
        else { Dat 'cb' "Cổng $p đóng ($($cong[$p])) - launcher chưa chạy." }
    }
    if ((Cong-Mo 5433) -and -not $launcherUp) { Dat 'cb' 'PostgreSQL (5433) đang chạy nhưng launcher thì không: có thể là tiến trình mồ côi. Thoát hẳn rồi mở lại TikTok Auto Kid; nếu vẫn kẹt, kết thúc tiến trình postgres.exe trong Task Manager.' }
    if (Http-Ok 'http://127.0.0.1:8010/up' 4) { Dat 'ok' 'Web trả lời http://localhost:8010' } elseif ($launcherUp) { Dat 'cb' 'Web chưa trả lời http://localhost:8010 (đang khởi động? chờ 1-2 phút).' }
    if (Http-Ok 'http://127.0.0.1:8765/health' 4) { Dat 'ok' 'Hub Xưởng Video trả lời /health' } elseif ($launcherUp) { Dat 'cb' 'Hub không trả lời (8765): app sẽ không lên lịch được cho tới khi hub chạy. Xem runtime\logs\xuong-video.err.log.' }

    Write-Host ''
    Write-Host '5. Tiện ích Chrome (đăng bài)' -ForegroundColor Cyan
    Dat 'ok' ("Thư mục tiện ích: " + (Join-Path $root 'extension\autotok'))
    Write-Host '      Gợi ý: chrome://extensions > bật "Chế độ nhà phát triển" > "Tải tiện ích đã giải nén" > chọn thư mục trên.' -ForegroundColor Gray
    Write-Host '      Trong tiện ích, địa chỉ máy chủ phải là http://localhost:8010; ghép nối ở http://localhost:8010/settings/chrome.' -ForegroundColor Gray
    if (Doc-Env $root 'FORK_CHROME_EXTENSION_ID') { Dat 'ok' 'FORK_CHROME_EXTENSION_ID đã đặt trong .env' } else { Dat 'ok' 'ID tiện ích tự suy ra từ khóa trong manifest.json (không cần đặt FORK_CHROME_EXTENSION_ID).' }
    Write-Host '      Lưu ý: Google Antigravity phải ĐANG MỞ khi dùng "Học cảnh". Gemini CLI không còn chạy được với tài khoản miễn phí.' -ForegroundColor Gray

    Write-Host ''
    $mau = if ($kq.loi -gt 0) { 'Red' } elseif ($kq.canhbao -gt 0) { 'Yellow' } else { 'Green' }
    Write-Host ("KẾT QUẢ: {0} ổn, {1} cảnh báo, {2} lỗi." -f $kq.ok, $kq.canhbao, $kq.loi) -ForegroundColor $mau
    return $kq
}

if ($KiemTra) {
    $r = @(Kiem-Tra-Suc-Khoe)[-1]
    if ($r.loi -gt 0) { exit 1 } else { exit 0 }
}

# ================================================================ CÀI ĐẶT
Write-Host ''
Write-Host '=============================================' -ForegroundColor White
Write-Host '   TikTok Auto Kid - Trình cài đặt một chạm  ' -ForegroundColor White
Write-Host '=============================================' -ForegroundColor White
if ($ThuKhong) { Write-Host '(Chế độ CHẠY THỬ: chỉ in các bước, không thay đổi gì)' -ForegroundColor Magenta }
$wvChinh = [Environment]::OSVersion.Version
if ($wvChinh.Major -lt 10 -or $wvChinh.Build -lt 17763 -or -not [Environment]::Is64BitOperatingSystem) {
    Write-Host "Windows này không được hỗ trợ (build $($wvChinh.Build), 64-bit: $([Environment]::Is64BitOperatingSystem)). Cần Windows 10 64-bit bản 1809 trở lên hoặc Windows 11." -ForegroundColor Red
    if ($TienDo) { Write-Host "##TD-LOI Windows này không được hỗ trợ. Cần Windows 10 64-bit bản 1809 trở lên hoặc Windows 11." }
    exit 1
}
TD 0 'tai-app' 'Đang chuẩn bị cài đặt...'

$root = Chon-ThuMuc
$script:GocCai = $root
if ($root -match '[^\u0000-\u007F]') {
    Write-Host "Cảnh báo: đường dẫn có ký tự ngoài ASCII; một số công cụ (Remotion, ffmpeg) có thể lỗi. Nên dùng đường dẫn không dấu." -ForegroundColor Yellow
    if ($TienDo) { Write-Host "##TD-CB Đường dẫn cài có ký tự có dấu; một số công cụ (Remotion, ffmpeg) có thể lỗi. Nên dùng đường dẫn không dấu." }
}
$script:LogFile = Join-Path $root 'runtime\logs\cai-dat.log'
if (-not $ThuKhong) { New-Item -ItemType Directory -Force (Split-Path $script:LogFile) | Out-Null }
Ghi-Log "Bắt đầu cài. Thư mục: $root; ThuKhong=$ThuKhong; Repo=$Repo"
Noi "Thư mục cài: $root"

# ---------------------------------------------------------------- 1. lấy mã nguồn
Tieu-De 'Lấy bản phát hành'
if (La-ThuMucCai $root) {
    Ok ("Đã có bản cài (phiên bản {0}) - bỏ qua tải, chuyển sang sửa chữa/hoàn tất cài đặt." -f (Get-Content (Join-Path $root 'VERSION') -Raw).Trim())
    Noi '  (Muốn lên bản mới: dùng nút Cập nhật trong app.)'
    TD 25 'tai-app' 'Đã có sẵn ứng dụng, chuyển sang bước cài phần mềm.'
}
else {
    if ((Test-Path $root) -and @(Get-ChildItem $root -Force -ErrorAction SilentlyContinue).Count -gt 0) {
        if ($TienDo) { Loi "Thư mục $root không trống và chưa có TikTok Auto Kid. Hãy chọn thư mục trống hoặc thư mục mới."; exit 1 }
        if (-not (Hoi-CoKhong "Thư mục $root không trống và chưa có TikTok Auto Kid. Vẫn cài vào đây?" $false)) { Noi 'Đã hủy.'; exit 1 }
    }
    TD 2 'tai-app' 'Đang tìm bản mới nhất trên mạng...'
    Noi "  Hỏi GitHub bản mới nhất của $Repo ..."
    $asset = $null; $shaAsset = $null; $ver = '?'
    try {
        $rel = Invoke-RestMethod -UseBasicParsing -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'TikTokAutoKid-Installer'; 'Accept' = 'application/vnd.github+json' } -TimeoutSec 30
        $ver = $rel.tag_name
        $asset = $rel.assets | Where-Object { $_.name -match '^tiktok-auto-kid-\d+\.\d+\.\d+.*\.zip$' } | Select-Object -First 1
        if ($asset) { $shaAsset = $rel.assets | Where-Object { $_.name -eq ($asset.name + '.sha256') } | Select-Object -First 1 }
    }
    catch {
        if ($ThuKhong) { Thu-Khong "Không gọi được GitHub ($($_.Exception.Message)); lúc cài thật sẽ cần Internet và bản phát hành đã đăng." }
        else { Loi "Không lấy được bản phát hành: $($_.Exception.Message). Kiểm tra Internet hoặc kho $Repo đã có Release chưa."; exit 1 }
    }
    if ($asset -and -not $shaAsset -and -not $ThuKhong) { Loi 'Bản phát hành thiếu file .sha256 - dừng để an toàn.'; exit 1 }
    if ($asset) {
        $mb = [math]::Round($asset.size / 1MB, 1)
        Noi "  Bản $ver : $($asset.name) ($mb MB)"
        TD 5 'tai-app' "Đang tải ứng dụng ($mb MB)..."
        $tmpDir = Join-Path $env:TEMP 'tiktok-auto-kid-cai-dat'
        $zip = Join-Path $tmpDir $asset.name
        if ($ThuKhong) { Thu-Khong "Tải $($asset.browser_download_url) -> $zip"; Thu-Khong 'Kiểm SHA256 rồi giải nén vào thư mục cài.' }
        else {
            New-Item -ItemType Directory -Force $tmpDir | Out-Null
            $shaFile = Join-Path $tmpDir ($asset.name + '.sha256')
            & curl.exe -sL --fail --retry 3 -o $shaFile $shaAsset.browser_download_url
            if ($LASTEXITCODE -ne 0) { Loi 'Không tải được file .sha256.'; exit 1 }
            $want = ((Get-Content $shaFile -Raw).Trim() -split '\s+')[0].ToLower()
            if ($want -notmatch '^[0-9a-f]{64}$') { Loi 'File .sha256 không hợp lệ.'; exit 1 }
            for ($try = 1; $try -le 3; $try++) {
                Noi "  Đang tải gói cài (lần $try)..."
                if ($TienDo) {
                    # curl chạy ẩn; đọc kích thước file mỗi giây để báo tiến độ (5% -> 20%)
                    $cp = Start-Process -FilePath 'curl.exe' -ArgumentList ('-sS -L --fail --retry 5 --retry-delay 3 -C - -o "' + $zip + '" "' + $asset.browser_download_url + '"') -PassThru -WindowStyle Hidden
                    while (-not $cp.HasExited) {
                        Start-Sleep -Milliseconds 1000
                        if (Test-Path $zip) {
                            $da = (Get-Item $zip).Length
                            $tl = if ($asset.size -gt 0) { [math]::Min(1.0, $da / $asset.size) } else { 0 }
                            TD ([int](5 + 15 * $tl)) 'tai-app' ("Đang tải ứng dụng: {0} / {1} MB" -f [math]::Round($da / 1MB), $mb)
                        }
                    }
                    $cp.WaitForExit()
                    $global:LASTEXITCODE = $cp.ExitCode
                }
                else { & curl.exe -L --fail --retry 5 --retry-delay 3 -C - --progress-bar -o $zip $asset.browser_download_url }
                TD 21 'tai-app' 'Đang kiểm tra gói vừa tải...'
                if ($LASTEXITCODE -eq 0 -and (Test-Path $zip) -and ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -eq $want)) { break }
                if (Test-Path $zip) { Remove-Item $zip -Force }
                if ($try -eq 3) { Loi 'Tải gói cài không thành công hoặc sai SHA256.'; exit 1 }
            }
            Ok 'Đã tải và kiểm SHA256 đúng.'
            Noi '  Đang giải nén...'
            TD 22 'tai-app' 'Đang giải nén ứng dụng...'
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            New-Item -ItemType Directory -Force $root | Out-Null
            $rootFull = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
            $za = [IO.Compression.ZipFile]::OpenRead($zip)
            try {
                $tongE = [math]::Max(1, $za.Entries.Count); $iE = 0
                foreach ($e in $za.Entries) {
                    $iE++
                    if (($iE % 200) -eq 0) { TD ([int](22 + 3 * $iE / $tongE)) 'tai-app' 'Đang giải nén ứng dụng...' }
                    if (-not $e.Name) { continue }
                    $dest = [IO.Path]::GetFullPath((Join-Path $root $e.FullName))
                    if (-not $dest.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw "Đường dẫn không an toàn trong gói: $($e.FullName)" }
                    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
                    [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $dest, $true)
                }
            } finally { $za.Dispose() }
            Remove-Item $zip, $shaFile -Force -ErrorAction SilentlyContinue
            if (-not (La-ThuMucCai $root)) { Loi 'Giải nén xong nhưng không thấy artisan/VERSION - gói hỏng?'; exit 1 }
            Ok "Đã giải nén vào $root"
            TD 25 'tai-app' 'Đã tải xong ứng dụng.'
        }
    }
    elseif (-not $ThuKhong) { Loi "Bản phát hành mới nhất của $Repo không có file tiktok-auto-kid-<phiên bản>.zip."; exit 1 }
}

# ---------------------------------------------------------------- 2. phần mềm cần có
TD 25 'phan-mem' 'Đang kiểm tra phần mềm cần có...'
Tieu-De 'Cài phần mềm còn thiếu (winget)'
function Them-Path-User([string]$dir) {
    # Thêm thư mục vào PATH của người dùng (bền vững) và của phiên này.
    try {
        $u = [Environment]::GetEnvironmentVariable('Path', 'User')
        if (-not $u) { $u = '' }
        if (($u -split ';') -notcontains $dir) { [Environment]::SetEnvironmentVariable('Path', (($u.TrimEnd(';') + ';' + $dir).TrimStart(';')), 'User') }
    } catch { Canh-Bao "Không ghi được PATH người dùng cho $dir" }
    if (($env:Path -split ';') -notcontains $dir) { $env:Path = $env:Path + ';' + $dir }
}
function Tai-File([string]$url, [string]$out) {
    $d = Split-Path $out
    New-Item -ItemType Directory -Force $d | Out-Null
    for ($i = 1; $i -le 3; $i++) {
        & curl.exe -L --fail --retry 5 --retry-delay 3 -C - -o $out $url
        if ($LASTEXITCODE -eq 0 -and (Test-Path $out)) { return $true }
        if (Test-Path $out) { Remove-Item $out -Force }
    }
    return $false
}
function Kiem-Chu-Ky([string]$file, [string]$tenNhaPhatHanh) {
    $sig = Get-AuthenticodeSignature $file
    return ($sig.Status -eq 'Valid' -and $sig.SignerCertificate.Subject -like "*$tenNhaPhatHanh*")
}
function Cai-TrucTiep([string]$loai) {
    # Dự phòng khi máy không có winget (Windows 10 cũ chưa có "App Installer"): tải thẳng từ trang chính thức.
    $tmp = Join-Path $env:TEMP 'tiktok-auto-kid-cai-dat\dl'
    $rt = Join-Path $script:GocCai 'runtime'
    try {
        switch ($loai) {
            'python' {
                $f = Join-Path $tmp 'python-3.11.9-amd64.exe'
                if (-not (Tai-File 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' $f)) { throw 'tải Python thất bại' }
                if (-not (Kiem-Chu-Ky $f 'Python Software Foundation')) { Remove-Item $f -Force; throw 'chữ ký số của bộ cài Python không hợp lệ' }
                $p = Start-Process -FilePath $f -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1', 'Include_test=0' -Wait -PassThru
                if ($p.ExitCode -ne 0) { throw "bộ cài Python trả mã $($p.ExitCode)" }
            }
            'vcredist' {
                $f = Join-Path $tmp 'vc_redist.x64.exe'
                if (-not (Tai-File 'https://aka.ms/vs/17/release/vc_redist.x64.exe' $f)) { throw 'tải VC++ Redistributable thất bại' }
                if (-not (Kiem-Chu-Ky $f 'Microsoft Corporation')) { Remove-Item $f -Force; throw 'chữ ký số của VC++ Redistributable không hợp lệ' }
                $p = Start-Process -FilePath $f -ArgumentList '/install', '/quiet', '/norestart' -Wait -PassThru
                if ($p.ExitCode -notin 0, 1638, 3010) { throw "bộ cài VC++ trả mã $($p.ExitCode) (cần quyền quản trị?)" }
            }
            'node' {
                $idx = Invoke-RestMethod -UseBasicParsing -Uri 'https://nodejs.org/dist/index.json' -TimeoutSec 30
                $v = ($idx | Where-Object { $_.lts -and ($_.files -contains 'win-x64-zip') } | Select-Object -First 1).version
                if (-not $v) { throw 'không tìm được bản Node.js LTS' }
                $name = "node-$v-win-x64.zip"
                $f = Join-Path $tmp $name
                if (-not (Tai-File "https://nodejs.org/dist/$v/$name" $f)) { throw 'tải Node.js thất bại' }
                $sums = (Invoke-WebRequest -UseBasicParsing -Uri "https://nodejs.org/dist/$v/SHASUMS256.txt" -TimeoutSec 30).Content
                $line = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($name) + '\s*$' } | Select-Object -First 1)
                $want = ($line -split '\s+')[0].ToLower()
                if (-not $want -or (Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -ne $want) { Remove-Item $f -Force; throw 'sai SHA256 của Node.js' }
                $x = Join-Path $tmp 'node-x'
                if (Test-Path $x) { Remove-Item $x -Recurse -Force }
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                [IO.Compression.ZipFile]::ExtractToDirectory($f, $x)
                $dest = Join-Path $rt 'node'
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
                New-Item -ItemType Directory -Force $rt | Out-Null
                Move-Item (Get-ChildItem $x | Select-Object -First 1).FullName $dest
                Remove-Item $x, $f -Recurse -Force -ErrorAction SilentlyContinue
                Them-Path-User $dest
            }
            'ffmpeg' {
                $f = Join-Path $tmp 'ffmpeg-release-essentials.zip'
                if (-not (Tai-File 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $f)) { throw 'tải ffmpeg thất bại' }
                $shaTxt = (Invoke-WebRequest -UseBasicParsing -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256' -TimeoutSec 30).Content
                $want = ([string]$shaTxt).Trim().Split(' ')[0].ToLower()
                if ($want -notmatch '^[0-9a-f]{64}$' -or (Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -ne $want) { Remove-Item $f -Force; throw 'sai SHA256 của ffmpeg' }
                $x = Join-Path $tmp 'ffmpeg-x'
                if (Test-Path $x) { Remove-Item $x -Recurse -Force }
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                [IO.Compression.ZipFile]::ExtractToDirectory($f, $x)
                $dest = Join-Path $rt 'ffmpeg'
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
                New-Item -ItemType Directory -Force $dest | Out-Null
                Move-Item (Join-Path (Get-ChildItem $x | Select-Object -First 1).FullName 'bin') (Join-Path $dest 'bin')
                Remove-Item $x, $f -Recurse -Force -ErrorAction SilentlyContinue
                Them-Path-User (Join-Path $dest 'bin')
            }
        }
        Cap-Nhat-Path
        Ok "Đã cài $loai bằng tải trực tiếp."
    } catch { Canh-Bao "Cài $loai bằng tải trực tiếp không thành công: $($_.Exception.Message)" }
}
function Cai-Winget([string]$id, [string]$ten, [string[]]$them = @(), [string]$truc = '', [scriptblock]$daCo = $null) {
    $coWinget = Co-Lenh 'winget'
    if (-not $coWinget) {
        if (-not $truc) { Canh-Bao "Không có winget - hãy tự cài $ten (winget install -e --id $id)."; return }
        Noi "  Máy không có winget (Windows 10 cũ chưa có 'App Installer') - tải thẳng $ten từ trang chính thức."
        if ($ThuKhong) { Thu-Khong "Tải trực tiếp: $truc"; return }
        Cai-TrucTiep $truc; return
    }
    $args2 = @('install', '-e', '--id', $id, '--silent', '--disable-interactivity', '--accept-package-agreements', '--accept-source-agreements') + $them
    if ($ThuKhong) { Thu-Khong ("winget " + ($args2 -join ' ')); return }
    Noi "  Đang cài $ten (có thể mất vài phút, đừng đóng cửa sổ)..."
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $out = (& winget @args2 2>&1 | Out-String); $rc = $LASTEXITCODE
    $ErrorActionPreference = $old
    Ghi-Log ("winget $id -> exit $rc`r`n" + $out)
    # 0 = xong; 0x8A15002B (-1978335189) = đã có / không có bản mới
    if ($rc -ne 0 -and $rc -ne -1978335189) { Canh-Bao "winget cài $ten trả mã $rc (xem log). Có thể cần tự cài." }
    Cap-Nhat-Path
}
if ($BoQuaPhanMem) { Noi '  Bỏ qua cài phần mềm (-BoQuaPhanMem).' }
else {
    Cap-Nhat-Path
    function Dam-Bao([string]$ten, [string]$id, [string[]]$them, [string]$truc, [scriptblock]$co, [int]$pct = 0, [string]$nhan = '') {
        if ($pct) { TD $pct 'phan-mem' "Đang kiểm tra $nhan..." }
        if (& $co) { Ok "$ten đã có"; return }
        if ($pct) { TD $pct 'phan-mem' "Đang cài $nhan (có thể mất vài phút)..." }
        Cai-Winget $id $ten $them $truc
        if ($ThuKhong) { return }
        if (& $co) { Ok "$ten đã sẵn sàng"; return }
        if (Co-Lenh 'winget') { Noi "  winget chưa cài được $ten - thử tải trực tiếp từ trang chính thức."; Cai-TrucTiep $truc; if (& $co) { Ok "$ten đã sẵn sàng"; return } }
        Canh-Bao "Chưa thấy $ten sau khi cài - mở cửa sổ mới và chạy lại TikTokAutoKid-Setup.exe (hoặc tự cài $ten)."
    }
    Dam-Bao 'Visual C++ 2015-2022 (PHP/PostgreSQL cần; có thể hiện hộp thoại xin quyền quản trị)' 'Microsoft.VCRedist.2015+.x64' @() 'vcredist' { Co-VCRedist } 27 'thư viện Visual C++'
    Dam-Bao 'Python 3.11' 'Python.Python.3.11' @('--scope', 'user') 'python' { [bool](Tim-Python) } 33 'Python'
    Dam-Bao 'Node.js LTS' 'OpenJS.NodeJS.LTS' @() 'node' { [bool](Tim-Node) } 40 'Node.js'
    Dam-Bao 'ffmpeg' 'Gyan.FFmpeg' @() 'ffmpeg' { Co-Lenh 'ffmpeg' } 46 'ffmpeg (xử lý video)'
    TD 50 'phan-mem' 'Đang kiểm tra Claude Code...'
    if (Co-Lenh 'claude') { Ok 'Claude Code CLI đã có' }
    elseif ($ThuKhong) { Thu-Khong 'npm.cmd install -g @anthropic-ai/claude-code' }
    elseif (Co-Lenh 'npm.cmd') {
        Noi '  Đang cài Claude Code CLI (npm)...'
        TD 50 'phan-mem' 'Đang cài Claude Code (có thể mất vài phút)...'
        $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        $o = (& npm.cmd install -g '@anthropic-ai/claude-code' --no-audit --no-fund 2>&1 | Out-String); $rc = $LASTEXITCODE
        $ErrorActionPreference = $old
        Ghi-Log ("npm claude-code -> exit $rc`r`n$o")
        Cap-Nhat-Path
        if (Co-Lenh 'claude') { Ok 'Đã cài Claude Code CLI. Sau khi mở app: vào Xưởng Video, đăng nhập từng tài khoản Claude.' } else { Canh-Bao 'Cài Claude Code CLI chưa thành công (xem log). Thử tay: npm i -g @anthropic-ai/claude-code' }
    }
    else { Canh-Bao 'Chưa có npm nên chưa cài được Claude Code CLI. Sau khi có Node.js, chạy lại TikTokAutoKid-Setup.exe.' }
}
TD 55 'phan-mem' 'Đã xong phần mềm cần có.'
if (Tim-Antigravity) { Ok 'Google Antigravity đã có (dùng cho "Học cảnh")' }
else {
    Canh-Bao 'Chưa có Google Antigravity. Chỉ cần cho tính năng "Học cảnh": hãy tự tải và cài từ https://antigravity.google rồi đăng nhập (khi học cảnh phải để ứng dụng đang mở).'
    if ($ThuKhong) { Thu-Khong 'Mở https://antigravity.google trong trình duyệt (tùy chọn).' }
    elseif (Hoi-CoKhong 'Mở trang tải Google Antigravity bây giờ?' $false) { Start-Process 'https://antigravity.google' }
}

# ---------------------------------------------------------------- 3. setup.ps1
Tieu-De 'Cài PHP, PostgreSQL, Caddy, Python venv, Remotion, cơ sở dữ liệu (setup.ps1)'
$setup = Join-Path $root 'scripts\native\setup.ps1'
TD 55 'du-lieu' 'Đang dựng cơ sở dữ liệu và công cụ nền...'
# khóa -> thông điệp thân thiện cho các mốc ##SETUP của setup.ps1
$script:TdSetup = @{
    php = 'Đang cài PHP'; composer = 'Đang chuẩn bị công cụ PHP'; pg = 'Đang cài cơ sở dữ liệu (tải khoảng 300 MB)'
    caddy = 'Đang cài máy chủ web'; venv = 'Đang tạo môi trường Python'; pip = 'Đang cài thư viện Python cho Xưởng Video'
    remotion = 'Đang cài công cụ dựng video (Remotion)'; env = 'Đang tạo cấu hình'; deps = 'Đang cài thư viện ứng dụng'
    db = 'Đang tạo cơ sở dữ liệu'; shortcut = 'Sắp xong phần dữ liệu'; xong = 'Đã xong phần dữ liệu'
}
if ($ThuKhong) {
    $them = ''; if ($ThuMucDuLieu) { $them = " -HubPath `"$ThuMucDuLieu`"" }
    Thu-Khong "powershell -File `"$setup`"$them"
    Thu-Khong 'Việc setup.ps1 sẽ làm: tải PHP/PostgreSQL/Caddy/composer (kiểm SHA256, tải tiếp khi đứt mạng), tạo venv + pip install, npm ci (Remotion),'
    Thu-Khong '  tạo .env mới (APP_KEY, FORK_CHROME_LAUNCHER_SECRET, FORK_HUB_KEY dùng chung với hub, XUONG_DATA, UPDATE_REPO), migrate CSDL.'
}
elseif (-not (Test-Path $setup)) { Loi "Không thấy $setup"; exit 1 }
else {
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $setup)
    if ($ThuMucDuLieu) { $a += @('-HubPath', $ThuMucDuLieu) }
    if ($TienDo) { $a += '-TienDo' }
    Noi '  Lần đầu mất khoảng 5-15 phút (tải ~400 MB, tùy mạng). Đừng đóng cửa sổ.'
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & powershell.exe @a 2>&1 | ForEach-Object {
        $s = "$_"
        if ($s -match '^##SETUP (\d+)\|([^|]*)\|(.*)$') {
            $pc = 55 + [int]([int]$Matches[1] * 0.35)
            $m = $script:TdSetup[$Matches[2]]; if (-not $m) { $m = 'Đang cài đặt' }
            if ($Matches[3].Trim()) { $m = "$m ($($Matches[3].Trim()))" } else { $m = "$m..." }
            TD $pc 'du-lieu' $m
            Ghi-Log "setup: $s"
        }
        else { Write-Host "  | $s" -ForegroundColor DarkGray; Ghi-Log "setup: $s" }
    }
    $rc = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($rc -ne 0) { Loi "setup.ps1 thất bại (mã $rc). Xem $script:LogFile; chạy lại TikTokAutoKid-Setup.exe sẽ tiếp tục từ chỗ dở."; exit 1 }
    Ok 'setup.ps1 hoàn tất.'
}

# ---------------------------------------------------------------- 4. lối tắt
TD 90 'loi-tat' 'Đang tạo lối tắt...'
Tieu-De 'Tạo lối tắt'
function Tao-LoiTat([string]$duongDan, [string]$exe, [string]$thuMucLam) {
    if ($ThuKhong) { Thu-Khong "Lối tắt: $duongDan -> $exe"; return }
    try {
        New-Item -ItemType Directory -Force (Split-Path $duongDan) | Out-Null
        $sh = New-Object -ComObject WScript.Shell
        $lk = $sh.CreateShortcut($duongDan)
        $lk.TargetPath = $exe; $lk.WorkingDirectory = $thuMucLam; $lk.Description = 'TikTok Auto Kid'
        $lk.Save()
        Ok "Đã tạo: $duongDan"
    } catch { Canh-Bao "Không tạo được lối tắt $duongDan : $($_.Exception.Message)" }
}
$exe = Join-Path $root 'TikTokAuto.exe'
if (-not (Test-Path $exe) -and -not $ThuKhong) { Canh-Bao 'Không thấy TikTokAuto.exe - bỏ qua lối tắt.' }
else {
    Tao-LoiTat (Join-Path ([Environment]::GetFolderPath('Desktop')) 'TikTok Auto Kid.lnk') $exe $root
    Tao-LoiTat (Join-Path ([Environment]::GetFolderPath('Programs')) 'TikTok Auto Kid.lnk') $exe $root
    $chayCung = [bool]$ChayCungWindows
    if (-not $chayCung -and -not $KhongHoi) { $chayCung = Hoi-CoKhong 'Tự mở TikTok Auto Kid khi bật máy (Chạy cùng Windows)?' $true }
    $lkStart = Join-Path ([Environment]::GetFolderPath('Startup')) 'TikTok Auto Kid.lnk'
    if ($chayCung) { Tao-LoiTat $lkStart $exe $root }
    elseif (-not $ThuKhong -and (Test-Path $lkStart) -and $KhongHoi) { Noi '  (Giữ nguyên lối tắt Chạy cùng Windows đã có.)' }
}

# ---------------------------------------------------------------- 5. chạy app
TD 95 'loi-tat' 'Đã tạo lối tắt.'
# install.json: nơi trình cài/launcher biết thư mục cài và thư mục dữ liệu (XUONG_DATA thật sự trong .env)
function Ghi-InstallJson {
    $duLieu = Doc-Env $root 'XUONG_DATA'
    if (-not $duLieu) { $duLieu = Doc-Env $root 'FORK_HUB_PATH' }
    if (-not $duLieu) { $duLieu = if ($ThuMucDuLieu) { $ThuMucDuLieu } else { Join-Path $root 'du-lieu\xuong-video' } }
    if (-not [IO.Path]::IsPathRooted($duLieu)) { $duLieu = Join-Path $root $duLieu }
    $duLieu = [IO.Path]::GetFullPath($duLieu.Replace('/', '\'))
    $ver = ''
    try { $ver = (Get-Content (Join-Path $root 'VERSION') -Raw -ErrorAction Stop).Trim() } catch {}
    $lk = Join-Path ([Environment]::GetFolderPath('Startup')) 'TikTok Auto Kid.lnk'
    $o = [ordered]@{
        thu_muc           = $root
        du_lieu           = $duLieu
        phien_ban         = $ver
        chay_cung_windows = [bool](Test-Path $lk)
        luc_cai           = (Get-Date).ToString('o')
    }
    if ($ThuKhong) { Thu-Khong ("Ghi $root\runtime\install.json: " + ($o | ConvertTo-Json -Compress)); return }
    try {
        New-Item -ItemType Directory -Force (Join-Path $root 'runtime') | Out-Null
        [IO.File]::WriteAllText((Join-Path $root 'runtime\install.json'), ($o | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        Ok 'Đã ghi runtime\install.json'
    } catch { Canh-Bao "Không ghi được install.json: $($_.Exception.Message)" }
}
TD 96 'khoi-dong' 'Đang hoàn tất...'
Tieu-De 'Khởi động và mở app'
Ghi-InstallJson
if ($TienDo) { Noi '  (Chế độ -TienDo: không mở trình duyệt, không khởi động app; trình cài GUI sẽ làm.)' }
elseif ($ThuKhong) { Thu-Khong "Chạy $exe, chờ http://127.0.0.1:8010/up (tối đa 4 phút), mở http://localhost:8010 trong trình duyệt." }
else {
    if (Http-Ok 'http://127.0.0.1:8009/api/status' 3) { Ok 'TikTok Auto Kid đang chạy sẵn.' }
    elseif (Test-Path $exe) { Start-Process -FilePath $exe -WorkingDirectory $root; Noi '  Đã mở TikTok Auto Kid (biểu tượng ở khay hệ thống). Đang chờ dịch vụ sẵn sàng...' }
    $end = (Get-Date).AddSeconds(240); $san = $false
    while ((Get-Date) -lt $end) { if (Http-Ok 'http://127.0.0.1:8010/up' 4) { $san = $true; break }; Start-Sleep -Seconds 3 }
    if ($san) { Ok 'App đã sẵn sàng.'; Start-Process 'http://localhost:8010' }
    else { Canh-Bao 'App chưa trả lời sau 4 phút. Xem runtime\logs\ hoặc chạy: scripts\install\cai-dat.ps1 -KiemTra' }
}

# ---------------------------------------------------------------- hướng dẫn tiếp
Write-Host ''
Write-Host '=============================================' -ForegroundColor White
$ketLuan = if ($ThuKhong) { 'Chạy thử xong (chưa thay đổi gì).' } elseif ($script:SoLoi -gt 0) { 'Cài xong nhưng có lỗi - xem phía trên.' } else { 'Cài đặt hoàn tất.' }
Write-Host $ketLuan -ForegroundColor Green
Write-Host ''
Write-Host 'Việc cần làm tay (một lần):' -ForegroundColor White
Write-Host '  1. Chrome: chrome://extensions > bật Chế độ nhà phát triển > Tải tiện ích đã giải nén > chọn thư mục:' -ForegroundColor Gray
Write-Host ("       " + (Join-Path $root 'extension\autotok')) -ForegroundColor Gray
Write-Host '  2. Xưởng Video: đăng nhập tài khoản Claude (Claude Code CLI) và điền khóa ElevenLabs trong phần cài đặt của hub.' -ForegroundColor Gray
Write-Host '  3. (Tùy chọn) Cài Google Antigravity để dùng "Học cảnh".' -ForegroundColor Gray
Write-Host ''
Write-Host ("Nhật ký: " + $script:LogFile) -ForegroundColor DarkGray
Write-Host 'Kiểm tra lại bất cứ lúc nào: scripts\install\cai-dat.ps1 -KiemTra' -ForegroundColor DarkGray
Ghi-Log "Kết thúc. Cảnh báo=$script:SoCanhBao Lỗi=$script:SoLoi"
if ($script:SoLoi -gt 0) { exit 1 }
TD 100 'xong' 'Cài đặt hoàn tất.'
exit 0
