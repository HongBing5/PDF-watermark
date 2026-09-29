# -*- coding: utf-8 -*-
r"""
PDF 批量加水印 · 桌面版
========================
pywebview 外壳（Windows 调系统自带 Edge WebView2，不打包浏览器）+ HTML 界面 + Python 后端。

核心原则：渲染代码零改动 —— 这里只负责把界面参数组装成 argparse 同构的 SimpleNamespace，
然后直接调用 pdf_watermark.py 里的 build_watermark_layer() / add_watermark()，
保证 GUI 产出的成品与已交付的 60+ 课件像素级一致。

启动：  python app_main.py
打包：  pyinstaller --noconfirm --onefile --noconsole --name "PDF批量加水印" \
            --add-data "ui.html;." --add-data "..\pdf_watermark.py;." app_main.py
"""
import os
import sys
import io
import json
import subprocess
import glob
import time
import types
import base64
import shutil
import tempfile
import threading

# ---- 无控制台时静音 stdout/stderr ----
# --noconsole 打包后 sys.stdout 是 GBK 管道，而 pdf_watermark 里的 print 含 ✓ / →，
# 一打印就 UnicodeEncodeError，会把批量处理每个文件都搞崩。这里直接丢到 devnull。
# 需要看输出时设环境变量 WM_DEBUG=1 即可保留。
if getattr(sys, "frozen", False) and not os.environ.get("WM_DEBUG"):
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass

# ---- 定位并导入 pdf_watermark.py（开发时在工作区上一级，打包后被 --add-data 放在 _MEI 根目录）----
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(_HERE), _HERE, getattr(sys, "_MEIPASS", "")):
    if _p and os.path.exists(os.path.join(_p, "pdf_watermark.py")):
        sys.path.insert(0, _p)
        break
def _dump_error(tag, tb):
    """无控制台时把异常详情写到 exe 同级 error.log"""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _HERE
    try:
        with open(os.path.join(base, "error.log"), "w", encoding="utf-8") as f:
            f.write(tag + "\n" + tb)
    except Exception:
        pass


try:
    import pdf_watermark as wm
except BaseException as e:  # 被打包却漏了 --add-data 时给出明确提示
    import traceback
    _dump_error("import pdf_watermark failed", traceback.format_exc())
    raise SystemExit("找不到 pdf_watermark.py（打包时需要 --add-data \"pdf_watermark.py;.\"）\n" + str(e))

import pymupdf
# pdf_watermark.py 是以「数据文件」打进 exe 的，PyInstaller 不会分析它的 import，
# 所以这里替它把 ImageDraw / ImageFont 静态导入一遍，否则打包后会
# ImportError: cannot import name 'ImageDraw' from 'PIL'
from PIL import Image, ImageDraw, ImageFont  # noqa: F401
import webview
from webview.dom import DOMEventHandler

UI = os.path.join(_HERE, "ui.html")
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _b = os.path.join(sys._MEIPASS, "ui.html")
    if os.path.exists(_b):
        UI = _b


# ============================ 参数组装（字段与 argparse 完全一致） ============================
ARG_FIELDS = [
    "text", "font_size", "rotate", "alpha", "grey",
    "gap_x", "gap_y", "suffix",
    "emboss", "light_color", "light_alpha", "dark_color", "dark_alpha", "stroke_div",
]
NUM_INT = {"grey", "light_color", "dark_color", "stroke_div"}
NUM_FLOAT = {"font_size", "rotate", "alpha", "gap_x", "gap_y", "light_alpha", "dark_alpha"}


def to_args(p: dict, dpi: int = None) -> types.SimpleNamespace:
    """把前端传来的参数字典 → 与 argparse.Namespace 同构的 SimpleNamespace。"""
    a = types.SimpleNamespace()
    for k in ARG_FIELDS:
        v = p.get(k, None)
        if k in NUM_INT:
            v = int(v) if v is not None else 0
        elif k in NUM_FLOAT:
            v = float(v) if v is not None else 0.0
        elif k == "emboss":
            v = bool(v)
        a.__dict__[k] = v
    a.font_index = 0
    a.overwrite = True
    a.dpi = int(dpi or wm.DEFAULT_DPI)
    a.font = wm.pick_font(None)
    return a


# ============================ 真实预览（渲染 PDF 页面 + 叠加水印层） ============================
def render_preview(pdf_path: str, args, page: int = 0, max_width: int = 1100) -> bytes:
    """
    与成品完全同源的预览：
      页面渲染 (dpi) + build_watermark_layer(dpi) 生成的 RGBA 层 → alpha 合成。
    水印层按页面 pt 尺寸 × dpi/72 生成，所以任意 dpi 下密度都与真实一致。
    """
    dpi = 96                      # 预览用 96dpi：够清晰且生成快；密度与 150dpi 成品相同
    args.dpi = dpi
    doc = pymupdf.open(pdf_path)
    try:
        pg = doc[min(max(page, 0), doc.page_count - 1)]
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
        layer = wm.build_watermark_layer(pg.rect.width, pg.rect.height, args)
        if layer.size != im.size:
            layer = layer.resize(im.size, Image.LANCZOS)
        im = Image.alpha_composite(im, layer).convert("RGB")
    finally:
        doc.close()

    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ============================ 暴露给 JS 的接口 ============================
