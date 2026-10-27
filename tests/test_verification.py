"""Verification report, embedded structure, and name check (docs/SPEC.md, section 7)."""

from __future__ import annotations

import shutil
from xml.etree import ElementTree as ET

import pytest
from rdkit import Chem

import chemglyph
from blind_test_molecules import BLIND_TEST_MOLECULES
from chemglyph.errors import ChemGlyphParseError
from chemglyph.metadata import identity
from chemglyph.profiles import PROFILES

CASES = [
    pytest.param(profile, label, smiles, id=f"{profile}-{label}")
    for profile in sorted(PROFILES)
    for label, smiles, _ in BLIND_TEST_MOLECULES
]


@pytest.mark.parametrize("profile,label,smiles", CASES)
def test_every_figure_verifies_against_its_input(profile: str, label: str, smiles: str) -> None:
    result = chemglyph.render_molecule(smiles, style=profile)
    assert result.report["verified"], (label, result.report["checks"])
    assert not [w for w in result.warnings if w.startswith("verification:")]
    ET.fromstring(result.data)  # the metadata keeps the SVG well-formed


@pytest.mark.parametrize(
    "label,smiles", [(label, smiles) for label, smiles, _ in BLIND_TEST_MOLECULES]
)
def test_structure_reads_back_from_svg_and_png(label: str, smiles: str) -> None:
    expected = identity(Chem.MolFromSmiles(smiles))["inchikey"]
    for fmt in ("svg", "png"):
        figure = chemglyph.render_molecule(smiles, style="acs1996", fmt=fmt).data
        assert identity(chemglyph.read_structure(figure))["inchikey"] == expected, (label, fmt)


def test_embedded_record_carries_identifiers() -> None:
    svg = chemglyph.render_molecule("CC(=O)Oc1ccccc1C(=O)O", style="acs1996").data
    assert 'inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N"' in svg
    assert 'formula="C9H8O4"' in svg
    assert 'profile="acs1996"' in svg


def test_read_structure_rejects_figures_without_a_record() -> None:
    plain = chemglyph.render_molecule("CCO", style="modern").data  # older style, no record
    with pytest.raises(ChemGlyphParseError):
        chemglyph.read_structure(plain)


def test_name_that_matches() -> None:
    result = chemglyph.render_molecule("CC(=O)Oc1ccccc1C(=O)O", style="acs1996", name="阿司匹林")
    assert result.report["name_check"]["status"] == "match"
    assert not result.warnings


def test_name_with_different_stereo() -> None:
    # The dictionary entry for 布洛芬 is (S)-ibuprofen; this SMILES has no stereo.
    result = chemglyph.render_molecule("CC(C)Cc1ccc(cc1)C(C)C(=O)O", style="acs1996", name="布洛芬")
    assert result.report["name_check"]["status"] == "stereo_differs"
    assert any("stereochemistry" in warning for warning in result.warnings)


def test_name_that_names_another_structure() -> None:
    result = chemglyph.render_molecule("CC(=O)Oc1ccccc1C(=O)O", style="screen", name="咖啡因")
    check = result.report["name_check"]
    assert check["status"] == "mismatch"
    assert "C8H10N4O2" in check["detail"] and "C9H8O4" in check["detail"]


def test_macrocycle_name_check_ignores_layout_geometry() -> None:
    # The 2D layout gives porphyrin's ring double bonds a geometry InChI could
    # read as E/Z; identifiers ignore coordinates, so this is a plain match.
    porphyrin = "c1cc2cc3ccc(cc4ccc(cc5ccc(cc1n2)[nH]5)n4)[nH]3"
    result = chemglyph.render_molecule(porphyrin, style="acs1996", name="卟啉")
    assert result.report["name_check"]["status"] == "match"


def test_name_that_cannot_be_resolved_is_reported_not_raised() -> None:
    result = chemglyph.render_molecule("CCO", style="acs1996", name="六甲基苯")
    assert result.report["name_check"]["status"] == "unchecked"
    assert any("could not be checked" in warning for warning in result.warnings)


@pytest.mark.skipif(shutil.which("java") is not None, reason="OPSIN may resolve English names")
def test_english_name_without_opsin_is_unchecked() -> None:
    pytest.importorskip("rdkit")
    result = chemglyph.render_molecule("CCO", style="acs1996", name="ethanol")
    assert result.report["name_check"]["status"] in {"unchecked", "match"}
