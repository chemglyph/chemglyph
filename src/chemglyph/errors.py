"""ChemGlyph exception hierarchy.

Every error raised by the public API is a :class:`ChemGlyphError` subclass,
so callers (including LLM agents) can catch one base type.
"""


class ChemGlyphError(Exception):
    """Base class for all ChemGlyph errors."""


class ChemGlyphParseError(ChemGlyphError):
    """Raised when a structure string (SMILES/InChI/molblock) cannot be parsed."""


class ChemGlyphStyleError(ChemGlyphError):
    """Raised for unknown style names or invalid style configuration."""


class ChemGlyphRenderError(ChemGlyphError):
    """Raised when rendering fails for a parsed structure (e.g. missing backend)."""


class ChemGlyphReactionError(ChemGlyphError):
    """Raised for malformed reaction specs or invalid layout parameters."""


class ChemGlyphDependencyError(ChemGlyphError):
    """Raised when an optional dependency (e.g. Java for OPSIN) is unavailable."""
