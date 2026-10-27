"""The 416-structure corpus (benchmarks/corpus.csv) as a regression net.

Every structure must render, verify against its input, and keep the label
margin unless the render says otherwise in a warning. Layout quality is
tracked against a list of known limitations: a molecule outside the list
that develops a severe layout problem fails the test, and a molecule on the
list that is fixed should be removed from it.
"""

from __future__ import annotations

import csv
import platform
import re
from pathlib import Path

import numpy as np
import pytest
import rdkit

import chemglyph
from chemglyph.engine import _distance_to_edges, _flatten

ROWS = list(csv.DictReader((Path(__file__).parents[1] / "benchmarks" / "corpus.csv").open()))

# Severe layout problems no candidate layout avoids yet (docs/progress, phase 1).
# Layouts differ between RDKit releases and, through floating point, between
# platforms (helicene on macOS arm64), so the list is kept for one release on
# Linux x86-64; elsewhere only the warning is checked.
LAYOUT_LIMITS_RDKIT = "2026.09"
KNOWN_LAYOUT_LIMITS = {
    "fullerene C60",  # a sphere has no planar drawing
    "helicene",  # the helix overlaps itself, as in printed drawings
    "adamantane",
    "cubane",
    "bicyclo[1.1.1]pentane",
    "hexamine",
    "(R)-BINAP",
    "morphine",
    "codeine",
    "paclitaxel",
    "vinblastine",
    "tetrodotoxin",
}

# Bonds the clipper leaves as RDKit drew them, with a warning.
KNOWN_CLIPPING_FALLBACKS = {"tetrodotoxin"}

_MARGIN_WARNINGS = ("label margin reduced", "too short", "drawn as RDKit")
CASES = [pytest.param(row, id=row["name"]) for row in ROWS]


@pytest.fixture(scope="module")
def renders() -> dict[str, chemglyph.RenderResult]:
    return {row["name"]: chemglyph.render_molecule(row["smiles"], style="acs1996") for row in ROWS}


def test_corpus_is_large_and_traceable() -> None:
    assert len(ROWS) >= 400
    for row in ROWS:
        assert row["source"] in {"pubchem", "manual"}
        assert row["cid"] or row["source"] == "manual"


def _composition(formula: str) -> dict[str, int]:
    """Element counts of a formula, ignoring order and a trailing charge.

    PubChem writes carbon-free formulas in Hill order (BH3O3) while RDKit
    puts hydrogen first (H3BO3), so the strings themselves differ.
    """
    counts: dict[str, int] = {}
    for element, number in re.findall(r"([A-Z][a-z]?)(\d*)", re.sub(r"[+-]\d*$", "", formula)):
        counts[element] = counts.get(element, 0) + int(number or 1)
    return counts


@pytest.mark.parametrize("row", CASES)
def test_structure_renders_and_verifies(row: dict, renders) -> None:
    result = renders[row["name"]]
    assert result.report["verified"], result.report["checks"]
    assert _composition(result.report["identity"]["formula"]) == _composition(row["formula"])


@pytest.mark.parametrize("row", CASES)
def test_label_margin_holds_or_is_reported(row: dict, renders) -> None:
    result = renders[row["name"]]
    if any(marker in warning for warning in result.warnings for marker in _MARGIN_WARNINGS):
        fallback = any("drawn as RDKit" in warning for warning in result.warnings)
        assert not fallback or row["name"] in KNOWN_CLIPPING_FALLBACKS
        return
    svg = result.data
    unit = (
        float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', svg).group(1))
        / result.report["width_pt"]
    )
    glyphs: dict[int, list] = {}
    for atom, path in re.findall(r"<path class='atom-(\d+)' d='([^']+)'", svg):
        glyphs.setdefault(int(atom), []).extend(_flatten(path))
    for match in re.finditer(
        r"<path class='bond-\d+ atom-(\d+) atom-(\d+)( hash| wedge)?' d='([^']+)'", svg
    ):
        points = np.array(
            [(float(x), float(y)) for x, y in re.findall(r"([-\d.]+),([-\d.]+)", match.group(4))]
        )
        if match.group(3) == " wedge":
            points = np.vstack([points, points[:1]])
        pieces = (
            [points[i : i + 2] for i in range(0, len(points), 2)]
            if match.group(3) == " hash"
            else [points]
        )
        for atom in (int(match.group(1)), int(match.group(2))):
            if atom not in glyphs:
                continue
            edges = np.array(glyphs[atom])
            for piece in pieces:
                samples = np.vstack(
                    [np.linspace(p, q, 20) for p, q in zip(piece, piece[1:], strict=False)]
                )
                gap = float(_distance_to_edges(samples, edges).min()) / unit
                assert gap >= 1.5, f"bond {gap:.2f} pt from atom {atom} with no warning"


_same_rdkit = pytest.mark.skipif(
    not rdkit.__version__.startswith(LAYOUT_LIMITS_RDKIT)
    or (platform.system(), platform.machine()) != ("Linux", "x86_64"),
    reason=f"layout limits are tracked for RDKit {LAYOUT_LIMITS_RDKIT} on Linux x86-64",
)


def test_severe_layout_problems_are_warned(renders) -> None:
    for name, result in renders.items():
        if result.report["layout"]["severe"]:
            assert any(w.startswith("layout check:") for w in result.warnings), name


@_same_rdkit
def test_severe_layout_problems_stay_within_known_limits(renders) -> None:
    severe = {name for name, result in renders.items() if result.report["layout"]["severe"]}
    assert severe <= KNOWN_LAYOUT_LIMITS, (
        f"new layout problems: {sorted(severe - KNOWN_LAYOUT_LIMITS)}"
    )


@_same_rdkit
def test_known_limits_are_still_limits(renders) -> None:
    """A fixed molecule must leave the list, so the list never hides progress."""
    severe = {name for name, result in renders.items() if result.report["layout"]["severe"]}
    fixed = KNOWN_LAYOUT_LIMITS - severe
    assert not fixed, f"now clean, remove from KNOWN_LAYOUT_LIMITS: {sorted(fixed)}"
