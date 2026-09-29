"""
PDF 平铺文字水印工具（通用版）

用法:
  # 单个文件（默认参数：©向上少年|侵权必究 / 18pt / 30° / 透明度0.10）
  python pdf_watermark.py 课件.pdf

  # 多个文件
  python pdf_watermark.py 课件1.pdf 课件2.pdf 课件3.pdf

  # 整个目录（处理目录下所有 PDF，不含已加水印的）
  python pdf_watermark.py --dir "C:\\我的课件"

  # 自定义参数
  python pdf_watermark.py 课件.pdf --text "©某某机构|侵权必究" --alpha 0.15 --font-size 20

  # 输出命名：在源文件名后追加后缀（默认 _带水印），想加日期就自己输
  python pdf_watermark.py --dir "C:\\我的课件" --suffix _带水印_20260928

  # 查看所有参数
  python pdf_watermark.py --help

说明:
  - 默认输出为「原文件名_带水印.pdf」，不会覆盖原文件
  - 输出文件名 = 源文件名 + 后缀（--suffix 控制），想加日期就自己把日期写进后缀
  - 采用 PIL 预渲染水印层 PNG + PyMuPDF insert_image 方案，
    旋转/透明度在任何 PDF 阅读器下都能正确显示
"""

import argparse
import glob
import math
import os
import sys
import time
import tempfile
import uuid

try:
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("缺少依赖，请先安装：")
    print("  pip install pymupdf Pillow")
    sys.exit(1)


# ---------------- 默认参数 ----------------
DEFAULT_TEXT = "©向上少年|侵权必究"
DEFAULT_FONT_SIZE = 18
DEFAULT_ROTATE = 30
DEFAULT_ALPHA = 0.10
DEFAULT_GREY = 191      # 浅灰 (255*0.75)
DEFAULT_GAP_X = 130
DEFAULT_GAP_Y = 95
DEFAULT_DPI = 150
# 系统字体候选（按优先级）
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑（推荐，字符全）
    r"C:\Windows\Fonts\simhei.ttf", # 黑体（不支持 ©）
    r"C:\Windows\Fonts\simsun.ttc", # 宋体
]
DEFAULT_FONT_INDEX = 0  # .ttc 里的字体序号，0=Regular
# ------------------------------------------


def pick_font(font_path: str = None) -> str:
    """挑选可用字体。"""
    if font_path:
        if os.path.exists(font_path):
            return font_path
        raise FileNotFoundError(f"字体不存在: {font_path}")
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到系统中文字体，请用 --font 指定字体文件路径")


