"""
一致性回归：同一个 PDF，分别用 (A) 命令行 pdf_watermark.py 和 (B) 打包后 exe 的后端处理，
渲染成品页面逐像素比对。GUI 只是参数组装层，两者必须完全一致。

用法： python verify_cli_parity.py
"""
import os, io, sys, json, time, shutil, subprocess, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(BASE, "dist", "PDF批量加水印.exe")
CLI_PY = r"C:\Users\HB\.workbuddy\binaries\python\envs\pdfwatermark\Scripts\python.exe"
WM_PY = os.path.join(os.path.dirname(BASE), "pdf_watermark.py")
PORT = 9334
WORK = os.path.join(BASE, "_parity")

PARAMS = dict(text="©向上少年|侵权必究", font_size=18, rotate=30, alpha=0.10, grey=191,
              gap_x=130, gap_y=95, suffix="_带水印", emboss=True, light_color=255,
              light_alpha=0.20, dark_color=25, dark_alpha=0.12, stroke_div=22)

shutil.rmtree(WORK, ignore_errors=True)
for d in ("src", "cli", "exe"):
    os.makedirs(os.path.join(WORK, d), exist_ok=True)

# 造一张 A4 中性灰测试页（水印在中间调上最吃参数，最能暴露差异）
import pymupdf
src = os.path.join(WORK, "src", "probe.pdf")
doc = pymupdf.open()
pg = doc.new_page(width=595, height=842)
pg.draw_rect(pg.rect, color=(0.55, 0.52, 0.48), fill=(0.55, 0.52, 0.48))
doc.save(src)
doc.close()
for d in ("cli", "exe"):
    shutil.copy(src, os.path.join(WORK, d, "probe.pdf"))

# ---------- A. 命令行 ----------
r = subprocess.run([CLI_PY, WM_PY, os.path.join(WORK, "cli", "probe.pdf"),
                    "--emboss", "--suffix", "_带水印"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
A = os.path.join(WORK, "cli", "probe_带水印.pdf")

# ---------- B. exe 后端 ----------
subprocess.run(["taskkill", "/F", "/IM", "PDF批量加水印.exe"], capture_output=True)
time.sleep(1)
env = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=%d" % PORT)
p = subprocess.Popen([EXE], env=env)
B = os.path.join(WORK, "exe", "probe_带水印.pdf")
try:
    import websocket
    ws = None
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(3)
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT, timeout=5))
        except Exception:
            continue
        cand = [d for d in tabs if d.get("type") == "page" and "ui.html" in (d.get("url") or "")]
        if not cand:
            continue
        try:
            ws = websocket.create_connection(cand[0]["webSocketDebuggerUrl"], timeout=60,
                                             suppress_origin=True)
        except Exception:
            continue
        expr = ('(function(){return typeof window.pywebview==="object"'
                '&&!!(window.pywebview.api&&window.pywebview.api.start);})()')
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": expr, "returnByValue": True}}))
        if json.loads(ws.recv()).get("result", {}).get("result", {}).get("value"):
            break
        ws.close()
        ws = None
    if not ws:
        print("exe 后端未就绪（CDP 连不上 WebView2 —— 常见于 WebView2 刚更新 / 从沙箱化 shell 启动）。")
        print("  退化验证：① `%s --selftest`；② 用 CArchiveReader 解出 exe 内嵌的")
        print("  ui.html / pdf_watermark.py，与磁盘版比 md5 —— 两者一致即可认定同源。")
        sys.exit(1)

    expr = ("window.pywebview.api.start(%s, %s, true)"
            % (json.dumps(PARAMS, ensure_ascii=False),
               json.dumps([os.path.join(WORK, "exe", "probe.pdf")])))
    ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    ws.recv()
    for _ in range(40):                      # 等成品落盘
        if os.path.exists(B):
            break
        time.sleep(1)
    ws.close()
finally:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    try:
        p.wait(6)
    except Exception:
        p.kill()

if not (os.path.exists(A) and os.path.exists(B)):
    print("缺成品： CLI=%s exe=%s" % (os.path.exists(A), os.path.exists(B)))
    sys.exit(1)

# ---------- 比对 ----------
from PIL import Image, ImageChops, ImageStat
def render(path):
    d = pymupdf.open(path)
    pix = d[0].get_pixmap(dpi=150)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    d.close()
    return im

ia, ib = render(A), render(B)
diff = ImageChops.difference(ia, ib)
st = ImageStat.Stat(diff)
mx = max(st.extrema[0][1], st.extrema[1][1], st.extrema[2][1])
print("尺寸  CLI=%s  exe=%s" % (ia.size, ib.size))
print("页数  CLI=%d  exe=%d" % (pymupdf.open(A).page_count, pymupdf.open(B).page_count))
print("像素差 mean=%.3f  rms=%.3f  峰值=%d（0 表示完全一致，个别抗锯齿差异属正常）"
      % (sum(st.mean) / 3, sum(st.rms) / 3, mx))
print("==>", "一致" if sum(st.mean) / 3 < 1.0 else "存在明显差异")
