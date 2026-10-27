"""Draw the README style gallery: three molecules in the three styles.

Every panel is rendered at the same dpi, so bonds have the same length in
all nine panels, which is the point of fixed-scale styles.

Usage::

    python benchmarks/gallery.py  # writes docs/images/gallery_3x3.png
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import chemglyph  # noqa: E402
from chemglyph.engine import font_file  # noqa: E402

STYLES = ["screen", "acs1996", "textbook"]
MOLECULES = [
    ("Benzoic acid", "OC(=O)c1ccccc1"),
    ("Caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("(S)-Ibuprofen", "CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O"),
]
DPI = 300  # a 14.4 pt bond is 60 px
CELL_W, CELL_H, HEADER, CAPTION = 456, 420, 76, 56
RULE = (224, 224, 224)
INK = (24, 24, 24)


def main() -> None:
    header_font = ImageFont.truetype(font_file(), 30)
    caption_font = ImageFont.truetype(font_file(), 24)
    sheet = Image.new("RGB", (CELL_W * len(STYLES), HEADER + CELL_H * len(MOLECULES)), "white")
    pen = ImageDraw.Draw(sheet)
    for column, style in enumerate(STYLES):
        pen.text(
            (column * CELL_W + CELL_W / 2, HEADER / 2),
            style,
            font=header_font,
            fill=INK,
            anchor="mm",
        )
    pen.line([(0, HEADER - 1), (sheet.width, HEADER - 1)], fill=RULE, width=1)
    for row, (name, smiles) in enumerate(MOLECULES):
        top = HEADER + row * CELL_H
        for column, style in enumerate(STYLES):
            png = chemglyph.render_molecule(smiles, style=style, fmt="png", dpi=DPI).data
            panel = Image.open(io.BytesIO(png)).convert("RGBA")
            left = column * CELL_W
            x = left + (CELL_W - panel.width) // 2
            y = top + (CELL_H - CAPTION - panel.height) // 2
            sheet.paste(panel, (x, y), panel)
            pen.text(
                (left + CELL_W / 2, top + CELL_H - CAPTION / 2),
                name,
                font=caption_font,
                fill=INK,
                anchor="mm",
            )
        if row < len(MOLECULES) - 1:
            pen.line([(0, top + CELL_H - 1), (sheet.width, top + CELL_H - 1)], fill=RULE, width=1)
    out = _REPO_ROOT / "docs" / "images" / "gallery_3x3.png"
    sheet.save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