def build_watermark_layer(page_w: float, page_h: float, args) -> Image.Image:
    """
    生成与页面同比例、含旋转平铺文字的水印层 PNG。
    """
    scale = args.dpi / 72
    W = int(page_w * scale)
    H = int(page_h * scale)
    font_size_px = int(args.font_size * scale)
    gap_x_px = int(args.gap_x * scale)
    gap_y_px = int(args.gap_y * scale)

    # 画布放大一圈，避免旋转裁切
    margin = int(math.hypot(W, H) * 0.4)
    canvas = Image.new("RGBA", (W + 2 * margin, H + 2 * margin), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(args.font, font_size_px, index=args.font_index)

    bbox = font.getbbox(args.text)
    tw_px = bbox[2] - bbox[0]
    th_px = bbox[3] - bbox[1]

    step_x = tw_px + gap_x_px
    step_y = th_px + gap_y_px
    cw, ch = canvas.size
    cx, cy = cw // 2, ch // 2

    # 平铺（奇偶行错开半格）
    row = 0
    y = -cy
    while y < cy:
        x = -cx + (step_x // 2 if row % 2 else 0)
        while x < cx:
            if args.emboss:
                # 浮雕双色：白字 + 深描边。浅底看得见深边，深底看得见白字，深浅通吃
                draw.text(
                    (cx + x, cy + y - th_px),
                    args.text, font=font,
                    fill=(args.light_color, args.light_color, args.light_color, int(255 * args.light_alpha)),
                    stroke_width=max(1, int(font_size_px // args.stroke_div)),
                    stroke_fill=(args.dark_color, args.dark_color, args.dark_color, int(255 * args.dark_alpha)),
                )
            else:
                color = (args.grey, args.grey, args.grey, int(255 * args.alpha))
                draw.text((cx + x, cy + y - th_px), args.text, font=font, fill=color)
            x += step_x
        y += step_y
        row += 1

    # 绕中心旋转（PIL 顺时针为负）
    rotated = canvas.rotate(-args.rotate, resample=Image.BICUBIC, expand=False)

    # 中心裁剪回页面尺寸
    rw, rh = rotated.size
    left = (rw - W) // 2
    top = (rh - H) // 2
    return rotated.crop((left, top, left + W, top + H))


def add_watermark(input_pdf: str, output_pdf: str, args) -> bool:
    """给单个 PDF 加水印。"""
    try:
        doc = pymupdf.open(input_pdf)
    except Exception as e:
        print(f"  ✗ 打开失败: {e}")
        return False

    total = doc.page_count
    if total == 0:
        print("  ✗ PDF 无页面")
        doc.close()
        return False

    page0 = doc.load_page(0)
    W, H = float(page0.rect.width), float(page0.rect.height)

    layer = build_watermark_layer(W, H, args)

    # 临时文件存水印层（文件名带 uuid，避免并发/复跑时互相覆盖）
    tmp_png = os.path.join(tempfile.gettempdir(), "_wm_layer_%s.png" % uuid.uuid4().hex)
    layer.save(tmp_png, optimize=True)

    for i, page in enumerate(doc):
        page.insert_image(
            page.rect,
            filename=tmp_png,
            overlay=True,
            keep_proportion=False,
        )

    # 先存到临时名再原子替换：避免在某些平台（如 Windows）上
    # 直接 save 到「已存在的输出文件」时抛 FzErrorSystem（复跑/overwrite 场景）。
    # 替换时若目标仍被占用（文件锁/杀软扫描），小退避重试几次，避免偶发失败。
    out_tmp = output_pdf + ".part"
    doc.save(out_tmp, deflate=True, garbage=4)
    doc.close()
    for _ in range(6):
        try:
            if os.path.exists(output_pdf):
                os.remove(output_pdf)
            os.replace(out_tmp, output_pdf)
            break
        except OSError:
            time.sleep(0.15)
    else:
        if os.path.exists(out_tmp):
            try:
                os.remove(out_tmp)
            except OSError:
                pass

    try:
        os.remove(tmp_png)
    except OSError:
        pass

    size_mb = os.path.getsize(output_pdf) / 1024 / 1024
    print(f"  ✓ {os.path.basename(input_pdf)} → {os.path.basename(output_pdf)} "
          f"({total} 页, {size_mb:.2f} MB)")
    return True


# ---- 输出命名规范（CLI 与 GUI 共用，保证两边成品路径完全一致）----
def build_output_path(src: str, args) -> str:
    """输出 = 源文件名 + 后缀，与源文件同目录。

    例如 src=第1课.pdf, suffix="_带水印" → 第1课_带水印.pdf。
    想加日期就自己把日期写进后缀，如 --suffix _带水印_20260928。
    """
    folder = os.path.dirname(os.path.abspath(src))
    stem, ext = os.path.splitext(os.path.basename(src))
    suffix = getattr(args, "suffix", "") or ""
    return os.path.join(folder, f"{stem}{suffix}{ext}")


def is_output(src: str, args) -> bool:
    """这个 PDF 是不是本工具生成的成品（用于整目录处理时跳过）。"""
    suffix = getattr(args, "suffix", "") or ""
    return bool(suffix) and suffix in os.path.basename(src)


def main():
    p = argparse.ArgumentParser(
        description="给 PDF 添加平铺文字水印",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python pdf_watermark.py 课件.pdf
  python pdf_watermark.py --dir "C:\\我的课件"
  python pdf_watermark.py 课件.pdf --text "©某某机构" --alpha 0.15
""",
    )
    p.add_argument("files", nargs="*", help="PDF 文件路径（可多个）")
    p.add_argument("--dir", help="处理该目录下所有 PDF")
    p.add_argument("--text", default=DEFAULT_TEXT, help=f"水印文字 (默认: {DEFAULT_TEXT})")
    p.add_argument("--font-size", type=float, default=DEFAULT_FONT_SIZE, help=f"字号 pt (默认: {DEFAULT_FONT_SIZE})")
    p.add_argument("--rotate", type=float, default=DEFAULT_ROTATE, help=f"文字倾斜角 (默认: {DEFAULT_ROTATE})")
    p.add_argument("--alpha", type=float, default=DEFAULT_ALPHA, help=f"透明度 0-1 (默认: {DEFAULT_ALPHA})")
    p.add_argument("--grey", type=int, default=DEFAULT_GREY, help=f"灰度 0-255 (默认: {DEFAULT_GREY})")
    p.add_argument("--gap-x", type=float, default=DEFAULT_GAP_X, help=f"水平间距 pt (默认: {DEFAULT_GAP_X})")
    p.add_argument("--gap-y", type=float, default=DEFAULT_GAP_Y, help=f"垂直间距 pt (默认: {DEFAULT_GAP_Y})")
    p.add_argument("--font", help="字体文件路径（默认自动选系统中文字体）")
    p.add_argument("--font-index", type=int, default=DEFAULT_FONT_INDEX, help=f".ttc 字体序号 (默认: {DEFAULT_FONT_INDEX})")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"渲染 DPI (默认: {DEFAULT_DPI})")
    p.add_argument("--suffix", default="_带水印", help=f"输出文件名后缀 (默认: _带水印)")
    p.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出文件")
    # 浮雕双色水印（深浅背景都可见）
    p.add_argument("--emboss", action="store_true", help="浮雕双色水印：白字+深描边，深浅背景都可见")
    p.add_argument("--light-color", type=int, default=255, help="浮雕白字灰度 0-255 (默认 255)")
    p.add_argument("--light-alpha", type=float, default=0.20, help="浮雕白字透明度 0-1 (默认 0.20)")
    p.add_argument("--dark-color", type=int, default=25, help="浮雕描边深色 0-255 (默认 25)")
    p.add_argument("--dark-alpha", type=float, default=0.12, help="浮雕描边透明度 0-1 (默认 0.12)")
    p.add_argument("--stroke-div", type=int, default=22, help="描边宽度 = 字号px / 该值 (默认 22)")

    args = p.parse_args()

    # 收集文件
    files = list(args.files)
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"✗ 目录不存在: {args.dir}")
            sys.exit(1)
        # 遍历一次目录：Windows 文件系统大小写不敏感，
        # 用 *.pdf + *.PDF 两个 glob 会重复匹配同一批文件
        for name in sorted(os.listdir(args.dir)):
            full = os.path.join(args.dir, name)
            if name.lower().endswith(".pdf") and os.path.isfile(full):
                files.append(full)

    # 过滤：排除本工具自己生成的成品（后缀命中，即已经加过水印的）
    files = [f for f in files if not is_output(f, args)]

    if not files:
        p.print_help()
        print("\n✗ 没有指定 PDF 文件。用 --dir 指定目录，或直接列出文件。")
        sys.exit(1)

    args.font = pick_font(args.font)

    print(f"水印文字: {args.text}")
    if args.emboss:
        print(f"模式: 浮雕双色（白字 {args.light_color}/{args.light_alpha} + 深描边 {args.dark_color}/{args.dark_alpha}）")
        print(f"参数: {args.font_size}pt / 倾斜 {args.rotate}° / 间距 {args.gap_x}x{args.gap_y} / 描边=字号/{args.stroke_div}")
    else:
        print(f"参数: {args.font_size}pt / 倾斜 {args.rotate}° / 透明度 {args.alpha} / "
              f"灰度 {args.grey} / 间距 {args.gap_x}x{args.gap_y}")
    print(f"字体: {os.path.basename(args.font)}")
    print(f"输出: 原名+{args.suffix} → 与源文件同目录")
    print(f"待处理 {len(files)} 个文件\n")

    ok = fail = 0
    for f in files:
        if not os.path.exists(f):
            print(f"  ✗ 文件不存在: {f}")
            fail += 1
            continue

        out = build_output_path(f, args)

        if os.path.exists(out) and not args.overwrite:
            print(f"  ⚠ 已存在，跳过（加 --overwrite 覆盖）: {os.path.basename(out)}")
            continue

        if add_watermark(f, out, args):
            ok += 1
        else:
            fail += 1

    print(f"\n完成: 成功 {ok} 个，失败 {fail} 个")


if __name__ == "__main__":
    main()
