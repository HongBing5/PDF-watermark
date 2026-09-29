@echo off
setlocal

set "PY=C://Users//HB//.workbuddy//binaries//python//envs//pdfwatermark//Scripts//python.exe"
set "SCRIPT=C://Users//HB//.workbuddy//skills//pdf-watermark//scripts//pdf_watermark.py"

if not exist "%PY%" (
    echo [ERROR] 找不到 Python:
    echo   %PY%
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo [ERROR] 找不到脚本:
    echo   %SCRIPT%
    pause
    exit /b 1
)

echo ============================================
echo   PDF 批量加水印 - 处理本文件夹
echo ============================================
echo.
echo   文件夹: %~dp0
echo   输出命名: 文件名_带水印.pdf
echo   模式: 浮雕双色 ^(深浅背景均可见^)
echo.

"%PY%" "%SCRIPT%" --dir "%~dp0." --emboss --suffix "_带水印"

echo.
echo   处理完毕。
pause
