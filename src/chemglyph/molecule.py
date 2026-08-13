"""Single-molecule rendering on top of RDKit (see §5 of the specification)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RenderResult:
    """Output of :func:`render_molecule`."""

    data: str | bytes
    fmt: str
    canonical_smiles: str
    mol_formula: str
    mol_weight: float
    warnings: list[str] = field(default_factory=list)


def render_molecule(
    structure: str,
    style: str = "modern",
    size: tuple[int, int] | None = None,
    fmt: str = "svg",
    transparent: bool = True,
    show_atom_indices: bool = False,
    highlight_atoms: list[int] | None = None,
) -> RenderResult:
    """Render a molecule from SMILES, InChI, or molblock."""
    raise NotImplementedError("TODO(M1): implement molecule rendering")
