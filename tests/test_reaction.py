"""Reaction layout engine tests (see §6.3 of the specification)."""

from __future__ import annotations

import re

import pytest

import chemglyph
from chemglyph.errors import ChemGlyphReactionError

ASPIRIN_STEP = {
    "steps": [
        {
            "reactants": ["OC(=O)c1ccccc1O", "CC(=O)OC(C)=O"],
            "products": ["CC(=O)Oc1ccccc1C(=O)O"],
            "conditions": {"above": "H2SO4 (cat.)", "below": "rt, 15 min"},
            "yield": "89%",
            "arrow": "forward",
        }
    ],
    "style": "modern",
}


def _render(spec: dict) -> str:
    return chemglyph.render_reaction(spec)


def _count(svg: str, token: str) -> int:
    return svg.count(token)


def test_single_step_with_conditions_and_yield() -> None:
    svg = _render(ASPIRIN_STEP)
    assert _count(svg, 'class="chemglyph-fragment"') == 3
    assert _count(svg, 'class="chemglyph-plus"') == 1
    assert _count(svg, 'class="chemglyph-arrow chemglyph-arrow-forward"') == 1
    assert _count(svg, 'class="chemglyph-arrowhead"') == 1
    assert _count(svg, 'class="chemglyph-condition"') == 2
    assert "H2SO4 (cat.)" in svg
    assert "rt, 15 min (89%)" in svg
    assert svg.count("<svg") == 1
    assert 'fill="#FFFFFF"' not in svg  # transparent background by default


def test_equilibrium_arrow_has_two_half_arrowheads() -> None:
    spec = {
        "steps": [
            {
                "reactants": ["CC(=O)O"],
                "products": ["CC(=O)[O-]", "O"],
                "arrow": "equilibrium",
            }
        ]
    }
    svg = _render(spec)
    assert _count(svg, "chemglyph-arrow-equilibrium") == 2  # two half arrows
    assert _count(svg, 'class="chemglyph-arrowhead"') == 2


def test_retro_arrow_draws_double_line_pointing_left() -> None:
    spec = {
        "steps": [
            {
                "reactants": ["CC(=O)Oc1ccccc1C(=O)O"],
                "products": ["OC(=O)c1ccccc1O"],
                "arrow": "retro",
            }
        ]
    }
    svg = _render(spec)
    assert _count(svg, "chemglyph-arrow-retro") == 2  # two parallel lines
    assert _count(svg, 'class="chemglyph-arrowhead"') == 2


def test_three_step_wrap_produces_multiple_rows() -> None:
    spec = {
        "steps": [
            {"reactants": ["O"], "products": ["CC"]},
            {"reactants": ["CC"], "products": ["CCC"]},
            {"reactants": ["CCC"], "products": ["CCCC"]},
        ],
        "layout": {"max_width": 260},
    }
    svg = _render(spec)
    translate_y = [
        float(value)
        for value in re.findall(
            r'class="chemglyph-fragment" transform="translate\([^,]+,([^)]+)\)"', svg
        )
    ]
    assert len(set(translate_y)) >= 2


def test_continuation_step_does_not_redraw_intermediate() -> None:
    spec = {
        "steps": [
            {"reactants": ["O"], "products": ["CC"]},
            {"reactants": ["CC"], "products": ["CCC"]},
        ],
        "layout": {"max_width": 2000},
    }
    svg = _render(spec)
    assert _count(svg, 'class="chemglyph-fragment"') == 3  # O, CC, CCC
    assert _count(svg, 'class="chemglyph-arrow chemglyph-arrow-') == 2


def test_empty_steps_rejected() -> None:
    with pytest.raises(ChemGlyphReactionError):
        _render({"steps": []})


def test_unknown_arrow_rejected() -> None:
    with pytest.raises(ChemGlyphReactionError):
        _render({"steps": [{"reactants": ["O"], "products": ["O"], "arrow": "wavy"}]})
