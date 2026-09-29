@echo off
chcp 936 >nul
cd /d "%~dp0"
set "PY=C:\Users\HB\.workbuddy\binaries\python\envs\wmapp\Scripts\python.exe"

if not exist "%PY%" (
  echo [错误] 找不到运行界面的 Python 环境：
  echo   %PY%
  pause
  exit /b 1
)

echo 正在打开界面预览（源码模式，未打包）...
echo   * 改完 ui.html 关掉再双击本文件即可看到最新效果
echo   * 界面满意了，再双击「build.bat」出成品
echo.
"%PY%" "%~dp0app_main.py"

echo.
echo 预览窗口已关闭。
pause
