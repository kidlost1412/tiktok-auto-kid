@echo off
rem Build TikTokAuto.exe (khong cua so console) vao dist\ va dummysvc de thu nghiem.
setlocal
cd /d "%~dp0"
set "PATH=%PATH%;C:\Program Files\Go\bin"
if not exist dist mkdir dist
go vet ./... || exit /b 1
go test ./... || exit /b 1
go build -trimpath -ldflags "-H=windowsgui -s -w" -o dist\TikTokAuto.exe . || exit /b 1
if not exist testdata\bin mkdir testdata\bin
go build -o testdata\bin\dummysvc.exe .\tools\dummysvc || exit /b 1
echo Xong: dist\TikTokAuto.exe
