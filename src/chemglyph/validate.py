"""Structure validation with quick fixes (see §7 of the specification).

Deliberately narrow: only syntactic and valence checks are performed. No
tautomer judgment, no "does this molecule exist" reasoning, no stability
inference. The four quick-fix rules are:

1. Unbalanced brackets / odd ring-closure numbers: report, never guess.
2. Lowercase aromatic atoms that fail kekulization: re-parse with uppercase.
3. Nitrogen valence errors: re-parse with a formal ``[N+]`` charge.
4. Everything else: pass RDKit's message through untouched.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, rdMolDescriptors

_MOLBLOCK_RE = re.compile(r"\bV(2000|3000)\b")
_AROMATIC_LETTERS = frozenset("cnosp")
_RDKIT_LOG_PREFIX = re.compile(r"^\s*\[?\d{2}:\d{2}:\d{2}\]?\s*")


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
    """Validate a structure string and report errors plus automatic fixes.

    SMILES input runs the quick-fix rules; InChI/molblock input is validated
    by parsing only (the SMILES-specific fixes do not apply).
    """
    text = structure.strip()
    if not text:
        return ValidationReport(
            valid=False,
            canonical_smiles=None,
            mol_formula=None,
            mol_weight=None,
            errors=[Issue("Structure string is empty.")],
        )

    if not _is_smiles_like(text):
        mol, raw_error = _parse_other(structure)
        if mol is not None:
            return _valid_report(mol)
        return ValidationReport(
            valid=False,
            canonical_smiles=None,
            mol_formula=None,
            mol_weight=None,
            errors=[Issue(raw_error or "RDKit could not parse the input.")],
        )

    mol, raw_error = parse_smiles(text)
    if mol is not None:
        return _valid_report(mol)

    errors = [Issue(raw_error or "RDKit could not parse the SMILES.")]
    fixes: list[Fix] = []
    syntax_issues = _syntax_issues(text)
    if syntax_issues:
        errors.extend(Issue(message) for message in syntax_issues)
    else:
        fixes.extend(_try_uppercase_fix(text))
        if not fixes:
            fixes.extend(_try_n_charge_fixes(text))

    report = ValidationReport(
        valid=False,
        canonical_smiles=None,
        mol_formula=None,
        mol_weight=None,
        errors=errors,
        fixes=fixes,
    )
    if fixes:
        fixed_mol = Chem.MolFromSmiles(fixes[0].fixed_smiles)
        report.canonical_smiles = fixes[0].fixed_smiles
        report.mol_formula = rdMolDescriptors.CalcMolFormula(fixed_mol)
        report.mol_weight = Descriptors.MolWt(fixed_mol)
    return report


def suggest_quick_fix(structure: str) -> str:
    """Return a one-line repair suggestion for an unparseable SMILES.

    Returns an empty string when no automatic fix applies.
    """
    text = structure.strip()
    if not text or not _is_smiles_like(text):
        return ""
    syntax_issues = _syntax_issues(text)
    if syntax_issues:
        return f"repair syntax first ({syntax_issues[0]}); no automatic fix is attempted"
    fixes = _try_uppercase_fix(text) or _try_n_charge_fixes(text)
    if fixes:
        return f"{fixes[0].description}: {fixes[0].fixed_smiles}"
    return ""


def _is_smiles_like(structure: str) -> bool:
    return not (structure.startswith("InChI=") or _MOLBLOCK_RE.search(structure))


def parse_smiles(smiles: str) -> tuple[Chem.Mol | None, str]:
    """Parse SMILES and return ``(mol, rdkit_error_message)``.

    RDKit reports parse/sanitize failures through its C++ logger, so the raw
    message is captured by routing RDKit logging through Python's ``logging``
    module for the duration of the call. This is a process-wide routing change;
    it is idempotent and leaves RDKit messages visible through the standard
    logger afterwards.
    """
    with _rdkit_error_capture() as messages:
        mol = Chem.MolFromSmiles(smiles)
    raw_error = ""
    if mol is None and messages:
        raw_error = " | ".join(messages)
    return mol, raw_error


def _parse_other(structure: str) -> tuple[Chem.Mol | None, str]:
    try:
        if structure.strip().startswith("InChI="):
            return Chem.MolFromInchi(structure.strip()), ""
        return Chem.MolFromMolBlock(structure), ""  # keep leading whitespace intact
    except Exception as exc:
        return None, str(exc)


def _valid_report(mol: Chem.Mol) -> ValidationReport:
    return ValidationReport(
        valid=True,
        canonical_smiles=Chem.MolToSmiles(mol),
        mol_formula=rdMolDescriptors.CalcMolFormula(mol),
        mol_weight=Descriptors.MolWt(mol),
    )


def _syntax_issues(smiles: str) -> list[str]:
    """Rule 1: report unbalanced brackets and odd ring-closure numbers."""
    issues: list[str] = []
    depth = 0
    ring_counts: dict[str, int] = {}
    index = 0
    while index < len(smiles):
        char = smiles[index]
        if char == "[":
            depth += 1
        elif char == "]":
            if depth == 0:
                issues.append("closing bracket without matching opening bracket")
            depth -= 1
        elif char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                issues.append("closing parenthesis without matching opening")
            depth -= 1
        elif char == "%":
            for offset in (1, 2):
                digit = smiles[index + offset : index + offset + 1]
                if digit.isdigit():
                    ring_counts[digit] = ring_counts.get(digit, 0) + 1
            index += 2
            continue
        elif char.isdigit() and depth == 0:
            ring_counts[char] = ring_counts.get(char, 0) + 1
        index += 1
    if depth > 0:
        issues.append("unclosed bracket or parenthesis")
    for digit, count in sorted(ring_counts.items()):
        if count % 2 == 1:
            issues.append(
                f"ring-closure number {digit} appears {count} time(s); "
                "ring closures must come in pairs"
            )
    return issues


def _try_uppercase_fix(smiles: str) -> list[Fix]:
    """Rule 2: re-parse with uppercase aromatic atoms after kekulize failure."""
    uppercased = _uppercase_aromatic_atoms(smiles)
    if uppercased == smiles:
        return []
    mol, _ = parse_smiles(uppercased)
    if mol is None:
        return []
    return [
        Fix(
            description=(
                "lowercase aromatic atoms could not be kekulized; re-parsed with uppercase letters"
            ),
            fixed_smiles=Chem.MolToSmiles(mol),
        )
    ]


def _try_n_charge_fixes(smiles: str) -> list[Fix]:
    """Rule 3: try a formal ``[N+]`` on bare nitrogen atoms for valence errors."""
    positions = [index for index, char in enumerate(_outside_brackets(smiles)) if char == "N"]
    for position in positions:
        candidate = f"{smiles[:position]}[N+]{smiles[position + 1 :]}"
        mol, _ = parse_smiles(candidate)
        if mol is not None:
            return [
                Fix(
                    description=(
                        "nitrogen valence error; re-parsed with a formal positive charge [N+]"
                    ),
                    fixed_smiles=Chem.MolToSmiles(mol),
                )
            ]
    return []


def _uppercase_aromatic_atoms(smiles: str) -> str:
    chars = list(smiles)
    for index, char in enumerate(_outside_brackets(smiles)):
        if char in _AROMATIC_LETTERS:
            chars[index] = char.upper()
    return "".join(chars)


def _outside_brackets(smiles: str) -> list[str]:
    """Copy of the SMILES with every in-bracket character replaced by space."""
    result = list(smiles)
    depth = 0
    for index, char in enumerate(smiles):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        elif depth > 0:
            result[index] = " "
    return result


@contextmanager
def _rdkit_error_capture() -> Iterator[list[str]]:
    """Capture RDKit log messages emitted while the context is active."""
    rdBase.LogToPythonLogger()
    logger = logging.getLogger("rdkit")
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(_RDKIT_LOG_PREFIX.sub("", record.getMessage()))

    handler = _Capture()
    previous_level = logger.level
    previous_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
