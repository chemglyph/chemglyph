"""Style preset tests: golden structural snapshots per §4.5.

Assertions are structural (element counts, color presence, stroke widths),
never pixel-level, so results are stable across platforms and fonts.
"""

from __future__ import annotations

import re

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


def _svg(smiles: str, style: str) -> str:
    result = chemglyph.render_molecule(smiles, style=style)
    assert result.fmt == "svg"
    return result.data


def _stroke_widths(svg: str) -> list[float]:
    return [float(value) for value in re.findall(r"stroke-width:([0-9.]+)", svg)]


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
    assert "#D62728" in benzoic  # O red
    assert "#D62728" in caffeine  # O red
    assert "#1F77B4" in caffeine  # N blue


@pytest.mark.parametrize("style", ["acs", "textbook-cn"])
def test_monochrome_styles_have_no_heteroatom_colors(style: str) -> None:
    benzoic = _svg(GOLDEN_MOLECULES["benzoic-acid"], style)
    assert "#D62728" not in benzoic
    assert "#1F77B4" not in benzoic


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


def test_transparent_background_by_default() -> None:
    svg = _svg(GOLDEN_MOLECULES["benzoic-acid"], "modern")
    assert "fill:#FFFFFF" not in svg


def test_opaque_background_when_requested() -> None:
    result = chemglyph.render_molecule(
        GOLDEN_MOLECULES["benzoic-acid"], style="modern", transparent=False
    )
    assert "fill:#FFFFFF" in result.data
