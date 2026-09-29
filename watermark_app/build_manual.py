# -*- coding: utf-8 -*-
"""把 使用说明.txt 渲染成排版精良的 PDF 手册（微软雅黑 + 马卡龙主题配色）。"""
import os
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, KeepTogether, HRFlowable)
from reportlab.lib.styles import ParagraphStyle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "C:/Windows/Fonts/msyh.ttc"
OUT = os.path.join(ROOT, "PDF批量加水印·使用说明.pdf")

# ---- 配色（与界面马卡龙主题一致）----
PURPLE = colors.HexColor("#6B45B0")   # 主色 葡萄紫
PURPLE_D = colors.HexColor("#553593")
MINT = colors.HexColor("#5BA57E")     # 开心果绿（强调）
LAV = colors.HexColor("#F3EEFA")      # 浅薰衣草底
TIPBG = colors.HexColor("#EEF6F0")    # 提示框浅绿底
INK = colors.HexColor("#2B2B33")
GREY = colors.HexColor("#6A6A75")
BOX = colors.HexColor("#E6DEF0")

pdfmetrics.registerFont(TTFont("msyh", FONT, subfontIndex=0))
pdfmetrics.registerFont(TTFont("msyhbd", FONT, subfontIndex=1))
pdfmetrics.registerFontFamily("msyh", normal="msyh", bold="msyhbd",
                              italic="msyh", boldItalic="msyhbd")

def S(name, **kw):
    base = dict(fontName="msyh", textColor=INK, leading=16)
    base.update(kw)
    return ParagraphStyle(name, **base)

def P(txt, style):
    return Paragraph(escape(txt), style)

# ---- 样式 ----
title_big = S("tb", fontName="msyhbd", fontSize=24, textColor=colors.white, leading=28)
title_sub = S("ts", fontSize=11.5, textColor=colors.white, leading=16)
intro = S("in", fontSize=10.5, textColor=GREY, leading=16)
sec = S("sec", fontName="msyhbd", fontSize=13.5, textColor=PURPLE_D, leading=18, spaceBefore=2)
body = S("bd", fontSize=10.3, leading=16)
body_ind = S("bdi", fontSize=10.3, leading=16, leftIndent=10)
bullet = S("bl", fontSize=10.3, leading=16, leftIndent=12, bulletIndent=2)
bullet_tip = S("blt", fontSize=10.3, leading=16, leftIndent=12, bulletIndent=2, textColor=INK)
step_t = S("st", fontSize=10.5, leading=16)
ex_txt = S("ex", fontSize=10.2, leading=17, textColor=INK, fontName="msyh")
foot = S("ft", fontSize=8.5, textColor=GREY, leading=12)
badge = S("bg", fontName="msyhbd", fontSize=11, textColor=colors.white, alignment=1, leading=14)

def section_title(text):
    bar = Table([[ "", Paragraph(text, sec) ]], colWidths=[5, None])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), PURPLE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return KeepTogether([Spacer(1, 10), bar, Spacer(1, 5)])

def steps(items):
    """items: list of (num:int, list_of_paragraphs)"""
    out = []
    for n, paras in items:
        badge_cell = Table([[ Paragraph(str(n), badge) ]], colWidths=[22])
        badge_cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PURPLE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        row = Table([[badge_cell, paras]], colWidths=[26, None])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (0, 0), 1),
            ("LEFTPADDING", (1, 0), (1, 0), 8),
            ("RIGHTPADDING", (1, 0), (1, 0), 4),
            ("TOPPADDING", (1, 0), (1, 0), 2),
            ("BOTTOMPADDING", (1, 0), (1, 0), 2),
        ]))
        out.append(row)
        out.append(Spacer(1, 7))
    return out

def bullets(items, style=bullet):
    out = []
    for it in items:
        out.append(Paragraph("· " + escape(it), style))
        out.append(Spacer(1, 3))
    return out

def box(lines, bg, txt_style=ex_txt):
    data = [[Paragraph(escape(l), txt_style)] for l in lines]
    t = Table(data, colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.75, BOX),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBEFORE", (0, 0), (0, -1), 3, MINT),
    ]))
    return KeepTogether([Spacer(1, 2), t, Spacer(1, 2)])

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BOX)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("msyh", 8.5)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 10.5 * mm,
                      "PDF 批量加水印 v1.0.0.0  ·  Design by HongBing  ·  ©HB 2026")
    canvas.drawRightString(A4[0] - 18 * mm, 10.5 * mm, "第 %d 页" % doc.page)
    canvas.restoreState()

