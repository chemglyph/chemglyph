"""Generate the README style gallery and comparison images (M4 artifact).

Run from the repository root::

    python scripts/generate_docs_images.py

Layout rules: every molecule is rendered on the same square canvas so the
grid stays uniform; the first column carries the molecule name and the header
row carries the renderer/style name. Light grid lines separate cells.
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

CELL = 320  # molecule canvas (square)
PAD = 24  # whitespace inside each cell
LABEL_COL = 240  # first column (molecule names)
HEADER_H = 64  # header strip height
ROW_H = CELL + 2 * PAD

BG = (255, 255, 255, 255)
TEXT = (24, 24, 24, 255)
BORDER = (212, 212, 212, 255)

GALLERY = [
    ("Benzoic acid", "OC(=O)c1ccccc1"),
    ("Caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("(S)-Ibuprofen", "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"),
]

STYLES = ["acs", "modern", "textbook-cn"]

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
    result = chemglyph.render_molecule(
        smiles, style=style, fmt="png", transparent=False, size=(CELL, CELL)
    )
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
    *,
    with_label_column: bool,
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    label_width = LABEL_COL if with_label_column else 0
    width = label_width + columns * (CELL + 2 * PAD)
    height = HEADER_H + rows * ROW_H
    image = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(image)
    for column in range(columns + 1):
        x = label_width + column * (CELL + 2 * PAD)
        draw.line([(x, 0), (x, height)], fill=BORDER, width=1)
    for row in range(rows + 1):
        y = HEADER_H + row * ROW_H
        draw.line([(0, y), (width, y)], fill=BORDER, width=1)
    return image, draw


def _header(draw: ImageDraw.ImageDraw, column: int, text: str, *, with_label_column: bool) -> None:
    label_width = LABEL_COL if with_label_column else 0
    x = label_width + column * (CELL + 2 * PAD) + (CELL + 2 * PAD) // 2
    draw.text((x, HEADER_H // 2), text, font=_font(26), fill=TEXT, anchor="mm")


def _label(draw: ImageDraw.ImageDraw, row: int, text: str) -> None:
    y = HEADER_H + row * ROW_H + ROW_H // 2
    draw.text((LABEL_COL // 2, y), text, font=_font(24), fill=TEXT, anchor="mm")


def _paste(
    sheet: Image.Image,
    image: Image.Image,
    column: int,
    row: int,
    *,
    with_label_column: bool,
) -> None:
    label_width = LABEL_COL if with_label_column else 0
    x0 = label_width + column * (CELL + 2 * PAD) + PAD
    y0 = HEADER_H + row * ROW_H + PAD
    thumb = image.copy()
    thumb.thumbnail((CELL, CELL))
    tx = x0 + (CELL - thumb.width) // 2
    ty = y0 + (CELL - thumb.height) // 2
    sheet.paste(thumb, (tx, ty), thumb)


def gallery(out_dir: Path) -> None:
    sheet, draw = _sheet(len(STYLES), len(GALLERY), with_label_column=True)
    draw.text((LABEL_COL // 2, HEADER_H // 2), "Molecule", font=_font(26), fill=TEXT, anchor="mm")
    for column, style in enumerate(STYLES):
        _header(draw, column, style, with_label_column=True)
    for row, (name, smiles) in enumerate(GALLERY):
        _label(draw, row, name)
        for column, style in enumerate(STYLES):
            _paste(sheet, _chemglyph_png(smiles, style), column, row, with_label_column=True)
    sheet.save(out_dir / "gallery_3x3.png")


def comparison(out_dir: Path) -> None:
    sheet, draw = _sheet(2, len(COMPARISON), with_label_column=True)
    draw.text((LABEL_COL // 2, HEADER_H // 2), "Molecule", font=_font(26), fill=TEXT, anchor="mm")
    _header(draw, 0, "ChemGlyph (modern)", with_label_column=True)
    _header(draw, 1, "RDKit default", with_label_column=True)
    for row, (name, smiles) in enumerate(COMPARISON):
        _label(draw, row, name)
        _paste(sheet, _chemglyph_png(smiles, "modern"), 0, row, with_label_column=True)
        _paste(sheet, _rdkit_default_png(smiles), 1, row, with_label_column=True)
    sheet.save(out_dir / "comparison_vs_rdkit.png")


def main() -> None:
    out_dir = _REPO_ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    gallery(out_dir)
    comparison(out_dir)
    print(f"Wrote gallery and comparison images to {out_dir}")


if __name__ == "__main__":
    main()
