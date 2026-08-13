"""End-to-end aspirin synthesis route demo (see §6 and the M2 milestone).

Run from the repository root::

    python examples/aspirin_synthesis.py

Writes ``examples/aspirin_synthesis.svg``.
"""

from __future__ import annotations

from pathlib import Path

import chemglyph

SPEC = {
    "steps": [
        {
            "reactants": ["OC(=O)c1ccccc1O", "CC(=O)OC(C)=O"],
            "products": ["CC(=O)Oc1ccccc1C(=O)O", "CC(=O)O"],
            "conditions": {"above": "H₂SO₄ (cat.)", "below": "rt, 15 min"},
            "yield": "89%",
            "arrow": "forward",
        },
        {
            "reactants": ["CC(=O)Oc1ccccc1C(=O)O"],
            "products": ["OC(=O)c1ccccc1O", "CC(=O)O"],
            "conditions": {"above": "NaOH", "below": "H₂O, reflux"},
            "yield": "91%",
            "arrow": "equilibrium",
        },
    ],
    "style": "modern",
    "layout": {"max_width": 1200, "align": "arrow"},
}


def main() -> None:
    svg = chemglyph.render_reaction(SPEC)
    output = Path(__file__).with_suffix(".svg")
    output.write_text(svg)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
