@echo off
chcp 65001 >nul
setlocal

set GH=D:\Hospital\tools\bin\gh.exe
cd /d D:\Hospital\github-114-monitor

echo ==========================================
echo 1. 登录 GitHub（会打开浏览器）
echo ==========================================
"%GH%" auth login --hostname github.com --git-protocol https --web
if errorlevel 1 goto :error

for /f "delims=" %%i in ('"%GH%" api user --jq .login') do set OWNER=%%i
if "%OWNER%"=="" goto :error
echo 当前 GitHub 用户：%OWNER%

echo ==========================================
echo 2. 创建公开仓库并推送
echo ==========================================
"%GH%" repo create "%OWNER%/huashan-114-monitor" --public --source=. --remote=origin --push
if errorlevel 1 goto :error

echo ==========================================
echo 3. 设置 Server酱 SendKey
echo ==========================================
echo 粘贴 SCT 开头的 SendKey，按回车（不会显示）。
"%GH%" secret set SERVERCHAN_SENDKEY --repo "%OWNER%/huashan-114-monitor"
if errorlevel 1 goto :error

echo ==========================================
echo 4. 运行一次干跑测试
echo ==========================================
"%GH%" workflow run monitor.yml --repo "%OWNER%/huashan-114-monitor" -f once=true -f dry_run=true
"%GH%" run list --repo "%OWNER%/huashan-114-monitor" --limit 5

echo.
echo 完成。打开仓库 Actions 页面查看日志。
pause
exit /b 0

:error
echo.
echo 出错了，请把上面的错误信息发给我。
pause
exit /b 1

