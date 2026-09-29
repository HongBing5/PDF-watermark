"""
打包后 exe 的端到端验收（走 WebView2 远程调试端口 CDP）
=====================================================
用法：
    python verify_exe.py            # 验收 dist/PDF批量加水印.exe
    DEV=1 python verify_exe.py      # 改成跑源码 app_main.py（开发模式）

依次验证：页面加载 → pywebview 桥接注入（后端方法列表）→ 调用后端真实预览
          → 截取界面图。任一步失败会打印原因。
"""
import os, io, sys, json, time, base64, subprocess, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(BASE, "dist", "PDF批量加水印.exe")
DEV_PY = r"C:\Users\HB\.workbuddy\binaries\python\envs\wmapp\Scripts\python.exe"
PORT = 9333
TITLE = "PDF 批量加水印"
OUTDIR = os.path.join(BASE, "_verify")
PROBE = os.path.join(OUTDIR, "probe3.pdf")
DROPDIR = os.path.join(OUTDIR, "dropdir")

os.makedirs(OUTDIR, exist_ok=True)

# ---- 造一个 3 页样本：浅 / 中 / 深 ----
if not os.path.exists(PROBE):
    import pymupdf
    doc = pymupdf.open()
    for c in [(0.93, 0.91, 0.86), (0.55, 0.52, 0.48), (0.20, 0.16, 0.14)]:
        pg = doc.new_page(width=595, height=842)
        pg.draw_rect(pg.rect, color=c, fill=c)
    doc.save(PROBE)
    doc.close()

# ---- 拖拽测试夹具：一个装 2 个 PDF + 1 个非 PDF 的文件夹 ----
def make_dropdir():
    import pymupdf
    os.makedirs(DROPDIR, exist_ok=True)
    for name, pages in (("拖拽A.pdf", 2), ("拖拽B.pdf", 1)):
        p = os.path.join(DROPDIR, name)
        if os.path.exists(p):
            continue
        d = pymupdf.open()
        for _ in range(pages):
            d.new_page(width=595, height=842)
        d.save(p)
        d.close()
    with open(os.path.join(DROPDIR, "说明.txt"), "w", encoding="utf-8") as f:
        f.write("非 PDF，应被忽略\n")

make_dropdir()

PARAMS = dict(text="©向上少年|侵权必究", font_size=18, rotate=30, alpha=0.10, grey=191,
              gap_x=130, gap_y=95, suffix="_带水印", emboss=True, light_color=255,
              light_alpha=0.20, dark_color=25, dark_alpha=0.12, stroke_div=22)

env = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=%d" % PORT)
CMD = [DEV_PY, os.path.join(BASE, "app_main.py")] if os.environ.get("DEV") else [EXE]

# 开跑前清场：onefile 的 bootloader 会有子进程残留，不清掉会连到旧的调试端口、验收错的实例
subprocess.run(["taskkill", "/F", "/IM", "PDF批量加水印.exe"], capture_output=True)
time.sleep(1)
p = subprocess.Popen(CMD, env=env)          # 故意不接管道：WebView2 子进程会占住管道导致 read 阻塞

_id = [0]


