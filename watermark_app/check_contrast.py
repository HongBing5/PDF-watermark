# -*- coding: utf-8 -*-
"""
对比度体检 —— 把 ui.html 里三套主题的色值解析出来，按 WCAG 2.1 算对比度。
用途：改主题配色后跑一遍，避免出现「浅底浅字看不见」。

用法：  python check_contrast.py
退出码：有任一关键文字对 < 4.5:1 时为 1
"""
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "ui.html")

# (前景变量, 背景变量, 说明)  —— 都是「文字压在某底色上」的真实组合
PAIRS = [
    ("text",  "bg",        "正文 / 页面底"),
    ("text",  "card",      "正文 / 卡片"),
    ("text",  "surface",   "正文 / 内嵌面板"),
    ("muted", "card",      "次要文字 / 卡片"),
    ("muted", "surface",   "次要文字 / 内嵌面板"),
    ("muted", "bg",        "次要文字 / 页面底"),
    ("faint", "card",      "提示文字 / 卡片"),
    ("faint", "bg",        "提示文字 / 页面底"),
    ("faint", "surface",   "提示文字 / 内嵌面板"),
    ("mint-d",  "tint-mint", "绿标签文字 / 绿底"),
    ("rose-d",  "tint-rose", "红标签文字 / 红底"),
    ("taro-d",  "tint-taro", "紫标签文字 / 紫底"),
    ("rose-d",  "card",      "主色文字 / 卡片"),
    ("mint-d",  "card",      "辅助色文字 / 卡片"),
]
# 白字按钮：白字压在主色上
WHITE_BUTTONS = [("rose-d", "主按钮"), ("mint-d", "文件区按钮"), ("taro-d", "紫按钮")]
# 主色按钮的渐变主轴（--grad-btn）：白字会落在渐变最浅的那一端，所以两端都要查
GRADIENTS = [("grad-btn", "主色按钮渐变")]
THRESHOLD = 4.5


def hex2rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = lum(hex2rgb(a)), lum(hex2rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_vars(css, selector):
    """取出主题块里的变量。纯色存成 name -> #hex；
    渐变（--grad-*）额外存一份 name:stops -> [所有色标]，供渐变端点的对比度检查用。"""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.S)
    if not m:
        return {}
    body = m.group(1)
    out = {}
    for name, val in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body):
        v = val.strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", v):
            out[name[2:]] = v
        elif name.startswith("--grad-"):
            stops = re.findall(r"#[0-9A-Fa-f]{6}", v)
            if stops:
                out[name[2:] + ":stops"] = stops
    return out


def main():
    css = open(HTML, encoding="utf-8").read()
    themes = {
        "马卡龙(默认)": parse_vars(css, ":root"),
        "麦当劳": parse_vars(css, 'html[data-theme="mcd"]'),
        "雪碧": parse_vars(css, 'html[data-theme="sprite"]'),
        "奥利奥": parse_vars(css, 'html[data-theme="oreo"]'),
    }
    bad = 0
    for tname, V in themes.items():
        print("\n=== %s ===" % tname)
        for fg, bg, desc in PAIRS:
            if fg not in V or bg not in V:
                print("  ? %-22s 缺变量" % desc)
                continue
            r = ratio(V[fg], V[bg])
            flag = "OK " if r >= THRESHOLD else "低!"
            if r < THRESHOLD:
                bad += 1
            print("  %s %-22s %5.2f:1   %s on %s" % (flag, desc, r, V[fg], V[bg]))
        for var, desc in WHITE_BUTTONS:
            if var not in V:
                continue
            r = ratio("#FFFFFF", V[var])
            flag = "OK " if r >= THRESHOLD else "低!"
            if r < THRESHOLD:
                bad += 1
            print("  %s 白字按钮 %-14s %5.2f:1   #FFFFFF on %s" % (flag, desc, r, V[var]))
        for var, desc in GRADIENTS:
            stops = V.get(var + ":stops") or []
            if not stops:
                print("  ? %-18s 缺变量" % desc)
                continue
            worst = min(stops, key=lambda c: ratio("#FFFFFF", c))
            r = ratio("#FFFFFF", worst)
            flag = "OK " if r >= THRESHOLD else "低!"
            if r < THRESHOLD:
                bad += 1
            print("  %s %-18s %5.2f:1   白字 on 最浅端 %s" % (flag, desc, r, worst))
    print("\n不达标项：%d 个（阈值 %.1f:1）" % (bad, THRESHOLD))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
