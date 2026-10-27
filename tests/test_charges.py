"""Charge signs: true minus signs, placed clear of bonds, and salts that do not collide."""

from __future__ import annotations

import math
import re

import numpy as np
import pytest

import chemglyph
from chemglyph.engine import _flatten


def _boxes(svg: str, atom: int) -> list[tuple[float, float, float, float]]:
    boxes = []
    for path in re.findall(rf"<path class='atom-{atom}' d='([^']+)'", svg):
        segments = np.array(_flatten(path))
        xs = np.r_[segments[:, 0], segments[:, 2]]
        ys = np.r_[segments[:, 1], segments[:, 3]]
        boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    return boxes


def test_negative_charge_is_a_minus_sign_as_wide_as_plus() -> None:
    svg = chemglyph.render_molecule("C[N+](C)(C)CC(=O)[O-]", style="acs1996").data
    plus = _boxes(svg, 1)[-1]  # the sign is drawn after the label
    minus = _boxes(svg, 7)[-1]
    plus_width, minus_width = plus[2] - plus[0], minus[2] - minus[0]
    assert minus_width == pytest.approx(plus_width, rel=0.05)
    assert (minus[3] - minus[1]) < 0.25 * minus_width  # a bar, not a box


def test_sign_moves_off_a_bond_that_leaves_the_upper_right() -> None:
    # Pyridine N-oxide: the O- bond to N goes up and right, where RDKit put the sign.
    result = chemglyph.render_molecule("[O-][n+]1ccccc1", style="textbook")
    svg = result.data
    o_label, sign = _boxes(svg, 0)[0], _boxes(svg, 0)[-1]
    bond = re.search(
        r"class='bond-0 atom-0 atom-1' d='M ([\d.]+),([\d.]+) L ([\d.]+),([\d.]+)'", svg
    )
    x1, y1, x2, y2 = map(float, bond.groups())
    centre = ((o_label[0] + o_label[2]) / 2, (o_label[1] + o_label[3]) / 2)
    sign_centre = ((sign[0] + sign[2]) / 2, (sign[1] + sign[3]) / 2)
    bond_angle = math.degrees(math.atan2(-(y2 - y1), x2 - x1))
    sign_angle = math.degrees(math.atan2(-(sign_centre[1] - centre[1]), sign_centre[0] - centre[0]))
    assert abs((sign_angle - bond_angle + 180) % 360 - 180) > 40
    assert result.report["layout"]["severe"] == 0


def test_no_bond_sits_inside_a_label() -> None:
    # The bond used to be placed in the counter of the O (its hole), clear of
    # every outline edge but inside the letter.
    result = chemglyph.render_molecule("[O-][n+]1ccccc1", style="textbook")
    assert result.report["layout"]["problems"].get("label_overlaps", 0) == 0
    bond = re.search(r"class='bond-0 atom-0 atom-1' d='M ([\d.]+),([\d.]+) L", result.data)
    x, y = map(float, bond.groups())
    o_label = _boxes(result.data, 0)[0]
    assert not (o_label[0] < x < o_label[2] and o_label[1] < y < o_label[3])


@pytest.mark.parametrize(
    "smiles",
    ["[Na+].[Cl-]", "C(=O)([O-])[O-].[Ca+2]", "[Mg+2].[Cl-].[Cl-]", "[CH3-].[Mg+2].[Br-]"],
)
def test_ions_of_a_salt_do_not_collide(smiles: str) -> None:
    for style in ("acs1996", "textbook"):
        result = chemglyph.render_molecule(smiles, style=style)
        assert result.report["layout"]["severe"] == 0, result.warnings
        assert result.report["verified"]


def test_metal_ions_carry_no_radical_dot() -> None:
    # RDKit's valence model gives [Cu+2] an unpaired electron; drawings never show it.
    copper = chemglyph.render_molecule("[Cu+2]", style="acs1996").data
    magnesium = chemglyph.render_molecule("[Mg+2]", style="acs1996").data
    assert copper.count("class='atom-0'") == magnesium.count("class='atom-0'")
    methyl = chemglyph.render_molecule("[CH3]", style="acs1996").data
    assert (
        methyl.count("class='atom-0'")
        == chemglyph.render_molecule("C", style="acs1996").data.count("class='atom-0'") + 1
    )  # an organic radical keeps its dot
