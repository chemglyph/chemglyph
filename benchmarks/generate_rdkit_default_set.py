"""Render the interim RDKit-default opponent panels for the blind test.

This is a stopgap while human-made ChemDraw/Ketcher panels are unavailable:
it renders every §11 molecule with stock RDKit defaults so the automated
half of a head-to-head comparison can run today. The real blind test still
uses the reference-editor protocol in RUNBOOK.md.

Usage::

    python benchmarks/generate_rdkit_default_set.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from rdkit import Chem  # noqa: E402
from rdkit.Chem import rdDepictor  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D  # noqa: E402

from blind_test_molecules import BLIND_TEST_MOLECULES  # noqa: E402

CANVAS = 400


def _render(smiles: str, fmt: str) -> bytes:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    if fmt == "svg":
        drawer = rdMolDraw2D.MolDraw2DSVG(CANVAS, CANVAS)
    else:
        drawer = rdMolDraw2D.MolDraw2DCairo(CANVAS, CANVAS)
    drawer.SetDrawOptions(rdMolDraw2D.MolDrawOptions())
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    data = drawer.GetDrawingText()
    return data.encode("utf-8") if isinstance(data, str) else bytes(data)


def main() -> None:
    out_dir = _REPO_ROOT / "benchmarks" / "rdkit_default_panels"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    for label, smiles, _note in BLIND_TEST_MOLECULES:
        svg_path = out_dir / f"{label}.svg"
        png_path = out_dir / f"{label}.png"
        svg_path.write_bytes(_render(smiles, "svg"))
        png_path.write_bytes(_render(smiles, "png"))
        manifest[label] = {
            "smiles": smiles,
            "svg": svg_path.name,
            "png": png_path.name,
        }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(manifest)} RDKit-default panels to {out_dir}")


if __name__ == "__main__":
    main()
