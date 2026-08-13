"""Structure validation with quick fixes (see §7 of the specification)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Issue:
    """A validation problem that could not be fixed automatically."""

    message: str


@dataclass
class Fix:
    """An automatically applicable repair, with a human-readable description."""

    description: str
    fixed_smiles: str


@dataclass
class ValidationReport:
    """Result of :func:`validate_structure`."""

    valid: bool
    canonical_smiles: str | None
    mol_formula: str | None
    mol_weight: float | None
    errors: list[Issue] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)


def validate_structure(structure: str) -> ValidationReport:
    """Validate a structure string and report errors plus automatic fixes."""
    raise NotImplementedError("TODO(M3): implement structure validation")
