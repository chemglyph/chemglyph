"""Render per-dimension style-parameter candidate sheets for the maintainer.

One sheet per dimension so a single change is never mixed with others:

- ``acs_padding.png``: acs padding ladder (0.02 / 0.035 / 0.05).
- ``modern_font.png``: modern min/max font ladder (14/32, 12/28, 8/20).
- ``modern_color.png``: CPK, darkened CPK, low-saturation palettes.
- ``modern_line.png``: line width + padding ladder.

Output goes to ``benchmarks/blind_review/`` (gitignored). The representative
molecule set is benzoic acid, caffeine, sulfate, triphenylphosphine, TNT and
18-crown-6.

Usage::

    python benchmarks/param_candidates.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

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
HEADER = 72
GAP = 20
ROW_H = CELL + 2 * PAD + 26
BG = (255, 255, 255, 255)
INK = (24, 24, 24, 255)

MOLECULES = [
    ("benzoic acid", "OC(=O)c1ccccc1"),
    ("caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("sulfate", "[O-]S(=O)(=O)[O-]"),
    ("triphenylphosphine", "c1ccc(cc1)P(c1ccccc1)c1ccccc1"),
    ("tnt", "Cc1c(cc(cc1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]"),
    ("18-crown-6", "C1COCCOCCOCCOCCOCCO1"),
]

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


def _variant(name: str, base: StyleSpec, overrides: dict) -> StyleSpec:
    return StyleSpec(
        name=name, draw_options={**base.draw_options, **overrides}, background="#ffffff"
    )


def _panel(smiles: str, spec: StyleSpec) -> Image.Image:
    mol = _parse_structure(smiles)
    _prepare_for_drawing(mol)
    options = _build_options(spec, mol=mol, transparent=False, show_atom_indices=False)
    return _img(_draw_png(mol, options, _estimate_canvas(mol), None))


def _colored_ink_stats(images: list[Image.Image]) -> tuple[float, float]:
    """Share of colored ink and its mean luminance (0=black, 255=white)."""
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


def _sheet(columns: list[tuple[str, StyleSpec]], out_path: Path) -> None:
    width = 2 * PAD + 220 + len(columns) * CELL + (len(columns) - 1) * GAP
    height = HEADER + len(MOLECULES) * ROW_H + PAD
    page = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(page)
    draw.text((PAD, 24), "molecule", font=_font(26), fill=INK, anchor="lm")
    for column, (header, _) in enumerate(columns):
        x = PAD + 220 + column * (CELL + GAP) + CELL // 2
        draw.text((x, 24), header, font=_font(23), fill=INK, anchor="mm")
    for row, (label, smiles) in enumerate(MOLECULES):
        y = HEADER + row * ROW_H
        draw.text((PAD, y + CELL // 2), label, font=_font(22), fill=INK, anchor="lm")
        for column, (_, spec) in enumerate(columns):
            panel = _panel(smiles, spec)
            x = PAD + 220 + column * (CELL + GAP) + (CELL - panel.width) // 2
            page.paste(panel, (x, y + (CELL - panel.height) // 2), panel)
    page.convert("RGB").save(out_path)
    print(f"wrote {out_path}")


def _acs_padding_sheet(out_dir: Path) -> None:
    base = get_style("acs")
    _sheet(
        [
            ("acs padding 0.02 (current)", _variant("probe", base, {"padding": 0.02})),
            ("acs padding 0.035", _variant("probe", base, {"padding": 0.035})),
            ("acs padding 0.05", _variant("probe", base, {"padding": 0.05})),
        ],
        out_dir / "acs_padding.png",
    )


def _modern_font_sheet(out_dir: Path) -> None:
    base = get_style("modern")
    _sheet(
        [
            ("modern font 14/32 (current)", _variant("probe", base, {})),
            (
                "modern font 12/28",
                _variant("probe", base, {"minFontSize": 12, "maxFontSize": 28}),
            ),
            (
                "modern font 8/20",
                _variant("probe", base, {"minFontSize": 8, "maxFontSize": 20}),
            ),
        ],
        out_dir / "modern_font.png",
    )


def _modern_color_sheet(out_dir: Path) -> None:
    base = get_style("modern")
    palettes = {
        "CPK": {8: "#FF0D0D", 7: "#3050F8", 16: "#E8C300", 17: "#1FB01F"},
        "darkened CPK": {8: "#C0392B", 7: "#2471A3", 16: "#A67C00", 17: "#1E8449"},
        "low saturation": {8: "#A93226", 7: "#2C5F8A", 16: "#8F7A1A", 17: "#2E7D46"},
    }
    columns = []
    for name, palette in palettes.items():
        columns.append((f"modern {name}", _variant("probe", base, {"atom_colours": palette})))
    _sheet(columns, out_dir / "modern_color.png")

    # Ink-share metric: render each palette's six molecules and measure the
    # share of drawn ink that is colored (heteroatom labels + their bond halves).
    metrics: dict[str, tuple[float, float]] = {}
    for name, palette in palettes.items():
        spec = _variant("probe", base, {"atom_colours": palette})
        panels = [_panel(smiles, spec) for _, smiles in MOLECULES]
        metrics[name] = _colored_ink_stats(panels)
    with open(out_dir / "modern_color_metrics.txt", "w", encoding="utf-8") as handle:
        for name, (share, mean_luminance) in metrics.items():
            handle.write(
                f"{name}: colored ink share {share:.3f}, mean luminance {mean_luminance:.1f}\n"
            )
    print(
        "colored-ink stats:",
        {
            name: (round(share, 3), round(mean_luminance, 1))
            for name, (share, mean_luminance) in metrics.items()
        },
    )


def _modern_line_sheet(out_dir: Path) -> None:
    base = get_style("modern")
    _sheet(
        [
            ("modern 2.4 / pad 0.03 (current)", _variant("probe", base, {})),
            (
                "modern 2.0 / pad 0.045",
                _variant("probe", base, {"bondLineWidth": 2.0, "padding": 0.045}),
            ),
            (
                "modern 1.8 / pad 0.06",
                _variant("probe", base, {"bondLineWidth": 1.8, "padding": 0.06}),
            ),
        ],
        out_dir / "modern_line.png",
    )


def main() -> None:
    out_dir = _REPO_ROOT / "benchmarks" / "blind_review"
    out_dir.mkdir(parents=True, exist_ok=True)
    _acs_padding_sheet(out_dir)
    _modern_font_sheet(out_dir)
    _modern_color_sheet(out_dir)
    _modern_line_sheet(out_dir)


if __name__ == "__main__":
    main()
