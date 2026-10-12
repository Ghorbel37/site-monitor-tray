"""Regenerate assets/app.ico and docs/tray-states.png from the drawing code.

Run from the repo root:  python tools/make_icons.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("PYSTRAY_BACKEND", "dummy")   # no tray needed to draw icons
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from site_notifier import COLORS, make_icon  # noqa: E402

BLUE = (37, 99, 235)


def app_icon(size):
    """Blue rounded square with a white heartbeat line and a green status dot."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((s * 0.04, s * 0.04, s * 0.96, s * 0.96), radius=s * 0.22, fill=BLUE + (255,))
    pts = [(0.14, 0.56), (0.34, 0.56), (0.42, 0.36), (0.52, 0.74), (0.59, 0.50), (0.63, 0.56)]
    d.line([(s * x, s * y) for x, y in pts], fill=(255, 255, 255, 255), width=int(s * 0.075), joint="curve")
    r = s * 0.095
    cx, cy = s * 0.79, s * 0.56
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=COLORS["up"] + (255,))
    return img.resize((size, size), Image.LANCZOS)


def states_preview():
    labels = {"up": "All up", "partial": "Some down", "down": "All down", "unknown": "Checking"}
    cell, pad = 150, 20
    img = Image.new("RGBA", (cell * len(labels), cell), (0, 0, 0, 0))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(img)
    for i, (state, label) in enumerate(labels.items()):
        icon = make_icon(state, 96)
        img.alpha_composite(icon, (i * cell + (cell - 96) // 2, pad - 8))
        w = d.textlength(label, font=font)
        d.text((i * cell + (cell - w) / 2, pad + 96), label, fill=(110, 115, 125, 255), font=font)
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big = app_icon(256)
    big.save(ROOT / "assets" / "app.ico", sizes=[(n, n) for n in sizes])
    big.save(ROOT / "assets" / "app.png")
    states_preview().save(ROOT / "docs" / "tray-states.png")
    print("wrote assets/app.ico, assets/app.png, docs/tray-states.png")


if __name__ == "__main__":
    main()
