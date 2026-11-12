@echo off
rem TikTok Auto Kid - cai dat mot chap. Bam dup file nay (co the tai rieng le tu trang Releases).
rem Co the them tuy chon, vi du:  CAI-DAT.bat -ThuKhong   (chay thu, khong thay doi gi)
rem                               CAI-DAT.bat -KiemTra    (kiem tra suc khoe cai dat)
setlocal
chcp 65001 >nul
title TikTok Auto Kid - Cai dat
set "HERE=%~dp0"
set "PS1=%HERE%scripts\install\cai-dat.ps1"
if not exist "%PS1%" (
  rem Tai rieng le: lay trinh cai dat tu ban phat hanh moi nhat tren GitHub
  set "TMPD=%TEMP%\tiktok-auto-kid-cai-dat"
  if not exist "%TEMP%\tiktok-auto-kid-cai-dat" mkdir "%TEMP%\tiktok-auto-kid-cai-dat"
  set "PS1=%TEMP%\tiktok-auto-kid-cai-dat\cai-dat.ps1"
  echo Dang tai trinh cai dat...
  curl.exe -L --fail --retry 3 -o "%TEMP%\tiktok-auto-kid-cai-dat\cai-dat.ps1" "https://github.com/kidlost1412/tiktok-auto-kid/releases/latest/download/cai-dat.ps1"
  if errorlevel 1 (
    echo Khong tai duoc trinh cai dat. Kiem tra Internet roi chay lai.
    pause
    exit /b 1
  )
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
