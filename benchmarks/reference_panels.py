"""Render Indigo/Ketcher reference panels next to chemglyph styles.

Indigo is the open-source engine that powers Ketcher, so its stock output is
the closest scriptable stand-in for a hand-made ChemDraw/Ketcher reference
panel. This script builds the anchor sheet for style tuning: one row per
blind-test molecule, columns ``reference | acs | modern``.

The sheet is for the maintainer's eyeball comparison, not for graders; it
never enters the blind deck. Outputs go to ``benchmarks/blind_review/``
(gitignored) and are never committed.

The Indigo column follows publication convention (see RUNBOOK.md): no
terminal CH3 labels, stereo wedges without the "Chiral" annotation, and a
label/bond ratio of ~0.68 (ChemDraw's 10 pt type on 14.4 pt bonds).

Usage::

    python benchmarks/reference_panels.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import resvg_py  # noqa: E402
from indigo import Indigo  # noqa: E402
from indigo.renderer import IndigoRenderer  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import chemglyph  # noqa: E402
from blind_test_molecules import BLIND_TEST_MOLECULES  # noqa: E402

CELL = 420  # square drawing cell
PAD = 24  # empty margin inside each cell
NAME_W = 260  # molecule-name column
HEADER_H = 84
ROW_H = CELL + 2 * PAD + 32
GAP = 20
ROWS_PER_PAGE = 10
TARGET_BOND = 30.0  # display bond length in px, shared across engines

BG = (255, 255, 255, 255)
INK = (24, 24, 24, 255)
BORDER = (214, 214, 214, 255)

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _svg_size(svg: str) -> tuple[float, float]:
    # RDKit uses width='150px' with single quotes; Indigo uses width="553"
    width = re.search(r"width=['\"]?([\d.]+)(?:px)?['\"]?", svg)
    height = re.search(r"height=['\"]?([\d.]+)(?:px)?['\"]?", svg)
    assert width and height, "SVG has no width/height"
    return float(width.group(1)), float(height.group(1))


def _rasterize(svg: str, zoom: float) -> Image.Image:
    data = resvg_py.svg_to_bytes(svg_string=svg, zoom=zoom, background="#ffffff")
    return _png(data)


def _chemglyph_panel(smiles: str, style: str) -> Image.Image:
    svg = chemglyph.render_molecule(smiles, style=style).data
    width, height = _svg_size(svg)
    fit = min((CELL - 2 * PAD) / width, (CELL - 2 * PAD) / height)
    # chemglyph's auto canvas already targets ~30 px bonds, so rasterize at
    # native size and only shrink when a molecule is larger than its cell.
    return _rasterize(svg, min(1.0, fit))


def _indigo() -> tuple[Indigo, IndigoRenderer]:
    indigo = Indigo()
    renderer = IndigoRenderer(indigo)
    indigo.setOption("render-output-format", "svg")
    indigo.setOption("render-background-color", "255,255,255")
    indigo.setOption("render-label-mode", "hetero")
    indigo.setOption("render-stereo-style", "ext")
    indigo.setOption("render-bond-length", TARGET_BOND)
    indigo.setOption("render-bond-line-width", 1.0)
    indigo.setOption("render-font-size", 14)
    return indigo, renderer


def _indigo_panel(indigo: Indigo, renderer: IndigoRenderer, smiles: str) -> Image.Image:
    mol = indigo.loadMolecule(smiles)
    mol.layout()
    svg = renderer.renderToBuffer(obj=mol).decode("utf-8")
    width, height = _svg_size(svg)
    fit = min((CELL - 2 * PAD) / width, (CELL - 2 * PAD) / height)
    return _rasterize(svg, min(1.0, fit))


def _sheet(rows: list[tuple[str, str]], page: int) -> None:
    width = 2 * PAD + NAME_W + 3 * CELL + 3 * GAP
    height = HEADER_H + len(rows) * ROW_H + PAD
    page_img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(page_img)
    draw.text((PAD, 28), "molecule", font=_font(26), fill=INK, anchor="lm")
    headers = ("reference (Indigo/Ketcher)", "chemglyph acs", "chemglyph modern")
    for column, header in enumerate(headers):
        x = PAD + NAME_W + column * (CELL + GAP) + CELL // 2
        draw.text((x, 28), header, font=_font(24), fill=INK, anchor="mm")

    indigo, renderer = _indigo()
    for row, (label, smiles) in enumerate(rows):
        y = HEADER_H + row * ROW_H
        draw.text((PAD, y + CELL // 2), label, font=_font(22), fill=INK, anchor="lm")
        panels = (
            _indigo_panel(indigo, renderer, smiles),
            _chemglyph_panel(smiles, "acs"),
            _chemglyph_panel(smiles, "modern"),
        )
        for column, panel in enumerate(panels):
            x = PAD + NAME_W + column * (CELL + GAP) + (CELL - panel.width) // 2
            page_img.paste(panel, (x, y + (CELL - panel.height) // 2), panel)

    out_dir = _REPO_ROOT / "benchmarks" / "blind_review"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"reference_sheet_page{page}.png"
    page_img.convert("RGB").save(out_path)
    print(f"wrote {out_path}")


def main() -> None:
    molecules = [(label, smiles) for label, smiles, _ in BLIND_TEST_MOLECULES]
    for page, start in enumerate(range(0, len(molecules), ROWS_PER_PAGE), start=1):
        _sheet(molecules[start : start + ROWS_PER_PAGE], page)


if __name__ == "__main__":
    main()
