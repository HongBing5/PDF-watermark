# PDF 批量加水印

给 PDF 课件批量打「©向上少年｜侵权必究」水印的桌面小工具。
**Windows 双击 `PDF批量加水印.exe` 即用，macOS 双击 `.app` 即用，不联网、无需装 Python。**

> 👉 **普通使用者**请看仓库里的 **`PDF批量加水印·使用说明.pdf`**（面向使用者的说明书）。
> 本文件是**开发者/维护者**视角，记录怎么改代码、怎么重新打包、怎么发版。

---

## 目录结构

```
文档添加水印/
├── PDF批量加水印.exe            ← 图形版成品（双击即用，可单独发给同事；gitignore 不入库）
├── PDF批量加水印·使用说明.pdf   ← 给使用者看的说明书（由 watermark_app/build_manual.py 生成）
├── pdf_watermark.py             ← ★核心：加水印 CLI。被 exe 通过 --add-data 打进包，
│                                     GUI 与 exe 共用同一个 build_output_path，改它两边一起变
├── pptx_to_pdf.ps1              ← 源文件是 PPTX 时，先转成 PDF 再用 exe 处理
├── presets.json                 ← 用户本地预设（运行时数据，gitignore 不入库）
├── watermark_app/               ← ★GUI 源码 + 构建脚本
│   ├── app_main.py              ← pywebview 入口（Python 后端）
│   ├── ui.html                  ← HTML 界面（含四套主题、新版本提示徽标）
│   ├── app.ico                  ← 程序图标（build_icon.py 生成，gitignore）
│   ├── theme_*.svg              ← 四套主题图标（麦当劳/雪碧/奥利奥/马卡龙）
│   ├── build.bat                ← Windows：重新打包成根目录 exe（清场→重建图标→打包→复制→自检）
│   ├── preview.bat              ← Windows：用 venv 跑源码预览界面（改完即时看，关窗即结束）
│   ├── build_mac.sh             ← macOS：bash 打包出 dist/PDF批量加水印.app
│   ├── build_icon.py            ← 生成 app.ico（印章风「印」字，含 Win/Mac 中文字体兜底）
│   ├── build_icons.py           ← 内联主题 SVG 成雪碧图
│   ├── build_version.py         ← 生成 Windows 版本信息资源 version_info.txt（@VER@ 在此）
│   ├── build_manual.py          ← 生成上面的 PDF 说明书
│   ├── build_bat.py             ← 生成 build.bat / preview.bat（GBK+CRLF，防中文乱码）
│   ├── check_*.py               ← 验收脚本（UI 状态机 / 对比度 / CDP / CLI 逐像素比对）
│   └── version_info.txt         ← build_version.py 产物（gitignore）
├── .github/workflows/release.yml ← 打 tag 自动云端构建 .exe + .app 并发布 Release
└── .gitignore
```

**已删除的历史文件**（不再需要）：`双击批量加水印.bat`（旧 CLI 双击入口，依赖 skill 副本路径、
写死旧 venv，现在直接用 exe）；`使用说明.txt`（已被 PDF 版取代）。

---

## 本地开发 / 构建

### Windows
- **预览界面**（改完 ui.html 想即时看）：双击 `watermark_app\preview.bat`
  —— 用本机 venv 跑源码，读最新 ui.html，关窗即结束，不生成任何产物。
- **重新打包 exe**：双击 `watermark_app\build.bat`
  —— 清掉残留进程 → 重建图标/雪碧图 → PyInstaller 打包 → 复制到根目录 → 自检。
- 打包用的 venv：`...\envs\wmapp\Scripts\python.exe`（依赖 pymupdf/pillow/pywebview/pythonnet/clr_loader/pyinstaller）。

### macOS（或 GitHub 云 Mac）
- `bash watermark_app/build_mac.sh` → 产出 `dist/PDF批量加水印.app`。

---

## ☑ 发版标准动作（关键，务必照做）

> 这是本项目最容易踩坑的一步，单独列出来。**改界面/算法后，本地先 preview 确认，再走下面流程。**

版本号采用 **两段式 `v主.次`**（如 `v1.0`、`v1.1`、`v2.0`）。本应用已稳定，迭代不频繁，不需要四段补丁号。

```bash
# 1) 改版本号（两处必须一致）
#    - watermark_app/ui.html  的  const APP_VER = "1.0";
#    - watermark_app/build_version.py 的  "@VER@": "1.0"
#    （Windows 文件属性里的版本号仍是内部 4 段元组 @VER_TUPLE@ = "1, 0, 0, 0"，不用动）

# 2) 提交并推到 main
git add -A && git commit -m "发版 v1.1" && git push origin main

# 3) 旧 tag 先删，再把新 tag 指向「含最新 .github/workflows 的提交」
git tag -d v1.1;  git push origin :refs/tags/v1.1
git tag v1.1  &&  git push origin v1.1
```

→ 云上 `release.yml` 自动构建 Windows `.exe` + macOS `.app`，上传到同名 **GitHub Release**。
同事去 Release 下载即双击即用。

⚠️ **tag 必须指向最新提交**：GitHub 跑的是「被推送那个 tag」里的 workflow 文件。
指向旧提交 → 跑的还是旧 workflow（曾经因此白等一轮）。所以顺序永远是：先 `push main`，再挪 tag。

⚠️ **本机推 GitHub 走 Clash 代理** `127.0.0.1:7897`（本仓库已设 local proxy，别删）：
直连 `github.com:443` 时通时断，Clash 没开时 `git push` 会 `schannel: handshake failed` / 21s 超时。
换机器/网络需重设 `git config http(s).proxy`。

---

## 新版本提示（界面里的小徽标）

`ui.html` 头部「Design by HongBing」旁有个会闪烁的「● 新版本 X.X」徽标。
启动 3 秒后 `fetch api.github.com/repos/{UPDATE_REPO}/releases/latest`，
把线上 `tag_name` 和本地 `APP_VER` 逐段比较，**只有线上严格大于本地**才点亮，
点它用系统浏览器打开 Release 下载页。无网络/还没发版/触发限流都静默，不影响使用。
（版本号相等时不会误报「有新版本」）

---

## 分发与已知限制

- 把 `PDF批量加水印.exe`（Win）/ `PDF批量加水印-macOS.zip` 解压出的 `.app`（Mac）发给同事即可。
- 未签名的 exe / app 首次打开会被 **SmartScreen / Gatekeeper** 拦，属正常：
  Windows 点「更多信息 → 仍要运行」；Mac 右键 `.app` → 打开，或终端 `xattr -cr` 后双击。
- 水印算法、输出命名（`_带水印` 后缀）的取舍见 `pdf_watermark.py` 与项目 memory。
