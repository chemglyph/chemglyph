"""Layout checks that guard the stereochemistry and degenerate inputs."""

from __future__ import annotations

import pytest
from rdkit import Chem

import chemglyph
from chemglyph.layout import check_layout
from chemglyph.molecule import _prepare_for_drawing, _render_with_profile
from chemglyph.profiles import PROFILES

QUININE = "COC1=CC2=C(C=CN=C2C=C1)[C@H]([C@@H]3C[C@@H]4CCN3C[C@@H]4C=C)O"

# CoordGen's layout of quinine under RDKit 2024.09. With it, that RDKit's
# wedging leaves the C4 bridgehead (atom 15) without a configuration; newer
# RDKit picks a wedge that keeps it. Either way the figure must be right.
QUININE_LAYOUT = [
    (-4.5176, 1.0639),
    (-3.6512, 0.5645),
    (-2.7856, 1.0651),
    (-1.9192, 0.5659),
    (-1.0536, 1.0665),
    (-0.1872, 0.5673),
    (0.6784, 1.0679),
    (0.6776, 2.0679),
    (-0.1888, 2.5673),
    (-1.0544, 2.0665),
    (-1.9208, 2.5659),
    (-2.7864, 2.0651),
    (-0.1864, -0.4327),
    (0.68, -0.9321),
    (0.6808, -1.9445),
    (1.5472, -2.4437),
    (0.3522, -2.9895),
    (0.9982, -2.4159),
    (1.5456, -0.4313),
    (2.4244, -0.9307),
    (2.425, -1.9431),
    (3.299, -2.4503),
    (4.1662, -1.9525),
    (-1.052, -0.9335),
]


@pytest.mark.parametrize("smiles", ["[H][H]", "[H]", "[H+]", "[2H][2H]"])
def test_hydrogen_only_species_render(smiles: str) -> None:
    # CoordGen returns NaN coordinates for these; the RDKit layout is used.
    result = chemglyph.render_molecule(smiles, style="acs1996")
    assert result.report["verified"]
    assert result.report["width_pt"] > 0


def test_check_layout_flags_no_stereo_problem_without_stereo() -> None:
    mol = Chem.MolFromSmiles("CC(Cl)Br")
    _prepare_for_drawing(mol)
    assert check_layout(mol).counts["stereo_lost"] == 0


def test_layout_that_hides_a_stereocentre_gets_an_explicit_h() -> None:
    mol = Chem.MolFromSmiles(QUININE)
    conformer = Chem.Conformer(mol.GetNumAtoms())
    conformer.Set3D(False)
    for index, (x, y) in enumerate(QUININE_LAYOUT):
        conformer.SetAtomPosition(index, (x, y, 0.0))
    mol.AddConformer(conformer)
    drawn, layout = _prepare_for_drawing(mol)
    method, report = layout
    assert method == "input"
    assert report.counts["stereo_lost"] == 0
    assert set(report.added_hydrogens) <= {15}
    result = _render_with_profile(
        drawn,
        PROFILES["acs1996"],
        "mol",
        layout=layout,
        size=None,
        transparent=True,
        show_atom_indices=False,
        highlight_atoms=None,
        dpi=300,
        name=None,
    )
    assert result.report["verified"], result.report["checks"]
    assert result.canonical_smiles == Chem.MolToSmiles(Chem.MolFromSmiles(QUININE))
    back = Chem.MolFromMolBlock(result.data)
    assert Chem.MolToSmiles(back) == Chem.MolToSmiles(Chem.MolFromSmiles(QUININE))


def test_flipped_wedge_fails_verification() -> None:
    from rdkit.Chem import rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D

    from chemglyph.engine import _wedges_match_stereo

    mol = Chem.MolFromSmiles("C[C@H](N)O")
    rdDepictor.Compute2DCoords(mol)
    prepared = rdMolDraw2D.PrepareMolForDrawing(mol)
    assert _wedges_match_stereo(prepared)
    for bond in prepared.GetBonds():
        if bond.GetBondDir() == Chem.BondDir.BEGINWEDGE:
            bond.SetBondDir(Chem.BondDir.BEGINDASH)
        elif bond.GetBondDir() == Chem.BondDir.BEGINDASH:
            bond.SetBondDir(Chem.BondDir.BEGINWEDGE)
    assert not _wedges_match_stereo(prepared)


def test_overlapping_labels_are_a_severe_layout_problem() -> None:
    # A molfile's own coordinates are kept, so two ions placed almost on top
    # of each other stay there and must be reported.
    ions = Chem.MolFromSmiles("[Na+].[Cl-]")
    conformer = Chem.Conformer(2)
    conformer.Set3D(False)
    conformer.SetAtomPosition(0, (0.0, 0.0, 0.0))
    conformer.SetAtomPosition(1, (0.5, 0.0, 0.0))
    ions.AddConformer(conformer)
    result = chemglyph.render_molecule(Chem.MolToMolBlock(ions), style="acs1996")
    assert result.report["layout"]["method"] == "input"
    assert result.report["layout"]["problems"]["label_overlaps"] >= 1
    assert any("labels of atom 0 and atom 1 overlap" in w for w in result.warnings)


def test_ring_fusion_hydrogens_do_not_land_on_atoms() -> None:
    # RDKit put progesterone's C9 H on C10 and flagged it with a red box.
    progesterone = "CC(=O)[C@H]1CC[C@@H]2[C@@]1(CC[C@H]3[C@H]2CCC4=CC(=O)CC[C@]34C)C"
    result = chemglyph.render_molecule(progesterone, style="acs1996")
    assert result.report["layout"]["severe"] == 0
    assert result.report["checks"]["wedges_match_stereo"]
    assert "#FF0000" not in result.data


@pytest.mark.parametrize(
    "smiles",
    [
        "C1C2CC3CC1CC(C2)C3",  # adamantane
        "C12C3C4C1C5C2C3C45",  # cubane
        "C1C2CC1C2",  # bicyclo[1.1.1]pentane
        "C1N2CN3CN1CN(C2)C3",  # hexamine
        "NC12CC3CC(CC(C3)C1)C2",  # amantadine
    ],
)
def test_cages_are_drawn_in_perspective_without_problems(smiles: str) -> None:
    import re

    result = chemglyph.render_molecule(smiles, style="acs1996")
    assert result.report["layout"]["method"] in {"projection", "ring-template"}
    assert result.report["layout"]["severe"] == 0, result.report["layout"]["examples"]
    # No cage carbon may look like a linear carbon and get a "C" label.
    carbons = {a.GetIdx() for a in Chem.MolFromSmiles(smiles).GetAtoms() if a.GetSymbol() == "C"}
    labelled = {int(i) for i in re.findall(r"<path class='atom-(\d+)' d=", result.data)}
    assert not carbons & labelled
