"""Generate the README style gallery and comparison images (M4 artifact).

Run from the repository root::

    python scripts/generate_docs_images.py

Layout: a clean grid with no label column. Column headers carry the renderer
or style name, molecules are centered in equal cells, and the molecule name
sits under each cell. Each molecule is rendered on its own aspect-matched
canvas and fitted into the cell so small structures do not float in a sea of
white space.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from rdkit import Chem  # noqa: E402
from rdkit.Chem import rdDepictor  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D  # noqa: E402

import chemglyph  # noqa: E402

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

CELL = 400  # cell width and height for a square drawing area
PAD = 28  # whitespace inside each cell
HEADER_H = 76  # header strip height
NAME_H = 48  # caption strip under each cell
ROW_H = CELL + 2 * PAD + NAME_H

BG = (255, 255, 255, 255)
TEXT = (24, 24, 24, 255)
BORDER = (212, 212, 212, 255)

GALLERY = [
    ("Benzoic acid", "OC(=O)c1ccccc1"),
    ("Caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("(S)-Ibuprofen", "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"),
]

STYLES = ["acs", "modern", "textbook-cn"]
STYLE_LABELS = {"acs": "ACS", "modern": "Modern", "textbook-cn": "Textbook (CN)"}

COMPARISON = [
    (
        "Cholesterol",
        "CC(C)CCC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(C)CC[C@H]1[C@H]2CC=C2C[C@@H](O)CC[C@]12C",
    ),
    (
        "Paclitaxel",
        "CC1=C2[C@@]([C@]([C@H]([C@@H]3[C@]4([C@H](OC4)C[C@@H]([C@]3(C(=O)[C@@H]2OC(=O)C)C)O)OC(=O)C)OC(=O)c2ccccc2)(C[C@@H]1OC(=O)[C@H](O)[C@@H](NC(=O)c1ccccc1)c1ccccc1)O)(C)C",
    ),
    (
        "Porphyrin (free base)",
        "c1cc2cc3ccc(cc4ccc(cc5ccc(cc1n2)[nH]5)n4)[nH]3",
    ),
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _from_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _chemglyph_png(smiles: str, style: str) -> Image.Image:
    result = chemglyph.render_molecule(smiles, style=style, fmt="png", transparent=False)
    return _from_png(result.data)


def _rdkit_default_png(smiles: str) -> Image.Image:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DCairo(CELL, CELL)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return _from_png(bytes(drawer.GetDrawingText()))


def _sheet(
    columns: int,
    rows: int,
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    width = columns * (CELL + 2 * PAD)
    height = HEADER_H + rows * ROW_H
    image = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(image)
    for row in range(rows):
        y = HEADER_H + row * ROW_H
        if row:
            draw.line([(0, y), (width, y)], fill=BORDER, width=1)
    draw.line([(0, HEADER_H), (width, HEADER_H)], fill=BORDER, width=1)
    return image, draw


def _header(draw: ImageDraw.ImageDraw, column: int, text: str) -> None:
    x = column * (CELL + 2 * PAD) + (CELL + 2 * PAD) // 2
    draw.text((x, HEADER_H // 2), text, font=_font(30), fill=TEXT, anchor="mm")


def _caption(draw: ImageDraw.ImageDraw, column: int, row: int, text: str) -> None:
    x = column * (CELL + 2 * PAD) + (CELL + 2 * PAD) // 2
    y = HEADER_H + row * ROW_H + 2 * PAD + CELL + NAME_H // 2
    draw.text((x, y), text, font=_font(24), fill=TEXT, anchor="mm")


def _paste(
    sheet: Image.Image,
    image: Image.Image,
    column: int,
    row: int,
) -> None:
    x0 = column * (CELL + 2 * PAD) + PAD
    y0 = HEADER_H + row * ROW_H + PAD
    thumb = image.copy()
    thumb.thumbnail((CELL, CELL))
    tx = x0 + (CELL - thumb.width) // 2
    ty = y0 + (CELL - thumb.height) // 2
    sheet.paste(thumb, (tx, ty), thumb)


def gallery(out_dir: Path) -> None:
    sheet, draw = _sheet(len(STYLES), len(GALLERY))
    for column, style in enumerate(STYLES):
        _header(draw, column, STYLE_LABELS[style])
    for row, (name, smiles) in enumerate(GALLERY):
        for column, style in enumerate(STYLES):
            _paste(sheet, _chemglyph_png(smiles, style), column, row)
            _caption(draw, column, row, name)
    sheet.save(out_dir / "gallery_3x3.png")


def comparison(out_dir: Path) -> None:
    sheet, draw = _sheet(2, len(COMPARISON))
    _header(draw, 0, "ChemGlyph (modern)")
    _header(draw, 1, "RDKit default")
    for row, (name, smiles) in enumerate(COMPARISON):
        _paste(sheet, _chemglyph_png(smiles, "modern"), 0, row)
        _paste(sheet, _rdkit_default_png(smiles), 1, row)
        _caption(draw, 0, row, name)
        _caption(draw, 1, row, name)
    sheet.save(out_dir / "comparison_vs_rdkit.png")


def main() -> None:
    out_dir = _REPO_ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    gallery(out_dir)
    comparison(out_dir)
    print(f"Wrote gallery and comparison images to {out_dir}")


if __name__ == "__main__":
    main()
