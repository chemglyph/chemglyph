"""ChemGlyph: publication-quality chemical structure & reaction rendering for AI agents."""

from .metadata import read_structure
from .molecule import RenderResult, render_molecule
from .naming import parse_name
from .reaction import render_reaction
from .validate import ValidationReport, validate_structure

__version__ = "0.2.0"

__all__ = [
    "parse_name",
    "read_structure",
    "render_molecule",
    "render_reaction",
    "validate_structure",
    "RenderResult",
    "ValidationReport",
    "__version__",
]