def build():
    doc = SimpleDocTemplate(OUT, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=20 * mm,
                            title="PDF 批量加水印 · 使用说明", author="HongBing")
    W = doc.width
    el = []

    # 标题卡
    card = Table([[Paragraph("PDF 批量加水印", title_big)],
                  [Paragraph("使用说明  ·  课件 PDF 版权水印工具", title_sub)],
                  [Paragraph("©向上少年  |  侵权必究", title_sub)]],
                 colWidths=[W])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PURPLE),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 1),
        ("TOPPADDING", (0, 2), (0, 2), 0),
        ("BOTTOMPADDING", (0, 2), (0, 2), 12),
    ]))
    el.append(card)
    el.append(Spacer(1, 8))
    el.append(P("本工具给 PDF 课件批量平铺版权水印，不修改、不删除原文件，三步即可上手。",
                intro))

    # 一、三步上手
    el.append(section_title("一、三步上手"))
    el += steps([
        (1, [P("双击  PDF批量加水印.exe", step_t),
             P("第一次打开会弹蓝色「Windows 已保护你的电脑」，点【更多信息】→【仍要运行】"
               "（程序没有数字签名，不是病毒）。首次启动要解压几秒，请稍等。", body)]),
        (2, [P("添加 PDF", step_t),
             P("· 点【PDF文件】—— 可多选，一次挑几个", body_ind),
             P("· 点【整个文件夹】—— 一整批全加进来", body_ind),
             P("· 或者直接把文件 / 文件夹【拖进窗口】", body_ind),
             P("列表里可以勾选只要哪几份，也可以点单行右边的 × 移除。", body)]),
        (3, [P("在中间「水印参数」里挑一个预设 → 点【开始处理】", step_t),
             P("窗口底部会显示进度，跑完会有提示。", body)]),
    ])

    # 二、成品在哪
    el.append(section_title("二、成品在哪（文件名自己拼）"))
    el.append(P("默认就在原文件旁边，文件名后面多一段 _带水印：", body))
    el.append(box(["第1课.pdf   →   第1课_带水印.pdf"], LAV))
    el.append(Spacer(1, 4))
    el.append(P("想改命名，就改「水印参数」里【输出文件名】那个输入框：输什么，就直接拼在源文件名后面。", body))
    el.append(box([
        "_带水印_20260928     →   第1课_带水印_20260928.pdf",
        "_已盖章              →   第1课_已盖章.pdf",
        "（清空）             →   第1课.pdf",
    ], LAV))
    el.append(Spacer(1, 4))
    el += bullets([
        "界面底部有一行提示，会实时写出「第1课.pdf 最终会变成什么」。",
        "原文件不会被修改，也不会被删除，放心用。",
        "已经生成过的成品再选一次会自动跳过，不会重复叠加。",
    ])

    # 三、四个内置预设
    el.append(section_title("三、四个内置预设（一般直接选就行）"))
    el += bullets([
        "课件通用 · 浮雕双色 —— 最常用，深浅背景都看得见",
        "大页面 1440×810 · 浮雕 —— 页面更大的课件",
        "深米色背景 · 普通浅灰",
        "浅米色古风 · 普通深灰",
    ])
    el.append(Spacer(1, 3))
    el.append(P("想改水印文字 / 字号 / 角度 / 疏密 / 深浅：在「水印参数」里调，右侧预览会跟着实时更新；"
                "调好了点下拉框右边的【软盘图标】存成自己的预设（起个名即可）。自己的预设可以用旁边的"
                "【垃圾桶图标】删掉；四个内置的删不掉（垃圾桶图标是灰的）。", body))
    el.append(Spacer(1, 3))
    el.append(P("右上角还有四个小图标，是界面配色主题，随便换着玩，不影响水印效果。", body))

    # 四、几个小提醒
    el.append(section_title("四、几个小提醒"))
    el.append(box([
        "建议【先拿 1 个文件试一下】，预览满意了再整批处理。",
        "页面整体偏白、或里面夹着深色照片时，用【浮雕双色】模式最稳：浅处见深描边，深处见白字，怎么都不会隐身。",
        "只支持 PDF。PPT / Word 请先另存为 PDF 再处理。",
        "处理大批量时别关窗口，等进度走完。",
    ], TIPBG, bullet_tip))

    # 五、电脑要求
    el.append(section_title("五、电脑要求"))
    el += bullets([
        "Windows 10 / 11",
        "需要 WebView2 运行时（Win11 和较新的 Win10 都自带）。",
        "万一打开是一整片空白：去微软官网搜索「Microsoft Edge WebView2 Runtime」下载安装，"
        "装完不用重启电脑，再打开本程序即可。",
    ])

    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    print("OK ->", OUT, os.path.getsize(OUT), "bytes")

if __name__ == "__main__":
    build()