def expand_pdfs(paths, suffix="_带水印"):
    """把「文件 + 文件夹」的混合列表摊平成待处理的 PDF 列表（去重、跳过已生成的成品）。
    选文件夹和拖文件夹都走这里，保证两条入口的行为完全一致。"""
    out, seen = [], set()
    for p in paths or []:
        try:
            if os.path.isdir(p):
                cand = sorted(
                    f for f in glob.glob(os.path.join(p, "*"))
                    if os.path.isfile(f) and f.lower().endswith(".pdf")
                )
            elif p.lower().endswith(".pdf"):
                cand = [p]
            else:
                cand = []
        except Exception:
            cand = []
        for f in cand:
            if suffix and suffix in os.path.basename(f):   # 已经加过水印的成品，跳过
                continue
            key = os.path.normcase(os.path.abspath(f))
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
    return out


class Api:
    # 注意：窗口引用必须以下划线开头（self._window）。
    # pywebview 注入 API 时会用 get_functions() 递归遍历 js_api 对象的所有公开属性，
    # 名字不以 _ 开头、又不可调用的对象会被继续递归下去。挂个 self.window 会让它
    # 一头钻进 Window → WinForms 原生控件里，注入直接卡死、所有后端方法都暴露不出来。
    def __init__(self):
        self._window = None

    # --- 供 Python 侧调用 JS ---
    def js(self, code):
        if self._window:
            try:
                self._window.evaluate_js(code)
            except Exception as e:
                print("[js]", e)

    # --- 选文件 / 选文件夹 ---
    def pick_pdfs(self, suffix="_带水印"):
        res = self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True,
            file_types=("PDF 文件 (*.pdf)",))
        return self._describe(res or [], suffix)

    def pick_dir(self, suffix="_带水印"):
        res = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        res = res[0] if isinstance(res, (list, tuple)) and res else (res or "")
        if not res:
            return []
        return self._describe(expand_pdfs([res], suffix), suffix)

    def dropped(self, paths, suffix="_带水印"):
        """拖拽落进窗口的文件 / 文件夹。
        路径不是 JS 传来的（浏览器拿不到），而是 pywebview 从 WebView2 的
        additionalObjects 里取出来附在 drop 事件上的 —— 见 _register_drop()。"""
        paths = list(paths or [])
        data = self._describe(expand_pdfs(paths, suffix), suffix)
        if data:
            # 复用前端同一套去重 / 渲染逻辑
            self.js("window.addFiles(%s)" % json.dumps(data, ensure_ascii=False))
        else:
            self.js("window.dropRejected(%d)" % len(paths))
        return data

    def _describe(self, paths, suffix):
        """补上文件名 / 页数 / 是否已处理"""
        out = []
        for p in paths:
            try:
                doc = pymupdf.open(p)
                n = doc.page_count
                doc.close()
            except Exception:
                continue
            base, ext = os.path.splitext(p)
            out.append({
                "path": p,
                "nm": os.path.basename(p),
                "pg": n,
                "done": os.path.exists(base + suffix + ext),
            })
        return out

    # --- 真实预览 ---
    def preview(self, params, path, page=0):
        try:
            if not path or not os.path.exists(path):
                return None
            data = render_preview(path, to_args(params), int(page))
            return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
        except Exception as e:
            print("[preview]", e)
            return None

    def page_count(self, path):
        try:
            doc = pymupdf.open(path)
            n = doc.page_count
            doc.close()
            return n
        except Exception:
            return 0

    # --- 批量处理 ---
    def start(self, params, paths, overwrite=True):
        args = to_args(params)
        paths = list(paths or [])

        def work():
            ok = fail = 0
            ok_paths = []
            total = len(paths)
            for i, p in enumerate(paths):
                name = os.path.basename(p)
                self.js(f"onProgress({i}, {total}, {json.dumps(name)})")
                try:
                    out = wm.build_output_path(p, args)   # 与 CLI 同源，命名规则完全一致
                    if os.path.exists(out) and not overwrite:
                        self.js(f"onSkip({json.dumps(name)})")
                        continue
                    if wm.add_watermark(p, out, args):
                        ok += 1
                        ok_paths.append(p)
                    else:
                        fail += 1
                except Exception as e:
                    print("[run]", e)
                    fail += 1
            self.js(f"onDone({ok}, {fail}, {json.dumps(ok_paths)})")

        threading.Thread(target=work, daemon=True).start()
        return True

    # --- 杂项 ---
    def reveal(self, path):
        """在文件管理器里定位到文件（跨平台：Win 资源管理器 / Mac Finder / Linux 文件）"""
        try:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            if sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            elif sys.platform == "win32":
                os.startfile(folder)            # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", folder], check=False)
            return True
        except Exception:
            return False

    def open_url(self, url):
        """用系统默认浏览器打开外链（更新提示、帮助页等；跨平台）"""
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", url], check=False)
            elif sys.platform == "win32":
                os.startfile(url)               # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", url], check=False)
            return True
        except Exception:
            return False

    def presets_file(self):
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _HERE
        return os.path.join(base, "presets.json")

    def load_presets(self):
        p = self.presets_file()
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_presets(self, arr):
        try:
            with open(self.presets_file(), "w", encoding="utf-8") as f:
                json.dump(list(arr or []), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print("[presets]", e)
            return False


def selftest():
    """
    自检模式：  PDF批量加水印.exe --selftest
    打包后是 GUI 无控制台，出问题看不到报错。跑一次自检会把结果写到 exe 同级的 selftest.log：
    验证 ui.html 是否被打包进去、pdf_watermark 能否导入、字体能否加载、
    并自建一张测试页真实跑一遍加水印 + 预览渲染，确认水印确实叠上去了。
    """
    out = []

    def p(s):
        out.append(str(s))
        print(s)

    p("frozen=%s  _MEIPASS=%s" % (getattr(sys, "frozen", False), getattr(sys, "_MEIPASS", "")))
    p("ui.html = %s | exists=%s" % (UI, os.path.exists(UI)))
    p("pdf_watermark = %s" % getattr(wm, "__file__", "?"))
    p("font = %s | exists=%s" % (wm.pick_font(None), os.path.exists(wm.pick_font(None) or "")))

    tmp = tempfile.mkdtemp(prefix="wmtest_")
    try:
        src = os.path.join(tmp, "probe.pdf")
        doc = pymupdf.open()
        pg = doc.new_page(width=595, height=842)          # A4
        pg.draw_rect(pg.rect, color=(0.55, 0.52, 0.48), fill=(0.55, 0.52, 0.48))  # 中性灰底
        doc.save(src)
        doc.close()

        params = dict(text="©向上少年|侵权必究", font_size=18, rotate=30, alpha=0.10,
                      grey=191, gap_x=130, gap_y=95, suffix="_带水印", emboss=True,
                      light_color=255, light_alpha=0.20, dark_color=25,
                      dark_alpha=0.12, stroke_div=22)
        args = to_args(params)
        dst = os.path.join(tmp, "probe_带水印.pdf")
        ok = wm.add_watermark(src, dst, args)
        p("add_watermark ok=%s | out exists=%s size=%s"
          % (ok, os.path.exists(dst), os.path.getsize(dst) if os.path.exists(dst) else 0))

        d2 = pymupdf.open(dst)
        p("pages: src=1 out=%d" % d2.page_count)
        p("images on page0 = %d" % len(d2[0].get_images(full=True)))
        d2.close()

        png = render_preview(src, to_args(params), 0)
        p("preview png bytes = %d" % len(png))
        im = Image.open(io.BytesIO(png)).convert("L")
        from PIL import ImageStat
        p("preview stddev = %.2f (有水印应 > 1)" % ImageStat.Stat(im).stddev[0])
        p("SELFTEST OK")
    except Exception as e:
        import traceback
        p("SELFTEST FAILED\n" + traceback.format_exc())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _HERE
    try:
        with open(os.path.join(base, "selftest.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(out))
    except Exception:
        pass
    return out


def _register_drop(win, api, tries=40):
    """把 drop 事件挂到 document 上（必须在 Python 侧注册）。

    为什么不能在 JS 里搞定：浏览器出于安全不给 File 对象真实路径，
    只有 WebView2 的 additionalObjects 能拿到；而 pywebview 只有在检测到
    「已注册 drop 监听」时才会把文件路径转发过来（webview/dom/element.py 里的
    _dnd_state['num_listeners']），然后用 pywebviewFullPath 附在事件上。
    prevent_default=True 还有第二个用处：阻止 WebView 把拖进来的 PDF 当网页打开。
    """
    def on_drop(e):
        try:
            files = ((e.get("dataTransfer") or {}).get("files")) or []
            paths = [f.get("pywebviewFullPath") for f in files
                     if isinstance(f, dict) and f.get("pywebviewFullPath")]
            api.dropped(paths)
        except Exception as ex:
            print("[drop]", ex)

    last = None
    for _ in range(tries):
        try:
            win.events.loaded.wait(1)        # 等页面就绪，否则 querySelector 拿不到 document
            win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
            return True
        except Exception as ex:
            last = ex
            time.sleep(0.25)
    print("[dnd] 注册 drop 监听失败：", last)
    return False


def main():
    api = Api()
    win = webview.create_window(
        "PDF批量加水印·©HB",
        url=UI,
        js_api=api,
        width=1280, height=800, min_size=(1080, 680),
        # 页面首帧之前的垫底色，跟马卡龙主题的 --bg 保持一致（改主题底色时记得同步这里）
        background_color="#FBF7FC",
    )
    api._window = win
    webview.start(lambda w: _register_drop(w, api), win, debug=False)


if __name__ == "__main__":
    if "--selftest" in sys.argv:      # 隐藏自检：把结果写到 exe 同级 selftest.log
        selftest()
        raise SystemExit(0)
    try:
        main()
    except Exception:
        # --noconsole 打包后看不到报错，落到 exe 同级的 error.log 便于排查
        import traceback
        _d = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _HERE
        try:
            with open(os.path.join(_d, "error.log"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
