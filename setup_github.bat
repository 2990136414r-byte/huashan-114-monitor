@echo off
setlocal

set GH=D:\Hospital\tools\bin\gh.exe
cd /d D:\Hospital\github-114-monitor

echo ==========================================
echo 1. Login to GitHub
echo ==========================================
"%GH%" auth login --hostname github.com --git-protocol https --web
if errorlevel 1 goto error

for /f "delims=" %%i in ('D:\Hospital\tools\bin\gh.exe api user --jq .login') do set OWNER=%%i
if "%OWNER%"=="" goto error
echo GitHub user: %OWNER%

echo ==========================================
echo 2. Create public repo and push
echo ==========================================
"%GH%" repo create "%OWNER%/huashan-114-monitor" --public --source=. --remote=origin --push
if errorlevel 1 goto error

echo ==========================================
echo 3. Set ServerChan SendKey
echo ==========================================
echo Paste SCT SendKey and press Enter:
"%GH%" secret set SERVERCHAN_SENDKEY --repo "%OWNER%/huashan-114-monitor"
if errorlevel 1 goto error

echo ==========================================
echo 4. Enable workflow and dry-run test
echo ==========================================
"%GH%" workflow enable monitor.yml --repo "%OWNER%/huashan-114-monitor"
"%GH%" workflow run monitor.yml --repo "%OWNER%/huashan-114-monitor" -f once=true -f dry_run=true
"%GH%" run list --repo "%OWNER%/huashan-114-monitor" --limit 5

echo.
echo Done. Open the repo Actions page.
pause
exit /b 0

:error
echo.
echo Failed. Send the error text to the assistant.
pause
exit /b 1

