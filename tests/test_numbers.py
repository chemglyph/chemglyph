"""Compound numbers: bold, at label size, centred under the structure, and recorded."""

from __future__ import annotations

import re

import pytest
from rdkit import Chem

import chemglyph
from chemglyph.errors import ChemGlyphRenderError
from chemglyph.profiles import PROFILES

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"


def _points(svg: str, pattern: str) -> list[tuple[float, float]]:
    return [
        (float(x), float(y))
        for path in re.findall(pattern, svg)
        for x, y in re.findall(r"(-?[\d.]+)[ ,](-?[\d.]+)", path)
    ]


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_number_sits_centred_under_the_structure_at_label_size(profile: str) -> None:
    svg = chemglyph.render_molecule(ASPIRIN, style=profile, number="12").data
    number = _points(svg, r"class='compound-number' d='([^']+)'")
    bonds = _points(svg, r"class='bond-\d+[^']*' d='([^']+)'")
    oxygen = _points(svg, r"class='atom-3' d='([^']+)'")
    assert number and bonds and oxygen
    p = PROFILES[profile]
    k = 10  # SVG user units per point
    height = max(y for _, y in number) - min(y for _, y in number)
    # Digits and the capital O have the same height in Liberation Sans.
    o_height = max(y for _, y in oxygen) - min(y for _, y in oxygen)
    assert height == pytest.approx(o_height, abs=0.3 * k)
    ink = bonds + _points(svg, r"class='atom-\d+' d='([^']+)'")
    ink_left = min(x for x, _ in ink)
    ink_right = max(x for x, _ in ink)
    centre = (min(x for x, _ in number) + max(x for x, _ in number)) / 2
    assert centre == pytest.approx((ink_left + ink_right) / 2, abs=0.5 * k)
    gap = min(y for _, y in number) - max(y for _, y in ink)
    assert gap == pytest.approx(0.5 * p.bond_length_pt * k, abs=1.0 * k)


def test_number_is_bold() -> None:
    plain_one = chemglyph.render_molecule("[Na+].[Cl-]", style="acs1996").data
    numbered = chemglyph.render_molecule("C", style="acs1996", number="1").data
    stroke = max(x for x, _ in _points(numbered, r"class='compound-number' d='([^']+)'"))
    stroke -= min(x for x, _ in _points(numbered, r"class='compound-number' d='([^']+)'"))
    # A bold "1" in Liberation Sans is wider than 3.5 pt at 10 pt; regular is about 2.9 pt.
    assert stroke > 35
    assert "compound-number" not in plain_one


@pytest.mark.parametrize("fmt", ["svg", "png", "pdf", "mol"])
def test_number_is_recorded_with_the_structure(fmt: str) -> None:
    result = chemglyph.render_molecule(ASPIRIN, number="2a", fmt=fmt)
    assert result.report["number"] == "2a"
    data = result.data
    mol = Chem.MolFromMolBlock(data) if fmt == "mol" else chemglyph.read_structure(data)
    assert mol.GetProp("_Name") == "2a"


@pytest.mark.parametrize("bad", ["<b>1</b>", "1\n2"])
def test_number_must_be_plain_text(bad: str) -> None:
    with pytest.raises(ChemGlyphRenderError):
        chemglyph.render_molecule(ASPIRIN, number=bad)
