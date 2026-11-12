param([string]$SanPham = "ma-san-pham", [int]$SoVideo = 50)
# Chay mot lo video tu dong lenh (khong qua giao dien):
#   powershell -ExecutionPolicy Bypass -File xuong-video\sanxuat.ps1 -SanPham ma-san-pham -SoVideo 50
# Thu muc du lieu: bien moi truong XUONG_DATA (mac dinh <repo>\du-lieu\xuong-video).
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
Set-Location $PSScriptRoot
$repo = Split-Path $PSScriptRoot -Parent
$py = Join-Path $repo 'runtime\xuong-venv\Scripts\python.exe'
if (-not (Test-Path $py) -and $env:XUONG_DATA) { $py = Join-Path $env:XUONG_DATA '.venv\Scripts\python.exe' }
& $py -X utf8 engine\sanxuat.py $SanPham $SoVideo
