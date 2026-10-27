"""Same input and version give byte-identical output (docs/SPEC.md, section 7)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

import pytest

import chemglyph

CASES = [
    ("CC(=O)Oc1ccccc1C(=O)O", {}),
    ("C1C2CC3CC1CC(C2)C3", {}),  # projection layout
    ("COC(=O)[C@H](CCOS(=O)(=O)c1ccc(C)cc1)NC(=O)OC(C)(C)C", {"abbreviate": True}),
    ("[O-][n+]1ccccc1", {"number": "3a"}),
    ("CC(=O)[O-].[Na+]", {}),
]
FORMATS = ["svg", "png", "pdf", "mol"]


def _digest(smiles: str, options: dict, fmt: str) -> str:
    data = chemglyph.render_molecule(smiles, style="acs1996", fmt=fmt, **options).data
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


@pytest.mark.parametrize("fmt", FORMATS)
def test_repeated_renders_are_identical(fmt: str) -> None:
    for smiles, options in CASES:
        assert _digest(smiles, options, fmt) == _digest(smiles, options, fmt), smiles


def test_renders_are_identical_across_processes() -> None:
    script = (
        "import hashlib, chemglyph\n"
        f"cases = {CASES!r}\n"
        f"for smiles, options in cases:\n"
        f"    for fmt in {FORMATS!r}:\n"
        "        d = chemglyph.render_molecule(smiles, style='acs1996', fmt=fmt, **options).data\n"
        "        d = d if isinstance(d, bytes) else d.encode()\n"
        "        print(hashlib.sha256(d).hexdigest())\n"
    )
    outputs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        run = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True
        )
        outputs.append(run.stdout)
    assert outputs[0] == outputs[1]
    expected = "".join(
        _digest(smiles, options, fmt) + "\n" for smiles, options in CASES for fmt in FORMATS
    )
    assert outputs[0] == expected
