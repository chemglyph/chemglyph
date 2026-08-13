"""Tests for SVG measurement helpers in svg_utils."""

from __future__ import annotations

import pytest

import chemglyph
from chemglyph.errors import ChemGlyphRenderError
from chemglyph.svg_utils import content_viewbox, extract_viewbox


def test_content_viewbox_hand_built_document() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
        '<rect x="10" y="20" width="30" height="40"/>'
        '<circle cx="80" cy="60" r="10"/>'
        '<line x1="100" y1="10" x2="120" y2="90"/>'
        "</svg>"
    )
    box = content_viewbox(svg)
    assert (box.x, box.y, box.width, box.height) == (10.0, 10.0, 110.0, 80.0)


def test_content_viewbox_margin_expands_box() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<circle cx="40" cy="40" r="5"/>'
        "</svg>"
    )
    box = content_viewbox(svg, margin=3.0)
    assert (box.x, box.y, box.width, box.height) == (32.0, 32.0, 16.0, 16.0)


def test_content_viewbox_is_tighter_than_rdkit_canvas() -> None:
    result = chemglyph.render_molecule("OC(=O)c1ccccc1")
    full = extract_viewbox(result.data)
    tight = content_viewbox(result.data)
    assert full is not None
    assert tight.width < full.width
    assert tight.height < full.height
    assert tight.x >= full.x
    assert tight.y >= full.y


def test_content_viewbox_falls_back_to_viewbox_without_geometry() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50"></svg>'
    assert content_viewbox(svg) == extract_viewbox(svg)


def test_content_viewbox_raises_without_geometry_or_viewbox() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    with pytest.raises(ChemGlyphRenderError):
        content_viewbox(svg)
