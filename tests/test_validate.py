"""Structure validation tests (see §7 of the specification)."""

from __future__ import annotations

import pytest
from rdkit import Chem

import chemglyph


def test_valid_smiles_report() -> None:
    report = chemglyph.validate_structure("CC(=O)Oc1ccccc1C(=O)O")
    assert report.valid
    assert report.canonical_smiles == "CC(=O)Oc1ccccc1C(=O)O"
    assert report.mol_formula == "C9H8O4"
    assert report.mol_weight == pytest.approx(180.16, abs=0.05)
    assert report.errors == []
    assert report.fixes == []


def test_inchi_passthrough() -> None:
    report = chemglyph.validate_structure(
        "InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)"
    )
    assert report.valid
    assert report.mol_formula == "C9H8O4"


def test_unbalanced_bracket_reported_without_guessing() -> None:
    report = chemglyph.validate_structure("CC(=O))O")
    assert not report.valid
    assert any("parenthesis" in issue.message for issue in report.errors)
    assert report.fixes == []


def test_odd_ring_closure_reported() -> None:
    report = chemglyph.validate_structure("C1CCC2")
    assert not report.valid
    assert any("ring-closure" in issue.message for issue in report.errors)


def test_lowercase_aromatic_kekulize_fix() -> None:
    report = chemglyph.validate_structure("c1cccc1")
    assert not report.valid
    assert len(report.fixes) == 1
    assert report.fixes[0].fixed_smiles == Chem.MolToSmiles(Chem.MolFromSmiles("C1CCCC1"))
    assert "kekulized" in report.fixes[0].description


def test_nitrogen_valence_fix_adds_charge() -> None:
    report = chemglyph.validate_structure("N(=O)=O")
    assert not report.valid
    assert len(report.fixes) == 1
    assert report.fixes[0].fixed_smiles == Chem.MolToSmiles(Chem.MolFromSmiles("[N+](=O)=O"))
    assert "nitrogen valence" in report.fixes[0].description


def test_unfixable_input_reports_rdkit_error() -> None:
    report = chemglyph.validate_structure("C#C#C#")
    assert not report.valid
    assert report.fixes == []
    assert report.errors
