"""Group abbreviations: where they apply, and that figures stay checkable."""

from __future__ import annotations

import pytest
from rdkit import Chem
from rdkit.Chem import rdDepictor

import chemglyph
from chemglyph.abbreviations import GROUPS, abbreviate, select
from chemglyph.errors import ChemGlyphStyleError

BOC_HOMOSERINE = "COC(=O)[C@H](CCOS(=O)(=O)c1ccc(C)cc1)NC(=O)OC(C)(C)C"


def _labels(smiles: str, choice=True) -> list[str]:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.Compute2DCoords(mol)
    found = abbreviate(mol, select(choice))
    return [] if found is None else sorted(group["label"] for group in found.groups)


@pytest.mark.parametrize(
    ("smiles", "labels"),
    [
        ("N[C@@H](Cc1ccccc1)C(=O)O", []),  # a benzyl side chain is not Bn
        ("CC(=O)c1ccccc1", []),  # acetophenone is not PhAc
        ("COC(=O)[C@H](Cc1ccccc1)NC(=O)OC(C)(C)C", ["NHBoc"]),
        ("CC(C)(C)OC(=O)N1CCCCC1", ["Boc"]),  # on a ring N: N-Boc
        ("C#C[Si](C)(C)C", ["TMS"]),  # silyl groups also on carbon
        ("CC(=O)Oc1ccccc1C(=O)O", ["OAc"]),
        ("OC[C@H]1O[C@@H](OCc2ccccc2)[C@H](O)[C@@H](O)[C@@H]1O", ["OBn"]),
        ("COCOCCc1ccccc1", ["OMOM"]),
        ("C(CCOC1CCCCO1)c1ccccc1", ["OTHP"]),
        (BOC_HOMOSERINE, ["NHBoc", "OTs"]),
    ],
)
def test_default_set_follows_journal_practice(smiles: str, labels: list[str]) -> None:
    assert _labels(smiles) == labels


def test_named_groups_include_common_substituents() -> None:
    assert _labels("COC(=O)c1ccc(C(C)(C)C)cc1", ["CO2Me", "t-Bu"]) == ["CO2Me", "t-Bu"]


def test_abbreviations_never_cover_most_of_the_molecule() -> None:
    assert _labels("Cc1ccc(S(=O)(=O)C[N+]#[C-])cc1") == []  # TosMIC stays drawn


def test_unknown_abbreviation_is_an_error() -> None:
    with pytest.raises(ChemGlyphStyleError, match="Unknown abbreviation"):
        chemglyph.render_molecule("CCO", abbreviate=["Xyz"])


def test_labels_mirror_for_bonds_from_the_right() -> None:
    mol = Chem.MolFromSmiles(BOC_HOMOSERINE)
    rdDepictor.Compute2DCoords(mol)
    drawn = abbreviate(mol, select(True)).drawn
    shown = {
        atom.GetProp("atomLabel"): (atom.GetProp("_displayLabel"), atom.GetProp("_displayLabelW"))
        for atom in drawn.GetAtoms()
        if atom.HasProp("atomLabel")
    }
    assert shown == {"NHBoc": ("NHBoc", "BocHN"), "OTs": ("OTs", "TsO")}


def test_every_group_parses_and_matches_its_own_structure() -> None:
    for group in GROUPS:
        attach = "O" if group.label in {"MOM", "THP"} else "C" if group.on_carbon else "N"
        smiles = attach + group.smiles
        host = f"CCCCCCCC{smiles}"  # enough atoms to stay under the coverage cap
        assert _labels(host, [group.label]), group.label


@pytest.mark.parametrize("fmt", ["svg", "png", "pdf", "mol"])
def test_every_output_keeps_the_full_structure(fmt: str) -> None:
    result = chemglyph.render_molecule(BOC_HOMOSERINE, abbreviate=True, fmt=fmt)
    assert result.report["verified"], result.report["checks"]
    data = result.data
    mol = Chem.MolFromMolBlock(data) if fmt == "mol" else chemglyph.read_structure(data)
    assert Chem.MolToSmiles(mol) == Chem.MolToSmiles(Chem.MolFromSmiles(BOC_HOMOSERINE))
    labels = sorted(g.GetProp("LABEL") for g in Chem.GetMolSubstanceGroups(mol))
    assert labels == ["NHBoc", "OTs"]  # structure editors show them as labels


def test_report_and_identity_use_the_full_molecule() -> None:
    plain = chemglyph.render_molecule(BOC_HOMOSERINE)
    short = chemglyph.render_molecule(BOC_HOMOSERINE, abbreviate=True)
    assert short.report["identity"] == plain.report["identity"]
    assert short.canonical_smiles == plain.canonical_smiles
    assert [g["label"] for g in short.report["abbreviations"]] == ["OTs", "NHBoc"]
    assert not short.warnings
    assert short.report["label_clearance_pt"] >= 1.6 - 0.01


def test_highlights_and_indices_refer_to_the_full_molecule() -> None:
    result = chemglyph.render_molecule(
        BOC_HOMOSERINE, abbreviate=True, highlight_atoms=[4, 20], show_atom_indices=True
    )
    assert result.report["verified"]
    assert "#FF7F7F" in result.data  # atom 20 sits inside NHBoc: its label is highlighted


def test_name_check_sees_through_abbreviations() -> None:
    result = chemglyph.render_molecule(
        "CC(=O)Oc1ccccc1C(=O)O", abbreviate=True, name="aspirin", style="acs1996"
    )
    assert result.report["abbreviations"][0]["label"] == "OAc"
    assert result.report["name_check"]["status"] in {"match", "unchecked"}
