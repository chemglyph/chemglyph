"""PDF and MOL output of the fixed-scale profiles, and highlight geometry."""

from __future__ import annotations

import io
import math
import re

import pytest
from rdkit import Chem

import chemglyph
from blind_test_molecules import BLIND_TEST_MOLECULES
from chemglyph.errors import ChemGlyphRenderError
from chemglyph.metadata import identity

pypdf = pytest.importorskip("pypdf")

CHOLESTEROL = "CC(C)CCC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(C)CC[C@H]1[C@H]2CC=C2C[C@@H](O)CC[C@]12C"


@pytest.mark.parametrize("style", ["acs1996", "screen", "textbook"])
def test_pdf_is_a_valid_page_of_the_figure_size(style: str) -> None:
    result = chemglyph.render_molecule(CHOLESTEROL, style=style, fmt="pdf")
    assert result.data.startswith(b"%PDF-1.4")
    reader = pypdf.PdfReader(io.BytesIO(result.data))
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert float(box.width) == pytest.approx(result.report["width_pt"], abs=0.01)
    assert float(box.height) == pytest.approx(result.report["height_pt"], abs=0.01)
    content = reader.pages[0].get_contents().get_data().decode("ascii")
    assert " c\n" in content  # glyph outlines as curves, not a raster image
    assert "/Image" not in result.data.decode("latin-1")


@pytest.mark.parametrize(
    "label,smiles", [(label, smiles) for label, smiles, _ in BLIND_TEST_MOLECULES]
)
def test_pdf_carries_the_structure(label: str, smiles: str) -> None:
    result = chemglyph.render_molecule(smiles, style="acs1996", fmt="pdf")
    back = chemglyph.read_structure(result.data)
    assert identity(back)["inchikey"] == result.report["identity"]["inchikey"], label


def test_pdf_is_deterministic() -> None:
    first = chemglyph.render_molecule(CHOLESTEROL, style="acs1996", fmt="pdf").data
    second = chemglyph.render_molecule(CHOLESTEROL, style="acs1996", fmt="pdf").data
    assert first == second


def test_mol_output_keeps_the_drawn_layout() -> None:
    result = chemglyph.render_molecule(CHOLESTEROL, style="acs1996", fmt="mol")
    mol = Chem.MolFromMolBlock(result.data)
    assert mol is not None and mol.GetNumConformers() == 1
    assert identity(mol)["inchikey"] == result.report["identity"]["inchikey"]


@pytest.mark.parametrize("fmt", ["pdf", "mol"])
def test_older_styles_refuse_pdf_and_mol(fmt: str) -> None:
    with pytest.raises(ChemGlyphRenderError, match="fixed-scale"):
        chemglyph.render_molecule("CCO", style="modern", fmt=fmt)


def test_highlighted_bonds_stay_narrower_than_half_a_bond() -> None:
    svg = chemglyph.render_molecule("CCCC", style="acs1996", highlight_atoms=[0, 1, 2, 3]).data
    bands = re.findall(r"<path class='bond-\d+[^']*' d='(M [^']*Z)' style='fill:#FF7F7F", svg)
    assert bands
    for path in bands:
        corners = [(float(x), float(y)) for x, y in re.findall(r"([-\d.]+),([-\d.]+)", path)]
        sides = [
            math.dist(corners[i], corners[(i + 1) % len(corners)]) for i in range(len(corners))
        ]
        assert min(sides) / 10 < 14.4 / 2  # the band once was 19 pt wide