def cmd(ws, method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == _id[0]:
            return m


def evaluate(ws, expr, await_promise=False):
    r = cmd(ws, "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
    res = r.get("result", {})
    if "exceptionDetails" in res:
        return None, res["exceptionDetails"].get("text", "JS 异常")
    return res.get("result", {}).get("value"), None


ok = True
ws = None
try:
    import websocket
    deadline = time.time() + 90
    tab = None
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
        v, err = evaluate(ws, "typeof window.pywebview")
        if v == "object":
            tab = cand[0]
            break
        ws.close()
        ws = None

    if not tab:
        print("[1] 失败：90 秒内没等到界面就绪")
        ok = False
    else:
        print("[1] 页面已加载:", tab.get("title"), "|", tab["url"])

        expr = ("(function(){var a=(window.pywebview&&window.pywebview.api)||{};"
                "return JSON.stringify({methods:Object.keys(a),"
                "dots:document.querySelectorAll('.dot').length,"
                "theme:document.documentElement.dataset.theme,"
                "files:FILES.length,hasApiVar:typeof HAS_API!=='undefined'&&HAS_API});})()")
        v, err = evaluate(ws, expr)
        info = json.loads(v) if v else {}
        good = bool(info.get("methods"))
        print("[2] 后端方法:", info.get("methods") or "(空) ")
        print("    主题图标:", info.get("dots"), "| 当前主题:", info.get("theme"),
              "| 文件数:", info.get("files"), "| 前端识别到后端:", info.get("hasApiVar"))
        ok = ok and good

        expr = ("window.pywebview.api.preview(%s, %s, 1)"
                % (json.dumps(PARAMS, ensure_ascii=False), json.dumps(PROBE)))
        val, err = evaluate(ws, expr, await_promise=True)
        if isinstance(val, str) and val.startswith("data:image/png;base64,"):
            from PIL import Image, ImageStat
            raw = base64.b64decode(val.split(",", 1)[1])
            im = Image.open(io.BytesIO(raw))
            sd = ImageStat.Stat(im.convert("L")).stddev[0]
            print("[3] 后端真实预览 OK: %d 字节 %s stddev=%.2f" % (len(raw), im.size, sd))
            im.save(os.path.join(OUTDIR, "preview_mid.png"))
        else:
            print("[3] 后端真实预览失败:", err or repr(val)[:150])
            ok = False

        # [4] 空列表状态的界面截图
        r = cmd(ws, "Page.captureScreenshot", {"format": "png"})
        d = r.get("result", {}).get("data")
        if d:
            open(os.path.join(OUTDIR, "ui_real.png"), "wb").write(base64.b64decode(d))
            print("[4] 空列表界面截图:", os.path.join(OUTDIR, "ui_real.png"))

        # [5] 模拟「用户已选好文件」：注入列表 → 等预览生成 → 核对真实预览是否占满
        expr = ("window.setFiles([{nm:'样本·三页测试.pdf', pg:3, done:false, path:%s}]);"
                "'ok'" % json.dumps(PROBE))
        evaluate(ws, expr)
        for _ in range(20):                       # 预览有 260ms 防抖，最多等 10 秒
            time.sleep(0.5)
            v, _e = evaluate(ws, "$('pv').style.display")
            if v == "block":
                break
        v, _e = evaluate(ws, "JSON.stringify({pvbox:getComputedStyle($('pvbox')).display,"
                             "chips:getComputedStyle($('chips')).display,"
                             "bar:getComputedStyle($('pvBar')).display,"
                             "name:$('pvName').textContent,files:FILES.length,"
                             "h:Math.round($('pvbox').getBoundingClientRect().height)})")
        info2 = json.loads(v) if v else {}
        print("[5] 载入文件后:", info2)
        ok = ok and info2.get("pvbox") == "block" and info2.get("files") == 1
        r = cmd(ws, "Page.captureScreenshot", {"format": "png"})
        d = r.get("result", {}).get("data")
        if d:
            open(os.path.join(OUTDIR, "ui_real_files.png"), "wb").write(base64.b64decode(d))
            print("[6] 载入文件后界面截图:", os.path.join(OUTDIR, "ui_real_files.png"))

        # ---- [7] 拖拽：先用 CDP 合成一次真实 drop（能成就走完整链路） ----
        evaluate(ws, "window.setFiles([]); 'ok'")
        try:
            cmd(ws, "Input.setInterceptDrags", {"enabled": True})
            v, _e = evaluate(ws, "JSON.stringify((function(){var r=$('pickCard')"
                                 ".getBoundingClientRect();"
                                 "return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+60)};})())")
            pt = json.loads(v) if v else {"x": 200, "y": 200}
            ddata = {"items": [], "files": [PROBE], "dragOperationsMask": 1}
            for ev in ("dragEnter", "dragOver"):
                cmd(ws, "Input.dispatchDragEvent",
                    {"type": ev, "x": pt["x"], "y": pt["y"], "data": ddata})
            time.sleep(0.5)
            v, _e = evaluate(ws, "document.body.classList.contains('dragging')")
            print("    拖拽悬停高亮:", v)
            rr = cmd(ws, "Page.captureScreenshot", {"format": "png"})
            dd = rr.get("result", {}).get("data")
            if dd:
                open(os.path.join(OUTDIR, "ui_drop_hint.png"), "wb").write(base64.b64decode(dd))
                print("    落点高亮截图:", os.path.join(OUTDIR, "ui_drop_hint.png"))
            cmd(ws, "Input.dispatchDragEvent",
                {"type": "drop", "x": pt["x"], "y": pt["y"], "data": ddata})
            time.sleep(2.5)
            v, _e = evaluate(ws, "JSON.stringify({n:FILES.length,nm:(FILES[0]||{}).nm,"
                                 "dragClass:document.body.classList.contains('dragging')})")
            info3 = json.loads(v) if v else {}
            real_drop = info3.get("n") == 1
            print("[7] 合成真实 drop:", info3, "->", "原生链路可用" if real_drop else "不支持（走 [8] 直测）")
        except Exception as ex:
            real_drop = False
            print("[7] 合成真实 drop 不可用:", str(ex)[:120])

        # ---- [8] 后端拖拽入口自测：文件夹摊平 / 非 PDF 过滤 / 去重 ----
        evaluate(ws, "window.setFiles([]); 'ok'")
        v, _e = evaluate(ws, "window.pywebview.api.dropped([])", await_promise=True)
        v2, _e = evaluate(ws, "document.getElementById('log').textContent")
        evaluate(ws, "window.setFiles([]); 'ok'")
        v3, _e = evaluate(ws, "window.pywebview.api.dropped([%s])"
                         % json.dumps(DROPDIR), await_promise=True)
        time.sleep(0.6)
        v4, _e = evaluate(ws, "JSON.stringify({n:FILES.length,"
                              "nms:FILES.map(function(f){return f.nm;}),"
                              "pg:FILES.map(function(f){return f.pg;})})")
        info4 = json.loads(v4) if v4 else {}
        names = info4.get("nms") or []
        good = (len(names) == 2 and all(n.endswith(".pdf") for n in names)
                and sorted(info4.get("pg") or []) == [1, 2])
        print("[8] 拖文件夹:", info4, "| 空拖入提示:", repr(v2))
        ok = ok and good
        r = cmd(ws, "Page.captureScreenshot", {"format": "png"})
        d = r.get("result", {}).get("data")
        if d:
            open(os.path.join(OUTDIR, "ui_real_drop.png"), "wb").write(base64.b64decode(d))
            print("[9] 拖拽后界面截图:", os.path.join(OUTDIR, "ui_real_drop.png"))
        try:
            cmd(ws, "Input.setInterceptDrags", {"enabled": False})
        except Exception:
            pass

        ws.close()
finally:
    # onefile 的 bootloader 是「父进程 + 真正干活的子进程」，只 terminate 父进程会留下孤儿进程
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    try:
        p.wait(6)
    except Exception:
        p.kill()

print("\n==>", "验收通过" if ok else "验收失败")
sys.exit(0 if ok else 1)
