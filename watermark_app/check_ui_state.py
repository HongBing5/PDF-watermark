# -*- coding: utf-8 -*-
"""
无头 Edge 行为探针：把 ui.html 加载后跑一段脚本，把结果写进 <title>，再 dump-dom 取回。
用于在不开窗口的情况下验证前端状态机（默认空列表、按钮禁用、预设只读等）。
不依赖 Python 后端，纯前端回归。
"""
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# 待验证的行为：每步返回一个表达式的结果
PROBE = r"""
<script>
function snap(tag){
  return {
    tag: tag,
    hasApi: HAS_API,                       // 无后端时应为 false，界面自动走 canvas 模拟
    theme: document.documentElement.dataset.theme,
    dots: document.querySelectorAll(".dot").length,
    files: FILES.length,
    count: $("fCount").textContent,
    selAllDisabled: $("btnSelAll").disabled,
    goDisabled: $("go").disabled,
    delPresetDisabled: $("btnDel").disabled,
    delPresetTitle: $("btnDel").title,
    presetValue: $("presetSel").value,
    empty: !!document.querySelector(".empty"),
    log: $("log").textContent,
    dropLeft: document.querySelectorAll(".drop").length,
    pickBtns: document.querySelectorAll(".pickbar .btn").length,
    iconBtns: document.querySelectorAll(".presetbar .iconbtn").length,  // 保存/删除 图标按钮
    saveRowShown: $("saveRow").style.display !== "none",
    saveIconOn: $("btnSave").classList.contains("on"),
    pvbox: getComputedStyle($("pvbox")).display,      // 无后端时预览回退到 canvas
    chips: getComputedStyle($("chips")).display,
    outHint: $("outHint").textContent,                // 输出命名提示（随模式实时变）
    customCount: custom.length
  };
}
var OUT = [];
OUT.push(snap("初始"));
window.setFiles([{nm:"a.pdf",pg:3,done:false,path:"C:/x/a.pdf"},
                 {nm:"b.pdf",pg:5,done:true, path:"C:/x/b.pdf"}]);
OUT.push(snap("载入2个文件"));
custom.push({name:"我的预设A", emboss:true, text:"t", fs:18, rot:30, gx:130, gy:95,
             la:0.2, da:0.12, sd:22, dc:25, al:0.1, gr:191, sfx:"_带水印"});
refreshSelect("c0");
OUT.push(snap("选中自定义预设"));
custom = []; refreshSelect("b0");
OUT.push(snap("内置预设"));
$("btnClr").click();
OUT.push(snap("清空后"));

// 图标按钮链路：保存 → 命名 → 点亮状态收起 → 删除
$("btnSave").click();
OUT.push(snap("点保存图标"));
$("saveName").value = "回归预设";
$("btnSaveOk").click();
OUT.push(snap("存好后"));
$("btnDel").click();
OUT.push(snap("删掉后"));

// 输出命名：后缀输入框改变，提示文案跟着变
function setVal(id, v, ev){ $(id).value = v; $(id).dispatchEvent(new Event(ev)); }
setVal("sfx", "_带水印", "input");
OUT.push(snap("后缀=默认"));
setVal("sfx", "_带水印_20260928", "input");
OUT.push(snap("后缀=带日期"));
setVal("sfx", "", "input");
OUT.push(snap("后缀=空(应原名)"));
document.title = "PROBE" + JSON.stringify(OUT);
</script>
"""


def main():
    h = open(os.path.join(BASE, "ui.html"), encoding="utf-8").read()
    p = os.path.join(BASE, "_probe_state.html")
    open(p, "w", encoding="utf-8", newline="\n").write(h.replace("</body>", PROBE + "</body>"))

    out = subprocess.run(
        [EDGE, "--headless=new", "--disable-gpu", "--virtual-time-budget=4000", "--dump-dom",
         "file:///" + p.replace("\\", "/")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"<title[^>]*>PROBE(.*?)</title>", out.stdout or "", re.S)
    os.remove(p)
    if not m:
        print("探针未执行，stdout 长度 =", len(out.stdout or ""))
        return 1

    import json
    for s in json.loads(m.group(1)):
        print("[%s]" % s.pop("tag"))
        for k, v in s.items():
            print("    %-18s %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
