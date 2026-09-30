@echo off
chcp 936 >nul
cd /d "%~dp0"
set "PY=C:\Users\HB\.workbuddy\binaries\python\envs\wmapp\Scripts\python.exe"

if not exist "%PY%" (
  echo [错误] 找不到打包用的 Python 环境：
  echo   %PY%
  pause
  exit /b 1
)

echo [1/4] 清理旧进程与旧成品...
taskkill /f /im "PDF批量加水印.exe" >nul 2>nul
if exist "dist\PDF批量加水印.exe" del /q "dist\PDF批量加水印.exe"

echo [2/4] 重建图标与界面雪碧图...
"%PY%" build_icon.py
"%PY%" build_icons.py

echo [3/4] 打包中（约 1 分钟，请勿关闭窗口）...
"%PY%" -m PyInstaller --noconfirm --onefile --noconsole --name "PDF批量加水印" ^
  --icon "app.ico" ^
  --version-file "version_info.txt" ^
  --add-data "ui.html;." ^
  --add-data "..\pdf_watermark.py;." ^
  --add-data "fonts;fonts" ^
  --collect-all webview ^
  --collect-all clr_loader ^
  --hidden-import PIL.ImageDraw ^
  --hidden-import PIL.ImageFont ^
  app_main.py
if errorlevel 1 (
  echo.
  echo [失败] 打包出错，请看上面的日志。
  pause
  exit /b 1
)

echo.
echo [4/4] 复制成品到工作区根目录（平时双击这个就行）...
if exist "..\PDF批量加水印.exe" del /q "..\PDF批量加水印.exe"
copy /y "dist\PDF批量加水印.exe" "..\PDF批量加水印.exe" >nul
echo --- 自检 ---
"dist\PDF批量加水印.exe" --selftest
if exist "dist\selftest.log" type "dist\selftest.log"
echo.
echo 打包完成。跑一遍 dist 里的 exe 试试吧。
pause
