"""Style presets for ChemGlyph rendering (see §4 of the specification).

Each style is a :class:`StyleSpec` whose ``draw_options`` map onto
``rdMolDraw2D.MolDrawOptions`` attributes. Two special keys are interpreted by
the renderer rather than assigned directly:

- ``acs1996_mode`` (bool): call ``rdMolDraw2D.SetACS1996Mode`` first.
- ``use_bw_atom_palette`` (bool): switch to the black/white atom palette.
- ``atom_colours`` (dict[int, str]): override atom palette entries by atomic
  number, values as ``#RRGGBB`` hex strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ChemGlyphStyleError

STYLES = {"acs", "modern", "textbook-cn"}


@dataclass(frozen=True)
class StyleSpec:
    """A rendering style: RDKit draw options plus post-processing parameters."""

    name: str
    draw_options: dict = field(default_factory=dict)
    background: str | None = None
    post: dict = field(default_factory=dict)


def get_style(name: str) -> StyleSpec:
    """Return the :class:`StyleSpec` for a named style."""
    if name not in _STYLE_TABLE:
        choices = ", ".join(sorted(STYLES))
        raise ChemGlyphStyleError(f"Unknown style {name!r}; choose one of: {choices}")
    return _STYLE_TABLE[name]


# acs: based on RDKit's built-in ACS1996 mode, then tuned for bond width,
# font size, label padding, and double-bond spacing per §4.1.
_ACS_OPTIONS = {
    "acs1996_mode": True,
    "use_bw_atom_palette": True,
    "bondLineWidth": 2.0,
    "multipleBondOffset": 0.18,
    "additionalAtomLabelPadding": 0.16,
    "minFontSize": 12,
    "maxFontSize": 28,
    "padding": 0.02,
}

# modern: default CPK palette with tuned heteroatom colors (O red, N blue,
# S dark yellow, Cl green); slightly heavier bonds for screen/chat display.
_MODERN_OPTIONS = {
    "atom_colours": {
        8: "#D62728",
        7: "#1F77B4",
        16: "#C78F00",
        17: "#2CA02C",
    },
    "bondLineWidth": 2.4,
    "multipleBondOffset": 0.18,
    "additionalAtomLabelPadding": 0.18,
    "minFontSize": 14,
    "maxFontSize": 32,
    "padding": 0.03,
}

# textbook-cn: pure black/white, ~1.3x the ACS bond width, larger labels,
# stereo wedges allowed but no other decorations.
_TEXTBOOK_CN_OPTIONS = {
    "use_bw_atom_palette": True,
    "bondLineWidth": 2.6,
    "multipleBondOffset": 0.20,
    "additionalAtomLabelPadding": 0.20,
    "minFontSize": 18,
    "maxFontSize": 40,
    "padding": 0.04,
    "addStereoAnnotation": False,
}

_STYLE_TABLE = {
    "acs": StyleSpec(
        name="acs",
        draw_options=dict(_ACS_OPTIONS),
        background="#ffffff",
        post={"stroke_scale": 1.0},
    ),
    "modern": StyleSpec(
        name="modern",
        draw_options=dict(_MODERN_OPTIONS),
        background="#ffffff",
        post={"stroke_scale": 1.0},
    ),
    "textbook-cn": StyleSpec(
        name="textbook-cn",
        draw_options=dict(_TEXTBOOK_CN_OPTIONS),
        background="#ffffff",
        post={"stroke_scale": 1.0},
    ),
}
