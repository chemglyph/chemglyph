"""Name-to-structure conversion tests (see §8 of the specification)."""

from __future__ import annotations

import shutil

import pytest

import chemglyph
from chemglyph.errors import ChemGlyphDependencyError, ChemGlyphParseError


def test_chinese_name_is_reserved_for_v02() -> None:
    with pytest.raises(NotImplementedError, match="planned for v0.2"):
        chemglyph.parse_name("阿司匹林")


def test_empty_name_rejected() -> None:
    with pytest.raises(ChemGlyphParseError):
        chemglyph.parse_name("   ")


def test_dependency_error_when_opsin_unavailable() -> None:
    try:
        import py2opsin  # noqa: F401

        has_opsin = True
    except ImportError:
        has_opsin = False
    has_java = shutil.which("java") is not None
    if has_opsin and has_java:
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
