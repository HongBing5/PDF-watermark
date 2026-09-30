# -*- coding: utf-8 -*-
"""
生成程序图标 app.ico —— 印章风：朱红底 + 白色「印」字（华文中宋，有金石味）。
换字/换色改下面常量后重跑即可。
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

# GitHub Actions 的 Windows 机器控制台是 cp1252，中文 print 会直接
# UnicodeEncodeError 中断构建。这里把 stdout 强制成 UTF-8（幂等、失败不影响）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")

# 印章红：外浅内深的渐变，模拟印泥压出来的层次
C_TOP = (216, 58, 43)
C_BOT = (168, 24, 14)
CHAR = "印"
# 华文中宋（衬线、笔画方正，最接近印章刻字）；没有就退回宋体 / 微软雅黑。
# 后面的 macOS 路径是给 GitHub Actions 的云 Mac 用的（那边没有 C:\Windows\Fonts，
# 不加就会退化成 load_default 的无中文字形，图标上的「印」字会变成空白）。
FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\STZHONGS.TTF",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def pick_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    # 兜底（无中文字形，图标会缺字）：显式报警，别让它静静糊过去
    print("WARN: no CJK font found, fallback to default font -> icon glyph may be blank")
    return ImageFont.load_default()


def make(size):
    S = size
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # 底：竖向渐变
    grad = Image.new("RGB", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / max(S - 1, 1)
        gd.line([(0, y), (S, y)],
                fill=tuple(int(C_TOP[i] + (C_BOT[i] - C_TOP[i]) * t) for i in range(3)))

    r = int(S * 0.22)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=255)
    im.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(im)
    # 印章内框：一圈细白边（小尺寸下会糊，16px 就不画了）
    if S >= 32:
        ins = S * 0.10
        w = max(1, int(S * 0.035))
        d.rounded_rectangle([ins, ins, S - 1 - ins, S - 1 - ins],
                            radius=int(r * 0.55), outline=(255, 255, 255, 70), width=w)

    f = pick_font(int(S * 0.60))
    bb = d.textbbox((0, 0), CHAR, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((S - w) / 2 - bb[0], (S - h) / 2 - bb[1] - S * 0.01),
           CHAR, font=f, fill=(255, 255, 255, 250))
    return im


if __name__ == "__main__":
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ims = [make(s) for s in sizes]
    # 注意：Pillow 保存多尺寸 ICO 时会以「基准图」的尺寸为上限裁掉更大的项
    # （size[0] > width → continue），所以基准图必须给最大的那张，其余用 append_images 带进去。
    # 早先拿 ims[0]（16×16）当基准，结果 ico 里只剩 16×16 一个尺寸，任务栏图标糊成一团。
    ims[-1].save(OUT, format="ICO", append_images=ims, sizes=[(s, s) for s in sizes])
    ims[-1].save(os.path.join(os.path.dirname(OUT), "_icon_preview.png"))
    print("icon ->", OUT, "| 尺寸:", sizes)
