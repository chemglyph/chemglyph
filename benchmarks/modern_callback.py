"""Modern-style callback comparison: revert exactly one weight-reduction.

The finalized modern style (font 12/28, darkened CPK, line width 1.8,
padding 0.06) lost too much heteroatom signal on small molecules. This sheet
shows the current state next to three single-item reverts so the maintainer
can pick one:

- A: font clamp back to 14/32
- B: palette back to classic CPK
- C: line width back to 2.0

Nothing is changed in ``styles.py`` until the maintainer confirms. Output is
``benchmarks/blind_review/modern_callback.png`` (gitignored).
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
from chemglyph.molecule import (  # noqa: E402
    _build_options,
    _draw_png,
    _estimate_canvas,
    _parse_structure,
    _prepare_for_drawing,
)
from chemglyph.styles import StyleSpec, get_style  # noqa: E402

CELL = 420
PAD = 24
NAME_W = 210
HEADER = 72
GAP = 20
ROW_H = CELL + 2 * PAD + 26
BG = (255, 255, 255, 255)
INK = (24, 24, 24, 255)

MOLECULES = [
    ("benzoic acid", "OC(=O)c1ccccc1"),
    ("vanillin", "COc1cc(C=O)ccc1O"),
    ("aspirin", "CC(=O)Oc1ccccc1C(=O)O"),
    ("caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("tnt", "Cc1c(cc(cc1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]"),
    ("18-crown-6", "C1COCCOCCOCCOCCOCCO1"),
]

CLASSIC_CPK = {8: "#FF0D0D", 7: "#3050F8", 16: "#E8C300", 17: "#1FB01F"}

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


def _img(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _variant_panel(smiles: str, overrides: dict) -> Image.Image:
    base = get_style("modern")
    spec = StyleSpec(
        name="callback",
        draw_options={**base.draw_options, **overrides},
        background="#ffffff",
    )
    mol = _parse_structure(smiles)
    _prepare_for_drawing(mol)
    options = _build_options(spec, mol=mol, transparent=False, show_atom_indices=False)
    return _img(_draw_png(mol, options, _estimate_canvas(mol), None))


def _current_panel(smiles: str) -> Image.Image:
    result = chemglyph.render_molecule(smiles, style="modern", fmt="png", transparent=False)
    return _img(result.data)


def _colored_ink_stats(images: list[Image.Image]) -> tuple[float, float]:
    colored = 0
    total = 0
    luminance = 0
    for image in images:
        for red, green, blue, alpha in image.getdata():
            if alpha < 128:
                continue
            if min(red, green, blue) < 180:
                total += 1
                if max(red, green, blue) - min(red, green, blue) > 30:
                    colored += 1
                    luminance += 0.299 * red + 0.587 * green + 0.114 * blue
    share = colored / total if total else 0.0
    mean_luminance = luminance / colored if colored else 0.0
    return share, mean_luminance


def main() -> None:
    columns = [
        ("current (12/28 + dark CPK + 1.8)", None, {}),
        ("A: font 14/32", {"minFontSize": 14, "maxFontSize": 32}, {}),
        ("B: classic CPK", {}, {"atom_colours": CLASSIC_CPK}),
        ("C: line 2.0", {}, {"bondLineWidth": 2.0}),
    ]
    width = 2 * PAD + NAME_W + len(columns) * CELL + (len(columns) - 1) * GAP
    height = HEADER + len(MOLECULES) * ROW_H + PAD
    page = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(page)
    draw.text((PAD, 24), "molecule", font=_font(26), fill=INK, anchor="lm")
    for column, (header, _, _) in enumerate(columns):
        x = PAD + NAME_W + column * (CELL + GAP) + CELL // 2
        draw.text((x, 24), header, font=_font(22), fill=INK, anchor="mm")

    panels_per_column: list[list[Image.Image]] = [[] for _ in columns]
    for row, (label, smiles) in enumerate(MOLECULES):
        y = HEADER + row * ROW_H
        draw.text((PAD, y + CELL // 2), label, font=_font(22), fill=INK, anchor="lm")
        for column, (_, font_overrides, other_overrides) in enumerate(columns):
            if font_overrides:
                panel = _variant_panel(smiles, font_overrides)
            elif other_overrides:
                panel = _variant_panel(smiles, other_overrides)
            else:
                panel = _current_panel(smiles)
            panels_per_column[column].append(panel)
            x = PAD + NAME_W + column * (CELL + GAP) + (CELL - panel.width) // 2
            page.paste(panel, (x, y + (CELL - panel.height) // 2), panel)

    out_dir = _REPO_ROOT / "benchmarks" / "blind_review"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "modern_callback.png"
    page.convert("RGB").save(out_path)
    print(f"wrote {out_path}")

    print("colored-ink stats (share, mean luminance):")
    for column, (header, _, _) in enumerate(columns):
        share, mean_luminance = _colored_ink_stats(panels_per_column[column])
        print(f"  {header}: share={share:.3f} luminance={mean_luminance:.1f}")


if __name__ == "__main__":
    main()
