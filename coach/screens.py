"""Render device screens on the server as raw RGB565.

Doing the drawing here means the device needs no Hebrew font and no
right-to-left text support: it just shows the pixels it gets. Sizes come
from the device (the StickS3 pet is 240x135 in landscape)."""
import os
import re

from bidi.algorithm import get_display as _bidi_display
from PIL import Image, ImageDraw, ImageFont, features

# Pillow built with libraqm lays out right-to-left text itself; without it we
# reorder the characters with python-bidi before drawing.
_HAS_RAQM = features.check("raqm")

BG = (12, 14, 24)
FG = (240, 240, 245)
ACCENT = (80, 220, 170)
DIM = (130, 135, 150)
BUBBLE = (250, 246, 232)
INK = (30, 32, 44)

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


def get_display(text: str) -> str:
    return text if _HAS_RAQM else _bidi_display(text)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (_FONT_BOLD_CANDIDATES if bold else _FONT_CANDIDATES):
        if path and os.path.exists(path):
            engine = ImageFont.Layout.RAQM if _HAS_RAQM else ImageFont.Layout.BASIC
            return ImageFont.truetype(path, size, layout_engine=engine)
    raise RuntimeError("No Hebrew-capable font found — install fonts-dejavu-core or set COACH_FONT")


def to_rgb565(img: Image.Image) -> bytes:
    """RGB image -> little-endian RGB565 bytes."""
    img = img.convert("RGB")
    w, h = img.size
    out = bytearray(w * h * 2)
    i = 0
    for r, g, b in img.getdata():
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
    out = []
    for l in lines:  # collapse runs of empty lines
        if l or (out and out[-1]):
            out.append(l)
    return out


def _rtl(d: ImageDraw.ImageDraw, right_x: float, y: float, text: str, font, fill) -> None:
    vis = get_display(text)
    d.text((right_x - font.getlength(vis), y), vis, font=font, fill=fill)


def _center(d: ImageDraw.ImageDraw, w: int, y: float, text: str, font, fill) -> None:
    vis = get_display(text)
    d.text(((w - font.getlength(vis)) / 2, y), vis, font=font, fill=fill)


def reply_pages(text: str, w: int = 240, h: int = 135) -> list[bytes]:
    """The pet's answer as speech-bubble pages of right-aligned Hebrew text."""
    font = _font(16 if h < 200 else 21)
    line_h = font.size + 6
    pad = 9
    left = 52  # the device draws a mini talking pet in this strip
    box = (left, 4, w - 5, h - 5)
    per_page = max(1, (box[3] - box[1] - 2 * pad + 6) // line_h)
    lines = _wrap(_clean(text), font, box[2] - box[0] - 2 * pad) or [""]
    chunks = [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
    pages = []
    for n, chunk in enumerate(chunks):
        img = Image.new("RGB", (w, h), BG)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(box, radius=14, fill=BUBBLE)
        d.polygon([(left, h - 44), (left, h - 28), (left - 12, h - 26)], fill=BUBBLE)  # tail -> pet
        y = box[1] + pad - 2
        for line in chunk:
            _rtl(d, box[2] - pad, y, line, font, INK)
            y += line_h
        if len(chunks) > 1:
            d.text((box[2] - 34, box[3] - 18), f"{n + 1}/{len(chunks)}", font=_font(11), fill=DIM)
        pages.append(to_rgb565(img))
    return pages


STAGE_NAMES = {"egg": "ביצה", "baby": "תינוק", "kid": "ילד", "teen": "נער", "adult": "בוגר"}


def stats_card(pet: dict, steps_today: int, goal: int, batt: int | None,
               w: int = 240, h: int = 135) -> bytes:
    """Status card: pet name/stage/level, steps today, XP bar."""
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    right = w - 10
    _rtl(d, right, 6, f"{pet['name']} · {STAGE_NAMES.get(pet['stage'], pet['stage'])}",
         _font(18, bold=True), ACCENT)
    f = _font(15)
    _rtl(d, right, 34, f"צעדים היום: {steps_today:,} / {goal:,}", f, FG)
    _rtl(d, right, 56, f"ניסיון: {pet['xp']:,}" + (f"  (לשלב הבא: {pet['next_xp']:,})" if pet.get("next_xp") else ""), f, FG)
    # step progress bar
    p = max(0.0, min(1.0, steps_today / goal)) if goal else 0
    d.rounded_rectangle((10, 84, right, 98), radius=7, fill=(40, 44, 60))
    if p > 0:
        d.rounded_rectangle((right - (right - 10) * p, 84, right, 98), radius=7, fill=ACCENT)
    tip = "יעד הושלם! 🎉" if p >= 1 else f"עוד {max(goal - steps_today, 0):,} צעדים ליעד"
    _rtl(d, right, 106, _clean(tip), _font(13), DIM)
    if batt is not None and batt >= 0:
        d.text((10, 108), f"{batt}%", font=_font(12), fill=DIM)
    return to_rgb565(img)
