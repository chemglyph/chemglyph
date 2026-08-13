"""Generate shuffled, numbered blind-test figures and the answer key (§11).

Usage::

    python benchmarks/generate_blind_test.py --seed 1234
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import rdkit

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import chemglyph  # noqa: E402
from blind_test_molecules import BLIND_TEST_MOLECULES, KNOWN_LIMITATIONS  # noqa: E402
from chemglyph import render_molecule  # noqa: E402
from chemglyph.errors import ChemGlyphRenderError  # noqa: E402


def generate(out_dir: Path, seed: int | None = None) -> dict:
    """Render every molecule in two styles under shuffled file numbers."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (label, smiles, style)
        for label, smiles, _note in BLIND_TEST_MOLECULES
        for style in ("acs", "modern")
    ]
    numbers = list(range(1, len(tasks) + 1))
    rng.shuffle(numbers)

    figures: dict[str, dict] = {}
    for number, (label, smiles, style) in zip(numbers, tasks, strict=True):
        style_key = f"chemglyph-{style}"
        stem = f"{number:03d}_{style_key}"
        svg_path = out_dir / f"{stem}.svg"
        png_path = out_dir / f"{stem}.png"
        svg_path.write_text(render_molecule(smiles, style=style, fmt="svg").data)
        png_status = "ok"
        try:
            png_path.write_bytes(render_molecule(smiles, style=style, fmt="png").data)
        except ChemGlyphRenderError as exc:
            png_status = f"skipped: {exc}"
        figures[stem] = {
            "number": number,
            "molecule": label,
            "smiles": smiles,
            "style": style,
            "svg": svg_path.name,
            "png": png_path.name if png_path.exists() else None,
            "png_status": png_status,
        }

    answer_key = {
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "chemglyph_version": chemglyph.__version__,
        "rdkit_version": rdkit.__version__,
        "styles": {"chemglyph-acs": "acs", "chemglyph-modern": "modern"},
        "known_limitations_excluded_from_denominator": sorted(KNOWN_LIMITATIONS),
        "figures": figures,
    }
    key_path = out_dir / "answer_key.json"
    key_path.write_text(json.dumps(answer_key, indent=2, ensure_ascii=False) + "\n")
    return answer_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the ChemGlyph blind test.")
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / "benchmarks" / "blind_test_output",
        help="output directory (default: benchmarks/blind_test_output)",
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for numbering")
    args = parser.parse_args()
    answer_key = generate(args.out, args.seed)
    print(f"Wrote {len(answer_key['figures'])} figures and answer_key.json to {args.out}")


if __name__ == "__main__":
    main()
