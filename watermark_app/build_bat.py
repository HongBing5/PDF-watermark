# -*- coding: utf-8 -*-
"""生成 build.bat（打包）和 preview.bat（看界面）。bat 必须写成 GBK + CRLF，所以不能用编辑器直接存。

2026-09-24 起改成两步走：先用「preview.bat」跑源码看界面 → 满意了再「build.bat」。
省得每改一点样式都要等一分钟打包、再测一遍。
2026-09-28：bat 名统一为英文（编码更稳、命令行里好敲）。
"""
import os

# ---- 1) 打包用 ----
BAT = r'''@echo off
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
'''

# ---- 2) 打包前看界面用（跑源码，不打包）----
PREVIEW = r'''@echo off
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
'''

HERE = os.path.dirname(os.path.abspath(__file__))
for name, text in (("build.bat", BAT), ("preview.bat", PREVIEW)):
    p = os.path.join(HERE, name)
    open(p, "wb").write(text.replace("\n", "\r\n").encode("gbk"))
    print("写出:", p, os.path.getsize(p), "字节")
