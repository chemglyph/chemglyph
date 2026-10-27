"""Phase 1 prototype: fixed-scale rendering against the ACS Document 1996 settings.

Renders the 20 blind-test molecules two ways and measures both:

- ``current``: ``chemglyph.render_molecule(style="acs")`` as released in 0.1.3
  (canvas first, drawing scaled to fit);
- ``acs1996``: one fixed physical scale. RDKit draws on a canvas large enough
  that its fixed bond length is honored exactly, at 10x resolution, and the
  result is cropped to the drawn content and labelled in points.

Measured per molecule: drawn bond length, line widths present, double-bond
spacing as a fraction of the bond length, and the height of an "O" glyph
(which tracks the label font size). The ACS targets are bond 14.4 pt, line
0.6 pt, spacing 18%, labels 10 pt.

Outputs go to ``benchmarks/blind_review/acs1996/`` (gitignored): one SVG per
molecule, ``measurements.json``, and ``comparison.png`` (both renderings at
the same physical scale, 4 px per pt).

Usage::

    python benchmarks/acs1996_prototype.py
"""

from __future__ import annotations

import io
import json
import math
import re
import statistics
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import resvg_py  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from rdkit import Chem  # noqa: E402
from rdkit.Chem import rdDepictor  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D  # noqa: E402

import chemglyph  # noqa: E402
from blind_test_molecules import BLIND_TEST_MOLECULES  # noqa: E402
from chemglyph.svg_utils import content_viewbox, inner_content  # noqa: E402

ACS = {"bond_pt": 14.4, "line_pt": 0.6, "spacing": 0.18, "font_pt": 10.0}
K = 10.0  # internal resolution: SVG user units per point
MARGIN_PT = 2.0
PX_PER_PT = 4  # raster scale for the comparison sheet

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
]
SHEET_MOLECULES = [
    "sulfate",
    "benzoic-acid",
    "caffeine",
    "s-ibuprofen",
    "triphenylphosphine",
    "cholesterol",
]
OUT_DIR = _REPO_ROOT / "benchmarks" / "blind_review" / "acs1996"


def _label_font() -> str | None:
    return next((path for path in FONT_CANDIDATES if Path(path).exists()), None)


def _prepared(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    return mol


def render_acs1996(smiles: str, font_file: str | None) -> tuple[str, dict]:
    """Fixed-scale rendering: returns (svg in pt units, raw measurements)."""
    mol = _prepared(smiles)
    mean = rdMolDraw2D.MeanBondLength(mol) or 1.0
    conformer = mol.GetConformer()
    xs = [conformer.GetAtomPosition(i).x for i in range(mol.GetNumAtoms())]
    ys = [conformer.GetAtomPosition(i).y for i in range(mol.GetNumAtoms())]
    scale = ACS["bond_pt"] * K / mean  # user units per coordinate unit
    width = int((max(xs) - min(xs)) * scale + 60 * K)
    height = int((max(ys) - min(ys)) * scale + 60 * K)

    options = rdMolDraw2D.MolDrawOptions()
    rdMolDraw2D.SetACS1996Mode(options, mean)
    options.padding = 0.0
    options.fixedBondLength = scale
    options.fixedFontSize = int(ACS["font_pt"] * K)
    options.bondLineWidth = ACS["line_pt"] * K
    options.scaleBondWidth = False
    if font_file:
        options.fontFile = font_file
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.SetDrawOptions(options)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    raw = drawer.GetDrawingText()
    raw = re.sub(r"<rect\b[^>]*(?:/>|>.*?</rect>)", "", raw, count=1, flags=re.DOTALL)

    bond_pt = []
    for bond in mol.GetBonds():
        begin, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        p1, p2 = drawer.GetDrawCoords(begin), drawer.GetDrawCoords(end)
        coord = (conformer.GetAtomPosition(begin) - conformer.GetAtomPosition(end)).Length()
        bond_pt.append(math.dist((p1.x, p1.y), (p2.x, p2.y)) / coord * mean / K)

    box = content_viewbox(raw, margin=MARGIN_PT * K)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{box.width / K:.2f}pt" '
        f'height="{box.height / K:.2f}pt" viewBox="{box.x:.1f} {box.y:.1f} '
        f'{box.width:.1f} {box.height:.1f}">{inner_content(raw)}</svg>'
    )
    return svg, {
        "bond_pt": bond_pt,
        "unit": K,
        "spacing": _double_bond_spacing(raw, mol),
        "glyph_o": _glyph_heights(raw, mol, "O", K),
        "lines": _stroke_widths(raw, K),
    }


