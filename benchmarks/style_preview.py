"""Render side-by-side style-variant sheets for human review.

The round-1 blind test showed the ``modern`` style losing almost every pair
to stock RDKit while ``acs`` was roughly even. This script renders candidate
tweaks next to the current styles and the RDKit baseline so the maintainer
can pick a direction before the styles are changed. Output is written to
``benchmarks/blind_review/preview/`` (gitignored).

Usage::

    python benchmarks/style_preview.py
"""

from __future__ import annotations

import io
import sys
from copy import deepcopy
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from rdkit import Chem  # noqa: E402
from rdkit.Chem import rdDepictor  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D  # noqa: E402

import chemglyph  # noqa: E402
from blind_test_molecules import BLIND_TEST_MOLECULES  # noqa: E402
from chemglyph.molecule import (  # noqa: E402
    _build_options,
    _draw_png,
    _parse_structure,
    _prepare_for_drawing,
)
from chemglyph.styles import StyleSpec, get_style  # noqa: E402

CELL = 420
PAD = 24
HEADER = 64
GAP = 20
INK = (24, 24, 24, 255)

_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_PREVIEW_MOLECULES = [
    "caffeine",
    "aspirin",
    "vanillin",
    "cholesterol",
    "triphenylphosphine",
    "paclitaxel",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _img(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _rdkit_panel(smiles: str, *, monochrome: bool) -> Image.Image:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    options = rdMolDraw2D.MolDrawOptions()
    if monochrome:
        options.useBWAtomPalette = True
    drawer = rdMolDraw2D.MolDraw2DCairo(CELL, CELL)
    drawer.SetDrawOptions(options)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return _img(bytes(drawer.GetDrawingText()))


def _chemglyph_panel(smiles: str, style: str) -> Image.Image:
    result = chemglyph.render_molecule(
        smiles, style=style, fmt="png", transparent=False, size=(CELL, CELL)
    )
    return _img(result.data)


def _variant_panel(smiles: str, spec: StyleSpec) -> Image.Image:
    mol = _parse_structure(smiles)
    _prepare_for_drawing(mol)
    options = _build_options(spec, mol=mol, transparent=False, show_atom_indices=False)
    return _img(_draw_png(mol, options, (CELL, CELL), None))


def _variant(name: str, options: dict) -> StyleSpec:
    return StyleSpec(name=name, draw_options=options, background="#ffffff")


def _sheet(columns: list[tuple[str, str]], out_path: Path) -> None:
    width = 2 * PAD + len(columns) * CELL + (len(columns) - 1) * GAP
    height = HEADER + len(_PREVIEW_MOLECULES) * (CELL + GAP) + PAD
    page = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(page)
    for col, (label, _) in enumerate(columns):
        x = PAD + col * (CELL + GAP) + CELL // 2
        draw.text((x, 30), label, font=_font(26), fill=INK, anchor="mm")
    for row, label in enumerate(_PREVIEW_MOLECULES):
        smiles = next(s for m, s, _ in BLIND_TEST_MOLECULES if m == label)
        y = HEADER + row * (CELL + GAP)
        draw.text((8, y + CELL // 2), label, font=_font(20), fill=INK, anchor="lm")
        for col, (_, kind) in enumerate(columns):
            if kind == "rdkit-color":
                image = _rdkit_panel(smiles, monochrome=False)
            elif kind == "rdkit-mono":
                image = _rdkit_panel(smiles, monochrome=True)
            elif kind.startswith("style:"):
                image = _chemglyph_panel(smiles, kind.split(":", 1)[1])
            else:
                image = _variant_panel(smiles, VARIANTS[kind])
            x = PAD + col * (CELL + GAP)
            page.paste(image, (x, y), image)
    page.convert("RGB").save(out_path)
    print(f"wrote {out_path}")


def _with(style: str, **overrides: object) -> StyleSpec:
    base = deepcopy(get_style(style))
    base = _variant(f"{style}-variant", {**base.draw_options, **overrides})
    return base


VARIANTS: dict[str, StyleSpec] = {
    "modern-v2": _with(
        "modern",
        bondLineWidth=2.0,
        multipleBondOffset=0.15,
        additionalAtomLabelPadding=0.16,
        minFontSize=12,
        maxFontSize=26,
        padding=0.06,
    ),
    "modern-v3": _with(
        "modern",
        bondLineWidth=2.0,
        multipleBondOffset=0.15,
        additionalAtomLabelPadding=0.16,
        minFontSize=12,
        maxFontSize=26,
        padding=0.06,
        atom_colours={
            8: "#C0392B",
            7: "#2471A3",
            16: "#A67C00",
            17: "#1E8449",
        },
    ),
    "acs-v2": _with(
        "acs",
        bondLineWidth=1.8,
        multipleBondOffset=0.15,
        minFontSize=14,
        maxFontSize=30,
        padding=0.05,
    ),
    "acs-v3": _with(
        "acs",
        bondLineWidth=1.5,
        multipleBondOffset=0.14,
        minFontSize=12,
        maxFontSize=26,
        padding=0.07,
    ),
}


def main() -> None:
    out_dir = _REPO_ROOT / "benchmarks" / "blind_review" / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    _sheet(
        [
            ("RDKit 彩色", "rdkit-color"),
            ("modern 现状", "style:modern"),
            ("modern-v2 留白", "modern-v2"),
            ("modern-v3 柔和色", "modern-v3"),
        ],
        out_dir / "modern_family.png",
    )
    _sheet(
        [
            ("RDKit 黑白", "rdkit-mono"),
            ("acs 现状", "style:acs"),
            ("acs-v2 留白", "acs-v2"),
            ("acs-v3 细线", "acs-v3"),
        ],
        out_dir / "acs_family.png",
    )


if __name__ == "__main__":
    main()
