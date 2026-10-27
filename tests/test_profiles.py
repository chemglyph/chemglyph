"""Conformance tests for the fixed-scale profiles (docs/SPEC.md, 5 and 7).

Every measurement here is taken from the rendered SVG alone, never from the
engine's own report, so the tests check the output a user actually gets.
Each profile is held to its own numbers; for acs1996 these are the ACS
Document 1996 settings: bond 14.4 pt, line 0.6 pt, bond spacing 18% of the
bond length, label margin 1.6 pt, hash spacing 2.5 pt, labels 10 pt.
"""

from __future__ import annotations

import io
import math
import re
from statistics import median

import pytest
from PIL import Image

import chemglyph
from blind_test_molecules import BLIND_TEST_MOLECULES
from chemglyph.engine import _distance_to_edges, _flatten
from chemglyph.profiles import PROFILES, Profile

TOLERANCE = 0.02  # 2%, the conformance tolerance in the spec
ALL_PROFILES = [PROFILES[name] for name in sorted(PROFILES)]

_SEGMENT = re.compile(
    r"class='bond-(\d+) atom-(\d+) atom-(\d+)' d='M ([-\d.]+),([-\d.]+) L ([-\d.]+),([-\d.]+)'"
)


def _render(smiles: str, profile: Profile = PROFILES["acs1996"]) -> str:
    return chemglyph.render_molecule(smiles, style=profile.name).data


def _unit(svg: str) -> float:
    """SVG user units per point, read from the declared size."""
    width_pt = float(re.search(r'width="([\d.]+)pt"', svg).group(1))
    viewbox_width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', svg).group(1))
    return viewbox_width / width_pt


def _labelled_atoms(svg: str) -> set[int]:
    return {int(v) for v in re.findall(r"<path class='atom-(\d+)' d=", svg)}


def _segments(svg: str) -> dict[int, list[tuple[int, int, float, float, float, float]]]:
    found: dict[int, list] = {}
    for match in _SEGMENT.finditer(svg):
        bond, a, b = (int(v) for v in match.group(1, 2, 3))
        found.setdefault(bond, []).append((a, b, *(float(v) for v in match.groups()[3:])))
    return found


def _plain_bond_lengths_pt(svg: str) -> list[float]:
    """Single-line bonds between two unlabelled atoms run centre to centre."""
    unit = _unit(svg)
    labelled = _labelled_atoms(svg)
    lengths = []
    for parts in _segments(svg).values():
        if len(parts) != 1:
            continue
        a, b, x1, y1, x2, y2 = parts[0]
        if a in labelled or b in labelled:
            continue
        lengths.append(math.dist((x1, y1), (x2, y2)) / unit)
    return lengths


ELIGIBLE = [(label, smiles) for label, smiles, _ in BLIND_TEST_MOLECULES]
BY_PROFILE = [
    pytest.param(profile, label, smiles, id=f"{profile.name}-{label}")
    for profile in ALL_PROFILES
    for label, smiles in ELIGIBLE
]
PROFILE_IDS = {"ids": [profile.name for profile in ALL_PROFILES]}


@pytest.mark.parametrize("profile,label,smiles", BY_PROFILE)
def test_bond_length_matches_the_profile(profile: Profile, label: str, smiles: str) -> None:
    lengths = _plain_bond_lengths_pt(_render(smiles, profile))
    if not lengths:
        pytest.skip(f"{label} has no unlabelled single bond to measure")
    # Bond lengths in a layout are uniform, so the typical bond is the profile's.
    assert median(lengths) == pytest.approx(profile.bond_length_pt, rel=TOLERANCE), label


@pytest.mark.parametrize("profile", ALL_PROFILES, **PROFILE_IDS)
def test_bond_length_is_identical_across_molecules(profile: Profile) -> None:
    medians = []
    for _, smiles in ELIGIBLE:
        lengths = _plain_bond_lengths_pt(_render(smiles, profile))
        if lengths:
            medians.append(median(lengths))
    # The scale is shared; only the layout itself varies. Crowded layouts
    # stretch a few bonds (paclitaxel's median single bond is 0.6% long).
    assert all(m == pytest.approx(profile.bond_length_pt, rel=0.01) for m in medians)


@pytest.mark.parametrize("profile,label,smiles", BY_PROFILE)
def test_no_stroke_is_thinner_than_the_line_width(
    profile: Profile, label: str, smiles: str
) -> None:
    svg = _render(smiles, profile)
    unit = _unit(svg)
    line = profile.line_width_pt
    widths = [float(v) / unit for v in re.findall(r"stroke-width:([\d.]+)px", svg)]
    assert widths, label
    assert min(widths) >= line - 0.01, label  # also above the IUPAC 0.5 pt floor
    assert any(abs(width - line) < 0.01 for width in widths), label


