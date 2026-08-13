"""Generate the README style gallery and comparison images (M4 artifact).

Run from the repository root::

    python scripts/generate_docs_images.py
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

FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
CELL = 360
LABEL_H = 42
PAD = 24
BG = (255, 255, 255, 255)
LABEL_COLOR = (20, 20, 20, 255)

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
    return ImageFont.truetype(FONT_PATH, size)


def _from_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _chemglyph_png(smiles: str, style: str) -> Image.Image:
    result = chemglyph.render_molecule(smiles, style=style, fmt="png", transparent=False)
    return _from_png(result.data)


def _rdkit_default_png(smiles: str, size: tuple[int, int]) -> Image.Image:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DCairo(*size)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return _from_png(bytes(drawer.GetDrawingText()))


def _sheet(columns: int, rows: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    width = PAD + columns * CELL + PAD
    height = PAD + rows * (LABEL_H + CELL) + PAD
    image = Image.new("RGBA", (width, height), BG)
    return image, ImageDraw.Draw(image)


def _paste_cell(
    sheet: Image.Image,
    image: Image.Image,
    *,
    column: int,
    row: int,
    caption: str,
) -> None:
    x = PAD + column * CELL
    y = PAD + row * (LABEL_H + CELL)
    draw = ImageDraw.Draw(sheet)
    if caption:
        draw.text((x + CELL // 2, y + 6), caption, font=_font(28), fill=LABEL_COLOR, anchor="mm")
    thumb = image.copy()
    thumb.thumbnail((CELL - 24, CELL - 24))
    tx = x + (CELL - thumb.width) // 2
    ty = y + LABEL_H + (CELL - thumb.height) // 2
    sheet.paste(thumb, (tx, ty), thumb)


def gallery(out_dir: Path) -> None:
    sheet, draw = _sheet(columns=len(STYLES) + 1, rows=len(GALLERY) + 1)
    for column, style in enumerate(STYLES):
        x = PAD + (column + 1) * CELL + CELL // 2
        draw.text((x, PAD + 8), style, font=_font(24), fill=LABEL_COLOR, anchor="mm")
    for row, (name, smiles) in enumerate(GALLERY):
        _cell_label(draw, 0, row + 1, name)
        for column, style in enumerate(STYLES):
            _paste_cell(
                sheet,
                _chemglyph_png(smiles, style),
                column=column + 1,
                row=row + 1,
                caption="",
            )
    sheet.save(out_dir / "gallery_3x3.png")


def comparison(out_dir: Path) -> None:
    sheet, draw = _sheet(columns=3, rows=len(COMPARISON) + 1)
    headers = ["Molecule", "ChemGlyph (modern)", "RDKit default"]
    for column, header in enumerate(headers):
        x = PAD + column * CELL + CELL // 2
        draw.text((x, PAD + 8), header, font=_font(24), fill=LABEL_COLOR, anchor="mm")
    for row, (name, smiles) in enumerate(COMPARISON):
        _cell_label(draw, 0, row + 1, name)
        _paste_cell(
            sheet,
            _chemglyph_png(smiles, "modern"),
            column=1,
            row=row + 1,
            caption="",
        )
        _paste_cell(
            sheet,
            _rdkit_default_png(smiles, (600, 500)),
            column=2,
            row=row + 1,
            caption="",
        )
    sheet.save(out_dir / "comparison_vs_rdkit.png")


def _cell_label(draw: ImageDraw.ImageDraw, column: int, row: int, text: str) -> None:
    x = PAD + column * CELL + CELL // 2
    y = PAD + row * (LABEL_H + CELL) + 6
    draw.text((x, y), text, font=_font(28), fill=LABEL_COLOR, anchor="mm")


def main() -> None:
    out_dir = _REPO_ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    gallery(out_dir)
    comparison(out_dir)
    print(f"Wrote gallery and comparison images to {out_dir}")


if __name__ == "__main__":
    main()
