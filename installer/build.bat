@echo off
rem Build TikTokAutoKid-Setup.exe (trinh cai co giao dien, khong cua so console) vao dist\.
rem Can: Go 1.27, Microsoft Edge WebView2 Runtime (co san tren Windows 11) de CHAY.
setlocal
cd /d "%~dp0"
set "PATH=%PATH%;C:\Program Files\Go\bin"
if not exist dist mkdir dist
if not exist embed mkdir embed
copy /y "..\scripts\install\cai-dat.ps1" "embed\cai-dat.ps1" >nul || exit /b 1
copy /y "..\VERSION" "embed\VERSION" >nul || exit /b 1
set /p VER=<embed\VERSION
rem Sinh lai bieu tuong + manifest + thong tin phien ban (rsrc_windows_amd64.syso)
pushd tools\genres
go run . -ico ..\..\assets\icon.ico -manifest ..\..\assets\app.manifest -version %VER% -o ..\..\rsrc_windows_amd64.syso || (popd & exit /b 1)
popd
go vet ./... || exit /b 1
go build -trimpath -ldflags "-H=windowsgui -s -w" -o dist\TikTokAutoKid-Setup.exe . || exit /b 1
echo Xong: dist\TikTokAutoKid-Setup.exe