@pytest.mark.parametrize("profile", ALL_PROFILES, **PROFILE_IDS)
def test_double_bond_spacing_matches_the_profile(profile: Profile) -> None:
    ratios = []
    for _, smiles in ELIGIBLE:
        svg = _render(smiles, profile)
        labelled = _labelled_atoms(svg)
        for parts in _segments(svg).values():
            if len(parts) != 2 or {parts[0][0], parts[0][1]} & labelled:
                continue
            (_, _, ax1, ay1, ax2, ay2), (_, _, bx1, by1, bx2, by2) = parts
            length_a = math.dist((ax1, ay1), (ax2, ay2))
            length_b = math.dist((bx1, by1), (bx2, by2))
            dx, dy = (ax2 - ax1) / length_a, (ay2 - ay1) / length_a
            gap = abs((bx1 - ax1) * dy - (by1 - ay1) * dx)
            ratios.append(gap / max(length_a, length_b))
    assert len(ratios) > 20
    assert min(ratios) == pytest.approx(profile.bond_spacing, abs=0.01)
    assert max(ratios) == pytest.approx(profile.bond_spacing, abs=0.01)


def _bond_shapes(svg: str) -> list[tuple[int, int, list[tuple[float, float]]]]:
    """Every drawn bond piece as (atom, atom, outline points): lines, hashes, wedges."""
    shapes = []
    for match in _SEGMENT.finditer(svg):
        a, b = int(match.group(2)), int(match.group(3))
        x1, y1, x2, y2 = (float(v) for v in match.groups()[3:])
        shapes.append((a, b, [(x1, y1), (x2, y2)]))
    for a, b, path in re.findall(
        r"<path class='bond-\d+ atom-(\d+) atom-(\d+) hash' d='([^']+)'", svg
    ):
        for line in re.findall(r"M ([-\d.]+),([-\d.]+) L ([-\d.]+),([-\d.]+)", path):
            x1, y1, x2, y2 = (float(v) for v in line)
            shapes.append((int(a), int(b), [(x1, y1), (x2, y2)]))
    for a, b, path in re.findall(
        r"<path class='bond-\d+ atom-(\d+) atom-(\d+) wedge' d='([^']+)'", svg
    ):
        corners = [(float(x), float(y)) for x, y in re.findall(r"([-\d.]+),([-\d.]+)", path)]
        shapes.append((int(a), int(b), [*corners, corners[0]]))
    return shapes


@pytest.mark.parametrize("profile,label,smiles", BY_PROFILE)
def test_bond_ends_keep_the_margin_from_label_glyphs(
    profile: Profile, label: str, smiles: str
) -> None:
    """Lines, hash marks, and wedge outlines all stop 1.6 pt from a label glyph."""
    import numpy as np

    svg = _render(smiles, profile)
    unit = _unit(svg)
    glyphs: dict[int, list] = {}
    for atom, path in re.findall(r"<path class='atom-(\d+)' d='([^']+)'", svg):
        glyphs.setdefault(int(atom), []).extend(_flatten(path))
    if not glyphs:
        pytest.skip(f"{label} has no labels")
    checked = 0
    for a, b, outline in _bond_shapes(svg):
        points = np.vstack(
            [np.linspace(p, q, 30) for p, q in zip(outline, outline[1:], strict=False)]
        )
        for atom in (a, b):
            if atom not in glyphs:
                continue
            gap = float(_distance_to_edges(points, np.array(glyphs[atom])).min()) / unit
            assert gap >= profile.margin_width_pt - 0.1, (
                f"{label}: bond {gap:.2f} pt from atom {atom}"
            )
            checked += 1
    assert checked, f"{label}: labels present but no bond reaches them"


@pytest.mark.parametrize(
    "profile,minimum",
    [(PROFILES["acs1996"], 3.5), (PROFILES["screen"], 3.5), (PROFILES["textbook"], 2.2)],
    ids=["acs1996", "screen", "textbook"],
)
def test_sulfate_bonds_stay_visible(profile: Profile, minimum: float) -> None:
    """Box clipping left 1.4 pt of each S-O bond; glyph clipping keeps ~4 pt.

    Coloured profiles draw each line as two halves, so lengths are summed per
    bond and divided by its number of lines (1 single, 2 double).
    """
    svg = _render("[O-]S(=O)(=O)[O-]", profile)
    unit = _unit(svg)
    lines_per_bond = {0: 1, 1: 2, 2: 2, 3: 1}
    for bond, parts in _segments(svg).items():
        total = sum(math.dist((x1, y1), (x2, y2)) for _, _, x1, y1, x2, y2 in parts)
        assert total / unit / lines_per_bond[bond] > minimum


