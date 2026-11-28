"""Render the watch screens on the server (240x240 RGB565).

Doing the drawing here means the watch needs no Hebrew font and no
right-to-left text support: it just shows the pixels it gets."""
import os
import re
from datetime import datetime

from bidi.algorithm import get_display as _bidi_display
from PIL import Image, ImageDraw, ImageFont, features

# Pillow built with libraqm lays out right-to-left text itself; without it we
# reorder the characters with python-bidi before drawing.
_HAS_RAQM = features.check("raqm")


def get_display(text: str) -> str:
    return text if _HAS_RAQM else _bidi_display(text)

W = H = 240
BG = (10, 12, 20)
FG = (240, 240, 245)
ACCENT = (0, 210, 140)
DIM = (120, 125, 140)

_FONT_CANDIDATES = [
    os.environ.get("COACH_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
_FONT_BOLD_CANDIDATES = [
    os.environ.get("COACH_FONT_BOLD", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (_FONT_BOLD_CANDIDATES if bold else _FONT_CANDIDATES):
        if path and os.path.exists(path):
            engine = ImageFont.Layout.RAQM if _HAS_RAQM else ImageFont.Layout.BASIC
            return ImageFont.truetype(path, size, layout_engine=engine)
    raise RuntimeError("No Hebrew-capable font found — install fonts-dejavu-core or set COACH_FONT")


def to_rgb565(img: Image.Image) -> bytes:
    """RGB image -> little-endian RGB565 bytes (what the watch pushes to the LCD)."""
    out = bytearray(W * H * 2)
    px = img.convert("RGB").load()
    i = 0
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out[i] = v & 0xFF
            out[i + 1] = v >> 8
            i += 2
    return bytes(out)


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def _clean(text: str) -> str:
    text = _EMOJI.sub("", text)
    text = re.sub(r"[*_#`]", "", text)       # strip markdown
    return re.sub(r"[ \t]+", " ", text).strip()


def _wrap(text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words, line = para.split(), ""
        for w in words:
            trial = f"{line} {w}".strip()
            if font.getlength(get_display(trial)) <= max_w:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = w
        lines.append(line)
    # collapse runs of empty lines
    out = []
    for l in lines:
        if l or (out and out[-1]):
            out.append(l)
    return out


def reply_pages(text: str) -> list[bytes]:
    """Split the coach's answer into full screens of right-aligned Hebrew text."""
    font = _font(21)
    line_h = 28
    top, bottom, margin = 22, 26, 22  # round-ish corners: keep text away from edges
    per_page = (H - top - bottom) // line_h
    lines = _wrap(_clean(text), font, W - 2 * margin) or [""]
    chunks = [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
    pages = []
    for n, chunk in enumerate(chunks):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        y = top
        for line in chunk:
            vis = get_display(line)
            d.text((W - margin - font.getlength(vis), y), vis, font=font, fill=FG)
            y += line_h
        if len(chunks) > 1:
            d.text((W // 2 - 14, H - 22), f"{n + 1}/{len(chunks)}", font=_font(14), fill=DIM)
        pages.append(to_rgb565(img))
    return pages


def home(now: datetime, steps: int, goal: int, batt: int | None, online_note: str = "") -> bytes:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # step ring
    p = max(0.0, min(1.0, steps / goal)) if goal else 0
    box = (12, 12, W - 12, H - 12)
    d.arc(box, 0, 360, fill=(35, 38, 50), width=12)
    if p > 0:
        d.arc(box, -90, -90 + 360 * p, fill=ACCENT, width=12)
    # clock
    t = now.strftime("%H:%M")
    f_time = _font(54, bold=True)
    d.text(((W - f_time.getlength(t)) / 2, 58), t, font=f_time, fill=FG)
    # steps
    s = f"{steps:,}"
    f_steps = _font(30, bold=True)
    d.text(((W - f_steps.getlength(s)) / 2, 122), s, font=f_steps, fill=ACCENT)
    lbl = get_display(f"צעדים מתוך {goal:,}")
    f_small = _font(15)
    d.text(((W - f_small.getlength(lbl)) / 2, 157), lbl, font=f_small, fill=DIM)
    hint = get_display(online_note or "החזק את המסך ודבר")
    f_hint = _font(13)
    d.text(((W - f_hint.getlength(hint)) / 2, 180), hint, font=f_hint, fill=DIM)
    if batt is not None and batt >= 0:
        b = f"{batt}%"
        d.text(((W - _font(13).getlength(b)) / 2, 36), b, font=_font(13), fill=DIM)
    return to_rgb565(img)