def render_current(smiles: str) -> tuple[str, dict]:
    """The released acs style; its SVG units are px, read here as pt."""
    svg = chemglyph.render_molecule(smiles, style="acs").data
    mol = _prepared(smiles)
    return svg, {
        "bond_pt": _carbon_bond_lengths(svg, mol),
        "unit": 1.0,
        "spacing": _double_bond_spacing(svg, mol),
        "glyph_o": _glyph_heights(svg, mol, "O", 1.0),
        "lines": _stroke_widths(svg, 1.0),
    }


_SEGMENT = re.compile(
    r"class='bond-(\d+) atom-(\d+) atom-(\d+)' d='M ([-\d.]+),([-\d.]+) L ([-\d.]+),([-\d.]+)'"
)


def _segments(svg: str) -> dict[int, list[tuple[float, float, float, float]]]:
    found: dict[int, list[tuple[float, float, float, float]]] = {}
    for match in _SEGMENT.finditer(svg):
        bond = int(match.group(1))
        found.setdefault(bond, []).append(tuple(float(v) for v in match.groups()[3:]))
    return found


def _bonds_of(svg: str, mol: Chem.Mol) -> dict[int, list[tuple[float, float, float, float]]]:
    return {i: v for i, v in _segments(svg).items() if i < mol.GetNumBonds()}


def _carbon_bond_lengths(svg: str, mol: Chem.Mol) -> list[float]:
    """Single C-C bonds are drawn atom center to atom center, so their
    segment length is the drawn bond length (no label shortening)."""
    lengths = []
    for bond, parts in _bonds_of(svg, mol).items():
        b = mol.GetBondWithIdx(bond)
        if b.GetBondType() != Chem.BondType.SINGLE or b.GetStereo() != Chem.BondStereo.STEREONONE:
            continue
        if b.GetBeginAtom().GetSymbol() != "C" or b.GetEndAtom().GetSymbol() != "C":
            continue
        if len(parts) != 1:
            continue
        x1, y1, x2, y2 = parts[0]
        lengths.append(math.dist((x1, y1), (x2, y2)))
    return lengths


def _double_bond_spacing(svg: str, mol: Chem.Mol) -> list[float]:
    """Perpendicular gap between the two lines of each C=C or aromatic bond,
    divided by the longer line (the bond length for an offset double bond)."""
    ratios = []
    for bond, parts in _bonds_of(svg, mol).items():
        if len(parts) != 2:
            continue
        b = mol.GetBondWithIdx(bond)
        if b.GetBeginAtom().GetSymbol() != "C" or b.GetEndAtom().GetSymbol() != "C":
            continue
        (ax1, ay1, ax2, ay2), (bx1, by1, bx2, by2) = parts
        length_a = math.dist((ax1, ay1), (ax2, ay2))
        length_b = math.dist((bx1, by1), (bx2, by2))
        if min(length_a, length_b) == 0:
            continue
        dx, dy = (ax2 - ax1) / length_a, (ay2 - ay1) / length_a
        gap = abs((bx1 - ax1) * dy - (by1 - ay1) * dx)
        ratios.append(gap / max(length_a, length_b))
    return ratios


def _glyph_heights(svg: str, mol: Chem.Mol, symbol: str, unit: float) -> list[float]:
    heights = []
    for atom in mol.GetAtoms():
        if atom.GetSymbol() != symbol or atom.GetFormalCharge() or atom.GetTotalNumHs():
            continue
        paths = re.findall(rf"<path class='atom-{atom.GetIdx()}' d='([^']+)'", svg)
        numbers = [float(v) for path in paths for v in re.findall(r"-?\d+\.?\d*", path)]
        if numbers:
            ys = numbers[1::2]
            heights.append((max(ys) - min(ys)) / unit)
    return heights


def _stroke_widths(svg: str, unit: float) -> list[float]:
    return sorted({round(float(v) / unit, 3) for v in re.findall(r"stroke-width:([\d.]+)px", svg)})


