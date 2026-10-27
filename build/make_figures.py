"""Render the two architecture diagrams for the DOCX build.

Canvas is 1400 units wide and is always placed at 17 cm, so 1 unit ≈ 0.344 pt:
a 29-unit font prints at ~10 pt, a 21-unit font at ~7.2 pt. All sizes below are
chosen so the smallest annotation still prints above 7 pt.
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

BASE = pathlib.Path(r"E:\记忆库")
OUT = BASE / "figures"
OUT.mkdir(exist_ok=True)

S = 2
FONT_R = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

NAVY = (0x1F, 0x38, 0x64)
BLUE = (0x2E, 0x54, 0x96)
TEAL = (0x1F, 0x6B, 0x63)
GREY = (0x5F, 0x6B, 0x7E)
INK = (0x1A, 0x1A, 0x1A)
LINE = (0xC2, 0xCD, 0xDC)
BAND = (0xF5, 0xF8, 0xFD)
BAND2 = (0xEC, 0xF2, 0xFA)
WHITE = (0xFF, 0xFF, 0xFF)
ACCENT = (0x8A, 0x9A, 0xB8)


def f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, int(size * S))


def box(d, xy, r=12, fill=BAND, outline=LINE, width=1.6, dash=False):
    x0, y0, x1, y1 = [v * S for v in xy]
    if dash:
        _dashed_rect(d, (x0, y0, x1, y1), outline, width * S, r * S)
    else:
        d.rounded_rectangle((x0, y0, x1, y1), radius=r * S, fill=fill,
                            outline=outline, width=max(1, int(width * S)))


def _dashed_rect(d, xy, color, w, r, seg=16):
    x0, y0, x1, y1 = xy
    step = seg * S
    for x in range(int(x0) + int(r), int(x1) - int(r), step * 2):
        d.line((x, y0, min(x + step, x1 - r), y0), fill=color, width=int(w))
        d.line((x, y1, min(x + step, x1 - r), y1), fill=color, width=int(w))
    for y in range(int(y0) + int(r), int(y1) - int(r), step * 2):
        d.line((x0, y, x0, min(y + step, y1 - r)), fill=color, width=int(w))
        d.line((x1, y, x1, min(y + step, y1 - r)), fill=color, width=int(w))
    d.arc((x0, y0, x0 + 2 * r, y0 + 2 * r), 180, 270, fill=color, width=int(w))
    d.arc((x1 - 2 * r, y0, x1, y0 + 2 * r), 270, 360, fill=color, width=int(w))
    d.arc((x0, y1 - 2 * r, x0 + 2 * r, y1), 90, 180, fill=color, width=int(w))
    d.arc((x1 - 2 * r, y1 - 2 * r, x1, y1), 0, 90, fill=color, width=int(w))


def text(d, xy, s, size=21, bold=False, fill=INK, anchor="la"):
    d.text((xy[0] * S, xy[1] * S), s, font=f(size, bold), fill=fill, anchor=anchor)


def text_w(s, size, bold=False):
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    return tmp.textlength(s, font=f(size, bold)) / S


def center_text(d, cx, y, s, size=21, bold=False, fill=INK):
    d.text((cx * S, y * S), s, font=f(size, bold), fill=fill, anchor="ma")


def arrow_down(d, x, y0, y1, color=ACCENT):
    d.line((x * S, y0 * S, x * S, (y1 - 10) * S), fill=color, width=int(2.2 * S))
    d.polygon([(x * S, y1 * S), ((x - 7) * S, (y1 - 12) * S), ((x + 7) * S, (y1 - 12) * S)],
              fill=color)


def arrow_right(d, y, x0, x1, color=ACCENT):
    d.line((x0 * S, y * S, (x1 - 10) * S, y * S), fill=color, width=int(2.2 * S))
    d.polygon([(x1 * S, y * S), ((x1 - 12) * S, (y - 7) * S), ((x1 - 12) * S, (y + 7) * S)],
              fill=color)


# --------------------------------------------------------------- figure 3-1
def fig_layers():
    W, H = 1400, 700
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    bands = [
        ("L1", NAVY, "摘要层 · SQLite 主库",
         ["l1_summary · tokenized_content · weight · valid_from / valid_to",
          "常驻磁盘，全文检索，参与排序与浮现"], "每条 0.2 ~ 0.5 KB"),
        ("L0", BLUE, "原文层 · 文件系统（压缩）",
         ["archive/l0/<hash>.zst · memory_documents · memory_blobs",
          "一份材料一个文件；条目用 offset / length 指向区间"], "整份压缩，不分块"),
        ("M", TEAL, "媒体层 · 文件系统（转码）",
         ["archive/audio/<hash>.opus · memory_media · ASR 转写",
          "转写后走 ingest 生成 L1，音频按 TTL 清理"], "每小时 8 ~ 15 MB"),
    ]

    y = 20
    for tag, color, title, lines, note in bands:
        box(d, (40, y, 1360, y + 200), r=14, fill=BAND, outline=LINE, width=1.8)
        d.rounded_rectangle([v * S for v in (80, y + 52, 180, y + 152)],
                            radius=12 * S, fill=color)
        center_text(d, 130, y + 78, tag, size=42, bold=True, fill=WHITE)
        text(d, (215, y + 32), title, size=33, bold=True, fill=color)
        text(d, (215, y + 92), lines[0], size=23, fill=INK)
        text(d, (215, y + 140), lines[1], size=23, fill=GREY)
        nw = text_w(note, 21)
        text(d, (1330 - nw, y + 146), note, size=21, fill=ACCENT)
        y += 230

    img.save(OUT / "fig_3_1_layers.png", optimize=True)
    print("fig_3_1_layers.png", img.size)


# --------------------------------------------------------------- figure 4-1
def fig_architecture():
    W, H = 1400, 770
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    # row A - consumers
    ya, hh, aw, gap = 14, 132, 430, 25
    ax = [30, 30 + aw + gap, 30 + 2 * (aw + gap)]
    for x, (t, s1, s2) in zip(ax, [
            ("AI 代理", "Cline / Claude Desktop", "MCP stdio 挂载"),
            ("Web 看板", "单文件 HTML · 9 个页面", "同源托管，免 CORS"),
            ("Obsidian + Git", "vault/*.md + WikiLink", "版本链双链，异步推送")]):
        box(d, (x, ya, x + aw, ya + hh), r=12, fill=BAND2, outline=LINE, width=1.8)
        center_text(d, x + aw / 2, ya + 18, t, size=30, bold=True, fill=NAVY)
        center_text(d, x + aw / 2, ya + 64, s1, size=21, fill=GREY)
        center_text(d, x + aw / 2, ya + 98, s2, size=21, fill=GREY)

    # row B - entry points
    yb = ya + hh + 56
    for (x0, x1), t, s in (
            ((100, 660), "mcp_server.py", "12 个 MCP 工具（薄封装）"),
            ((690, 1300), "dashboard.py :8765", "鉴权 · 路由 · 校验 · 限流")):
        box(d, (x0, yb, x1, yb + 112), r=12, fill=WHITE, outline=BLUE, width=2.0)
        center_text(d, (x0 + x1) / 2, yb + 16, t, size=28, bold=True, fill=BLUE)
        center_text(d, (x0 + x1) / 2, yb + 66, s, size=21, fill=GREY)

    arrow_down(d, 245, ya + hh + 2, yb - 4)
    arrow_down(d, 790, ya + hh + 2, yb - 4)
    arrow_down(d, 1155, ya + hh + 2, yb - 4)

    # row C - service layer
    yc = yb + 112 + 56
    box(d, (30, yc, 1030, yc + 148), r=12, fill=BAND, outline=NAVY, width=2.0)
    text(d, (56, yc + 16), "服务层 · src/", size=30, bold=True, fill=NAVY)
    text(d, (56, yc + 70),
         "storage · ingest · retriever · decay · version_chain · conflict_guard",
         size=21, fill=INK)
    text(d, (56, yc + 108),
         "media_ingest · asr_adapter · archive_manager · textproc · config · exporter",
         size=21, fill=INK)

    arrow_down(d, 375, yb + 112 + 2, yc - 4)
    arrow_down(d, 990, yb + 112 + 2, yc - 4)

    # row D - storage
    yd = yc + 148 + 54
    box(d, (30, yd, 500, yd + 170), r=12, fill=WHITE, outline=LINE, width=1.8)
    text(d, (54, yd + 14), "SQLite memory.db（WAL）", size=27, bold=True, fill=NAVY)
    text(d, (54, yd + 60), "9 张表 · 3 个 FTS5", size=19, fill=GREY)
    text(d, (54, yd + 94), "6 个触发器 · 17 个索引", size=19, fill=GREY)
    text(d, (54, yd + 128), "一连接一线程 · IMMEDIATE", size=19, fill=GREY)

    box(d, (530, yd, 1030, yd + 170), r=12, fill=WHITE, outline=LINE, width=1.8)
    text(d, (554, yd + 14), "文件系统", size=27, bold=True, fill=NAVY)
    text(d, (554, yd + 60), "archive/{l0,audio,transcript}", size=19, fill=GREY)
    text(d, (554, yd + 94), "cache/restore · vault/ · var/", size=19, fill=GREY)
    text(d, (554, yd + 128), "按哈希分桶，zstd / opus", size=19, fill=GREY)

    arrow_down(d, 265, yc + 148 + 2, yd - 4)
    arrow_down(d, 780, yc + 148 + 2, yd - 4)

    # external dependencies
    ex0, ex1 = 1060, 1370
    box(d, (ex0, yc, ex1, yd + 170), r=12, fill=(0xFA, 0xFB, 0xFD), outline=ACCENT,
        width=1.5, dash=True)
    text(d, (ex0 + 22, yc + 16), "外部依赖", size=26, bold=True, fill=GREY)
    yy = yc + 56
    for head, sub in [("DeepSeek API", "提炼 · 冲突判定"),
                      ("faster-whisper", "本地 ASR"),
                      ("ffmpeg", "转码 · 探测"),
                      ("Git 远端", "vault 备份")]:
        text(d, (ex0 + 22, yy), head, size=21, bold=True, fill=INK)
        text(d, (ex0 + 22, yy + 28), sub, size=19, fill=GREY)
        yy += 68

    arrow_right(d, yc + 74, 1034, 1056)

    img.save(OUT / "fig_4_1_architecture.png", optimize=True)
    print("fig_4_1_architecture.png", img.size)


if __name__ == "__main__":
    fig_layers()
    fig_architecture()
