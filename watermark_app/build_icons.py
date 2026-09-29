# -*- coding: utf-8 -*-
"""把品牌 svg 内联成 <symbol> 雪碧图(sprite)插入 ui.html，避免打包 exe 时还要带外部文件。

当前四套主题：麦当劳 / 雪碧 / 马卡龙 / 奥利奥（百事已于 2026-09-24 移除，可乐.svg 未再使用）。
源文件统一命名 theme_<主题>.svg（2026-09-28 起）。
换图标：覆盖同名 svg 后重跑本脚本（幂等，会先移除旧 sprite）。
顺带清掉 svg 里没用的编辑器属性（p-id / t / class），能省 10%~20% 体积。
"""
import re, os

BASE = os.path.dirname(os.path.abspath(__file__))
MAP = [("theme_mcd.svg", "ico-mcd"), ("theme_sprite.svg", "ico-sprite"),
       ("theme_macaron.svg", "ico-macaron"), ("theme_oreo.svg", "ico-oreo")]


def clean(inner):
    """去掉 iconfont 导出的冗余属性，纯 path 保留不动。"""
    inner = re.sub(r'\sp-id="\d+"', '', inner)
    inner = re.sub(r'\st="\d+"', '', inner)
    inner = re.sub(r'\sclass="icon"', '', inner)
    return inner


syms = []
for fn, sid in MAP:
    s = open(os.path.join(BASE, fn), encoding="utf-8").read()
    vb = re.search(r'viewBox="([^"]+)"', s).group(1)
    inner = re.sub(r'^.*?<svg[^>]*>', '', s, flags=re.S)
    inner = re.sub(r'</svg>\s*$', '', inner)
    if not inner.rstrip().endswith('>'):
        raise SystemExit("解析失败：%s 的 svg 内容不完整" % fn)
    syms.append('<symbol id="%s" viewBox="%s">%s</symbol>' % (sid, vb, clean(inner)))

sprite = ('<!-- 品牌图标雪碧图（由 %s 生成） -->\n'
          '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">\n'
          % ",".join(f for f, _ in MAP)) + "\n".join(syms) + "\n</svg>\n"

p = os.path.join(BASE, "ui.html")
h = open(p, encoding="utf-8").read()
# 幂等：先移除旧的 sprite
h2 = re.sub(r'<!-- 品牌图标雪碧图.*?</svg>\n', '', h, flags=re.S)
if h2 == h and "品牌图标雪碧图" in h:
    raise SystemExit("旧 sprite 未能移除，请检查 ui.html 结构")
h = h2
if "<body>\n" not in h:
    raise SystemExit("ui.html 里找不到 <body> 锚点")
h = h.replace("<body>\n", "<body>\n" + sprite, 1)
open(p, "w", encoding="utf-8", newline="\n").write(h)
print("ok, sprite bytes =", len(sprite), "| html bytes =", len(h),
      "| symbols =", len(syms))