def _summary(raw: dict) -> dict:
    def spread(values: list[float]) -> list[float] | None:
        return [round(min(values), 3), round(max(values), 3)] if values else None

    return {
        "bond_pt": spread(raw["bond_pt"]),
        "lines_pt": raw["lines"],
        "double_bond_spacing": spread(raw["spacing"]),
        "o_glyph_pt": spread(raw["glyph_o"]),
    }


def _raster(svg: str, zoom: float) -> Image.Image:
    # resvg rejects "pt" sizes; drop the unit so one user unit is one point.
    svg = re.sub(r'(width|height)="([\d.]+)pt"', r'\1="\2"', svg)
    data = resvg_py.svg_to_bytes(svg_string=svg, zoom=zoom, background="#ffffff")
    return Image.open(io.BytesIO(data)).convert("RGB")


def _sheet(rows: list[tuple[str, list[Image.Image]]], names: list[str]) -> Image.Image:
    cjk = next(
        (
            path
            for path in [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/System/Library/Fonts/PingFang.ttc",
            ]
            if Path(path).exists()
        ),
        None,
    )
    font = ImageFont.truetype(cjk, 30) if cjk else ImageFont.load_default()
    small = ImageFont.truetype(cjk, 22) if cjk else ImageFont.load_default()
    gap, label_w, head_h = 48, 300, 70
    col_w = [max(images[i].width for _, images in rows) for i in range(len(names))]
    row_h = [max(img.height for img in images) for _, images in rows]
    width = label_w + sum(col_w) + gap * (len(names) + 1)
    height = head_h + sum(row_h) + gap * (len(rows) + 1)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    x = label_w + gap
    for name, w in zip(names, col_w, strict=True):
        draw.text((x + w // 2, head_h // 2), name, font=small, fill=(60, 60, 60), anchor="mm")
        x += w + gap
    y = head_h + gap
    for (label, images), h in zip(rows, row_h, strict=True):
        draw.text((24, y + h // 2), label, font=font, fill=(20, 20, 20), anchor="lm")
        x = label_w + gap
        for image, w in zip(images, col_w, strict=True):
            sheet.paste(image, (x + (w - image.width) // 2, y + h - image.height))
            x += w + gap
        y += h + gap
        draw.line([(0, y - gap // 2), (width, y - gap // 2)], fill=(225, 225, 225), width=2)
    return sheet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font_file = _label_font()
    results: dict[str, dict] = {}
    current_imgs, proto_imgs = {}, {}
    for label, smiles, _note in BLIND_TEST_MOLECULES:
        proto_svg, proto_raw = render_acs1996(smiles, font_file)
        current_svg, current_raw = render_current(smiles)
        (OUT_DIR / f"{label}.svg").write_text(proto_svg)
        results[label] = {"acs1996": _summary(proto_raw), "current": _summary(current_raw)}
        if label in SHEET_MOLECULES:
            proto_imgs[label] = _raster(proto_svg, PX_PER_PT)
            current_imgs[label] = _raster(current_svg, PX_PER_PT)

    def pooled(engine: str, key: str) -> list[float]:
        values = []
        for item in results.values():
            span = item[engine][key]
            if span:
                values.extend(span)
        return values

    report = {
        "targets": ACS,
        "label_font": font_file,
        "molecules": results,
        "overall": {
            engine: {
                key: [round(min(pooled(engine, key)), 3), round(max(pooled(engine, key)), 3)]
                for key in ("bond_pt", "double_bond_spacing", "o_glyph_pt")
            }
            for engine in ("acs1996", "current")
        },
    }
    (OUT_DIR / "measurements.json").write_text(json.dumps(report, indent=2) + "\n")

    sheet = _sheet(
        [
            ("0.1.3 的 acs\n（各图比例不同）", [current_imgs[m] for m in SHEET_MOLECULES]),
            ("固定比例 acs1996\n原型", [proto_imgs[m] for m in SHEET_MOLECULES]),
        ],
        SHEET_MOLECULES,
    )
    sheet.save(OUT_DIR / "comparison.png")

    print(json.dumps(report["overall"], indent=2))
    bonds = [statistics.median(v["acs1996"]["bond_pt"]) for v in results.values()]
    print(f"acs1996 median bond per molecule: {min(bonds):.3f} to {max(bonds):.3f} pt")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
