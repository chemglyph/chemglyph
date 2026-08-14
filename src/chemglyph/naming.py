"""Name-to-structure conversion (see §8 and v0.2 of the specification).

English IUPAC/common names resolve offline through OPSIN (optional
``py2opsin``). Chinese names resolve through a small built-in dictionary, or
through an optional caller-provided ``translator`` that converts the name to
English first. No online lookups (no PubChem), by design.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable

from rdkit import Chem

from .errors import ChemGlyphDependencyError, ChemGlyphParseError
from .zh_dict import ZH_NAMES

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def parse_name(name: str, translator: Callable[[str], str] | None = None) -> str:
    """Parse an IUPAC/common name into canonical SMILES.

    Args:
        name: an English or Chinese chemical name.
        translator: optional callable converting a Chinese name to English;
            used only when the name is not in the built-in Chinese
            dictionary. ChemGlyph itself never performs online translation.

    The built-in dictionary is consulted first, including Latin-script
    aliases such as "TNT", "DMSO", and "DMF", so those resolve without OPSIN.

    Raises:
        NotImplementedError: the Chinese name is unknown and no translator
            was provided.
        ChemGlyphDependencyError: OPSIN/py2opsin or Java is unavailable.
        ChemGlyphParseError: the name could not be resolved.
    """
    text = name.strip()
    if not text:
        raise ChemGlyphParseError("Name is empty.")
    if text in ZH_NAMES:
        return _canonicalize_dict_entry(text)
    if _CJK_RE.search(text):
        return _resolve_chinese(text, translator)
    return _resolve_english(text)


def _canonicalize_dict_entry(text: str) -> str:
    mol = Chem.MolFromSmiles(ZH_NAMES[text])
    if mol is None:
        raise ChemGlyphParseError(f"Built-in dictionary entry for {text!r} is invalid")
    return Chem.MolToSmiles(mol)


def _resolve_chinese(text: str, translator: Callable[[str], str] | None) -> str:
    if translator is None:
        raise NotImplementedError(
            f"Chinese name {text!r} is not in ChemGlyph's built-in dictionary "
            f"({len(ZH_NAMES)} entries). Provide the English name, or pass a "
            "`translator` callable that converts it to English; ChemGlyph "
            "performs no online lookups by design."
        )
    translated = translator(text)
    if not isinstance(translated, str) or not translated.strip():
        raise ChemGlyphParseError(f"The translator returned no usable English name for {text!r}.")
    if _CJK_RE.search(translated):
        raise ChemGlyphParseError(
            f"The translator returned another Chinese name for {text!r}; "
            "provide an English translation."
        )
    return _resolve_english(translated.strip())


def _resolve_english(text: str) -> str:
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