@pytest.mark.parametrize(
    "smiles",
    [
        "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O",  # s-ibuprofen
        "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",  # glucose
    ],
)
@pytest.mark.parametrize("profile", ALL_PROFILES, **PROFILE_IDS)
def test_hashed_wedges_use_the_hash_spacing(profile: Profile, smiles: str) -> None:
    svg = _render(smiles, profile)
    unit = _unit(svg)
    hashes = re.findall(r"<path class='bond-\d+ atom-\d+ atom-\d+ hash' d='([^']+)'", svg)
    assert hashes
    for path in hashes:
        lines = re.findall(r"M ([-\d.]+),([-\d.]+) L ([-\d.]+),([-\d.]+)", path)
        assert len(lines) >= 3  # IUPAC 2008: at least three hashes
        centres = [((float(a) + float(c)) / 2, (float(b) + float(d)) / 2) for a, b, c, d in lines]
        gaps = [math.dist(p, q) / unit for p, q in zip(centres, centres[1:], strict=False)]
        assert max(gaps) <= profile.hash_spacing_pt * 1.25
        assert min(gaps) >= profile.hash_spacing_pt * 0.6


@pytest.mark.parametrize("profile", ALL_PROFILES, **PROFILE_IDS)
def test_label_size_is_the_same_in_every_molecule(profile: Profile) -> None:
    heights = []
    for smiles in ["OC(=O)c1ccccc1", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "COc1cc(C=O)ccc1O"]:
        svg = _render(smiles, profile)
        unit = _unit(svg)
        for _atom, path in re.findall(r"<path class='atom-(\d+)' d='([^']+)'", svg):
            ys = [float(v) for v in re.findall(r"-?\d+\.?\d*", path)][1::2]
            heights.append((max(ys) - min(ys)) / unit)
    # Cap height of the bundled Liberation Sans is about 0.71 of the font size.
    font = profile.font_size_pt
    assert 0.65 * font < min(heights) and max(heights) < 0.76 * font


def test_output_is_deterministic() -> None:
    smiles = "CC(C)CCC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(C)CC[C@H]1[C@H]2CC=C2C[C@@H](O)CC[C@]12C"
    assert _render(smiles) == _render(smiles)


def test_png_size_follows_dpi() -> None:
    result = chemglyph.render_molecule("OC(=O)c1ccccc1", style="acs1996", fmt="png", dpi=300)
    image = Image.open(io.BytesIO(result.data))
    width_pt = result.report["width_pt"]
    assert image.width == pytest.approx(width_pt * 300 / 72, abs=2)


def test_report_and_warnings() -> None:
    result = chemglyph.render_molecule("[O-]S(=O)(=O)[O-]", style="acs1996", size=(300, 300))
    assert result.report["profile"] == "acs1996"
    assert result.report["bond_length_pt"] == [14.4, 14.4]
    assert result.report["label_clearance_pt"] >= 1.55
    assert any("size is ignored" in warning for warning in result.warnings)


def test_every_bond_is_drawn() -> None:
    from rdkit import Chem

    for label, smiles in ELIGIBLE:
        mol = Chem.MolFromSmiles(smiles)
        svg = _render(smiles)
        drawn = {int(v) for v in re.findall(r"class='bond-(\d+)", svg)}
        assert set(range(mol.GetNumBonds())) <= drawn, label


def test_opaque_background() -> None:
    svg = chemglyph.render_molecule("CCO", style="acs1996", transparent=False).data
    assert 'fill="#ffffff"' in svg


def test_unknown_style_lists_profiles() -> None:
    from chemglyph.errors import ChemGlyphStyleError

    with pytest.raises(ChemGlyphStyleError, match="acs1996"):
        chemglyph.render_molecule("CCO", style="neon")


def test_screen_colours_heteroatoms_and_acs_stays_black() -> None:
    screen = _render("Cn1cnc2c1c(=O)n(C)c(=O)n2C", PROFILES["screen"])
    acs = _render("Cn1cnc2c1c(=O)n(C)c(=O)n2C", PROFILES["acs1996"])
    assert "#FF0D0D" in screen and "#3050F8" in screen  # classic CPK O and N
    assert "#FF0D0D" not in acs and "#3050F8" not in acs


@pytest.mark.parametrize("profile,label,smiles", BY_PROFILE)
def test_clipping_never_falls_back(profile: Profile, label: str, smiles: str) -> None:
    """Every bond next to a label is clipped by the glyph rule, never left as RDKit drew it."""
    result = chemglyph.render_molecule(smiles, style=profile.name)
    fallbacks = [w for w in result.warnings if "drawn as RDKit placed it" in w]
    assert not fallbacks, f"{label}: {fallbacks}"
