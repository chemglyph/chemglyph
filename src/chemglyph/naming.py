"""Name-to-structure conversion via OPSIN (see §8 of the specification).

MVP scope: English IUPAC/common names only, resolved offline by OPSIN through
the optional ``py2opsin`` dependency. Chinese names are reserved for v0.2.
No online lookups (no PubChem), by design.
"""

from __future__ import annotations

import re
import shutil

from rdkit import Chem

from .errors import ChemGlyphDependencyError, ChemGlyphParseError

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def parse_name(name: str) -> str:
    """Parse an English IUPAC/common name into canonical SMILES.

    Raises:
        NotImplementedError: Chinese names (planned for v0.2).
        ChemGlyphDependencyError: OPSIN/py2opsin or Java is unavailable.
        ChemGlyphParseError: the name could not be resolved.
    """
    text = name.strip()
    if not text:
        raise ChemGlyphParseError("Name is empty.")
    if _CJK_RE.search(text):
        raise NotImplementedError(
            "Chinese name parsing is planned for v0.2; English IUPAC/common "
            "names are supported in v0.1."
        )
    if shutil.which("java") is None:
        raise ChemGlyphDependencyError(
            "Name parsing requires a Java runtime for OPSIN. Install Java "
            "(e.g. `brew install openjdk` or your system package manager) and "
            "ensure `java` is on PATH."
        )
    try:
        from py2opsin import py2opsin
    except ImportError as exc:
        raise ChemGlyphDependencyError(
            "Name parsing needs the optional OPSIN binding. Install with "
            "`pip install 'chemglyph[opsin]'` (a Java runtime is also required)."
        ) from exc
    try:
        result = py2opsin.parse_name(text)
    except Exception as exc:
        raise ChemGlyphDependencyError(f"OPSIN failed to run for {text!r}: {exc}") from exc
    smiles = (result or {}).get("smiles")
    if not smiles:
        raise ChemGlyphParseError(f"Could not resolve name to a structure: {text!r}")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ChemGlyphParseError(f"OPSIN returned an unparseable SMILES for {text!r}: {smiles!r}")
    return Chem.MolToSmiles(mol)
