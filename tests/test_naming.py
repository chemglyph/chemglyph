"""Name-to-structure conversion tests (see §8 of the specification)."""

from __future__ import annotations

import shutil

import pytest
from rdkit import Chem

import chemglyph
from chemglyph.errors import ChemGlyphDependencyError, ChemGlyphParseError
from chemglyph.zh_dict import ZH_NAMES


def _opsin_available() -> bool:
    try:
        import py2opsin  # noqa: F401
    except ImportError:
        return False
    return shutil.which("java") is not None


def test_chinese_name_in_builtin_dictionary() -> None:
    assert chemglyph.parse_name("阿司匹林") == "CC(=O)Oc1ccccc1C(=O)O"


def test_chinese_name_not_in_dictionary_raises_notimplemented() -> None:
    with pytest.raises(NotImplementedError, match="built-in dictionary"):
        chemglyph.parse_name("六甲基苯")


@pytest.mark.skipif(
    not _opsin_available(),
    reason="OPSIN + Java are required to resolve the translator's English output",
)
def test_translator_hook_resolves_chinese_name() -> None:
    smiles = chemglyph.parse_name("六甲基苯", translator=lambda _: "aspirin")
    assert smiles == "CC(=O)Oc1ccccc1C(=O)O"


def test_translator_returning_chinese_is_rejected() -> None:
    with pytest.raises(ChemGlyphParseError, match="another Chinese"):
        chemglyph.parse_name("六甲基苯", translator=lambda _: "阿司匹林")


def test_dictionary_entries_are_valid() -> None:
    for zh, stored in ZH_NAMES.items():
        mol = Chem.MolFromSmiles(stored)
        assert mol is not None, zh
        assert chemglyph.parse_name(zh) == Chem.MolToSmiles(mol)


def test_empty_name_rejected() -> None:
    with pytest.raises(ChemGlyphParseError):
        chemglyph.parse_name("   ")


def test_dependency_error_when_opsin_unavailable() -> None:
    if _opsin_available():
        pytest.skip("OPSIN and Java are available; skipping the failure-path test")
    with pytest.raises(ChemGlyphDependencyError):
        chemglyph.parse_name("aspirin")


@pytest.mark.skipif(
    shutil.which("java") is None,
    reason="Java runtime required by OPSIN is not installed",
)
def test_english_name_resolution_when_available() -> None:
    pytest.importorskip("py2opsin")
    smiles = chemglyph.parse_name("aspirin")
    assert smiles == "CC(=O)Oc1ccccc1C(=O)O"
