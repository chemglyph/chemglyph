"""Style preset tests: golden structural snapshots per §4.5.

Assertions are structural (element counts, color presence, stroke widths),
never pixel-level, so results are stable across platforms and fonts.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import pytest
from rdkit import Chem

import chemglyph
from chemglyph.errors import ChemGlyphStyleError
from chemglyph.styles import STYLES, StyleSpec, get_style

GOLDEN_MOLECULES = {
    "benzoic-acid": "OC(=O)c1ccccc1",
    "caffeine": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "s-ibuprofen": "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O",
}

_EXPECTED_BOND_WIDTH = {"acs": 2.0, "modern": 2.4, "textbook-cn": 2.6}
_EXPECTED_FONT_SIZES = {
    "acs": (16, 36),
    "modern": (14, 32),
    "textbook-cn": (18, 40),
}


def _svg(smiles: str, style: str) -> str:
    result = chemglyph.render_molecule(smiles, style=style)
    assert result.fmt == "svg"
    return result.data


def _stroke_widths(svg: str) -> list[float]:
    return [float(value) for value in re.findall(r"stroke-width:([0-9.]+)", svg)]


def _label_heights(svg: str) -> list[float]:
    root = ET.fromstring(svg)
    heights: list[float] = []
    for element in root.iter():
        if (element.attrib.get("class") or "").startswith("atom-"):
            numbers = [
                float(value) for value in re.findall(r"-?\d+\.?\d*", element.attrib.get("d", ""))
            ]
            if len(numbers) >= 4:
                ys = numbers[1::2]
                heights.append(max(ys) - min(ys))
    return heights


def _first_bond_length(svg: str) -> float:
    match = re.search(r"d='M\s*([\d.]+),([\d.]+)\s+L\s*([\d.]+),([\d.]+)'", svg)
    assert match is not None, "no plain bond found in SVG"
    x1, y1, x2, y2 = (float(part) for part in match.groups())
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def _element_ids(svg: str) -> tuple[set[int], set[int]]:
    bonds = {int(value) for value in re.findall(r"bond-(\d+)", svg)}
    atoms = {int(value) for value in re.findall(r"atom-(\d+)", svg)}
    return bonds, atoms


def test_styles_registered_and_resolvable() -> None:
    assert STYLES == {"acs", "modern", "textbook-cn"}
    for name in STYLES:
        spec = get_style(name)
        assert isinstance(spec, StyleSpec)
        assert spec.name == name


def test_unknown_style_raises() -> None:
    with pytest.raises(ChemGlyphStyleError):
        get_style("neon")


@pytest.mark.parametrize("style", sorted(STYLES))
@pytest.mark.parametrize("label", sorted(GOLDEN_MOLECULES))
def test_golden_snapshots_match_structure(style: str, label: str) -> None:
    smiles = GOLDEN_MOLECULES[label]
    mol = Chem.MolFromSmiles(smiles)
    svg = _svg(smiles, style)
    bonds, atoms = _element_ids(svg)
    # Every atom and bond must be drawn exactly once as a class id; wedge
    # dashes repeat bond classes, so compare id sets rather than raw counts.
    assert bonds == set(range(mol.GetNumBonds()))
    assert atoms == set(range(mol.GetNumAtoms()))
    assert "viewBox" in svg


def test_modern_colors_heteroatoms() -> None:
    benzoic = _svg(GOLDEN_MOLECULES["benzoic-acid"], "modern")
    caffeine = _svg(GOLDEN_MOLECULES["caffeine"], "modern")
    assert "#FF0D0D" in benzoic  # O red (CPK)
    assert "#FF0D0D" in caffeine  # O red (CPK)
    assert "#3050F8" in caffeine  # N blue (CPK)


@pytest.mark.parametrize("style", ["acs", "textbook-cn"])
def test_monochrome_styles_have_no_heteroatom_colors(style: str) -> None:
    benzoic = _svg(GOLDEN_MOLECULES["benzoic-acid"], style)
    assert "#FF0D0D" not in benzoic
    assert "#3050F8" not in benzoic


@pytest.mark.parametrize("style", sorted(STYLES))
def test_stereo_wedge_is_rendered(style: str) -> None:
    ibuprofen = _svg(GOLDEN_MOLECULES["s-ibuprofen"], style)
    # RDKit draws a dashed stereo wedge as many short segments sharing one
    # bond class id (plain bonds repeat at most ~3 times for double bonds).
    bond_counts: dict[str, int] = {}
    for value in re.findall(r"class=['\"]bond-(\d+)", ibuprofen):
        bond_counts[value] = bond_counts.get(value, 0) + 1
    assert max(bond_counts.values()) >= 8


def test_textbook_bonds_are_thicker_than_acs() -> None:
    smiles = GOLDEN_MOLECULES["caffeine"]
    acs_widths = _stroke_widths(_svg(smiles, "acs"))
    textbook_widths = _stroke_widths(_svg(smiles, "textbook-cn"))
    assert sum(acs_widths) / len(acs_widths) < sum(textbook_widths) / len(textbook_widths)


@pytest.mark.parametrize("style", sorted(STYLES))
def test_bond_stroke_width_matches_style_golden(style: str) -> None:
    svg = _svg(GOLDEN_MOLECULES["caffeine"], style)
    widths = _stroke_widths(svg)
    expected = _EXPECTED_BOND_WIDTH[style]
    assert widths, "no stroke widths found in SVG"
    assert max(widths) <= expected + 0.15
    assert any(abs(width - expected) < 0.1 for width in widths)


def test_style_spec_bond_widths_match_golden() -> None:
    for style, expected in _EXPECTED_BOND_WIDTH.items():
        assert get_style(style).draw_options["bondLineWidth"] == expected


def test_style_spec_font_sizes_match_golden() -> None:
    for style, expected in _EXPECTED_FONT_SIZES.items():
        options = get_style(style).draw_options
        assert (options["minFontSize"], options["maxFontSize"]) == expected


@pytest.mark.parametrize("style", sorted(STYLES))
def test_labels_are_readable_at_default_canvas(style: str) -> None:
    """Every style must keep atom labels readable at the auto-sized canvas."""
    smiles = GOLDEN_MOLECULES["benzoic-acid"]
    heights = sorted(_label_heights(_svg(smiles, style)))
    median = heights[len(heights) // 2]
    # Roughly >= 18px font (sans-serif cap height ~0.7em); RDKit's ACS1996
    # preset pins labels at 10px (7px cap), which this floor rejects.
    assert median >= 12.0


def test_acs_labels_scale_with_canvas_instead_of_being_pinned() -> None:
    """ACS labels must scale with the canvas, not stay pinned at 10px.

    Regression guard for the ACS1996 preset: ``SetACS1996Mode`` pins
    ``fixedFontSize`` at 10px and ``fixedBondLength`` at an absolute size.
    The acs StyleSpec must disable both so the declared ``minFontSize`` /
    ``maxFontSize`` range governs, otherwise the letters look tiny next to
    bonds on any reasonably sized canvas.
    """
    smiles = GOLDEN_MOLECULES["benzoic-acid"]
    result = chemglyph.render_molecule(smiles, style="acs", size=(320, 320))
    heights = sorted(_label_heights(result.data))
    median = heights[len(heights) // 2]
    bond = _first_bond_length(result.data)
    assert median >= 14.0, "ACS labels reverted to the pinned 10px font"
    # The ACS proportion should stay label-forward: cap height roughly
    # 0.3-0.8x a bond. A mis-scaled mean bond length (e.g. 0.18) inflates
    # bonds ~8x and drags this ratio below 0.2.
    assert 0.3 <= median / bond <= 0.8


def test_transparent_background_by_default() -> None:
    svg = _svg(GOLDEN_MOLECULES["benzoic-acid"], "modern")
    assert "fill:#FFFFFF" not in svg


def test_opaque_background_when_requested() -> None:
    result = chemglyph.render_molecule(
        GOLDEN_MOLECULES["benzoic-acid"], style="modern", transparent=False
    )
    assert "fill:#FFFFFF" in result.data
