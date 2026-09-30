#!/usr/bin/env bash
# ============================================================
#  PDF 批量加水印 · macOS 打包脚本
#  在 Mac 上（或 GitHub Actions 云 Mac）跑一次，生成
#  dist/PDF批量加水印.app —— 把这个 .app 发给同事，双击即用、
#  不联网、无需安装 Python（界面走系统自带的 WebKit，不需要 WebView2）。
#
#  用法：
#    本地 Mac：  bash build_mac.sh
#    （需先装好 Python 3.11 并 pip install pymupdf pillow pywebview pyinstaller pyobjc）
#  CI 里：由 .github/workflows/build-mac.yml 调用，依赖已在 workflow 里装好。
# ============================================================
set -e
cd "$(dirname "$0")"

PYBIN=$(command -v python3 || command -v python)
echo "== 1/3 生成 macOS 图标 app.icns =="
"$PYBIN" - <<'PY'
from PIL import Image
ico = Image.open("app.ico")
ico.size = max(ico.info["sizes"])   # 显式取最大帧（256），避免拿到 16x16 放大成糊图
ico.load()
ico.convert("RGBA").save("app.icns")
print("app.icns 已生成", ico.size)
PY

echo "== 2/3 PyInstaller 打包 .app =="
# macOS 用 : 作 --add-data 的分隔符（Windows 是 ;）
pyinstaller --noconfirm --windowed \
  --name "PDF批量加水印" \
  --icon "app.icns" \
  --add-data "ui.html:." \
  --add-data "../pdf_watermark.py:." \
  --add-data "fonts:fonts" \
  --hidden-import PIL.ImageDraw \
  --hidden-import PIL.ImageFont \
  --hidden-import webview.platforms.cocoa \
  app_main.py

echo "== 3/3 完成 =="
echo "产物：dist/PDF批量加水印.app"
echo "分发：右键该 .app -> 压缩，把 zip 发给同事；同事解压后双击即可。"
echo "（首次打开若被「无法验证开发者」拦住：右键 .app -> 打开，或在终端跑 xattr -cr 后双击）"
