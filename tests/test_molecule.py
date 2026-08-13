"""Molecule rendering tests (see §5 of the specification)."""

from __future__ import annotations

import re

import pytest
from rdkit import Chem

import chemglyph
from chemglyph.errors import (
    ChemGlyphParseError,
    ChemGlyphRenderError,
    ChemGlyphStyleError,
)

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
ASPIRIN_INCHI = "InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)"


def test_smiles_metadata() -> None:
    result = chemglyph.render_molecule(ASPIRIN)
    assert result.fmt == "svg"
    assert "<svg" in result.data
    assert result.canonical_smiles == Chem.MolToSmiles(Chem.MolFromSmiles(ASPIRIN))
    assert result.mol_formula == "C9H8O4"
    assert result.mol_weight == pytest.approx(180.16, abs=0.05)
    assert result.warnings == []


def test_inchi_input() -> None:
    result = chemglyph.render_molecule(ASPIRIN_INCHI)
    assert result.mol_formula == "C9H8O4"
    assert result.canonical_smiles == Chem.MolToSmiles(Chem.MolFromSmiles(ASPIRIN))


def test_molblock_input() -> None:
    molblock = Chem.MolToMolBlock(Chem.MolFromSmiles(ASPIRIN))
    result = chemglyph.render_molecule(molblock)
    assert result.mol_formula == "C9H8O4"


def test_parse_error_includes_rdkit_message_and_suggestion() -> None:
    with pytest.raises(ChemGlyphParseError) as exc_info:
        chemglyph.render_molecule("C1CCC2")
    message = str(exc_info.value)
    assert "Could not parse structure" in message
    assert "Suggested fix" in message


def test_unbalanced_parenthesis_suggestion_points_at_syntax() -> None:
    with pytest.raises(ChemGlyphParseError) as exc_info:
        chemglyph.render_molecule("CC(=O))O")
    assert "repair syntax first" in str(exc_info.value)


def test_unknown_style_raises() -> None:
    with pytest.raises(ChemGlyphStyleError):
        chemglyph.render_molecule(ASPIRIN, style="nope")


def test_invalid_format_raises() -> None:
    with pytest.raises(ChemGlyphRenderError):
        chemglyph.render_molecule(ASPIRIN, fmt="gif")


def test_explicit_size_controls_viewbox() -> None:
    result = chemglyph.render_molecule(ASPIRIN, size=(400, 300))
    assert re.search(r"""viewBox=['"]0 0 400 300['"]""", result.data)


def test_atom_indices_add_text_labels() -> None:
    plain = chemglyph.render_molecule(ASPIRIN).data
    indexed = chemglyph.render_molecule(ASPIRIN, show_atom_indices=True).data
    assert indexed.count("<path") > plain.count("<path")


def test_highlight_atoms_draws_markers() -> None:
    plain = chemglyph.render_molecule(ASPIRIN).data
    highlighted = chemglyph.render_molecule(ASPIRIN, highlight_atoms=[0, 1]).data
    assert "ellipse" not in plain
    assert "ellipse" in highlighted


def test_unassigned_stereo_center_warning() -> None:
    result = chemglyph.render_molecule("CC(Cl)O")
    assert any(
        warning == "stereo centers without defined configuration: 1" for warning in result.warnings
    )


def test_png_rendering_when_cairo_available() -> None:
    try:
        result = chemglyph.render_molecule(ASPIRIN, fmt="png")
    except ChemGlyphRenderError as exc:
        if "Cairo" in str(exc):
            pytest.skip("RDKit Cairo backend not available in this environment")
        raise
    assert result.fmt == "png"
    assert isinstance(result.data, bytes)
    assert result.data.startswith(b"\x89PNG")
